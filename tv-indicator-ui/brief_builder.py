"""
Extract structured data from each TradingView indicator.
Each extractor applies Python rules to compute a deterministic signal
(BULLISH / BEARISH / NEUTRAL / CAUTION) from the MCP data values.
Returns (brief_text, screenshot_b64, signal_dict) per indicator.
"""
import base64
import logging
import fibstruct as _fibstruct_mod
import mcpe as _mcpe_mod
import harmonic as _harmonic_mod
import ichimoku as _ichimoku_mod

logger = logging.getLogger(__name__)


# ── generic helpers ───────────────────────────────────────────────────────────

def _first_study(data: dict) -> dict:
    studies = data.get("studies") or []
    return studies[0] if studies else {}


def _table_rows(data: dict) -> list:
    study = _first_study(data)
    tables = study.get("tables") or []
    return tables[0].get("rows") or [] if tables else []


def _parse_dashboard(rows: list) -> dict:
    d = {}
    for row in rows:
        parts = [p.strip() for p in str(row).split("|")]
        if len(parts) >= 2:
            d[parts[0]] = parts[1]
    return d


def _labels(data: dict) -> list:
    return _first_study(data).get("labels") or []


def _levels(data: dict) -> list:
    return _first_study(data).get("horizontal_levels") or []


def _zones(data: dict) -> list:
    return _first_study(data).get("zones") or []


def _encode_b64(path: str | None) -> str | None:
    if not path:
        return None
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception as e:
        logger.debug(f"Screenshot encode failed ({path}): {e}")
        return None


def _screenshot_path(data: dict) -> str | None:
    return data.get("file_path") if data.get("success") else None


def _fmt_labels(labels: list, n: int = 15) -> str:
    if not labels:
        return "  (none)"
    return "\n".join(
        f"  - {l.get('text','?')} @ ${l.get('price','?')}"
        for l in labels[-n:]
    )


def _parse_pct(s: str) -> float | None:
    """Parse '67%' → 0.67 or '0.67' → 0.67. Returns None if unparseable."""
    if not s or s in ("Unknown", "—", ""):
        return None
    try:
        val = float(str(s).strip().rstrip('%').strip())
        return val / 100 if val > 1.5 else val
    except Exception:
        return None


def _signal(name: str, bias: str, reasons: list, key_values: dict) -> dict:
    return {"indicator": name, "signal": bias, "reasons": reasons, "key_values": key_values}


# ── public entry point ────────────────────────────────────────────────────────

async def build_brief(
    tv,
    key: str,
    shorttitle: str,
    full_title: str,
    ticker: str,
    timeframe: str,
    price: str,
    date: str,
) -> tuple:
    """Return (brief_text, screenshot_b64, signal_dict)."""
    add_result = await tv.call("chart_manage_indicator", action="add", indicator=full_title)
    if not add_result.get("success"):
        logger.debug(f"chart_manage_indicator for {shorttitle}: {add_result}")

    screenshot_data = await tv.call(
        "capture_screenshot", region="chart",
        filename=f"{ticker}_{timeframe}_{key}"
    )
    screenshot_b64 = _encode_b64(_screenshot_path(screenshot_data))

    header = (
        f"## {shorttitle} Brief\n"
        f"Symbol: {ticker} | Timeframe: {timeframe} | Date: {date} | Price: ${price}\n\n"
    )

    try:
        dispatch = {
            "mcpe":      _mcpe,
            "harmonic":  _harmonic,
            "ichimoku":  _ichimoku,
            "fibstruct": _fibstruct,
            "demark":    _demark,
        }
        body, sig = await dispatch[key](tv)
    except Exception as e:
        logger.error(f"brief_builder error for {key}: {e}")
        body = f"[Data extraction failed: {e}]"
        sig  = _signal(key, "UNKNOWN", [str(e)], {})

    return header + body, screenshot_b64, sig


# ── signal computation — deterministic Python rules on MCP values ─────────────





def _fibstruct_signal(bias_str: str, labels: list, confluence_str: str, zones: list) -> dict:
    bias_up = (bias_str or "").upper()
    reasons = []

    # CHoCH = primary reversal signal — takes priority over dashboard bias
    choch_bull = [l for l in labels if "choch" in l.get("text", "").lower()
                  and any(w in l.get("text", "").upper() for w in ["UP", "BULL", "↑", "BUY"])]
    choch_bear = [l for l in labels if "choch" in l.get("text", "").lower()
                  and any(w in l.get("text", "").upper() for w in ["DOWN", "BEAR", "↓", "SELL"])]
    bos = [l for l in labels if "bos" in l.get("text", "").lower()]

    if choch_bull:
        bias = "BULLISH"
        reasons.append("Bullish CHoCH detected — primary reversal signal")
    elif choch_bear:
        bias = "BEARISH"
        reasons.append("Bearish CHoCH detected — primary reversal signal")
    elif "BULL" in bias_up or "LONG" in bias_up or "UP" in bias_up:
        bias = "BULLISH"
        reasons.append(f"Structure bias: {bias_str}")
    elif "BEAR" in bias_up or "SHORT" in bias_up or "DOWN" in bias_up:
        bias = "BEARISH"
        reasons.append(f"Structure bias: {bias_str}")
    else:
        bias = "NEUTRAL"
        reasons.append(f"Bias: {bias_str or 'Unknown'}")

    if bos:
        reasons.append(f"{len(bos)} BOS label(s) — trend continuation signals")

    conf = _parse_pct(confluence_str)
    if conf is not None:
        pct   = conf if conf <= 1 else conf / 100
        label = "Strong" if pct >= 0.60 else "Moderate" if pct >= 0.30 else "Weak"
        reasons.append(f"Fibonacci confluence: {label} ({confluence_str})")

    if zones:
        z = zones[0]
        reasons.append(f"Golden zone: ${z.get('low','?')} – ${z.get('high','?')}")

    return _signal("FibStruct", bias, reasons, {
        "Bias":         bias_str or "—",
        "Confluence":   confluence_str or "—",
        "CHoCH (bull)": str(len(choch_bull)),
        "CHoCH (bear)": str(len(choch_bear)),
        "BOS":          str(len(bos)),
    })


def _demark_compute(closes: list) -> list:
    """Exact Pine Script translation: buySetup/sellSetup counts from close prices."""
    n          = len(closes)
    buy_setup  = [0] * n
    sell_setup = [0] * n
    for i in range(4, n):
        pb = buy_setup[i - 1]
        ps = sell_setup[i - 1]
        buy_setup[i]  = (1 if pb == 13 else pb + 1) if closes[i] < closes[i - 4] else 0
        sell_setup[i] = (1 if ps == 13 else ps + 1) if closes[i] > closes[i - 4] else 0
    return buy_setup, sell_setup


def _demark_signal_from_ohlcv(bars: list) -> dict:
    closes     = [b["close"] for b in bars]
    buy, sell  = _demark_compute(closes)
    n          = len(bars)

    # Walk backwards to find most recent 9/13 exhaustion signals
    last_buy_ex = last_sell_ex = None
    for i in range(n - 1, -1, -1):
        if last_buy_ex is None and buy[i] in (9, 13):
            last_buy_ex  = {"count": buy[i],  "close": closes[i], "bars_ago": n - 1 - i}
        if last_sell_ex is None and sell[i] in (9, 13):
            last_sell_ex = {"count": sell[i], "close": closes[i], "bars_ago": n - 1 - i}
        if last_buy_ex and last_sell_ex:
            break

    # Current bar active count
    cur_buy  = buy[-1]
    cur_sell = sell[-1]

    def recency(ex):
        if ex is None:
            return 9999
        return ex["bars_ago"]

    def rlabel(ex):
        if ex is None:
            return "none"
        a = ex["bars_ago"]
        if a == 0:   return "this bar"
        if a <= 5:   return f"active ({a}b ago)"
        if a <= 20:  return f"fading ({a}b ago)"
        return f"stale ({a}b ago)"

    reasons = []

    if last_buy_ex or last_sell_ex:
        if recency(last_buy_ex) <= recency(last_sell_ex):
            bias = "BULLISH"
            ex   = last_buy_ex
            reasons.append(f"Downward exhaustion: Long {ex['count']} @ ${ex['close']:.2f} — {rlabel(ex)}")
            if last_sell_ex:
                reasons.append(f"Earlier sell signal: Short {last_sell_ex['count']} @ ${last_sell_ex['close']:.2f} ({rlabel(last_sell_ex)})")
        else:
            bias = "BEARISH"
            ex   = last_sell_ex
            reasons.append(f"Upward exhaustion: Short {ex['count']} @ ${ex['close']:.2f} — {rlabel(ex)}")
            if last_buy_ex:
                reasons.append(f"Earlier buy signal: Long {last_buy_ex['count']} @ ${last_buy_ex['close']:.2f} ({rlabel(last_buy_ex)})")
    else:
        bias = "NEUTRAL"
        reasons.append("No TD 9/13 exhaustion signals in visible range")

    # Warn if approaching exhaustion
    if cur_buy >= 7:
        reasons.append(f"Active DOWN count: {cur_buy}/13 — {'exhaustion NOW' if cur_buy in (9,13) else 'approaching exhaustion' if cur_buy >= 9 else f'{13 - cur_buy} bars to Long 9'}")
    elif cur_sell >= 7:
        reasons.append(f"Active UP count: {cur_sell}/13 — {'exhaustion NOW' if cur_sell in (9,13) else 'approaching exhaustion' if cur_sell >= 9 else f'{13 - cur_sell} bars to Short 9'}")

    b_str = f"Long {last_buy_ex['count']} — {rlabel(last_buy_ex)} @ ${last_buy_ex['close']:.2f}" if last_buy_ex else "none"
    s_str = f"Short {last_sell_ex['count']} — {rlabel(last_sell_ex)} @ ${last_sell_ex['close']:.2f}" if last_sell_ex else "none"

    return _signal("DeMark", bias, reasons, {
        "Buy count (now)":   str(cur_buy),
        "Sell count (now)":  str(cur_sell),
        "Last Long signal":  b_str,
        "Last Short signal": s_str,
    })


# ── per-indicator data extractors ─────────────────────────────────────────────

async def _mcpe(tv) -> tuple[str, dict]:
    # MCPE computed directly from OHLCV — exact Python translation of Pine Script v2.0.
    raw  = await tv.call("data_get_ohlcv", count=200)
    bars = raw.get("bars") or []
    if not bars:
        return "[OHLCV unavailable — cannot compute MCPE]", _signal("MCPE", "UNKNOWN", ["OHLCV call failed"], {})
    body, sig = _mcpe_mod.build_brief_from_ohlcv(bars)
    return body, sig


async def _harmonic(tv) -> tuple[str, dict]:
    # HAV computed directly from OHLCV — exact Python translation of Pine Script v1.1.
    # Length is inferred from bar spacing (5/8/13/21 by timeframe).
    raw  = await tv.call("data_get_ohlcv", count=300)
    bars = raw.get("bars") or []
    if not bars:
        return "[OHLCV unavailable — cannot compute HAV]", _signal("HAV", "UNKNOWN", ["OHLCV call failed"], {})
    body, sig = _harmonic_mod.build_brief_from_ohlcv(bars)
    return body, sig


async def _ichimoku(tv) -> tuple[str, dict]:
    # Ichimoku computed directly from OHLCV — exact Python translation of LuxAlgo Pine Script.
    raw  = await tv.call("data_get_ohlcv", count=300)
    bars = raw.get("bars") or []
    if not bars:
        return "[OHLCV unavailable — cannot compute Ichimoku]", _signal("Ichimoku", "UNKNOWN", ["OHLCV call failed"], {})
    body, sig = _ichimoku_mod.build_brief_from_ohlcv(bars)
    return body, sig


async def _fibstruct(tv) -> tuple[str, dict]:
    # FibStruct is computed directly from OHLCV bars — no indicator on chart needed.
    # Exact Python translation of the Pine Script v1.5.2 state machine.
    raw  = await tv.call("data_get_ohlcv", count=200)
    bars = raw.get("bars") or []
    if not bars:
        return "[OHLCV unavailable — cannot compute FibStruct]", _signal("FibStruct", "UNKNOWN", ["OHLCV call failed"], {})

    body, sig = _fibstruct_mod.build_brief_from_ohlcv(bars)
    return body, sig


_DEMARK_BUY_COLORS = {
    1: '#11e7f2', 2: '#11d9f2', 3: '#11cbf2', 4: '#11aff2', 5: '#1193f2',
    6: '#1176f2', 7: '#105df4', 8: '#1051f5', 9: '#0f44f5', 10: '#0c3de0',
    11: '#0935ca', 12: '#062eb4', 13: '#02269e',
}
_DEMARK_SELL_COLORS = {
    1: '#eef211', 2: '#efdc11', 3: '#f0c511', 4: '#f1af11', 5: '#f29811',
    6: '#f28811', 7: '#f27811', 8: '#f26811', 9: '#f25811', 10: '#ea420d',
    11: '#e12c09', 12: '#d81605', 13: '#cf0000',
}


async def _demark(tv) -> tuple[str, dict]:
    # DeMark is computed directly from OHLCV close prices — no indicator on chart needed.
    # Exact Python translation of the Pine Script buySetup/sellSetup logic.
    raw  = await tv.call("data_get_ohlcv", count=100)
    bars = raw.get("bars") or []
    if not bars:
        return "[OHLCV unavailable — cannot compute DeMark]", _signal("DeMark", "UNKNOWN", ["OHLCV call failed"], {})

    closes     = [b["close"] for b in bars]
    buy, sell  = _demark_compute(closes)
    n          = len(bars)

    import datetime
    def ts(unix): return datetime.datetime.fromtimestamp(unix).strftime("%Y-%m-%d")

    # ── chart data (last 80 bars, per-candle DeMark colors matching Pine Script) ──
    chart_data = []
    for i in range(max(0, n - 80), n):
        b, s = buy[i], sell[i]
        bar  = bars[i]
        if b > 0:
            c = _DEMARK_BUY_COLORS.get(b, '#0f44f5')
        elif s > 0:
            c = _DEMARK_SELL_COLORS.get(s, '#f29811')
        else:
            c = '#26a69a' if bar['close'] >= bar['open'] else '#ef5350'

        lbl = None
        if b in (9, 13):    lbl = f"Long {b}"
        elif b >= 7:         lbl = str(b)
        elif s in (9, 13):  lbl = f"Short {s}"
        elif s >= 7:         lbl = str(s)

        chart_data.append({
            "time":        bar["time"],
            "open":        bar["open"],
            "high":        bar["high"],
            "low":         bar["low"],
            "close":       bar["close"],
            "color":       c,
            "wickColor":   c,
            "borderColor": c,
            "buy":         b,
            "sell":        s,
            "label":       lbl,
        })

    # ── brief text ────────────────────────────────────────────────────────────
    labelled_rows = []
    for i in range(n):
        b, s = buy[i], sell[i]
        if b >= 7:
            lbl = f"Long {b}" if b in (9, 13) else str(b)
            labelled_rows.append(f"  {ts(bars[i]['time'])}  close={closes[i]:>8.2f}  buySetup={b:>2}  → {lbl}")
        elif s >= 7:
            lbl = f"Short {s}" if s in (9, 13) else str(s)
            labelled_rows.append(f"  {ts(bars[i]['time'])}  close={closes[i]:>8.2f}  sellSetup={s:>2}  → {lbl}")

    cur_bar  = bars[-1]
    cur_b, cur_s = buy[-1], sell[-1]

    body = f"""Source: OHLCV close prices (exact Pine Script translation)
Current bar: {ts(cur_bar['time'])}  close={cur_bar['close']:.2f}
  buySetup  = {cur_b}  (consecutive closes < close[4] — downtrend exhausted at 9/13 → BUY)
  sellSetup = {cur_s}  (consecutive closes > close[4] — uptrend exhausted at 9/13 → SELL)

Recent signal labels (count ≥ 7):
{chr(10).join(labelled_rows[-15:]) if labelled_rows else "  (none in range)"}

Colors: blue gradient = downtrend (buy setup) · orange/red gradient = uptrend (sell setup)
Markers: ▲ Long 9/13 = buy exhaustion · ▼ Short 9/13 = sell exhaustion
"""

    sig = _demark_signal_from_ohlcv(bars)
    sig["chart_data"] = chart_data
    return body, sig
