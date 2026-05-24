"""
FibStruct (Fibonacci Structure Engine [WillyAlgoTrader]) — pure Python.
Exact translation of Pine Script v1.5.2 algorithm from OHLCV bars.

Key outputs:
  swing_labels   — HH / HL / LH / LL events
  struct_events  — BOS / CHoCH events (price level + bar)
  sweep_events   — liquidity sweep events
  buy_signals    — confirmed BUY signal bars
  sell_signals   — confirmed SELL signal bars
  fib_levels     — current Fibonacci level state (for chart price lines)

Run standalone:  python fibstruct_compute.py
"""

import json, datetime
from pathlib import Path


# ── ATR(14) ──────────────────────────────────────────────────────────────────

def compute_atr(bars, period=14):
    n = len(bars)
    tr  = [0.0] * n
    atr = [0.0] * n
    for i in range(n):
        h, l = bars[i]["high"], bars[i]["low"]
        pc = bars[i - 1]["close"] if i > 0 else bars[i]["close"]
        tr[i] = max(h - l, abs(h - pc), abs(l - pc))
    atr[period - 1] = sum(tr[:period]) / period
    for i in range(period, n):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    return atr


# ── Body EMA(14) for engulfing ────────────────────────────────────────────────

def compute_body_ema(bars, period=14):
    n = len(bars)
    body = [abs(b["close"] - b["open"]) for b in bars]
    ema  = [0.0] * n
    if n >= period:
        ema[period - 1] = sum(body[:period]) / period
        for i in range(period, n):
            ema[i] = (ema[i - 1] * (period - 1) + body[i]) / period
    return body, ema


# ── Main computation ──────────────────────────────────────────────────────────

def compute_fibstruct(bars, swing_len=10, atr_mult=0.5, conf_tol=0.3,
                      cooldown=5, eq_tol=0.1):
    n      = len(bars)
    highs  = [b["high"]  for b in bars]
    lows   = [b["low"]   for b in bars]
    opens  = [b["open"]  for b in bars]
    closes = [b["close"] for b in bars]
    times  = [b["time"]  for b in bars]

    atrs           = compute_atr(bars)
    body, body_ema = compute_body_ema(bars)
    warmup         = max(swing_len * 3, 50)

    # ── Pine `var` state ──────────────────────────────────────────────────────
    sw_h1, sw_h1_idx   = None, None
    sw_h2, sw_h2_idx   = None, None
    sw_l1, sw_l1_idx   = None, None
    sw_l2, sw_l2_idx   = None, None

    structure_bias      = 0
    last_choch_dir      = 0
    last_broken_h_idx   = None
    last_broken_l_idx   = None

    eqh_active, eqh_price = False, None
    eql_active, eql_price = False, None
    last_swept_h_idx       = None
    last_swept_l_idx       = None

    fib_dir                 = 0
    fib_sh, fib_sl          = None, None
    fib_sh_idx, fib_sl_idx  = None, None
    fib_h_live, fib_l_live  = False, False

    bars_since_sig = 999

    # ── Output collections ────────────────────────────────────────────────────
    swing_labels  = []   # {time, price, text, position}
    struct_events = []   # {time, price, type, direction}
    sweep_events  = []   # {time, price, direction, level}
    buy_signals   = []   # {time, price}
    sell_signals  = []   # {time, price}

    # Track per-bar state for chart coloring
    bar_states = []      # {buy_signal, sell_signal, choch_bull, choch_bear, bos_bull, bos_bear}

    fib_levels_final = {}

    for t in range(n):
        atr       = atrs[t]
        is_warmed = t >= warmup
        bars_since_sig += 1

        # ── Pivot detection (Pine: detected `swing_len` bars late) ──────────
        new_sh = new_sl = False
        pi = t - swing_len
        if pi >= swing_len:
            lo_i, hi_i = pi - swing_len, pi + swing_len + 1
            win_h = highs[lo_i:hi_i]
            win_l = lows[lo_i:hi_i]
            ph_val = highs[pi] if win_h and highs[pi] == max(win_h) else None
            pl_val = lows[pi]  if win_l and lows[pi]  == min(win_l) else None
        else:
            ph_val = pl_val = None

        atr_min = atr * atr_mult if atr > 0 else 0.0

        if ph_val is not None:
            if sw_l1 is None or (ph_val - sw_l1) >= atr_min:
                sw_h2, sw_h2_idx = sw_h1, sw_h1_idx
                sw_h1, sw_h1_idx = ph_val, pi
                new_sh = True

        if pl_val is not None:
            if sw_h1 is None or (sw_h1 - pl_val) >= atr_min:
                sw_l2, sw_l2_idx = sw_l1, sw_l1_idx
                sw_l1, sw_l1_idx = pl_val, pi
                new_sl = True

        # ── Swing labels ──────────────────────────────────────────────────────
        if is_warmed and new_sh and sw_h2 is not None:
            lbl = "HH" if sw_h1 > sw_h2 else "LH"
            swing_labels.append({
                "time": times[sw_h1_idx], "price": sw_h1,
                "text": lbl, "position": "above",
                "color": "#26a69a" if lbl == "HH" else "#ef5350"
            })

        if is_warmed and new_sl and sw_l2 is not None:
            lbl = "HL" if sw_l1 > sw_l2 else "LL"
            swing_labels.append({
                "time": times[sw_l1_idx], "price": sw_l1,
                "text": lbl, "position": "below",
                "color": "#26a69a" if lbl == "HL" else "#ef5350"
            })

        # ── EQH / EQL ─────────────────────────────────────────────────────────
        eq_tol_val = atr * eq_tol if atr > 0 else 0.0
        if new_sh and sw_h2 is not None and abs(sw_h1 - sw_h2) <= eq_tol_val and is_warmed:
            eqh_active = True
            eqh_price  = (sw_h1 + sw_h2) / 2
        if new_sl and sw_l2 is not None and abs(sw_l1 - sw_l2) <= eq_tol_val and is_warmed:
            eql_active = True
            eql_price  = (sw_l1 + sw_l2) / 2

        # ── Liquidity sweeps ──────────────────────────────────────────────────
        sweep_high = sweep_low = False
        if is_warmed:
            ref_h     = eqh_price if eqh_active else sw_h1
            ref_l     = eql_price if eql_active else sw_l1
            ref_h_idx = sw_h2_idx if eqh_active else sw_h1_idx
            ref_l_idx = sw_l2_idx if eql_active else sw_l1_idx

            if (ref_h is not None
                    and (last_swept_h_idx is None or ref_h_idx != last_swept_h_idx)
                    and highs[t] > ref_h and closes[t] < ref_h and opens[t] < ref_h):
                sweep_high       = True
                last_swept_h_idx = ref_h_idx
                if eqh_active:
                    eqh_active = False
                sweep_events.append({
                    "time": times[t], "price": highs[t],
                    "direction": "high", "level": ref_h
                })

            if (ref_l is not None
                    and (last_swept_l_idx is None or ref_l_idx != last_swept_l_idx)
                    and lows[t] < ref_l and closes[t] > ref_l and opens[t] > ref_l):
                sweep_low        = True
                last_swept_l_idx = ref_l_idx
                if eql_active:
                    eql_active = False
                sweep_events.append({
                    "time": times[t], "price": lows[t],
                    "direction": "low", "level": ref_l
                })

        # ── BOS / CHoCH ───────────────────────────────────────────────────────
        is_choch = is_bos = False
        is_bull  = is_bear  = False
        if is_warmed:
            bull_ok = (sw_h1 is not None and closes[t] > sw_h1
                       and (last_broken_h_idx is None or sw_h1_idx != last_broken_h_idx))
            bear_ok = (sw_l1 is not None and closes[t] < sw_l1
                       and (last_broken_l_idx is None or sw_l1_idx != last_broken_l_idx))

            if bull_ok and bear_ok:
                if structure_bias <= 0:
                    bear_ok = False
                else:
                    bull_ok = False

            if bull_ok:
                is_choch = structure_bias <= 0
                is_bos   = not is_choch
                if is_choch:
                    last_choch_dir   = 1
                    last_swept_h_idx = None
                    last_swept_l_idx = None
                structure_bias    = 1
                is_bull           = True
                last_broken_h_idx = sw_h1_idx
                struct_events.append({
                    "time": times[t], "price": sw_h1,
                    "type": "CHoCH" if is_choch else "BOS",
                    "direction": "bull"
                })

            if bear_ok:
                is_choch = structure_bias >= 0
                is_bos   = not is_choch
                if is_choch:
                    last_choch_dir   = -1
                    last_swept_h_idx = None
                    last_swept_l_idx = None
                structure_bias    = -1
                is_bear           = True
                last_broken_l_idx = sw_l1_idx
                struct_events.append({
                    "time": times[t], "price": sw_l1,
                    "type": "CHoCH" if is_choch else "BOS",
                    "direction": "bear"
                })

        # ── Fib anchors ───────────────────────────────────────────────────────
        if is_choch and is_bull:
            fib_dir = 1
            fib_sh, fib_sh_idx = highs[t], t
            fib_sl, fib_sl_idx = sw_l1, sw_l1_idx
            fib_h_live, fib_l_live = True, False
        if is_choch and is_bear:
            fib_dir = -1
            fib_sl, fib_sl_idx = lows[t], t
            fib_sh, fib_sh_idx = sw_h1, sw_h1_idx
            fib_l_live, fib_h_live = True, False
        if is_bos and is_bull:
            fib_sh, fib_sh_idx = highs[t], t
            fib_sl, fib_sl_idx = sw_l1, sw_l1_idx
            fib_h_live, fib_l_live = True, False
        if is_bos and is_bear:
            fib_sl, fib_sl_idx = lows[t], t
            fib_sh, fib_sh_idx = sw_h1, sw_h1_idx
            fib_l_live, fib_h_live = True, False

        if not is_bull and not is_bear:
            if fib_h_live and fib_sh is not None and highs[t] > fib_sh:
                fib_sh, fib_sh_idx = highs[t], t
            if fib_l_live and fib_sl is not None and lows[t] < fib_sl:
                fib_sl, fib_sl_idx = lows[t], t

        if new_sh and fib_h_live and sw_h1 is not None:
            fib_sh, fib_sh_idx = sw_h1, sw_h1_idx
            fib_h_live = False
        if new_sl and fib_l_live and sw_l1 is not None:
            fib_sl, fib_sl_idx = sw_l1, sw_l1_idx
            fib_l_live = False

        if new_sh and not fib_h_live and sw_h1 is not None and fib_sh is not None and sw_h1 != fib_sh:
            fib_sh, fib_sh_idx = sw_h1, sw_h1_idx
        if new_sl and not fib_l_live and sw_l1 is not None and fib_sl is not None and sw_l1 != fib_sl:
            fib_sl, fib_sl_idx = sw_l1, sw_l1_idx

        # ── Fib levels ────────────────────────────────────────────────────────
        fib_valid = (fib_sh is not None and fib_sl is not None
                     and fib_sh > fib_sl and fib_dir != 0)
        fib236 = fib382 = fib500 = fib618 = fib786 = fib_tgt50 = fib_tgt = None

        if fib_valid:
            rng = fib_sh - fib_sl
            if fib_dir == 1:
                fib236    = fib_sh - rng * 0.236
                fib382    = fib_sh - rng * 0.382
                fib500    = fib_sh - rng * 0.500
                fib618    = fib_sh - rng * 0.618
                fib786    = fib_sh - rng * 0.786
                fib_tgt50 = fib_sh + rng * 0.5
                fib_tgt   = fib_sh + rng * 0.618
            else:
                fib236    = fib_sl + rng * 0.236
                fib382    = fib_sl + rng * 0.382
                fib500    = fib_sl + rng * 0.500
                fib618    = fib_sl + rng * 0.618
                fib786    = fib_sl + rng * 0.786
                fib_tgt50 = fib_sl - rng * 0.5
                fib_tgt   = fib_sl - rng * 0.618

        # ── Premium / Discount ────────────────────────────────────────────────
        in_premium = in_discount = False
        if fib500 is not None and fib_valid:
            if fib_dir == 1:
                in_premium  = closes[t] > fib500
                in_discount = closes[t] <= fib500
            else:
                in_premium  = closes[t] < fib500
                in_discount = closes[t] >= fib500

        # ── Confluence scoring ─────────────────────────────────────────────────
        conf_tol_val = atr * conf_tol if atr > 0 else 0.001

        def near(level):
            if level is None:
                return False
            return (abs(closes[t] - level) <= conf_tol_val
                    or (lows[t] <= level + conf_tol_val and highs[t] >= level - conf_tol_val))

        conf_w = 0.0
        if fib_valid:
            if near(fib236): conf_w += 1.0
            if near(fib382): conf_w += 1.5
            if near(fib500): conf_w += 2.0
            if near(fib618): conf_w += 2.5
            if near(fib786): conf_w += 1.5
        if sw_h1 is not None and near(sw_h1): conf_w += 1.0
        if sw_l1 is not None and near(sw_l1): conf_w += 1.0
        if sweep_high or sweep_low:           conf_w += 2.0

        conf_score = min(conf_w * 10.0, 100.0)

        # ── Engulfing patterns ─────────────────────────────────────────────────
        bd     = body[t]
        bd_avg = body_ema[t] if t >= 14 else bd
        is_long_body = bd > bd_avg
        bd_prev     = body[t - 1] if t > 0 else 0.0
        bd_avg_prev  = body_ema[t - 1] if t >= 15 else bd_avg
        is_small_prev = bd_prev < bd_avg_prev
        body_bigger   = bd > bd_prev

        bearish_eng = bullish_eng = False
        if t > 0 and is_warmed:
            c0, o0 = closes[t], opens[t]
            c1, o1 = closes[t - 1], opens[t - 1]
            bearish_eng = (c0 < o0 and is_long_body and body_bigger and c1 > o1
                           and is_small_prev and o0 > c1 and c0 < o1)
            bullish_eng = (c0 > o0 and is_long_body and body_bigger and c1 < o1
                           and is_small_prev and o0 < c1 and c0 > o1)

        bull_eng_ctx = bullish_eng and (in_discount or conf_w >= 1.5)
        bear_eng_ctx = bearish_eng and (in_premium  or conf_w >= 1.5)

        # ── Signal logic ───────────────────────────────────────────────────────
        sweep_buy  = sweep_low  and is_warmed and (in_discount or conf_w >= 2.0)
        sweep_sell = sweep_high and is_warmed and (in_premium  or conf_w >= 2.0)

        buy_eng_ok  = bull_eng_ctx and structure_bias == 1  and conf_w >= 1.5
        sell_eng_ok = bear_eng_ctx and structure_bias == -1 and conf_w >= 1.5
        buy_choch   = is_choch and is_bull
        sell_choch  = is_choch and is_bear

        buy_raw  = buy_eng_ok  or buy_choch  or sweep_buy
        sell_raw = sell_eng_ok or sell_choch or sweep_sell
        if buy_raw and sell_raw:
            buy_raw = sell_raw = False

        did_buy = did_sell = False
        if is_warmed and buy_raw and bars_since_sig >= cooldown:
            buy_signals.append({"time": times[t], "price": closes[t]})
            bars_since_sig = 0
            did_buy = True
        elif is_warmed and sell_raw and bars_since_sig >= cooldown:
            sell_signals.append({"time": times[t], "price": closes[t]})
            bars_since_sig = 0
            did_sell = True

        bar_states.append({
            "buy":   did_buy,
            "sell":  did_sell,
            "choch_bull": is_choch and is_bull,
            "choch_bear": is_choch and is_bear,
            "bos_bull":   is_bos and is_bull,
            "bos_bear":   is_bos and is_bear,
            "in_premium": in_premium,
            "in_discount": in_discount,
            "conf_score":  conf_score,
        })

        if t == n - 1:
            fib_levels_final = {
                "direction":      fib_dir,
                "swing_high":     fib_sh,
                "swing_low":      fib_sl,
                "fib236":         fib236,
                "fib382":         fib382,
                "fib500":         fib500,
                "fib618":         fib618,
                "fib786":         fib786,
                "fib_target":     fib_tgt,
                "fib_tgt50":      fib_tgt50,
                "golden_zone_top": max(fib500, fib786) if fib500 and fib786 else None,
                "golden_zone_bot": min(fib500, fib786) if fib500 and fib786 else None,
                "target_zone_top": max(fib_tgt, fib_tgt50) if fib_tgt and fib_tgt50 else None,
                "target_zone_bot": min(fib_tgt, fib_tgt50) if fib_tgt and fib_tgt50 else None,
                "in_premium":     in_premium,
                "in_discount":    in_discount,
                "conf_score":     conf_score,
                "structure_bias": structure_bias,
                "last_choch_dir": last_choch_dir,
                "eqh_active":     eqh_active,
                "eql_active":     eql_active,
                "eqh_price":      eqh_price,
                "eql_price":      eql_price,
            }

    return {
        "swing_labels":  swing_labels,
        "struct_events": struct_events,
        "sweep_events":  sweep_events,
        "buy_signals":   buy_signals,
        "sell_signals":  sell_signals,
        "fib_levels":    fib_levels_final,
        "bar_states":    bar_states,
    }


# ── Build chart_data (for Lightweight Charts rendering) ──────────────────────

def build_chart_data(bars, result, display_count=80):
    n       = len(bars)
    start   = max(0, n - display_count)
    r_bars  = bars[start:]
    r_states = result["bar_states"][start:]
    fib     = result["fib_levels"]

    # ── Candlestick bars with signal-driven coloring ──────────────────────────
    chart_bars = []
    for i, (b, st) in enumerate(zip(r_bars, r_states)):
        if st["buy"]:
            color = wick = border = "#00e676"   # bright green — BUY signal
        elif st["sell"]:
            color = wick = border = "#ff5252"   # bright red  — SELL signal
        elif st["choch_bull"] or st["bos_bull"]:
            color  = "#26a69a"
            wick   = "#4dd0e1"
            border = "#4dd0e1"
        elif st["choch_bear"] or st["bos_bear"]:
            color  = "#ef5350"
            wick   = "#ff8a80"
            border = "#ff8a80"
        elif b["close"] >= b["open"]:
            color = "#26a69a"; wick = "#26a69a"; border = "#26a69a"
        else:
            color = "#ef5350"; wick = "#ef5350"; border = "#ef5350"

        chart_bars.append({
            "time": b["time"], "open": b["open"],
            "high": b["high"], "low": b["low"], "close": b["close"],
            "color": color, "wickColor": wick, "borderColor": border,
        })

    # Time set for filtering markers to visible range
    visible_times = {b["time"] for b in r_bars}

    # ── Markers: swing labels → small circles ────────────────────────────────
    markers = []
    for ev in result["swing_labels"]:
        if ev["time"] not in visible_times:
            continue
        markers.append({
            "time":     ev["time"],
            "position": "aboveBar" if ev["position"] == "above" else "belowBar",
            "color":    ev["color"],
            "shape":    "circle",
            "text":     ev["text"],
            "size":     0.8,
        })

    # ── Markers: BOS / CHoCH ─────────────────────────────────────────────────
    for ev in result["struct_events"]:
        if ev["time"] not in visible_times:
            continue
        is_bull = ev["direction"] == "bull"
        shape   = "arrowUp" if is_bull else "arrowDown"
        color   = "#4dd0e1" if ev["type"] == "CHoCH" else "#29b6f6"
        if not is_bull:
            color = "#ff8a65" if ev["type"] == "CHoCH" else "#ffa726"
        markers.append({
            "time":     ev["time"],
            "position": "belowBar" if is_bull else "aboveBar",
            "color":    color,
            "shape":    shape,
            "text":     ev["type"],
            "size":     1.2,
        })

    # ── Markers: sweeps ───────────────────────────────────────────────────────
    for ev in result["sweep_events"]:
        if ev["time"] not in visible_times:
            continue
        is_high = ev["direction"] == "high"
        markers.append({
            "time":     ev["time"],
            "position": "aboveBar" if is_high else "belowBar",
            "color":    "#ff9100",
            "shape":    "circle",
            "text":     "SWP",
            "size":     0.6,
        })

    # ── Markers: BUY / SELL signals ───────────────────────────────────────────
    for ev in result["buy_signals"]:
        if ev["time"] not in visible_times:
            continue
        markers.append({
            "time":     ev["time"],
            "position": "belowBar",
            "color":    "#00e676",
            "shape":    "arrowUp",
            "text":     "BUY",
            "size":     2.0,
        })
    for ev in result["sell_signals"]:
        if ev["time"] not in visible_times:
            continue
        markers.append({
            "time":     ev["time"],
            "position": "aboveBar",
            "color":    "#ff5252",
            "shape":    "arrowDown",
            "text":     "SELL",
            "size":     2.0,
        })

    # Sort markers by time (required by Lightweight Charts)
    markers.sort(key=lambda m: m["time"])

    # ── Price lines: Fibonacci levels ─────────────────────────────────────────
    fib_color  = "#42a5f5"
    bull_color = "#00e676"
    bear_color = "#ff5252"
    tgt_color  = bull_color if fib.get("direction", 0) == 1 else bear_color

    price_lines = []
    if fib.get("fib382"):
        price_lines.append({"price": fib["fib382"], "color": fib_color,  "width": 1, "style": 1, "label": "0.382"})
    if fib.get("fib500"):
        price_lines.append({"price": fib["fib500"], "color": fib_color,  "width": 2, "style": 2, "label": "0.500"})
    if fib.get("fib618"):
        price_lines.append({"price": fib["fib618"], "color": "#ffd600",  "width": 2, "style": 0, "label": "0.618 ★"})
    if fib.get("fib786"):
        price_lines.append({"price": fib["fib786"], "color": fib_color,  "width": 1, "style": 1, "label": "0.786"})
    if fib.get("fib_target"):
        price_lines.append({"price": fib["fib_target"],  "color": tgt_color, "width": 2, "style": 2,
                             "label": "Target ↑" if fib["direction"] == 1 else "Target ↓"})
    if fib.get("fib_tgt50"):
        price_lines.append({"price": fib["fib_tgt50"], "color": tgt_color, "width": 1, "style": 1, "label": "-0.5"})
    if fib.get("swing_high"):
        price_lines.append({"price": fib["swing_high"], "color": "#ef5350", "width": 1, "style": 3, "label": "SwHigh"})
    if fib.get("swing_low"):
        price_lines.append({"price": fib["swing_low"],  "color": "#26a69a", "width": 1, "style": 3, "label": "SwLow"})

    return {
        "bars":         chart_bars,
        "markers":      markers,
        "price_lines":  price_lines,
        "golden_zone":  {
            "top": fib.get("golden_zone_top"),
            "bot": fib.get("golden_zone_bot"),
        },
        "target_zone": {
            "top": fib.get("target_zone_top"),
            "bot": fib.get("target_zone_bot"),
            "direction": fib.get("direction", 0),
        },
    }


# ── Signal summary ────────────────────────────────────────────────────────────

def build_signal(result, bars):
    fib = result["fib_levels"]
    bias = fib.get("structure_bias", 0)

    if bias > 0:
        signal = "BULLISH"
    elif bias < 0:
        signal = "BEARISH"
    else:
        signal = "NEUTRAL"

    fib_dir_str = "Long ↑" if fib.get("last_choch_dir", 0) > 0 else (
        "Short ↓" if fib.get("last_choch_dir", 0) < 0 else "—")

    zone = "Premium" if fib.get("in_premium") else ("Discount" if fib.get("in_discount") else "Neutral")
    conf = fib.get("conf_score", 0)
    conf_str = "Strong" if conf >= 60 else ("Moderate" if conf >= 30 else ("Weak" if conf > 0 else "None"))

    reasons = []
    if bias > 0:
        reasons.append("Structure bias: Bullish (last break was CHoCH up or BOS bull)")
    elif bias < 0:
        reasons.append("Structure bias: Bearish (last break was CHoCH down or BOS bear)")
    else:
        reasons.append("Structure bias: Neutral — no confirmed break yet")

    if fib.get("fib618"):
        reasons.append(f"Fib 0.618 (Golden Ratio) @ ${fib['fib618']:.2f}")
    if fib.get("golden_zone_top") and fib.get("golden_zone_bot"):
        reasons.append(
            f"Golden Zone 0.5–0.786: ${fib['golden_zone_bot']:.2f} – ${fib['golden_zone_top']:.2f}")
    if zone != "Neutral":
        reasons.append(f"Price in {zone} zone (relative to 0.5 fib)")
    if conf > 0:
        reasons.append(f"Confluence: {conf_str} ({conf:.0f}/100)")

    recent_buys  = result["buy_signals"][-3:]
    recent_sells = result["sell_signals"][-3:]
    if recent_buys:
        import datetime
        t = recent_buys[-1]["time"]
        d = datetime.datetime.fromtimestamp(t).strftime("%Y-%m-%d")
        reasons.append(f"Last BUY signal: {d} @ ${recent_buys[-1]['price']:.2f}")
    if recent_sells:
        import datetime
        t = recent_sells[-1]["time"]
        d = datetime.datetime.fromtimestamp(t).strftime("%Y-%m-%d")
        reasons.append(f"Last SELL signal: {d} @ ${recent_sells[-1]['price']:.2f}")

    return {
        "indicator": "FibStruct",
        "signal":    signal,
        "reasons":   reasons,
        "key_values": {
            "Structure Bias":   "Bullish" if bias > 0 else ("Bearish" if bias < 0 else "Neutral"),
            "Fib Direction":    fib_dir_str,
            "Zone":             zone,
            "Confluence":       f"{conf_str} ({conf:.0f}/100)",
            "0.618 level":      f"${fib['fib618']:.2f}" if fib.get("fib618") else "—",
            "Target":           f"${fib['fib_target']:.2f}" if fib.get("fib_target") else "—",
        },
    }


# ── Main entry point (called from brief_builder.py) ──────────────────────────

def build_brief_from_ohlcv(bars):
    result     = compute_fibstruct(bars)
    chart_data = build_chart_data(bars, result)
    sig        = build_signal(result, bars)
    sig["chart_data"] = chart_data

    fib  = result["fib_levels"]
    bias = fib.get("structure_bias", 0)
    bias_str = "Bullish" if bias > 0 else ("Bearish" if bias < 0 else "Neutral")
    zone = "Premium" if fib.get("in_premium") else ("Discount" if fib.get("in_discount") else "Neutral")
    conf = fib.get("conf_score", 0)
    conf_str = "Strong" if conf >= 60 else ("Moderate" if conf >= 30 else ("Weak" if conf > 0 else "None"))

    import datetime
    def ts(unix):
        return datetime.datetime.fromtimestamp(unix).strftime("%Y-%m-%d")

    cur = bars[-1]
    recent_buys  = result["buy_signals"][-3:]
    recent_sells = result["sell_signals"][-3:]

    buy_str  = ", ".join(f"{ts(s['time'])} @ ${s['price']:.2f}" for s in recent_buys)  or "none"
    sell_str = ", ".join(f"{ts(s['time'])} @ ${s['price']:.2f}" for s in recent_sells) or "none"

    brief = f"""FibStruct — Fibonacci Structure Engine (computed from OHLCV)
Current bar: {ts(cur['time'])}  close=${cur['close']:.2f}

Structure:
  Bias:          {bias_str}
  Fib Direction: {"Long ↑" if fib.get('last_choch_dir',0) > 0 else ("Short ↓" if fib.get('last_choch_dir',0) < 0 else "—")}
  Zone:          {zone}
  Confluence:    {conf_str} ({conf:.0f}/100)

Fibonacci Levels (current):
  Swing High:    ${fib.get('swing_high', 0):.2f}
  Swing Low:     ${fib.get('swing_low', 0):.2f}
  0.382:         ${fib.get('fib382', 0):.2f}
  0.500:         ${fib.get('fib500', 0):.2f}
  0.618 ★:       ${fib.get('fib618', 0):.2f}
  0.786:         ${fib.get('fib786', 0):.2f}
  Target (-0.618): ${fib.get('fib_target', 0):.2f}

Golden Zone (0.5–0.786): ${fib.get('golden_zone_bot', 0):.2f} – ${fib.get('golden_zone_top', 0):.2f}
Target Zone:             ${fib.get('target_zone_bot', 0):.2f} – ${fib.get('target_zone_top', 0):.2f}

Recent signals:
  BUY:  {buy_str}
  SELL: {sell_str}

Structure events (last 5):
"""
    for ev in result["struct_events"][-5:]:
        brief += f"  {ts(ev['time'])}  {ev['type']} {ev['direction'].upper()} @ ${ev['price']:.2f}\n"

    return brief, sig


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    data_path = Path(__file__).parent / "gld_daily_ohlcv_200.json"
    with open(data_path) as f:
        data = json.load(f)

    bars = data["bars"]
    brief, sig = build_brief_from_ohlcv(bars)

    print("=" * 60)
    print(f"Symbol: {data['symbol']}  Resolution: {data['resolution']}")
    print("=" * 60)
    print(brief)
    print("-" * 60)
    print("SIGNAL OUTPUT:")
    sig_no_chart = {k: v for k, v in sig.items() if k != "chart_data"}
    print(json.dumps(sig_no_chart, indent=2))
    print("-" * 60)
    cd = sig["chart_data"]
    print(f"chart_data: {len(cd['bars'])} bars, {len(cd['markers'])} markers, "
          f"{len(cd['price_lines'])} price lines")
    print(f"  golden_zone: {cd['golden_zone']}")
    print(f"  target_zone: {cd['target_zone']}")
