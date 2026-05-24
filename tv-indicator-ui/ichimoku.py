"""
ichimoku.py — Ichimoku Theories [LuxAlgo] Python translation.

Core components:
  - 5 Ichimoku lines: Tenkan, Kijun, Senkou A/B, Chikou
  - LuxAlgo swing detector (right-side only pivot, alternating leg state machine)
  - Price Theory: V / E / N / NT / 2E / 3E targets from last developing N-wave (A→B→C)
  - Signal: kumo position + TK cross + price target direction
"""
import math
import datetime


# ── Defaults matching Pine Script inputs ──────────────────────────────────────

TENKAN_LEN  = 9
KIJUN_LEN   = 26
SPAN_B_LEN  = 52
OFFSET      = 26   # chikou/senkou shift
PIVOT_LEN   = 10   # default swing length


# ── Ichimoku line computations ────────────────────────────────────────────────

def _average(highs, lows, t, length):
    """(highest + lowest) / 2 over [t-length+1 .. t]."""
    lo = max(0, t - length + 1)
    h  = max(highs[lo : t + 1])
    l  = min(lows[lo  : t + 1])
    return (h + l) / 2


def _compute_lines(bars,
                   tenkan_len=TENKAN_LEN,
                   kijun_len=KIJUN_LEN,
                   span_b_len=SPAN_B_LEN,
                   offset=OFFSET):
    """
    Returns arrays: tenkan, kijun, span_a, span_b, chikou — all bar-by-bar.
    Senkou Span A/B are COMPUTED at bar t; TradingView DISPLAYS them at t+offset.
    For signal analysis, cloud visible at bar t = span_a[t-offset], span_b[t-offset].
    """
    n      = len(bars)
    highs  = [b["high"]  for b in bars]
    lows   = [b["low"]   for b in bars]
    closes = [b["close"] for b in bars]

    tenkan  = [None] * n
    kijun   = [None] * n
    span_a  = [None] * n
    span_b  = [None] * n
    chikou  = [None] * n

    for t in range(n):
        if t >= tenkan_len - 1:
            tenkan[t] = _average(highs, lows, t, tenkan_len)
        if t >= kijun_len - 1:
            kijun[t]  = _average(highs, lows, t, kijun_len)
        if tenkan[t] is not None and kijun[t] is not None:
            span_a[t] = (tenkan[t] + kijun[t]) / 2
        if t >= span_b_len - 1:
            span_b[t] = _average(highs, lows, t, span_b_len)
        # chikou[t] = close[t], plotted offset bars in the past → chart time = times[t-offset]
        chikou[t] = closes[t]

    return tenkan, kijun, span_a, span_b, chikou


# ── Swing / leg detection (LuxAlgo style, right-side only) ───────────────────

def _detect_swings(bars, pivot_len=PIVOT_LEN):
    """
    LuxAlgo leg() + startOfNewLeg() logic.
    Pivot high at pi = t - L: highs[pi] > max(highs[pi+1 .. t])
    Pivot low  at pi = t - L: lows[pi]  < min(lows[pi+1 .. t])
    Strict alternation: only record a pivot when the leg DIRECTION changes.
    Returns list of {"idx","time","price","is_high"}.
    """
    n      = len(bars)
    highs  = [b["high"] for b in bars]
    lows   = [b["low"]  for b in bars]
    times  = [b["time"] for b in bars]

    L   = pivot_len
    leg = 0   # 0=BEARISH, 1=BULLISH — current leg direction
    swings = []

    for t in range(n):
        pi = t - L
        if pi < 0:
            continue
        right_h = highs[pi + 1 : t + 1]
        right_l = lows[pi + 1  : t + 1]
        if not right_h:
            continue

        new_leg_high = highs[pi] > max(right_h)
        new_leg_low  = lows[pi]  < min(right_l)

        prev_leg = leg
        if new_leg_high:
            leg = 0   # BEARISH_LEG
        elif new_leg_low:
            leg = 1   # BULLISH_LEG

        if leg != prev_leg:
            if leg == 0:   # start of bearish → pivot high
                swings.append({"idx": pi, "time": times[pi],
                               "price": highs[pi], "is_high": True})
            else:           # start of bullish → pivot low
                swings.append({"idx": pi, "time": times[pi],
                               "price": lows[pi], "is_high": False})

    return swings


# ── Price Theory targets (N-wave A→B→C) ──────────────────────────────────────

def _price_targets(swings):
    """
    Compute V/E/N/NT/2E/3E from the last 3 swing points.
    Returns dict or None if no developing N-wave.
    """
    if len(swings) < 3:
        return None

    A, B, C   = swings[-3], swings[-2], swings[-1]
    ap, bp, cp = A["price"], B["price"], C["price"]
    threshold  = abs(ap - bp) * 0.2

    is_bull = (ap < bp
               and cp > ap + threshold
               and cp < bp - threshold)
    is_bear = (ap > bp
               and cp < ap - threshold
               and cp > bp + threshold)

    if is_bull:
        return {
            "direction": "bullish",
            "V":  bp + (bp - cp),
            "E":  bp + (bp - ap),
            "N":  cp + (bp - ap),
            "NT": cp + (cp - ap),
            "2E": bp + 2 * (bp - ap),
            "3E": bp + 3 * (bp - ap),
            "A": ap, "B": bp, "C": cp,
        }
    elif is_bear:
        return {
            "direction": "bearish",
            "V":  bp - (cp - bp),
            "E":  bp - (ap - bp),
            "N":  cp - (ap - bp),
            "NT": cp - (ap - cp),
            "2E": bp - 2 * (ap - bp),
            "3E": bp - 3 * (ap - bp),
            "A": ap, "B": bp, "C": cp,
        }
    return None


# ── Main compute ──────────────────────────────────────────────────────────────

def compute(bars,
            tenkan_len=TENKAN_LEN,
            kijun_len=KIJUN_LEN,
            span_b_len=SPAN_B_LEN,
            offset=OFFSET,
            pivot_len=PIVOT_LEN):
    """
    Full Ichimoku state for every bar.
    Returns dict with arrays + per-bar list.
    """
    n      = len(bars)
    closes = [b["close"] for b in bars]
    times  = [b["time"]  for b in bars]

    tenkan, kijun, span_a, span_b, chikou = _compute_lines(
        bars, tenkan_len, kijun_len, span_b_len, offset)

    swings = _detect_swings(bars, pivot_len)
    targets = _price_targets(swings)

    # Per-bar cloud status (uses cloud computed offset bars ago)
    per_bar = []
    for t in range(n):
        tk = tenkan[t]
        kj = kijun[t]
        sa = span_a[t]
        sb = span_b[t]

        # Cloud visible at bar t = span_a/span_b computed `offset` bars ago
        cloud_t = t - offset
        if cloud_t >= 0 and span_a[cloud_t] is not None and span_b[cloud_t] is not None:
            cloud_top = max(span_a[cloud_t], span_b[cloud_t])
            cloud_bot = min(span_a[cloud_t], span_b[cloud_t])
            cloud_bull = span_a[cloud_t] >= span_b[cloud_t]
        else:
            cloud_top = cloud_bot = cloud_bull = None

        price = closes[t]
        if cloud_top is not None:
            if price > cloud_top:
                kumo_pos = "above"
            elif price < cloud_bot:
                kumo_pos = "below"
            else:
                kumo_pos = "inside"
        else:
            kumo_pos = None

        # TK cross (close crosses tenkan)
        tk_cross = None
        if t > 0 and tk is not None and kj is not None:
            prev_tk = tenkan[t - 1]
            prev_kj = kijun[t - 1]
            if prev_tk is not None and prev_kj is not None:
                if prev_tk <= prev_kj and tk > kj:
                    tk_cross = "bull"
                elif prev_tk >= prev_kj and tk < kj:
                    tk_cross = "bear"

        per_bar.append({
            "time":       times[t],
            "close":      price,
            "tenkan":     tk,
            "kijun":      kj,
            "span_a":     sa,
            "span_b":     sb,
            "cloud_top":  cloud_top,
            "cloud_bot":  cloud_bot,
            "cloud_bull": cloud_bull,
            "kumo_pos":   kumo_pos,
            "tk_cross":   tk_cross,
        })

    return {
        "per_bar":  per_bar,
        "swings":   swings,
        "targets":  targets,
        "tenkan":   tenkan,
        "kijun":    kijun,
        "span_a":   span_a,
        "span_b":   span_b,
        "chikou":   chikou,
        "times":    times,
        "closes":   closes,
        "n":        n,
    }


# ── Chart data ────────────────────────────────────────────────────────────────

def chart_data(bars, result, display_count=100):
    """
    Returns dict for Lightweight Charts:
      bars       — candles colored by kumo position
      tenkan     — [{time, value}] line series
      kijun      — [{time, value}] line series
      span_a     — [{time, value}] (computed time, not shifted)
      span_b     — [{time, value}] (computed time, not shifted)
      chikou     — [{time, value}] shifted 26 bars back
      markers    — swing highs/lows + TK crosses
      price_lines — price targets + cloud top/bot + tenkan/kijun
      summary    — signal summary dict
    """
    n     = result["n"]
    start = max(0, n - display_count)

    per_bar = result["per_bar"]
    times   = result["times"]
    tenkan  = result["tenkan"]
    kijun   = result["kijun"]
    span_a  = result["span_a"]
    span_b  = result["span_b"]
    chikou  = result["closes"]   # chikou value at bar t → displayed at time[t-offset]

    # Candles colored by kumo position
    kumo_colors = {"above": "#00c896", "below": "#ef5350", "inside": "#7c4dff", None: "#8b949e"}
    chart_bars = []
    for i, b in enumerate(bars[start:], start=start):
        pos = per_bar[i]["kumo_pos"]
        col = kumo_colors.get(pos, "#8b949e")
        # Use neutral candle coloring but tint wick by kumo
        up_col  = "#26a69a" if b["close"] >= b["open"] else "#ef5350"
        chart_bars.append({
            "time":        b["time"],
            "open":        b["open"],
            "high":        b["high"],
            "low":         b["low"],
            "close":       b["close"],
            "color":       col,
            "wickColor":   col,
            "borderColor": col,
        })

    # Line series data (display window)
    def _line(arr, start_idx):
        return [{"time": times[i], "value": arr[i]}
                for i in range(start_idx, n)
                if arr[i] is not None]

    tenkan_data = _line(tenkan, start)
    kijun_data  = _line(kijun,  start)
    span_a_data = _line(span_a, start)
    span_b_data = _line(span_b, start)

    # Cloud fill segments: bullish (SpanA>=SpanB, green) / bearish (SpanB>SpanA, red)
    # Each array holds only the bars belonging to that segment; gaps create proper breaks.
    cloud_bull_top = []  # SpanA (higher boundary of bull cloud)
    cloud_bull_bot = []  # SpanB (lower boundary of bull cloud)
    cloud_bear_top = []  # SpanB (higher boundary of bear cloud)
    cloud_bear_bot = []  # SpanA (lower boundary of bear cloud)
    for i in range(start, n):
        sa, sb = span_a[i], span_b[i]
        if sa is None or sb is None:
            continue
        t = times[i]
        if sa >= sb:
            cloud_bull_top.append({"time": t, "value": sa})
            cloud_bull_bot.append({"time": t, "value": sb})
        else:
            cloud_bear_top.append({"time": t, "value": sb})
            cloud_bear_bot.append({"time": t, "value": sa})

    # Chikou: close at bar t displayed at time[t - offset]
    chikou_data = []
    for i in range(start, n):
        ci = i - OFFSET
        if ci >= 0:
            chikou_data.append({"time": times[ci], "value": chikou[i]})

    # Markers: swing highs/lows (green/red circles) + TK crosses
    start_time = bars[start]["time"] if bars else 0
    markers = []
    for sw in result["swings"]:
        if sw["time"] < start_time:
            continue
        if sw["is_high"]:
            markers.append({"time": sw["time"], "position": "aboveBar",
                            "color": "#ef5350", "shape": "circle",
                            "text": "H", "size": 1.0})
        else:
            markers.append({"time": sw["time"], "position": "belowBar",
                            "color": "#00c896", "shape": "circle",
                            "text": "L", "size": 1.0})

    for pb in per_bar[start:]:
        if pb["tk_cross"] == "bull":
            markers.append({"time": pb["time"], "position": "belowBar",
                            "color": "#00c896", "shape": "arrowUp",
                            "text": "TK↑", "size": 1.5})
        elif pb["tk_cross"] == "bear":
            markers.append({"time": pb["time"], "position": "aboveBar",
                            "color": "#ef5350", "shape": "arrowDown",
                            "text": "TK↓", "size": 1.5})

    markers.sort(key=lambda m: m["time"])

    # Price lines: current tenkan, kijun, cloud, targets
    cur     = per_bar[-1]
    tgt     = result["targets"]
    price_lines = []

    if cur["cloud_top"] is not None:
        price_lines += [
            {"price": cur["cloud_top"], "color": "#7c4dff", "width": 1, "style": 2,
             "label": f"Kumo Top ${cur['cloud_top']:.2f}"},
            {"price": cur["cloud_bot"], "color": "#7c4dff", "width": 1, "style": 2,
             "label": f"Kumo Bot ${cur['cloud_bot']:.2f}"},
        ]
    if cur["tenkan"] is not None:
        price_lines.append({"price": cur["tenkan"], "color": "#ef5350", "width": 1, "style": 0,
                            "label": f"Tenkan ${cur['tenkan']:.2f}"})
    if cur["kijun"] is not None:
        price_lines.append({"price": cur["kijun"], "color": "#2962ff", "width": 1, "style": 0,
                            "label": f"Kijun ${cur['kijun']:.2f}"})

    if tgt:
        tgt_col = "#00c896" if tgt["direction"] == "bullish" else "#ef5350"
        for label in ["V", "E", "N", "NT"]:
            if label in tgt:
                price_lines.append({"price": tgt[label], "color": tgt_col,
                                    "width": 1, "style": 1,
                                    "label": f"{label} ${tgt[label]:.2f}"})

    # Summary
    close_now = bars[-1]["close"]
    kumo_pos  = cur["kumo_pos"]
    cloud_bull = cur["cloud_bull"]

    # Recent TK crosses (last 20 bars)
    recent_tk = [(pb["time"], pb["tk_cross"])
                 for pb in per_bar[-20:] if pb["tk_cross"]]
    last_tk   = recent_tk[-1][1] if recent_tk else None

    if kumo_pos == "above":
        if last_tk == "bull":
            signal = "BULLISH"
        else:
            signal = "BULLISH"
    elif kumo_pos == "below":
        if last_tk == "bear":
            signal = "BEARISH"
        else:
            signal = "BEARISH"
    else:
        signal = "NEUTRAL"

    summary = {
        "signal":       signal,
        "kumo_pos":     kumo_pos,
        "cloud_bull":   cloud_bull,
        "last_tk_cross": last_tk,
        "tenkan":       cur["tenkan"],
        "kijun":        cur["kijun"],
        "cloud_top":    cur["cloud_top"],
        "cloud_bot":    cur["cloud_bot"],
        "close":        close_now,
        "swing_count":  len(result["swings"]),
        "has_targets":  tgt is not None,
        "target_dir":   tgt["direction"] if tgt else None,
        "targets":      {k: v for k, v in (tgt or {}).items()
                         if k in ("V", "E", "N", "NT", "2E", "3E")},
    }

    return {
        "bars":            chart_bars,
        "tenkan":          tenkan_data,
        "kijun":           kijun_data,
        "span_a":          span_a_data,
        "span_b":          span_b_data,
        "chikou":          chikou_data,
        "cloud_bull_top":  cloud_bull_top,
        "cloud_bull_bot":  cloud_bull_bot,
        "cloud_bear_top":  cloud_bear_top,
        "cloud_bear_bot":  cloud_bear_bot,
        "markers":         markers,
        "price_lines":     price_lines,
        "summary":         summary,
    }


# ── Entry point ───────────────────────────────────────────────────────────────

def build_brief_from_ohlcv(bars):
    """Returns (brief_text, signal_dict_with_chart_data)."""
    result = compute(bars)
    cd     = chart_data(bars, result)
    sm     = cd["summary"]
    cur    = result["per_bar"][-1]
    tgt    = result["targets"]

    def ts(u): return datetime.datetime.fromtimestamp(u).strftime("%Y-%m-%d")

    close_now = bars[-1]["close"]
    cur_date  = ts(bars[-1]["time"])

    # Bias
    bias = sm["signal"]

    reasons = []
    pos_map = {"above": "price ABOVE cloud → bullish",
               "below": "price BELOW cloud → bearish",
               "inside": "price INSIDE cloud → neutral/transition",
               None: "cloud N/A (insufficient history)"}
    reasons.append(f"Kumo: {pos_map.get(sm['kumo_pos'], sm['kumo_pos'])}")

    if sm["last_tk_cross"]:
        dir_s = "Bullish (Tenkan > Kijun)" if sm["last_tk_cross"] == "bull" else "Bearish (Tenkan < Kijun)"
        reasons.append(f"Recent TK cross: {dir_s}")
    else:
        reasons.append("No recent TK cross in last 20 bars")

    if tgt:
        bull = tgt["direction"] == "bullish"
        reasons.append(f"Price Theory: {'Bullish' if bull else 'Bearish'} N-wave developing")
        reasons.append(f"  Targets — V:{tgt['V']:.2f}  E:{tgt['E']:.2f}  N:{tgt['N']:.2f}  NT:{tgt['NT']:.2f}")
    else:
        reasons.append("Price Theory: No developing N-wave on last 3 swings")

    reasons.append(f"Swing points detected: {sm['swing_count']}")

    # Brief text
    def fv(v): return f"${v:.2f}" if v is not None else "—"

    lines = [
        "Ichimoku Theories [LuxAlgo] (computed from OHLCV)",
        f"Current bar: {cur_date}  close={fv(close_now)}",
        "",
        "Ichimoku Lines:",
        f"  Tenkan Sen (9):  {fv(cur['tenkan'])}",
        f"  Kijun Sen (26):  {fv(cur['kijun'])}",
        f"  Senkou Span A:   {fv(cur['span_a'])}",
        f"  Senkou Span B:   {fv(cur['span_b'])}",
        "",
        "Kumo (Cloud) Status:",
        f"  Cloud Top:       {fv(cur['cloud_top'])}",
        f"  Cloud Bottom:    {fv(cur['cloud_bot'])}",
        f"  Cloud Color:     {'Bullish (green — SpanA > SpanB)' if cur['cloud_bull'] else 'Bearish (red — SpanB > SpanA)' if cur['cloud_bull'] is not None else '—'}",
        f"  Price Position:  {sm['kumo_pos'] or '—'}",
        "",
        f"Swing Points Detected: {sm['swing_count']}",
    ]

    if result["swings"]:
        lines.append("Recent Swings (last 6):")
        for sw in result["swings"][-6:]:
            kind = "High" if sw["is_high"] else "Low"
            lines.append(f"  {ts(sw['time'])}  {kind}  {fv(sw['price'])}")

    if tgt:
        bull = tgt["direction"] == "bullish"
        lines += [
            "",
            f"Price Theory Targets ({tgt['direction'].upper()} N-wave A→B→C):",
            f"  A = {fv(tgt['A'])}  B = {fv(tgt['B'])}  C = {fv(tgt['C'])}",
            f"  V  = {fv(tgt['V'])}   (B + (B-C))",
            f"  E  = {fv(tgt['E'])}   (B + (B-A))",
            f"  N  = {fv(tgt['N'])}   (C + (B-A))",
            f"  NT = {fv(tgt['NT'])}  (C + (C-A))",
            f"  2E = {fv(tgt['2E'])}  (extended)",
            f"  3E = {fv(tgt['3E'])}  (extended)",
        ]
    else:
        lines += ["", "Price Theory: No developing N-wave found in last 3 swings."]

    key_values = {
        "Kumo":    sm["kumo_pos"] or "—",
        "TK":      ("▲ Bull" if sm["last_tk_cross"] == "bull" else "▼ Bear" if sm["last_tk_cross"] == "bear" else "None"),
        "Tenkan":  fv(cur["tenkan"]),
        "Kijun":   fv(cur["kijun"]),
        "SpanA":   fv(cur["span_a"]),
        "SpanB":   fv(cur["span_b"]),
        "N-wave":  sm["target_dir"].capitalize() if sm["target_dir"] else "None",
        "Swings":  str(sm["swing_count"]),
    }
    if tgt:
        key_values["N Target"] = fv(tgt["N"])
        key_values["E Target"] = fv(tgt["E"])

    sig = {
        "indicator":  "Ichimoku",
        "signal":     bias,
        "reasons":    reasons,
        "key_values": key_values,
        "chart_data": cd,
    }
    return "\n".join(lines), sig
