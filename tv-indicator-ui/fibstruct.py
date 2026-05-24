"""
FibStruct computation module — exact Python translation of Pine Script v1.5.2.
Imported by brief_builder.py and usable standalone.
"""
import datetime
import json


def _atr(bars, period=14):
    n = len(bars)
    tr = [max(b["high"] - b["low"],
              abs(b["high"] - (bars[i-1]["close"] if i > 0 else b["close"])),
              abs(b["low"]  - (bars[i-1]["close"] if i > 0 else b["close"])))
          for i, b in enumerate(bars)]
    atr = [0.0] * n
    if n >= period:
        atr[period - 1] = sum(tr[:period]) / period
        for i in range(period, n):
            atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    return atr


def _body_ema(bars, period=14):
    n    = len(bars)
    body = [abs(b["close"] - b["open"]) for b in bars]
    ema  = [0.0] * n
    if n >= period:
        ema[period - 1] = sum(body[:period]) / period
        for i in range(period, n):
            ema[i] = (ema[i - 1] * (period - 1) + body[i]) / period
    return body, ema


def compute(bars, swing_len=10, atr_mult=0.5, conf_tol=0.3, cooldown=5, eq_tol=0.1):
    """
    Bar-by-bar state machine simulation of the Pine Script.
    Returns a dict of event arrays + per-bar state + final fib_levels.
    """
    n      = len(bars)
    highs  = [b["high"]  for b in bars]
    lows   = [b["low"]   for b in bars]
    opens  = [b["open"]  for b in bars]
    closes = [b["close"] for b in bars]
    times  = [b["time"]  for b in bars]

    atrs          = _atr(bars)
    body, body_em = _body_ema(bars)
    warmup        = max(swing_len * 3, 50)

    sw_h1, sw_h1_idx = None, None
    sw_h2, sw_h2_idx = None, None
    sw_l1, sw_l1_idx = None, None
    sw_l2, sw_l2_idx = None, None

    structure_bias     = 0
    last_choch_dir     = 0
    last_broken_h_idx  = None
    last_broken_l_idx  = None

    eqh_active, eqh_price = False, None
    eql_active, eql_price = False, None
    last_swept_h_idx       = None
    last_swept_l_idx       = None

    fib_dir               = 0
    fib_sh, fib_sl        = None, None
    fib_sh_idx, fib_sl_idx = None, None
    fib_h_live, fib_l_live = False, False

    bars_since_sig = 999

    swing_labels  = []
    struct_events = []
    sweep_events  = []
    buy_signals   = []
    sell_signals  = []
    bar_states    = []
    fib_final     = {}

    for t in range(n):
        atr       = atrs[t]
        is_warmed = t >= warmup
        bars_since_sig += 1

        # Pivot detection (Pine: confirmed swing_len bars late)
        pi = t - swing_len
        ph_val = pl_val = None
        if pi >= swing_len:
            lo_i, hi_i = pi - swing_len, pi + swing_len + 1
            wh = highs[lo_i:hi_i]
            wl = lows[lo_i:hi_i]
            if wh and highs[pi] == max(wh): ph_val = highs[pi]
            if wl and lows[pi]  == min(wl): pl_val = lows[pi]

        atr_min = atr * atr_mult if atr > 0 else 0.0
        new_sh = new_sl = False

        if ph_val is not None and (sw_l1 is None or (ph_val - sw_l1) >= atr_min):
            sw_h2, sw_h2_idx = sw_h1, sw_h1_idx
            sw_h1, sw_h1_idx = ph_val, pi
            new_sh = True

        if pl_val is not None and (sw_h1 is None or (sw_h1 - pl_val) >= atr_min):
            sw_l2, sw_l2_idx = sw_l1, sw_l1_idx
            sw_l1, sw_l1_idx = pl_val, pi
            new_sl = True

        if is_warmed and new_sh and sw_h2 is not None:
            lbl = "HH" if sw_h1 > sw_h2 else "LH"
            swing_labels.append({"time": times[sw_h1_idx], "price": sw_h1,
                                  "text": lbl, "position": "above",
                                  "color": "#26a69a" if lbl == "HH" else "#ef5350"})

        if is_warmed and new_sl and sw_l2 is not None:
            lbl = "HL" if sw_l1 > sw_l2 else "LL"
            swing_labels.append({"time": times[sw_l1_idx], "price": sw_l1,
                                  "text": lbl, "position": "below",
                                  "color": "#26a69a" if lbl == "HL" else "#ef5350"})

        # EQH / EQL
        eq_tv = atr * eq_tol if atr > 0 else 0.0
        if is_warmed and new_sh and sw_h2 is not None and abs(sw_h1 - sw_h2) <= eq_tv:
            eqh_active = True; eqh_price = (sw_h1 + sw_h2) / 2
        if is_warmed and new_sl and sw_l2 is not None and abs(sw_l1 - sw_l2) <= eq_tv:
            eql_active = True; eql_price = (sw_l1 + sw_l2) / 2

        # Liquidity sweeps
        sweep_high = sweep_low = False
        if is_warmed:
            rh = eqh_price if eqh_active else sw_h1
            rl = eql_price if eql_active else sw_l1
            rh_i = sw_h2_idx if eqh_active else sw_h1_idx
            rl_i = sw_l2_idx if eql_active else sw_l1_idx

            if (rh is not None
                    and (last_swept_h_idx is None or rh_i != last_swept_h_idx)
                    and highs[t] > rh and closes[t] < rh and opens[t] < rh):
                sweep_high = True; last_swept_h_idx = rh_i
                if eqh_active: eqh_active = False
                sweep_events.append({"time": times[t], "price": highs[t], "direction": "high", "level": rh})

            if (rl is not None
                    and (last_swept_l_idx is None or rl_i != last_swept_l_idx)
                    and lows[t] < rl and closes[t] > rl and opens[t] > rl):
                sweep_low = True; last_swept_l_idx = rl_i
                if eql_active: eql_active = False
                sweep_events.append({"time": times[t], "price": lows[t], "direction": "low", "level": rl})

        # BOS / CHoCH
        is_choch = is_bos = is_bull = is_bear = False
        if is_warmed:
            bull_ok = (sw_h1 is not None and closes[t] > sw_h1
                       and (last_broken_h_idx is None or sw_h1_idx != last_broken_h_idx))
            bear_ok = (sw_l1 is not None and closes[t] < sw_l1
                       and (last_broken_l_idx is None or sw_l1_idx != last_broken_l_idx))
            if bull_ok and bear_ok:
                bear_ok = False if structure_bias <= 0 else None
                bull_ok = False if bear_ok is None else bull_ok
                if bear_ok is None: bear_ok = True; bull_ok = False

            if bull_ok:
                is_choch = structure_bias <= 0; is_bos = not is_choch
                if is_choch:
                    last_choch_dir = 1; last_swept_h_idx = None; last_swept_l_idx = None
                structure_bias = 1; is_bull = True; last_broken_h_idx = sw_h1_idx
                struct_events.append({"time": times[t], "price": sw_h1,
                                       "type": "CHoCH" if is_choch else "BOS", "direction": "bull"})
            if bear_ok:
                is_choch = structure_bias >= 0; is_bos = not is_choch
                if is_choch:
                    last_choch_dir = -1; last_swept_h_idx = None; last_swept_l_idx = None
                structure_bias = -1; is_bear = True; last_broken_l_idx = sw_l1_idx
                struct_events.append({"time": times[t], "price": sw_l1,
                                       "type": "CHoCH" if is_choch else "BOS", "direction": "bear"})

        # Fib anchors
        if is_choch and is_bull:
            fib_dir = 1; fib_sh, fib_sh_idx = highs[t], t
            fib_sl, fib_sl_idx = sw_l1, sw_l1_idx; fib_h_live, fib_l_live = True, False
        if is_choch and is_bear:
            fib_dir = -1; fib_sl, fib_sl_idx = lows[t], t
            fib_sh, fib_sh_idx = sw_h1, sw_h1_idx; fib_l_live, fib_h_live = True, False
        if is_bos and is_bull:
            fib_sh, fib_sh_idx = highs[t], t; fib_sl, fib_sl_idx = sw_l1, sw_l1_idx
            fib_h_live, fib_l_live = True, False
        if is_bos and is_bear:
            fib_sl, fib_sl_idx = lows[t], t; fib_sh, fib_sh_idx = sw_h1, sw_h1_idx
            fib_l_live, fib_h_live = True, False

        if not is_bull and not is_bear:
            if fib_h_live and fib_sh is not None and highs[t] > fib_sh:
                fib_sh, fib_sh_idx = highs[t], t
            if fib_l_live and fib_sl is not None and lows[t] < fib_sl:
                fib_sl, fib_sl_idx = lows[t], t
        if new_sh and fib_h_live and sw_h1 is not None:
            fib_sh, fib_sh_idx = sw_h1, sw_h1_idx; fib_h_live = False
        if new_sl and fib_l_live and sw_l1 is not None:
            fib_sl, fib_sl_idx = sw_l1, sw_l1_idx; fib_l_live = False
        if new_sh and not fib_h_live and sw_h1 and fib_sh and sw_h1 != fib_sh:
            fib_sh, fib_sh_idx = sw_h1, sw_h1_idx
        if new_sl and not fib_l_live and sw_l1 and fib_sl and sw_l1 != fib_sl:
            fib_sl, fib_sl_idx = sw_l1, sw_l1_idx

        # Fib levels
        fib_valid = fib_sh and fib_sl and fib_sh > fib_sl and fib_dir != 0
        f236 = f382 = f500 = f618 = f786 = ft50 = ftgt = None
        if fib_valid:
            rng = fib_sh - fib_sl
            if fib_dir == 1:
                f236 = fib_sh - rng*0.236; f382 = fib_sh - rng*0.382
                f500 = fib_sh - rng*0.500; f618 = fib_sh - rng*0.618
                f786 = fib_sh - rng*0.786
                ft50 = fib_sh + rng*0.5;  ftgt = fib_sh + rng*0.618
            else:
                f236 = fib_sl + rng*0.236; f382 = fib_sl + rng*0.382
                f500 = fib_sl + rng*0.500; f618 = fib_sl + rng*0.618
                f786 = fib_sl + rng*0.786
                ft50 = fib_sl - rng*0.5;  ftgt = fib_sl - rng*0.618

        # Premium / Discount
        in_prem = in_disc = False
        if f500 and fib_valid:
            in_prem = (closes[t] > f500) if fib_dir == 1 else (closes[t] < f500)
            in_disc = not in_prem

        # Confluence score
        ctol = atr * conf_tol if atr > 0 else 0.001
        def near(lv):
            if lv is None: return False
            return (abs(closes[t] - lv) <= ctol
                    or (lows[t] <= lv + ctol and highs[t] >= lv - ctol))
        cw = 0.0
        if fib_valid:
            if near(f236): cw += 1.0
            if near(f382): cw += 1.5
            if near(f500): cw += 2.0
            if near(f618): cw += 2.5
            if near(f786): cw += 1.5
        if sw_h1 and near(sw_h1): cw += 1.0
        if sw_l1 and near(sw_l1): cw += 1.0
        if sweep_high or sweep_low: cw += 2.0
        conf_score = min(cw * 10.0, 100.0)

        # Engulfing
        bd = body[t]; bd_avg = body_em[t] if t >= 14 else bd
        bd_p = body[t-1] if t > 0 else 0.0; bd_ap = body_em[t-1] if t >= 15 else bd_avg
        is_long = bd > bd_avg; is_sp = bd_p < bd_ap; bigger = bd > bd_p
        bearish_e = bullish_e = False
        if t > 0 and is_warmed:
            c0,o0,c1,o1 = closes[t],opens[t],closes[t-1],opens[t-1]
            bearish_e = c0 < o0 and is_long and bigger and c1 > o1 and is_sp and o0 > c1 and c0 < o1
            bullish_e = c0 > o0 and is_long and bigger and c1 < o1 and is_sp and o0 < c1 and c0 > o1

        be_ctx = bearish_e and (in_prem or cw >= 1.5)
        bue_ctx = bullish_e and (in_disc or cw >= 1.5)

        # Signals
        sw_buy  = sweep_low  and is_warmed and (in_disc or cw >= 2.0)
        sw_sell = sweep_high and is_warmed and (in_prem or cw >= 2.0)
        buy_raw  = (bue_ctx and structure_bias == 1 and cw >= 1.5) or (is_choch and is_bull) or sw_buy
        sell_raw = (be_ctx and structure_bias == -1 and cw >= 1.5) or (is_choch and is_bear) or sw_sell
        if buy_raw and sell_raw: buy_raw = sell_raw = False

        did_buy = did_sell = False
        if is_warmed and buy_raw and bars_since_sig >= cooldown:
            buy_signals.append({"time": times[t], "price": closes[t]})
            bars_since_sig = 0; did_buy = True
        elif is_warmed and sell_raw and bars_since_sig >= cooldown:
            sell_signals.append({"time": times[t], "price": closes[t]})
            bars_since_sig = 0; did_sell = True

        bar_states.append({
            "buy": did_buy, "sell": did_sell,
            "choch_bull": is_choch and is_bull, "choch_bear": is_choch and is_bear,
            "bos_bull": is_bos and is_bull,     "bos_bear":  is_bos and is_bear,
            "in_premium": in_prem, "in_discount": in_disc, "conf_score": conf_score,
        })

        if t == n - 1:
            fib_final = {
                "direction": fib_dir, "swing_high": fib_sh, "swing_low": fib_sl,
                "fib382": f382, "fib500": f500, "fib618": f618,
                "fib786": f786, "fib236": f236, "fib_target": ftgt, "fib_tgt50": ft50,
                "golden_zone_top": max(f500, f786) if f500 and f786 else None,
                "golden_zone_bot": min(f500, f786) if f500 and f786 else None,
                "target_zone_top": max(ftgt, ft50)  if ftgt and ft50  else None,
                "target_zone_bot": min(ftgt, ft50)  if ftgt and ft50  else None,
                "in_premium": in_prem, "in_discount": in_disc,
                "conf_score": conf_score, "structure_bias": structure_bias,
                "last_choch_dir": last_choch_dir,
                "eqh_active": eqh_active, "eql_active": eql_active,
                "eqh_price": eqh_price,   "eql_price":  eql_price,
            }

    return {
        "swing_labels":  swing_labels,
        "struct_events": struct_events,
        "sweep_events":  sweep_events,
        "buy_signals":   buy_signals,
        "sell_signals":  sell_signals,
        "fib_levels":    fib_final,
        "bar_states":    bar_states,
    }


def chart_data(bars, result, display_count=80):
    """Build Lightweight Charts-ready chart_data dict."""
    n      = len(bars)
    start  = max(0, n - display_count)
    rb     = bars[start:]
    rs     = result["bar_states"][start:]
    fib    = result["fib_levels"]

    chart_bars = []
    for b, st in zip(rb, rs):
        if st["buy"]:
            col = wick = bdr = "#00e676"
        elif st["sell"]:
            col = wick = bdr = "#ff5252"
        elif st["choch_bull"] or st["bos_bull"]:
            col = "#26a69a"; wick = bdr = "#4dd0e1"
        elif st["choch_bear"] or st["bos_bear"]:
            col = "#ef5350"; wick = bdr = "#ff8a80"
        elif b["close"] >= b["open"]:
            col = wick = bdr = "#26a69a"
        else:
            col = wick = bdr = "#ef5350"
        chart_bars.append({"time": b["time"], "open": b["open"], "high": b["high"],
                            "low": b["low"], "close": b["close"],
                            "color": col, "wickColor": wick, "borderColor": bdr})

    vis = {b["time"] for b in rb}

    markers = []
    for ev in result["swing_labels"]:
        if ev["time"] not in vis: continue
        markers.append({"time": ev["time"],
                         "position": "aboveBar" if ev["position"] == "above" else "belowBar",
                         "color": ev["color"], "shape": "circle",
                         "text": ev["text"], "size": 0.8})

    for ev in result["struct_events"]:
        if ev["time"] not in vis: continue
        is_bull = ev["direction"] == "bull"
        color = ("#4dd0e1" if ev["type"] == "CHoCH" else "#29b6f6") if is_bull else \
                ("#ff8a65" if ev["type"] == "CHoCH" else "#ffa726")
        markers.append({"time": ev["time"],
                         "position": "belowBar" if is_bull else "aboveBar",
                         "color": color, "shape": "arrowUp" if is_bull else "arrowDown",
                         "text": ev["type"], "size": 1.2})

    for ev in result["sweep_events"]:
        if ev["time"] not in vis: continue
        markers.append({"time": ev["time"],
                         "position": "aboveBar" if ev["direction"] == "high" else "belowBar",
                         "color": "#ff9100", "shape": "circle", "text": "SWP", "size": 0.6})

    for ev in result["buy_signals"]:
        if ev["time"] not in vis: continue
        markers.append({"time": ev["time"], "position": "belowBar",
                         "color": "#00e676", "shape": "arrowUp", "text": "BUY", "size": 2.0})
    for ev in result["sell_signals"]:
        if ev["time"] not in vis: continue
        markers.append({"time": ev["time"], "position": "aboveBar",
                         "color": "#ff5252", "shape": "arrowDown", "text": "SELL", "size": 2.0})

    markers.sort(key=lambda m: m["time"])

    fib_c = "#42a5f5"
    tc    = "#00e676" if fib.get("direction", 0) == 1 else "#ff5252"
    price_lines = []
    for ratio, key, color, width, style in [
        ("0.382", "fib382", fib_c, 1, 1),
        ("0.500", "fib500", fib_c, 2, 2),
        ("0.618 ★", "fib618", "#ffd600", 2, 0),
        ("0.786", "fib786", fib_c, 1, 1),
        ("SwHigh", "swing_high", "#ef5350", 1, 3),
        ("SwLow",  "swing_low",  "#26a69a", 1, 3),
    ]:
        if fib.get(key):
            price_lines.append({"price": fib[key], "color": color, "width": width,
                                  "style": style, "label": ratio})
    for ratio, key in [("Target", "fib_target"), ("-0.5", "fib_tgt50")]:
        if fib.get(key):
            lbl = ("Target ↑" if fib["direction"] == 1 else "Target ↓") if ratio == "Target" else ratio
            price_lines.append({"price": fib[key], "color": tc, "width": 2 if ratio == "Target" else 1,
                                  "style": 2 if ratio == "Target" else 1, "label": lbl})

    return {
        "bars":        chart_bars,
        "markers":     markers,
        "price_lines": price_lines,
        "golden_zone": {"top": fib.get("golden_zone_top"), "bot": fib.get("golden_zone_bot")},
        "target_zone": {"top": fib.get("target_zone_top"), "bot": fib.get("target_zone_bot"),
                        "direction": fib.get("direction", 0)},
    }


def build_brief_from_ohlcv(bars):
    """Main entry point: returns (brief_text, signal_dict_with_chart_data)."""
    result = compute(bars)
    cd     = chart_data(bars, result)
    fib    = result["fib_levels"]
    bias   = fib.get("structure_bias", 0)

    bias_str  = "Bullish" if bias > 0 else ("Bearish" if bias < 0 else "Neutral")
    fdir_str  = "Long ↑" if fib.get("last_choch_dir",0) > 0 else ("Short ↓" if fib.get("last_choch_dir",0) < 0 else "—")
    zone      = "Premium" if fib.get("in_premium") else ("Discount" if fib.get("in_discount") else "Neutral")
    conf      = fib.get("conf_score", 0)
    conf_str  = "Strong" if conf >= 60 else ("Moderate" if conf >= 30 else ("Weak" if conf > 0 else "None"))

    def ts(u): return datetime.datetime.fromtimestamp(u).strftime("%Y-%m-%d")
    cur = bars[-1]

    buy_strs  = [f"{ts(s['time'])} @ ${s['price']:.2f}" for s in result["buy_signals"][-3:]]
    sell_strs = [f"{ts(s['time'])} @ ${s['price']:.2f}" for s in result["sell_signals"][-3:]]

    brief = f"""FibStruct — Fibonacci Structure Engine (computed from OHLCV)
Current bar: {ts(cur['time'])}  close=${cur['close']:.2f}

Structure:
  Bias:          {bias_str}
  Fib Direction: {fdir_str}
  Zone:          {zone}
  Confluence:    {conf_str} ({conf:.0f}/100)

Fibonacci Levels (current):
  Swing High:      ${fib.get('swing_high', 0):.2f}
  Swing Low:       ${fib.get('swing_low', 0):.2f}
  0.382:           ${fib.get('fib382', 0):.2f}
  0.500:           ${fib.get('fib500', 0):.2f}
  0.618 ★:         ${fib.get('fib618', 0):.2f}
  0.786:           ${fib.get('fib786', 0):.2f}
  Target (-0.618): ${fib.get('fib_target', 0):.2f}

Golden Zone (0.5–0.786): ${fib.get('golden_zone_bot', 0):.2f} – ${fib.get('golden_zone_top', 0):.2f}
Target Zone:             ${fib.get('target_zone_bot', 0):.2f} – ${fib.get('target_zone_top', 0):.2f}

Recent signals:
  BUY:  {", ".join(buy_strs)  or "none"}
  SELL: {", ".join(sell_strs) or "none"}

Structure events (last 5):
"""
    for ev in result["struct_events"][-5:]:
        brief += f"  {ts(ev['time'])}  {ev['type']} {ev['direction'].upper()} @ ${ev['price']:.2f}\n"

    reasons = []
    if bias > 0:
        reasons.append("Structure bias: Bullish — last break was CHoCH/BOS up")
    elif bias < 0:
        reasons.append("Structure bias: Bearish — last break was CHoCH/BOS down")
    else:
        reasons.append("Structure bias: Neutral — no confirmed break yet")

    if fib.get("fib618"):
        reasons.append(f"Fib 0.618 (Golden Ratio) @ ${fib['fib618']:.2f}")
    if fib.get("golden_zone_top") and fib.get("golden_zone_bot"):
        reasons.append(f"Golden Zone 0.5–0.786: ${fib['golden_zone_bot']:.2f} – ${fib['golden_zone_top']:.2f}")
    if zone != "Neutral":
        reasons.append(f"Price in {zone} zone (relative to 0.5 fib)")
    if conf > 0:
        reasons.append(f"Confluence: {conf_str} ({conf:.0f}/100)")
    if buy_strs:
        reasons.append(f"Last BUY signal: {buy_strs[-1]}")
    if sell_strs:
        reasons.append(f"Last SELL signal: {sell_strs[-1]}")

    sig = {
        "indicator": "FibStruct",
        "signal":    "BULLISH" if bias > 0 else ("BEARISH" if bias < 0 else "NEUTRAL"),
        "reasons":   reasons,
        "key_values": {
            "Structure Bias": bias_str,
            "Fib Direction":  fdir_str,
            "Zone":           zone,
            "Confluence":     f"{conf_str} ({conf:.0f}/100)",
            "0.618 level":    f"${fib['fib618']:.2f}" if fib.get("fib618") else "—",
            "Target":         f"${fib['fib_target']:.2f}" if fib.get("fib_target") else "—",
        },
        "chart_data": cd,
    }
    return brief, sig
