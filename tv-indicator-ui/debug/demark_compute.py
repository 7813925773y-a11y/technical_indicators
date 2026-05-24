"""
DeMark TD Sequential — pure Python computation from OHLCV close prices.

Pine Script logic (exact translation):
  buySetup  := close < close[4] ? (buySetup[1]  == 13 ? 1 : buySetup[1]  + 1) : 0
  sellSetup := close > close[4] ? (sellSetup[1] == 13 ? 1 : sellSetup[1] + 1) : 0

  buySetup  counts consecutive bars where close < close[4]  → downtrend → exhausted at 9/13 → BUY signal
  sellSetup counts consecutive bars where close > close[4]  → uptrend  → exhausted at 9/13 → SELL signal

Labels shown on chart: counts 7-13, with 9 and 13 labelled "Long"/"Short" explicitly.
"""

import json
import datetime
from pathlib import Path


def compute_demark(closes: list[float]) -> list[dict]:
    """
    Compute DeMark TD Sequential counts for each bar.
    Returns list of dicts: {index, close, buy_setup, sell_setup, signal, label}
    """
    n = len(closes)
    buy_setup  = [0] * n
    sell_setup = [0] * n

    for i in range(n):
        if i < 4:
            # Not enough history — counts stay 0
            buy_setup[i]  = 0
            sell_setup[i] = 0
        else:
            prev_buy  = buy_setup[i - 1]
            prev_sell = sell_setup[i - 1]

            if closes[i] < closes[i - 4]:
                buy_setup[i]  = 1 if prev_buy == 13 else prev_buy + 1
            else:
                buy_setup[i]  = 0

            if closes[i] > closes[i - 4]:
                sell_setup[i] = 1 if prev_sell == 13 else prev_sell + 1
            else:
                sell_setup[i] = 0

    results = []
    for i in range(n):
        b = buy_setup[i]
        s = sell_setup[i]

        # Label text (mirrors what the indicator draws on chart)
        if b == 9:
            label = "Long 9"
        elif b == 13:
            label = "Long 13"
        elif b >= 7:
            label = str(b)
        elif s == 9:
            label = "Short 9"
        elif s == 13:
            label = "Short 13"
        elif s >= 7:
            label = str(s)
        else:
            label = None

        # Signal classification
        if b == 9 or b == 13:
            signal = "BUY_EXHAUSTION"
        elif s == 9 or s == 13:
            signal = "SELL_EXHAUSTION"
        else:
            signal = None

        results.append({
            "index":      i,
            "close":      closes[i],
            "buy_setup":  b,
            "sell_setup": s,
            "label":      label,
            "signal":     signal,
        })

    return results


def summarise(results: list[dict], bars: list[dict]) -> dict:
    """
    Produce the signal summary that brief_builder.py needs:
      - most recent buy exhaustion signal (9 or 13)
      - most recent sell exhaustion signal (9 or 13)
      - current active count direction and value
      - bars since last signal (recency)
    """
    n = len(results)

    # Walk backwards to find most recent exhaustion signals
    last_buy_ex  = None   # most recent bar with buy_setup in {9,13}
    last_sell_ex = None   # most recent bar with sell_setup in {9,13}

    for i in range(n - 1, -1, -1):
        r = results[i]
        if last_buy_ex is None and r["buy_setup"] in (9, 13):
            last_buy_ex = {"bars_ago": n - 1 - i, "count": r["buy_setup"], "close": r["close"], **bars[i]}
        if last_sell_ex is None and r["sell_setup"] in (9, 13):
            last_sell_ex = {"bars_ago": n - 1 - i, "count": r["sell_setup"], "close": r["close"], **bars[i]}
        if last_buy_ex and last_sell_ex:
            break

    # Current bar state
    cur = results[-1]
    if cur["buy_setup"] > 0:
        current_direction = "DOWN"
        current_count     = cur["buy_setup"]
    elif cur["sell_setup"] > 0:
        current_direction = "UP"
        current_count     = cur["sell_setup"]
    else:
        current_direction = "RESET"
        current_count     = 0

    # Overall signal: most recent exhaustion signal wins
    def recency_score(ex):
        return ex["bars_ago"] if ex else 9999

    if last_buy_ex or last_sell_ex:
        if recency_score(last_buy_ex) <= recency_score(last_sell_ex):
            bias = "BULLISH"   # most recent = downtrend exhausted → buy
            primary = last_buy_ex
        else:
            bias = "BEARISH"   # most recent = uptrend exhausted → sell
            primary = last_sell_ex
    else:
        bias    = "NEUTRAL"
        primary = None

    def recency_label(bars_ago):
        if bars_ago is None:
            return "none"
        if bars_ago == 0:
            return "this bar"
        if bars_ago <= 5:
            return f"active ({bars_ago}b ago)"
        if bars_ago <= 20:
            return f"fading ({bars_ago}b ago)"
        return f"stale ({bars_ago}b ago)"

    return {
        "bias":              bias,
        "current_direction": current_direction,
        "current_count":     current_count,
        "last_buy_exhaustion": {
            "count":     last_buy_ex["count"] if last_buy_ex else None,
            "close":     last_buy_ex["close"] if last_buy_ex else None,
            "bars_ago":  last_buy_ex["bars_ago"] if last_buy_ex else None,
            "recency":   recency_label(last_buy_ex["bars_ago"] if last_buy_ex else None),
        },
        "last_sell_exhaustion": {
            "count":     last_sell_ex["count"] if last_sell_ex else None,
            "close":     last_sell_ex["close"] if last_sell_ex else None,
            "bars_ago":  last_sell_ex["bars_ago"] if last_sell_ex else None,
            "recency":   recency_label(last_sell_ex["bars_ago"] if last_sell_ex else None),
        },
        "primary_signal": primary,
    }


def build_brief_from_ohlcv(bars: list[dict]) -> tuple[str, dict]:
    """
    Main entry point: takes list of OHLCV dicts, returns (brief_text, signal_dict).
    This replaces the label-based approach entirely.
    """
    closes  = [b["close"] for b in bars]
    results = compute_demark(closes)
    summary = summarise(results, bars)

    # Recent signals table (last 30 bars that had a label)
    labelled = [(r, bars[r["index"]]) for r in results if r["label"]][-15:]

    def ts(unix):
        return datetime.datetime.fromtimestamp(unix).strftime("%Y-%m-%d")

    rows = "\n".join(
        f"  {ts(b['time'])}  close={r['close']:>8.2f}  "
        f"buy={r['buy_setup']:>2}  sell={r['sell_setup']:>2}  → {r['label']}"
        for r, b in labelled
    ) or "  (none in visible range)"

    cur = results[-1]
    cur_bar = bars[-1]

    brief = f"""TD Sequential (computed from OHLCV — no indicator required)
Current bar: {ts(cur_bar['time'])}  close={cur_bar['close']:.2f}
  buySetup={cur['buy_setup']}  (downtrend count — exhausted at 9/13 → BUY)
  sellSetup={cur['sell_setup']}  (uptrend count — exhausted at 9/13 → SELL)
  Current active sequence: {summary['current_direction']} count={summary['current_count']}

Last buy exhaustion (Long 9/13):
  count={summary['last_buy_exhaustion']['count']}  close={summary['last_buy_exhaustion']['close']}  {summary['last_buy_exhaustion']['recency']}

Last sell exhaustion (Short 9/13):
  count={summary['last_sell_exhaustion']['count']}  close={summary['last_sell_exhaustion']['close']}  {summary['last_sell_exhaustion']['recency']}

Recent label events (last 15):
{rows}
"""

    signal = {
        "indicator": "DeMark",
        "signal":    summary["bias"],
        "reasons":   _build_reasons(summary),
        "key_values": {
            "Buy count (now)":  str(cur["buy_setup"]),
            "Sell count (now)": str(cur["sell_setup"]),
            "Last Long signal":  f"{summary['last_buy_exhaustion']['recency']} @ ${summary['last_buy_exhaustion']['close']}",
            "Last Short signal": f"{summary['last_sell_exhaustion']['recency']} @ ${summary['last_sell_exhaustion']['close']}",
        },
    }

    return brief, signal


def _build_reasons(summary: dict) -> list[str]:
    reasons = []
    b = summary["last_buy_exhaustion"]
    s = summary["last_sell_exhaustion"]

    if summary["bias"] == "BULLISH":
        reasons.append(
            f"Downward exhaustion: Long {b['count']} @ ${b['close']} — {b['recency']}"
        )
        if s["count"]:
            reasons.append(
                f"Earlier upward exhaustion: Short {s['count']} @ ${s['close']} — {s['recency']}"
            )
    elif summary["bias"] == "BEARISH":
        reasons.append(
            f"Upward exhaustion: Short {s['count']} @ ${s['close']} — {s['recency']}"
        )
        if b["count"]:
            reasons.append(
                f"Earlier downward exhaustion: Long {b['count']} @ ${b['close']} — {b['recency']}"
            )
    else:
        reasons.append("No TD 9/13 exhaustion signals in visible range")

    cur_dir = summary["current_direction"]
    cur_cnt = summary["current_count"]
    if cur_cnt > 0:
        reasons.append(
            f"Active count: {cur_dir} sequence at {cur_cnt}/13"
            + (" — approaching exhaustion" if cur_cnt >= 7 else "")
        )

    return reasons


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    data_path = Path(__file__).parent / "gld_daily_ohlcv.json"
    with open(data_path) as f:
        data = json.load(f)

    bars  = data["bars"]
    brief, signal = build_brief_from_ohlcv(bars)

    print("=" * 60)
    print(f"Symbol: {data['symbol']}  Resolution: {data['resolution']}")
    print("=" * 60)
    print(brief)
    print("-" * 60)
    print("SIGNAL OUTPUT (what brief_builder returns to UI):")
    print(json.dumps(signal, indent=2))
