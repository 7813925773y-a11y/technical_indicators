"""
harmonic.py — Harmonic Auto-Validator Python translation (HAV Pine Script v1.1)
Confirmed patterns only, Standard tolerance (±0.060), linear mode (no log).
"""
import math
import statistics as _stats
import datetime


# ── Tolerance tables (Standard preset ±0.060) ─────────────────────────────────

_TOL = {
    "Gartley":   {"B_ideal": 0.618, "D_ideal": 0.786,
                  "B":  (0.558, 0.678), "BC": (0.382, 0.886),
                  "CD": (1.130, 1.618), "D":  (0.726, 0.846)},
    "Bat":       {"B_ideal": 0.500, "D_ideal": 0.886,
                  "B":  (0.440, 0.560), "BC": (0.382, 0.886),
                  "CD": (1.618, 2.618), "D":  (0.826, 0.946)},
    "Alt Bat":   {"B_ideal": 0.382, "D_ideal": 1.130,
                  "B":  (0.322, 0.442), "BC": (0.382, 0.886),
                  "CD": (2.000, 3.618), "D":  (1.070, 1.190)},
    "Butterfly": {"B_ideal": 0.786, "D_ideal": 1.272,
                  "B":  (0.726, 0.846), "BC": (0.382, 0.886),
                  "CD": (1.618, 2.618), "D":  (1.212, 1.332)},
    "Crab":      {"B_ideal": 0.500, "D_ideal": 1.618,
                  "B":  (0.440, 0.560), "BC": (0.382, 0.886),
                  "CD": (2.618, 3.618), "D":  (1.558, 1.678)},
    "Deep Crab": {"B_ideal": 0.886, "D_ideal": 1.618,
                  "B":  (0.826, 0.946), "BC": (0.382, 0.886),
                  "CD": (2.618, 3.618), "D":  (1.558, 1.678)},
}

# Retrace family: D sits between X and A (r_XD < 1)
_RETRACE_FAMILY = {"Gartley", "Bat"}
# Extension family: D extends past X (r_XD > 1)
_EXTENSION_FAMILY = {"Alt Bat", "Butterfly", "Crab", "Deep Crab"}


# ── Low-level helpers ──────────────────────────────────────────────────────────

def _atr_wilder(bars, period=14):
    n = len(bars)
    tr  = [0.0] * n
    atr = [0.0] * n
    for i in range(n):
        h, l = bars[i]["high"], bars[i]["low"]
        pc = bars[i-1]["close"] if i > 0 else bars[i]["close"]
        tr[i] = max(h - l, abs(h - pc), abs(l - pc))
    if n >= period:
        atr[period-1] = sum(tr[:period]) / period
        for i in range(period, n):
            atr[i] = (atr[i-1] * (period-1) + tr[i]) / period
    return atr


def _retrace(anchor_far, anchor_near, point):
    """|anchor_far - point| / |anchor_far - anchor_near| (linear)."""
    denom = abs(anchor_far - anchor_near)
    if denom < 1e-10:
        return 0.0
    return abs(anchor_far - point) / denom


def _infer_length(bars):
    """Guess zigzag length from bar spacing, matching Pine's auto table."""
    if len(bars) < 2:
        return 13
    dt = bars[-1]["time"] - bars[-2]["time"]  # seconds
    mins = dt / 60
    if mins <= 30:   return 5
    if mins <= 240:  return 8
    if mins <= 1440: return 13
    return 21


# ── Pivot detection ─────────────────────────────────────────────────────────────

def _push_pivot(buf, p):
    """Strict alternating zigzag — same dir: keep more extreme; else append."""
    if not buf:
        buf.append(p)
        return
    last = buf[-1]
    if last["is_high"] == p["is_high"]:
        more_extreme = p["price"] > last["price"] if p["is_high"] else p["price"] < last["price"]
        if more_extreme:
            buf[-1] = p
    else:
        buf.append(p)
    while len(buf) > 12:
        buf.pop(0)


def _detect_pivots(highs, lows, times, length):
    """
    Sequential pivot detection matching Pine's ta.pivothigh/pivotlow + f_push_pivot.
    At each bar t, the candidate pivot is at pi = t - length.
    Requires `length` bars to the left AND right of pi — right window ends at t.
    """
    n = len(highs)
    buf = []

    for t in range(n):
        pi = t - length
        if pi < length:
            continue
        right_end = t + 1  # exclusive; right window = [pi+1 .. t]

        # Pivot high
        left_h  = highs[pi - length : pi]
        right_h = highs[pi + 1 : right_end]
        if left_h and right_h:
            if highs[pi] > max(left_h) and highs[pi] > max(right_h):
                _push_pivot(buf, {"idx": pi, "time": times[pi], "price": highs[pi], "is_high": True})

        # Pivot low
        left_l  = lows[pi - length : pi]
        right_l = lows[pi + 1 : right_end]
        if left_l and right_l:
            if lows[pi] < min(left_l) and lows[pi] < min(right_l):
                _push_pivot(buf, {"idx": pi, "time": times[pi], "price": lows[pi], "is_high": False})

    return buf


# ── Structural validation ─────────────────────────────────────────────────────

def _validate(pX, pA, pB, pC, pD, pat_name, atr_v, min_xa_atr=2.0):
    """
    Returns (valid, bullish, r_AB, r_BC, r_CD, r_XD) or None on failure.
    Structural rules:
      Retrace family (Gartley, Bat): D between X and C
      Extension family (others):     D beyond X
    """
    t = _TOL[pat_name]

    # Direction alternation
    dirs = [pX["is_high"], pA["is_high"], pB["is_high"], pC["is_high"], pD["is_high"]]
    if any(dirs[i] == dirs[i+1] for i in range(4)):
        return None

    bullish = not pX["is_high"]  # X is a low → bullish

    # Structural ordering
    xp, ap, bp, cp, dp = [p["price"] for p in (pX, pA, pB, pC, pD)]

    if pat_name in _RETRACE_FAMILY:
        if bullish:
            ok = (xp < ap and
                  xp < bp < ap and
                  bp < cp < ap and
                  xp < dp < cp)
        else:
            ok = (xp > ap and
                  ap < bp < xp and
                  ap < cp < bp and
                  cp < dp < xp)
    else:  # extension — D beyond X
        if bullish:
            ok = (xp < ap and
                  xp < bp < ap and
                  bp < cp < ap and
                  dp < xp)
        else:
            ok = (xp > ap and
                  ap < bp < xp and
                  ap < cp < bp and
                  dp > xp)

    if not ok:
        return None

    # XA size filter
    if abs(ap - xp) < min_xa_atr * atr_v:
        return None

    # Compute ratios
    r_AB = _retrace(ap, xp, bp)
    r_BC = _retrace(bp, ap, cp)
    r_CD = _retrace(cp, bp, dp)
    r_XD = _retrace(ap, xp, dp)

    # Check ratio bands
    if not (t["B"][0]  <= r_AB <= t["B"][1]):   return None
    if not (t["BC"][0] <= r_BC <= t["BC"][1]):  return None
    if not (t["CD"][0] <= r_CD <= t["CD"][1]):  return None
    if not (t["D"][0]  <= r_XD <= t["D"][1]):   return None

    return (bullish, r_AB, r_BC, r_CD, r_XD)


# ── PRZ construction ──────────────────────────────────────────────────────────

def _proj(C, B, ratio):
    """C - ratio*(C-B) — projects D from C opposite to C-B direction."""
    return C - ratio * (C - B)

def _proj_xa(A, X, ratio):
    """A - ratio*(A-X) — projects D as extension/retrace of XA from A."""
    return A - ratio * (A - X)

def _abcd(A, B, C, mult=1.0):
    """AB=CD (or 1.27 AB=CD) projected from C. ab_vec = B-A."""
    ab_vec = B - A
    return C + mult * ab_vec


_PRZ_PROJS = {
    "Gartley":   lambda A, X, B, C: [
        ("0.786 XA",  _proj_xa(A, X, 0.786)),
        ("1.27 BC",   _proj(C, B, 1.27)),
        ("1.618 BC",  _proj(C, B, 1.618)),
        ("AB=CD",     _abcd(A, B, C, 1.0)),
    ],
    "Bat":       lambda A, X, B, C: [
        ("0.886 XA",      _proj_xa(A, X, 0.886)),
        ("1.618 BC",      _proj(C, B, 1.618)),
        ("2.618 BC",      _proj(C, B, 2.618)),
        ("AB=CD",         _abcd(A, B, C, 1.0)),
        ("1.27 AB=CD",    _abcd(A, B, C, 1.27)),
    ],
    "Alt Bat":   lambda A, X, B, C: [
        ("1.13 XA",       _proj_xa(A, X, 1.130)),
        ("2.0 BC",        _proj(C, B, 2.0)),
        ("3.618 BC",      _proj(C, B, 3.618)),
        ("1.27 AB=CD",    _abcd(A, B, C, 1.27)),
    ],
    "Butterfly": lambda A, X, B, C: [
        ("1.272 XA",      _proj_xa(A, X, 1.272)),
        ("1.618 BC",      _proj(C, B, 1.618)),
        ("2.618 BC",      _proj(C, B, 2.618)),
        ("1.27 AB=CD",    _abcd(A, B, C, 1.27)),
    ],
    "Crab":      lambda A, X, B, C: [
        ("1.618 XA",      _proj_xa(A, X, 1.618)),
        ("2.618 BC",      _proj(C, B, 2.618)),
        ("3.618 BC",      _proj(C, B, 3.618)),
        ("1.27 AB=CD",    _abcd(A, B, C, 1.27)),
    ],
    "Deep Crab": lambda A, X, B, C: [
        ("1.618 XA",      _proj_xa(A, X, 1.618)),
        ("2.618 BC",      _proj(C, B, 2.618)),
        ("3.618 BC",      _proj(C, B, 3.618)),
        ("1.27 AB=CD",    _abcd(A, B, C, 1.27)),
    ],
}

_ABCD_LABEL = {
    "Gartley":   "AB=CD",
    "Bat":       None,       # either AB=CD or 1.27 AB=CD
    "Alt Bat":   "1.27 AB=CD",
    "Butterfly": "1.27 AB=CD",
    "Crab":      "1.27 AB=CD",
    "Deep Crab": "1.27 AB=CD",
}


def _build_prz(pA, pX, pB, pC, pat_name, atr_v):
    """Build PRZ zone + projections with outlier filtering (3×ATR from median)."""
    A, X, B, C = pA["price"], pX["price"], pB["price"], pC["price"]
    raw_projs = _PRZ_PROJS[pat_name](A, X, B, C)
    prices    = [p for _, p in raw_projs]
    med       = _stats.median(prices)

    in_zone, out_zone = [], []
    for lbl, price in raw_projs:
        if abs(price - med) <= 3.0 * atr_v:
            in_zone.append({"label": lbl, "price": price, "in_prz": True})
        else:
            out_zone.append({"label": lbl, "price": price, "in_prz": False})

    projections = in_zone + out_zone

    if in_zone:
        prz_top = max(p["price"] for p in in_zone)
        prz_bot = min(p["price"] for p in in_zone)
        conf    = len(in_zone)
    else:
        prz_top = max(prices)
        prz_bot = min(prices)
        conf    = 0

    # AB=CD convergence
    abcd_lbl = _ABCD_LABEL.get(pat_name)
    if abcd_lbl is None:
        # Bat: either AB=CD or 1.27 AB=CD
        abcd_conv = any(p["in_prz"] and p["label"] in ("AB=CD", "1.27 AB=CD")
                        for p in projections)
    else:
        abcd_conv = any(p["in_prz"] and p["label"] == abcd_lbl
                        for p in projections)

    return {
        "top":             prz_top,
        "bot":             prz_bot,
        "confluence":      conf,
        "projections":     projections,
        "abcd_converges":  abcd_conv,
    }


# ── Scoring ────────────────────────────────────────────────────────────────────

def _score(pat_name, r_AB, r_XD, prz, abcd_conv, atr_v, penalize_no_abcd=True):
    t = _TOL[pat_name]
    ab_dev  = abs(r_AB - t["B_ideal"])
    xd_dev  = abs(r_XD - t["D_ideal"])
    ab_norm = 1.0 - min(ab_dev / 0.100, 1.0)
    xd_norm = 1.0 - min(xd_dev / 0.100, 1.0)
    ratio_score = (ab_norm + xd_norm) * 2.0        # 0–4

    zone_h      = prz["top"] - prz["bot"]
    tightness   = 1.0 - min(zone_h / (atr_v * 3.0), 1.0)
    tight_score = tightness * 3.0                  # 0–3

    conf_score  = min(prz["confluence"], 3)         # 0–3

    total = ratio_score + tight_score + conf_score
    if not abcd_conv and penalize_no_abcd:
        total = max(0.0, total - 2.0)
    return round(total * 10.0) / 10.0


# ── Main compute ───────────────────────────────────────────────────────────────

def compute(bars, min_score=6, min_conf=2, min_xa_atr=2.0, length=None):
    """
    Detect harmonic patterns from OHLCV bars.
    Returns list of confirmed pattern dicts (newest first).
    """
    n      = len(bars)
    highs  = [b["high"]  for b in bars]
    lows   = [b["low"]   for b in bars]
    closes = [b["close"] for b in bars]
    times  = [b["time"]  for b in bars]

    atr14 = _atr_wilder(bars, 14)
    L     = length if length else _infer_length(bars)

    pivots = _detect_pivots(highs, lows, times, L)

    patterns = []
    seen = set()  # (idx_X, idx_D) dedup key

    for i in range(len(pivots) - 5):
        pX, pA, pB, pC, pD = pivots[i:i+5]
        key = (pX["idx"], pD["idx"])
        if key in seen:
            continue

        # ATR at D confirmation bar (use pivots[i+5].idx as the confirmation bar)
        conf_idx = min(pivots[i+5]["idx"], n - 1)
        atr_v    = atr14[conf_idx] or atr14[-1]

        winner = None
        winner_score = -1.0

        for pat_name in _TOL:
            result = _validate(pX, pA, pB, pC, pD, pat_name, atr_v, min_xa_atr)
            if result is None:
                continue
            bullish, r_AB, r_BC, r_CD, r_XD = result
            prz = _build_prz(pA, pX, pB, pC, pat_name, atr_v)
            if prz["confluence"] < min_conf:
                continue
            sc = _score(pat_name, r_AB, r_XD, prz, prz["abcd_converges"], atr_v)
            if sc < min_score:
                continue
            if sc > winner_score:
                winner_score = sc
                winner = {
                    "pattern_type":  pat_name,
                    "is_bullish":    bullish,
                    "score":         sc,
                    "abcd_converges": prz["abcd_converges"],
                    "r_AB": r_AB, "r_BC": r_BC, "r_CD": r_CD, "r_XD": r_XD,
                    "prz":           prz,
                    "pX": pX, "pA": pA, "pB": pB, "pC": pC, "pD": pD,
                    "atr_v":         atr_v,
                    "conf_idx":      conf_idx,
                }

        if winner:
            seen.add(key)
            patterns.append(winner)

    patterns.sort(key=lambda p: p["pD"]["idx"])
    return patterns


# ── Chart data ─────────────────────────────────────────────────────────────────

_BULL_COLOR = "#26a69a"
_BEAR_COLOR = "#ef5350"
_WARN_COLOR = "#ffb300"

_PAT_COLORS = {
    "Gartley":   ("#00c896", "#ff4466"),   # teal bull / red bear
    "Bat":       ("#00b4d8", "#ff6b35"),
    "Alt Bat":   ("#48cae4", "#e63946"),
    "Butterfly": ("#f4a261", "#e76f51"),
    "Crab":      ("#a8dadc", "#e9c46a"),
    "Deep Crab": ("#b5e48c", "#d62828"),
}


def chart_data(bars, patterns, display_count=80):
    """
    Returns chart_data dict with:
      bars        — plain neutral candles
      markers     — XABCD pivot markers for recent patterns
      price_lines — PRZ top/bot for the most recent pattern
      prz_zones   — all recent patterns' PRZ info
      summary     — latest pattern summary
    """
    n     = len(bars)
    start = max(0, n - display_count)
    rb    = bars[start:]
    start_time = rb[0]["time"] if rb else 0

    # Plain neutral candles
    chart_bars = []
    for b in rb:
        up   = b["close"] >= b["open"]
        col  = "#26a69a" if up else "#ef5350"
        chart_bars.append({
            "time": b["time"], "open": b["open"],
            "high": b["high"], "low": b["low"], "close": b["close"],
            "color": col, "wickColor": col, "borderColor": col,
        })

    # Markers + price lines for patterns visible in the display window
    markers    = []
    price_lines = []
    prz_zones  = []

    visible_pats = [p for p in patterns if p["pD"]["time"] >= start_time]
    recent_pats  = visible_pats[-3:] if len(visible_pats) > 3 else visible_pats

    for pat in recent_pats:
        bull = pat["is_bullish"]
        bull_col, bear_col = _PAT_COLORS.get(pat["pattern_type"], (_BULL_COLOR, _BEAR_COLOR))
        col  = bull_col if bull else bear_col
        col_warn = _WARN_COLOR if not pat["abcd_converges"] else col

        pivot_labels = [
            ("X", pat["pX"]), ("A", pat["pA"]), ("B", pat["pB"]),
            ("C", pat["pC"]), ("D", pat["pD"]),
        ]
        for lbl, pv in pivot_labels:
            if pv["time"] < start_time:
                continue
            # X and D get special marker shapes
            if lbl == "D":
                shape  = "arrowUp" if bull else "arrowDown"
                pos    = "belowBar" if bull else "aboveBar"
                size   = 2.5
                m_col  = col_warn
            else:
                shape  = "circle"
                pos    = "belowBar" if pv["is_high"] == False else "aboveBar"
                size   = 1.0
                m_col  = col
            markers.append({
                "time":     pv["time"],
                "position": pos,
                "color":    m_col,
                "shape":    shape,
                "text":     lbl,
                "size":     size,
            })

        prz_zones.append({
            "top":        pat["prz"]["top"],
            "bot":        pat["prz"]["bot"],
            "mid":        (pat["prz"]["top"] + pat["prz"]["bot"]) / 2,
            "pattern":    pat["pattern_type"],
            "bullish":    bull,
            "score":      pat["score"],
            "abcd_conv":  pat["abcd_converges"],
            "d_time":     pat["pD"]["time"],
            "projections": pat["prz"]["projections"],
        })

    # Price lines for MOST RECENT pattern's PRZ
    if recent_pats:
        last = recent_pats[-1]
        bull = last["is_bullish"]
        bc, _ = _PAT_COLORS.get(last["pattern_type"], (_BULL_COLOR, _BEAR_COLOR))
        pc = bc if bull else _BEAR_COLOR
        price_lines = [
            {"price": last["prz"]["top"], "color": pc, "width": 2, "style": 0,
             "label": f"PRZ Top ${last['prz']['top']:.2f}"},
            {"price": last["prz"]["bot"], "color": pc, "width": 2, "style": 0,
             "label": f"PRZ Bot ${last['prz']['bot']:.2f}"},
            {"price": (last["prz"]["top"] + last["prz"]["bot"]) / 2,
             "color": pc, "width": 1, "style": 1, "label": "PRZ Mid"},
        ]

    # Summary
    if patterns:
        last = patterns[-1]
        bull = last["is_bullish"]
        cur  = bars[-1]["close"]
        in_prz = last["prz"]["bot"] <= cur <= last["prz"]["top"]
        summary = {
            "pattern_count":   len(patterns),
            "latest_pattern":  last["pattern_type"],
            "latest_bullish":  bull,
            "latest_score":    last["score"],
            "latest_abcd":     last["abcd_converges"],
            "latest_prz_top":  last["prz"]["top"],
            "latest_prz_mid":  (last["prz"]["top"] + last["prz"]["bot"]) / 2,
            "latest_prz_bot":  last["prz"]["bot"],
            "latest_r_AB":     round(last["r_AB"], 3),
            "latest_r_BC":     round(last["r_BC"], 3),
            "latest_r_CD":     round(last["r_CD"], 3),
            "latest_r_XD":     round(last["r_XD"], 3),
            "price_in_prz":    in_prz,
            "current_price":   cur,
            "visible_patterns": len(recent_pats),
        }
    else:
        summary = {
            "pattern_count":    0,
            "latest_pattern":   None,
            "price_in_prz":     False,
        }

    markers.sort(key=lambda m: m["time"])
    return {
        "bars":        chart_bars,
        "markers":     markers,
        "price_lines": price_lines,
        "prz_zones":   prz_zones,
        "summary":     summary,
    }


# ── Entry point ────────────────────────────────────────────────────────────────

def build_brief_from_ohlcv(bars, min_score=6, min_conf=2, length=None):
    """Returns (brief_text, signal_dict_with_chart_data)."""
    patterns = compute(bars, min_score=min_score, min_conf=min_conf, length=length)
    cd       = chart_data(bars, patterns)
    sm       = cd["summary"]

    def ts(u): return datetime.datetime.fromtimestamp(u).strftime("%Y-%m-%d")

    cur_price = bars[-1]["close"]
    cur_date  = ts(bars[-1]["time"])

    # Signal bias
    if not patterns:
        bias    = "NEUTRAL"
        reasons = ["No confirmed harmonic patterns detected in the lookback window."]
    else:
        last = patterns[-1]
        bull = last["is_bullish"]
        in_prz = sm["price_in_prz"]
        if in_prz:
            bias = "BULLISH" if bull else "BEARISH"
            reasons = [
                f"Price is INSIDE the {last['pattern_type']} PRZ — reversal zone active.",
            ]
        elif bull:
            bias    = "BULLISH"
            reasons = [f"{last['pattern_type']} bullish pattern confirmed — approaching PRZ."]
        else:
            bias    = "BEARISH"
            reasons = [f"{last['pattern_type']} bearish pattern confirmed — approaching PRZ."]

        reasons.append(f"Score: {last['score']}/10 {'(AB=CD ✓)' if last['abcd_converges'] else '(AB=CD ⚠)'}")
        reasons.append(f"PRZ: ${last['prz']['bot']:.2f} – ${last['prz']['top']:.2f}")
        reasons.append(f"Ratios: AB={last['r_AB']:.3f}  BC={last['r_BC']:.3f}  "
                       f"CD={last['r_CD']:.3f}  XD={last['r_XD']:.3f}")
        reasons.append(f"Total confirmed patterns: {len(patterns)}")

    # Brief text
    lines = [
        f"HAV — Harmonic Auto-Validator (computed from OHLCV)",
        f"Current bar: {cur_date}  close=${cur_price:.2f}",
        "",
    ]
    if not patterns:
        lines.append("No confirmed harmonic patterns found.")
        lines.append("(HAV detects 1-4 patterns/year on daily TF — sparse by design.)")
    else:
        last    = patterns[-1]
        bull    = last["is_bullish"]
        in_prz  = sm["price_in_prz"]
        dir_str = "▲ BULLISH" if bull else "▼ BEARISH"
        lines += [
            f"Latest Pattern: {last['pattern_type']} [{dir_str}]",
            f"  Score:        {last['score']}/10",
            f"  AB=CD:        {'✓ Converges' if last['abcd_converges'] else '⚠ Non-convergent'}",
            f"  PRZ:          ${last['prz']['bot']:.2f} – ${last['prz']['top']:.2f}  "
            f"(mid ${(last['prz']['top']+last['prz']['bot'])/2:.2f})",
            f"  Price in PRZ: {'YES ←' if in_prz else 'No'}",
            "",
            "Ratios:",
            f"  r_AB = {last['r_AB']:.3f}  (ideal {_TOL[last['pattern_type']]['B_ideal']})",
            f"  r_BC = {last['r_BC']:.3f}",
            f"  r_CD = {last['r_CD']:.3f}",
            f"  r_XD = {last['r_XD']:.3f}  (ideal {_TOL[last['pattern_type']]['D_ideal']})",
            "",
            "Pivot Points:",
            f"  X: ${last['pX']['price']:.2f}  ({ts(last['pX']['time'])})",
            f"  A: ${last['pA']['price']:.2f}  ({ts(last['pA']['time'])})",
            f"  B: ${last['pB']['price']:.2f}  ({ts(last['pB']['time'])})",
            f"  C: ${last['pC']['price']:.2f}  ({ts(last['pC']['time'])})",
            f"  D: ${last['pD']['price']:.2f}  ({ts(last['pD']['time'])})",
            "",
            "PRZ Projections:",
        ]
        for p in last["prz"]["projections"]:
            mark = "✓" if p["in_prz"] else "✗"
            lines.append(f"  {mark}  {p['label']:15s}  ${p['price']:.2f}")

        if len(patterns) > 1:
            lines += ["", f"Recent Patterns ({len(patterns)} total, newest last):"]
            for pat in patterns[-5:]:
                d = "▲" if pat["is_bullish"] else "▼"
                in_p = "← IN PRZ" if pat["prz"]["bot"] <= cur_price <= pat["prz"]["top"] else ""
                lines.append(
                    f"  {ts(pat['pD']['time'])}  {d} {pat['pattern_type']:10s}  "
                    f"score={pat['score']}/10  PRZ ${pat['prz']['bot']:.2f}–${pat['prz']['top']:.2f}  {in_p}"
                )

    key_values = {
        "Patterns":   str(len(patterns)),
        "Latest":     sm.get("latest_pattern") or "None",
        "Direction":  ("▲ Bullish" if sm.get("latest_bullish") else "▼ Bearish") if sm.get("latest_pattern") else "—",
        "Score":      f"{sm.get('latest_score', 0)}/10" if sm.get("latest_pattern") else "—",
        "AB=CD":      ("✓" if sm.get("latest_abcd") else "⚠") if sm.get("latest_pattern") else "—",
        "PRZ Top":    f"${sm['latest_prz_top']:.2f}" if sm.get("latest_prz_top") else "—",
        "PRZ Bot":    f"${sm['latest_prz_bot']:.2f}" if sm.get("latest_prz_bot") else "—",
        "In PRZ":     "YES" if sm.get("price_in_prz") else "No",
    }

    sig = {
        "indicator":  "HAV",
        "signal":     bias,
        "reasons":    reasons,
        "key_values": key_values,
        "chart_data": cd,
    }
    return "\n".join(lines), sig
