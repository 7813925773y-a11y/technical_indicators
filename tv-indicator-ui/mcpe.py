"""
MCPE — Market Cycle Projection Engine (Python translation of Pine Script v2.0).
Imported by brief_builder.py and usable standalone.

Phase classification:
  Markup:       lr_slope_norm > 0.1  AND expanding (ATR expanding)
  Markdown:     lr_slope_norm < -0.1 AND expanding
  Accumulation: -0.1 <= slope <= 0.1 AND price_pos < 0.4  (flat + low in range)
  Distribution: -0.1 <= slope <= 0.1 AND price_pos >= 0.4 (flat + high in range)
  Transition:   else

Projection:
  proj_up = phase in (Accumulation, Markdown)  → next phase going up
  amplitude = cycle_range * 0.75  (Last Cycle mode, default)
  target = close ± amplitude
"""
import datetime
import math


# ── Low-level helpers ─────────────────────────────────────────────────────────

def _atr_wilder(bars, period):
    """Wilder's smoothed ATR (same as Pine's ta.atr)."""
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


def _sma(values, period):
    """Simple moving average array."""
    n = len(values)
    out = [0.0] * n
    for i in range(n):
        if i >= period - 1:
            out[i] = sum(values[i-period+1 : i+1]) / period
    return out


def _highest(values, period, i):
    """highest(values, period) at index i."""
    lo = max(0, i - period + 1)
    return max(values[lo:i+1])


def _lowest(values, period, i):
    """lowest(values, period) at index i."""
    lo = max(0, i - period + 1)
    return min(values[lo:i+1])


def _linreg_value(series, t, length):
    """
    ta.linreg(series, length, 0) at bar t.
    Fits OLS to series[t-length+1 .. t] and returns value at t (end of window).
    """
    if t < length - 1:
        return None
    y = series[t - length + 1 : t + 1]
    n = length
    sx  = n * (n - 1) / 2
    sx2 = n * (n - 1) * (2*n - 1) / 6
    sy  = sum(y)
    sxy = sum(i * y[i] for i in range(n))
    denom = n * sx2 - sx * sx
    if abs(denom) < 1e-12:
        return y[-1]
    slope = (n * sxy - sx * sy) / denom
    intercept = (sy - slope * sx) / n
    return intercept + slope * (n - 1)  # value at x = n-1 (the last bar)


# ── Main computation ──────────────────────────────────────────────────────────

def compute(bars, cycle_len=50):
    """
    Compute per-bar MCPE state.
    Returns list of dicts (one per bar) + summary of final bar.
    """
    n       = len(bars)
    highs   = [b["high"]   for b in bars]
    lows    = [b["low"]    for b in bars]
    closes  = [b["close"]  for b in bars]
    volumes = [b.get("volume", 0) for b in bars]
    times   = [b["time"]   for b in bars]

    atr14    = _atr_wilder(bars, 14)
    atr_slow = _atr_wilder(bars, cycle_len)
    vol_sma  = _sma(volumes, 20)

    results = []
    prev_phase  = None
    phase_start = 0

    for t in range(n):
        cy_high = _highest(highs, cycle_len, t)
        cy_low  = _lowest(lows,  cycle_len, t)
        cy_rng  = cy_high - cy_low
        cy_mid  = (cy_high + cy_low) / 2

        a14  = atr14[t]
        aslo = atr_slow[t]
        vsma = vol_sma[t]
        vol  = volumes[t]

        # Linear regression slope (normalized by ATR14)
        lr0 = _linreg_value(closes, t, cycle_len)
        lr1 = _linreg_value(closes, t - 1, cycle_len) if t >= 1 else lr0
        lr_slope = (lr0 - lr1) if (lr0 is not None and lr1 is not None) else 0.0
        lr_slope_norm = lr_slope / max(a14, 0.0001)

        atr_ratio  = a14 / max(aslo, 0.0001)
        expanding  = atr_ratio > 1.1
        contracting = atr_ratio < 0.85

        price_pos = (closes[t] - cy_low) / max(cy_rng, 0.0001)

        vol_rising  = vol > vsma * 1.2
        vol_falling = vol < vsma * 0.8

        # Phase classification (exact Pine Script logic)
        if lr_slope_norm > 0.1 and expanding:
            phase = "Markup"
        elif lr_slope_norm < -0.1 and expanding:
            phase = "Markdown"
        elif -0.1 <= lr_slope_norm <= 0.1 and price_pos < 0.4:
            phase = "Accumulation"
        elif -0.1 <= lr_slope_norm <= 0.1 and price_pos >= 0.4:
            phase = "Distribution"
        else:
            phase = "Transition"

        if phase != prev_phase:
            prev_phase  = phase
            phase_start = t

        phase_duration = t - phase_start
        cycle_strength = round(abs(price_pos - 0.5) * 200)

        # Projection
        proj_up       = phase in ("Accumulation", "Markdown")
        proj_amplitude = cy_rng * 0.75  # Last Cycle mode
        proj_target    = closes[t] + proj_amplitude if proj_up else closes[t] - proj_amplitude
        proj_pct       = proj_amplitude / closes[t] * 100

        vol_status = "Elevated" if vol_rising else ("Low" if vol_falling else "Normal")
        vol_str    = "Expanding" if expanding else ("Contracting" if contracting else "Normal")

        next_phase = {
            "Accumulation": "Markup",
            "Markup":        "Distribution",
            "Distribution":  "Markdown",
            "Markdown":      "Accumulation",
        }.get(phase, "Transition")

        results.append({
            "time":           times[t],
            "close":          closes[t],
            "phase":          phase,
            "phase_duration": phase_duration,
            "cycle_strength": cycle_strength,
            "price_pos":      price_pos,
            "cycle_high":     cy_high,
            "cycle_mid":      cy_mid,
            "cycle_low":      cy_low,
            "cycle_range":    cy_rng,
            "atr14":          a14,
            "expanding":      expanding,
            "contracting":    contracting,
            "vol_rising":     vol_rising,
            "vol_falling":    vol_falling,
            "vol_status":     vol_status,
            "volatility":     vol_str,
            "proj_up":        proj_up,
            "proj_target":    proj_target,
            "proj_pct":       proj_pct,
            "next_phase":     next_phase,
            "phase_changed":  phase_duration == 0,
        })

    return results


# Phase colors matching Pine Script barcolor palette
_PHASE_COLOR = {
    "Markup":       "#00e676",   # green
    "Markdown":     "#ff5252",   # red
    "Accumulation": "#00bcd4",   # cyan
    "Distribution": "#ff9800",   # orange
    "Transition":   "#7c4dff",   # purple
}


def chart_data(bars, results, display_count=80):
    """Build Lightweight Charts-ready chart_data dict."""
    n     = len(bars)
    start = max(0, n - display_count)
    rb    = bars[start:]
    rr    = results[start:]

    # Candlesticks colored by Wyckoff phase
    chart_bars = []
    for b, r in zip(rb, rr):
        phase_col = _PHASE_COLOR.get(r["phase"], "#8b949e")
        chart_bars.append({
            "time":        b["time"],
            "open":        b["open"],
            "high":        b["high"],
            "low":         b["low"],
            "close":       b["close"],
            "color":       phase_col,
            "wickColor":   phase_col,
            "borderColor": phase_col,
        })

    # Markers: phase transition labels
    vis = {b["time"] for b in rb}
    markers = []
    for r in rr:
        if r["time"] not in vis or not r["phase_changed"]:
            continue
        phase = r["phase"]
        col   = _PHASE_COLOR.get(phase, "#8b949e")
        # Place above for bearish phases, below for bullish
        is_bull = phase in ("Accumulation", "Markup")
        markers.append({
            "time":     r["time"],
            "position": "belowBar" if is_bull else "aboveBar",
            "color":    col,
            "shape":    "arrowUp" if is_bull else "arrowDown",
            "text":     phase,
            "size":     1.5,
        })
    markers.sort(key=lambda m: m["time"])

    # Current state from last bar
    cur = results[-1]

    # Price lines: Cycle High, Mid, Low + projection target
    proj_col = "#00e676" if cur["proj_up"] else "#ff5252"
    proj_pct_str = f"{'+' if cur['proj_up'] else '-'}{cur['proj_pct']:.1f}%"

    price_lines = [
        {"price": cur["cycle_high"], "color": "#ff5252", "width": 2, "style": 0, "label": f"Cycle High ${cur['cycle_high']:.2f}"},
        {"price": cur["cycle_mid"],  "color": "#7c4dff", "width": 1, "style": 1, "label": "Mid"},
        {"price": cur["cycle_low"],  "color": "#00e676", "width": 2, "style": 0, "label": f"Cycle Low ${cur['cycle_low']:.2f}"},
        {"price": cur["proj_target"],"color": proj_col,  "width": 2, "style": 2, "label": f"Proj. {proj_pct_str}"},
    ]

    return {
        "bars":        chart_bars,
        "markers":     markers,
        "price_lines": price_lines,
        "summary":     {
            "phase":          cur["phase"],
            "phase_duration": cur["phase_duration"],
            "cycle_strength": cur["cycle_strength"],
            "price_pos_pct":  round(cur["price_pos"] * 100),
            "volatility":     cur["volatility"],
            "vol_status":     cur["vol_status"],
            "proj_up":        cur["proj_up"],
            "proj_pct":       round(cur["proj_pct"], 1),
            "proj_target":    cur["proj_target"],
            "next_phase":     cur["next_phase"],
            "cycle_high":     cur["cycle_high"],
            "cycle_mid":      cur["cycle_mid"],
            "cycle_low":      cur["cycle_low"],
        },
    }


def build_brief_from_ohlcv(bars):
    """Main entry point: returns (brief_text, signal_dict_with_chart_data)."""
    results = compute(bars)
    cd      = chart_data(bars, results)
    cur     = results[-1]
    sm      = cd["summary"]

    def ts(u): return datetime.datetime.fromtimestamp(u).strftime("%Y-%m-%d")

    # Signal bias
    phase = cur["phase"]
    if phase == "Markup":
        bias = "BULLISH"
    elif phase == "Markdown":
        bias = "BEARISH"
    elif phase == "Accumulation":
        bias = "BULLISH"      # bottoming → next is Markup
    elif phase == "Distribution":
        bias = "BEARISH"      # topping → next is Markdown
    else:
        bias = "NEUTRAL"

    # Build reasons
    reasons = []
    pos = sm["price_pos_pct"]
    reasons.append(f"Phase: {phase} (duration: {cur['phase_duration']} bars)")
    reasons.append(f"Cycle position: {pos}% — {'upper range ⚠' if pos >= 70 else 'lower range (buy zone)' if pos < 30 else 'mid range'}")
    reasons.append(f"Volatility: {sm['volatility']} | Volume: {sm['vol_status']}")
    dir_str = "↑ Upward" if cur["proj_up"] else "↓ Downward"
    reasons.append(f"Projection: {dir_str} {sm['proj_pct']:.1f}% → target ${sm['proj_target']:.2f} (next: {sm['next_phase']})")
    reasons.append(f"Cycle strength: {sm['cycle_strength']}/100")

    # Phase-specific commentary
    phase_notes = {
        "Markup":        "LR slope rising + volatility expanding → active uptrend, ride momentum",
        "Markdown":      "LR slope falling + volatility expanding → active downtrend, avoid longs",
        "Accumulation":  "Flat slope, price in lower range → institutions accumulating, watch for Markup breakout",
        "Distribution":  "Flat slope, price in upper range → institutional distribution, watch for Markdown",
        "Transition":    "Mixed signals — no clean phase; wait for confirmation",
    }
    reasons.append(phase_notes.get(phase, ""))

    cur_bar = bars[-1]
    brief = f"""MCPE — Market Cycle Projection Engine (computed from OHLCV)
Current bar: {ts(cur_bar['time'])}  close=${cur_bar['close']:.2f}

Dashboard:
  Cycle Phase:     {phase}
  Phase Duration:  {cur['phase_duration']} bars
  Cycle Strength:  {sm['cycle_strength']} / 100
  Cycle Position:  {pos}%
  Volatility:      {sm['volatility']}
  Volume:          {sm['vol_status']}
  Projection:      {"Upward" if cur['proj_up'] else "Downward"}
  Proj. Target:    {sm['proj_pct']:.1f}% (${sm['proj_target']:.2f})

Cycle Levels:
  Cycle High:  ${sm['cycle_high']:.2f}
  Cycle Mid:   ${sm['cycle_mid']:.2f}
  Cycle Low:   ${sm['cycle_low']:.2f}

Next Expected Phase: {sm['next_phase']}

Recent Phase Transitions (last 6):
"""
    transitions = [(r, bars[i]) for i, r in enumerate(results) if r["phase_changed"]][-6:]
    for r, b in transitions:
        brief += f"  {ts(b['time'])}  → {r['phase']}  (pos={r['price_pos']*100:.0f}%  str={r['cycle_strength']})\n"

    sig = {
        "indicator":  "MCPE",
        "signal":     bias,
        "reasons":    reasons,
        "key_values": {
            "Phase":         phase,
            "Duration":      f"{cur['phase_duration']} bars",
            "Position":      f"{pos}%",
            "Strength":      f"{sm['cycle_strength']}/100",
            "Volatility":    sm["volatility"],
            "Volume":        sm["vol_status"],
            "Projection":    f"{'↑' if cur['proj_up'] else '↓'} {sm['proj_pct']:.1f}%",
            "Target":        f"${sm['proj_target']:.2f}",
            "Next Phase":    sm["next_phase"],
        },
        "chart_data": cd,
    }
    return brief, sig
