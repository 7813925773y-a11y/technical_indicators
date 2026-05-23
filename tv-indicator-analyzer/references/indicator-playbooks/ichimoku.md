# Playbook — Ichimoku Theories [LuxAlgo]

## Methodology Summary

This indicator combines four Goichi Hosoda concepts:

**Ichimoku Kinkō Hyō** — five lines defining equilibrium at short/medium/long horizons:
- **Tenkan Sen** (9-period midpoint): short-term momentum
- **Kijun Sen** (26-period midpoint): medium-term trend anchor
- **Senkou Span A** (midpoint of TK, plotted 26 bars forward): fast kumo edge
- **Senkou Span B** (52-period midpoint, plotted 26 bars forward): slow kumo edge
- **Chikou Span** (close plotted 26 bars back): confirmation of current price vs. past structure
- **Kumo** (cloud between Span A and B): primary support/resistance zone

**Time Theory** — Kihon Suchi sequence (9, 17, 26, 33, 42, 51, 65, 76, 129, 172, 200, 257). Markets turn at intervals matching these numbers. **Kihon Suchi** forecasts from base. **Taito Suchi** repeats same-size cycles.

**Wave Theory** — I (single leg), V (two legs), N (three legs, the most common), P (contracting), Y (expanding), W (double top/bottom).

**Price Theory** — N-wave price targets: V (A+(C-B)), E (C+(C-B)), N (C+(A-B)), NT (A+1.618×(A-B)), 2E, 3E.

---

## Data Extraction

### Agent prompt (exact tools to call)

```
1. data_get_study_values(study_filter="LuxAlgo - Ichimoku Theories")
   → Returns current values for Tenkan, Kijun, Senkou A, Senkou B, Chikou

2. data_get_pine_labels(study_filter="LuxAlgo - Ichimoku Theories", max_labels=100)
   → Wave theory labels: I/V/N/P/Y/W wave markers with price/bar info
   → Time cycle labels: cycle size annotations

3. data_get_pine_lines(study_filter="LuxAlgo - Ichimoku Theories")
   → Time cycle forecast lines (vertical dashed lines = projected turning points)
   → Price theory target lines (V/E/N/NT/2E/3E horizontal levels)

4. capture_screenshot(region="chart")
   → Save screenshot path
```

---

## Brief Template

```markdown
## Ichimoku Theories Brief
Symbol: <TICKER> | Timeframe: <TF> | Date: <DATE> | Price: $<PRICE>

Ichimoku Lines:
- Tenkan Sen: $<value>
- Kijun Sen:  $<value>
- Senkou Span A: $<value>
- Senkou Span B: $<value>
- Chikou Span: $<value>

Kumo Analysis:
- Price vs Kumo: <ABOVE (bullish) / INSIDE (neutral) / BELOW (bearish)>
- Kumo Color: <BULLISH (A > B) / BEARISH (A < B)>
- Kumo Twist Ahead: <YES at bar +N / NO>
- Chikou vs Past Price: <ABOVE (confirms bullish) / BELOW (confirms bearish) / IN CLOUD>

TK Cross:
- Status: <BULLISH CROSS (TK > KJ) / BEARISH CROSS (TK < KJ) / NO RECENT CROSS>
- TK above Kumo: <YES / NO>

Time Theory:
- Detected cycles: <list cycle sizes in bars, e.g. "17-bar, 26-bar">
- Forecast mode: <Kihon Suchi / Taito Suchi / none>
- Next projected turning point: <bar offset or date>

Wave Theory:
- Active waves visible: <list types: I/V/N/P/Y/W>
- Current dominant wave: <type + direction>
- Wave legs completed: <N/3 legs for N-wave, etc.>

Price Targets (N-wave):
- V target: $<value> (or "none")
- E target: $<value> (or "none")
- N target: $<value> (or "none")
- NT target: $<value> (or "none")
- Extended (2E/3E): $<value> (or "none")

Screenshot: <path>
```

---

## Interpretation Guide (for CrewAI analyst)

### Kumo (Cloud) — Primary Filter
- **Price above bullish kumo**: Strong uptrend. Long bias. Support zone = kumo top.
- **Price above bearish kumo**: Trend turning. Watch for kumo twist (A/B flip) as confirmation.
- **Price inside kumo**: Neutral/consolidation. Reduce directional conviction.
- **Price below kumo**: Downtrend. Short bias. Resistance = kumo bottom.
- **Kumo twist ahead** (Span A crosses Span B in the future 26 bars): impending trend change signal. Strong when confirmed by Chikou.

### TK Cross
- **Bullish TK cross above kumo**: All three conditions aligned — highest conviction long signal.
- **Bullish TK cross inside/below kumo**: Weaker. Needs kumo confirmation before full size.
- **Bearish TK cross below kumo**: Strong short signal.
- **TK crossing back to flat**: Trend losing momentum, reduce exposure.

### Chikou Span Confirmation
- Chikou above past price AND above past kumo: Full bullish confirmation.
- Chikou below past price AND below past kumo: Full bearish confirmation.
- Chikou inside past kumo: ambiguous, reduce size.

### Time Theory — When to Expect the Turn
- A cycle of size N bars = market has shown rhythm at that interval.
- Kihon Suchi projection: next turn expected at N + one Kihon sequence number (e.g., 26 bars out).
- Taito Suchi: if current cycle matches a past cycle exactly, the next turn is at the same interval forward.
- The "next projected turning point" = when to tighten stops or expect a reversal, not a guaranteed date.

### Wave Theory — Structure and Extent
- **N wave** (most common): three-leg move (impulse → pullback → impulse). If on leg 1 or 2, the full N target ahead. If leg 3 extended, watch for exhaustion.
- **I wave**: single impulsive leg. Rare on confirmation — usually the first leg of a larger wave.
- **V wave**: sharp reversal. Two legs, faster. Often completes back near the start of the prior I wave.
- **P/Y waves**: converging or expanding structure. Breakout pending.
- **W wave**: double top/bottom. Often precedes a larger reversal.

### Price Targets
- V target: conservative, one measured move. First target.
- E target: two measured moves from B.
- N target: extension from A — most common completion for strong moves.
- NT target: 1.618 extension — for impulsive moves. High conviction required.
- Extended (2E/3E): only in extreme trending conditions.

### When Ichimoku signals a trade
- TK bullish cross + price above bullish kumo + Chikou above past price → highest conviction long
- Price retesting Kijun Sen from above in an established uptrend → pullback entry
- Kumo twist ahead + TK cross in same direction → timing confluence with Time Theory
- Wave structure showing leg 1 of N wave completing → entry before leg 3

### When Ichimoku does NOT signal a trade
- Price inside kumo → wait for resolution
- TK cross in direction opposite to kumo → conflicted, reduce size
- No visible wave structure or time cycle → insufficient data
