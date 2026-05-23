# Playbook — TD Sequential (Tom DeMark Heatmap)

## Methodology Summary

TD Sequential counts bars in a setup sequence from 1 to 13. A new bullish count starts when a close is **below** the close 4 bars earlier (`close < close[4]`) for the 1st of 9 consecutive bars. A new bearish count starts when a close is **above** close[4].

**Key exhaustion numbers:**
- **TD 9** (Setup completion): Price has made 9 consecutive closes in one direction relative to close[4]. Signals setup exhaustion — a potential pause or reversal.
- **TD 13** (Countdown completion): After a setup of 9 completes, a further 13-bar countdown in the same direction confirms deep exhaustion. Strongest reversal signal.

The indicator colors candles by count (bright yellow→dark red for bullish; bright blue→dark blue for bearish) and displays labels at counts 7–13 with "Long" or "Short" labels at 9 and 13.

**DeMark's use case**: short-term price reversals. Signals across all timeframes but most reliable as a timing/exhaustion overlay rather than a standalone trend indicator.

---

## Data Extraction

### Agent prompt (exact tools to call)

```
1. data_get_pine_labels(study_filter="TD heatmap", max_labels=100)
   → Count labels (7, 8, 9, 10, 11, 12, 13) with "Long" or "Short" at 9/13
   → Parse: count number, direction (Long/Short), approximate price level, bars ago

2. capture_screenshot(region="chart")
   → Save screenshot path — candle coloring shows the full count context visually
```

---

## Brief Template

```markdown
## TD Sequential Brief
Symbol: <TICKER> | Timeframe: <TF> | Date: <DATE> | Price: $<PRICE>

Current Count:
- Direction: <Bullish (bearish setup = longs will come) / Bearish (bullish setup)>
- Count: <1–13 or "between setups">
- Bars since last 9: <N bars ago or "N/A">
- Bars since last 13: <N bars ago or "N/A">

Recent Signals (from labels, newest first):
<For each label found:>
- <Long / Short> <9 or 13> at ~$<price> (<N> bars ago)

Candle Coloring Context: <describe dominant color from screenshot — yellow/red = bullish count, blue/dark blue = bearish count>

Screenshot: <path>
```

---

## Interpretation Guide (for CrewAI analyst)

### TD 9 — Setup Exhaustion
- **Bearish TD 9** (labeled "Short"): 9 consecutive closes above close[4]. The *upward* move has exhausted its setup. Expect at minimum a pause, potentially a reversal. Short signal.
- **Bullish TD 9** (labeled "Long"): 9 consecutive closes below close[4]. The *downward* move is exhausted. Long signal.
- Strongest when: (1) count 9 occurs at a Fibonacci level (see FibStruct), (2) in a harmonic PRZ, (3) near an Ichimoku kumo edge.

### TD 13 — Countdown Exhaustion
- **Bearish TD 13**: Deepest exhaustion signal. Follows a TD 9 with 13 more qualifying bars. Marks the end of the intermediate-term advance.
- **Bullish TD 13**: End of intermediate-term decline.
- TD 13 is the **highest conviction DeMark signal**. Weight it significantly in synthesis.

### Perfected Setup
- A TD 9 is "perfected" if bar 8 or 9 has a high (for bearish) greater than highs of bars 6 and 7. This perfected version is a stronger reversal signal.

### Count Direction Confusion
Note: the count direction describes which price action is being counted, not the trade direction:
- A **bearish setup** (close > close[4] for 9 bars) counts the **upward** exhaustion → signals a potential **short**.
- A **bullish setup** (close < close[4] for 9 bars) counts the **downward** exhaustion → signals a potential **long**.

If the brief labels show "Long 9" or "Long 13" = a BUY signal. "Short 9" or "Short 13" = a SELL signal.

### Recency Matters
- A TD 9 or 13 that printed **1–5 bars ago**: Active signal. High relevance.
- **6–20 bars ago**: Signal is fading. Market may have already reacted. Lower weight.
- **> 20 bars ago**: Stale. Market moved on. Reference only as context, don't use as entry trigger.

### Combining with Other Indicators
DeMark provides **timing**, other indicators provide **direction and levels**. Strongest setups occur when:
- FibStruct is at Golden Zone (price level) + DeMark shows TD 9 exhaustion (timing)
- MCPE transitions to Accumulation + DeMark shows TD 9 Long (both indicate selling exhaustion)
- Ichimoku Kijun retest (price level) + DeMark TD 9 Long (timing confirmation)
- Harmonic PRZ reached (price zone) + DeMark TD 9 (timing confirms the reversal zone)

### When DeMark signals a trade
- TD 9 **or** TD 13 labeled "Long" or "Short" within the last 5 bars → active exhaustion signal
- TD 13 signal + another indicator confirming the level → very high conviction

### When DeMark does NOT signal a trade
- Count is mid-sequence (e.g., at count 4): in progress, wait for 9 to complete
- Most recent 9 or 13 signal is > 20 bars old: stale, market absorbed it
- Count reset mid-sequence (common in choppy conditions): DeMark is not reliable on this TF currently
- Count direction contradicts trade direction AND no 13 yet: don't fight the count
