# Playbook — FibStruct (Fibonacci Structure Engine)

## Methodology Summary

FibStruct chains five components into a dependency pipeline:

1. **ATR-filtered pivot detection** — `ta.pivothigh`/`ta.pivotlow` with a minimum size filter (swing must exceed ATR × multiplier). Only swings of meaningful size drive structure.

2. **BOS/CHoCH detection** — tracks `structureBias` (+1 bullish, -1 bearish):
   - **BOS** (Break of Structure): continuation — close breaks a swing in the direction of existing bias
   - **CHoCH** (Change of Character): reversal — close breaks a swing against existing bias

3. **Fibonacci anchoring** — on each structure break, Fibonacci levels are drawn from the structure-defined swing. Live edge trails price, locks on next confirmed pivot.

4. **Confluence scoring** (0–100) — proximity to Fibonacci levels within ATR tolerance:
   - 0.618 → weight 2.5 (golden ratio, highest)
   - 0.500 → weight 2.0
   - 0.382 → weight 1.5
   - 0.786 → weight 1.5
   - 0.236 → weight 1.0
   - Swing levels → +1.0 each
   - **Liquidity sweeps** → boost weight (+)

5. **Premium/Discount zones** — relative to 0.500 level:
   - **Premium** (close > Fib 0.500): above equilibrium → expensive
   - **Discount** (close ≤ Fib 0.500): below equilibrium → cheap

6. **Liquidity engine** — Equal Highs (EQH) / Equal Lows (EQL) detection. Sweep = wick through level then close back inside. Sweeps boost confluence score and can trigger signals.

---

## Data Extraction

### Agent prompt (exact tools to call)

```
1. data_get_pine_tables(study_filter="FibStruct")
   → Dashboard rows: Bias, Fib Dir, Confluence, Zone, Near Fib, ATR(14), Liquidity

2. data_get_pine_labels(study_filter="FibStruct", max_labels=100)
   → Structure labels: BOS, CHoCH, HH, HL, LH, LL
   → Signal labels: BUY, SELL (if enabled)
   → Sweep labels: SWEEP HIGH, SWEEP LOW (orange ✗)

3. data_get_pine_lines(study_filter="FibStruct")
   → Fibonacci levels: 0.236, 0.382, 0.500, 0.618, 0.786, -0.500, Target -0.618
   → BOS/CHoCH structure lines

4. data_get_pine_boxes(study_filter="FibStruct")
   → Golden Zone box (0.500–0.786)
   → Target Zone box (-0.500 to -0.618)

5. capture_screenshot(region="chart")
   → Save screenshot path
```

---

## Brief Template

```markdown
## FibStruct Brief
Symbol: <TICKER> | Timeframe: <TF> | Date: <DATE> | Price: $<PRICE>

Dashboard:
- Structure Bias: <BULLISH (+1) / BEARISH (-1) / NEUTRAL (0)>
- Fib Direction: <Long ↑ / Short ↓>
- Confluence Score: <XX>/100 (<Strong ≥60 / Moderate ≥30 / Weak / None>)
- Current Zone: <PREMIUM / DISCOUNT>
- Near Fib: <level> at $<value> (<X.X> ATR away)
- ATR(14): $<value>
- Liquidity: <EQH ↑ / EQL ↓ / EQH+EQL / —>

Recent Structure (latest 5 labels):
<list each: type (BOS/CHoCH/HH/HL/LH/LL), direction, price, approximate bars ago>

Fibonacci Levels (current anchor):
- Swing High: $<value>
- Swing Low: $<value>
- 0.236: $<value>
- 0.382: $<value>
- 0.500: $<value> (Equilibrium)
- 0.618: $<value> (Golden Ratio)
- 0.786: $<value>
- -0.500: $<value>
- Target -0.618: $<value>

Zones:
- Golden Zone (0.500–0.786): $<low> – $<high>
- Target Zone (-0.500 to -0.618): $<low> – $<high>

Recent Signals/Sweeps:
<list any BUY/SELL/SWEEP labels from labels, with price and bars ago>

Screenshot: <path>
```

---

## Interpretation Guide (for CrewAI analyst)

### Structure Bias — The Primary Filter
- **BULLISH (+1)**: CHoCH broke a swing high from a bearish context → trend reversed up. Trade longs.
- **BEARISH (-1)**: CHoCH broke a swing low from a bullish context → trend reversed down. Trade shorts.
- **NEUTRAL (0)**: No confirmed structure break yet. Wait.

CHoCH is the strongest reversal signal in FibStruct — it requires no additional confluence and fires a signal immediately.

### BOS vs CHoCH
- **BOS** = trend continuation (price breaks a swing in the direction of existing bias). Confirms the trend is intact.
- **CHoCH** = trend reversal. The most important label. Multiple BOS labels followed by a CHoCH = exhausted trend reversing.

### HH/HL/LH/LL Pattern Reading
- HH + HL sequence → bullish structure (higher highs, higher lows). Long bias.
- LH + LL sequence → bearish structure. Short bias.
- HH → LH (failed to make new HH) → early warning of momentum loss.
- First HL after a series of LL → potential trend change brewing.

### Confluence Score Interpretation
- **Strong (≥ 60)**: Price is at one or more high-weight Fibonacci levels. Entry signal with full size.
- **Moderate (30–59)**: Price near a level, but not optimal. Reduced size or wait for tighter approach.
- **Weak (> 0)**: Minimal Fibonacci confluence. Only trade with strong signal from other indicator.
- **None (0)**: Price is in no-man's land. Skip.

### Premium / Discount and the Golden Zone
- **In Discount** (< 0.500, especially 0.500–0.786 zone): Look for bullish entries. This is the "buy low" zone.
- **In Premium** (> 0.500): Look for bearish entries or exits of longs. The "sell high" zone.
- **Golden Zone** (0.500–0.786): Highest-probability retracement area. Most retests find support/resistance here.
- Entry rule: bullish engulfing in Discount + Confluence Strong = full-size long. Bearish engulfing in Premium = short.

### Target Zone
- **Target Zone** (-0.500 to -0.618): Fibonacci extension target for the next impulse leg. This is where price typically reaches after a confirmed retracement entry.

### Liquidity Engine
- **EQH/EQL active**: Resting stops above (EQH) or below (EQL) the market. Smart money will hunt these.
- **Sweep occurred**: Price pierced the level with a wick, closed back inside → stop hunt complete. High-probability reversal setup.
- **Sweep in Golden Zone**: Sweep + Fib confluence = highest conviction signal. Strongest entry condition.

### When FibStruct signals a trade
- CHoCH in direction of trade → immediate reversal signal
- Price retracing into Golden Zone (0.500–0.786) with Strong confluence (≥ 60) + Discount zone → long entry
- Liquidity sweep of EQL followed by close above → long entry (bears flushed)
- BOS confirming direction + price pulling back to 0.618 level → continuation entry

### When FibStruct does NOT signal a trade
- Neutral bias (0) → no confirmed structure
- Price in no-man's land (zero confluence) → not near any Fibonacci level
- Recent CHoCH invalidated by another CHoCH in opposite direction → whipsaw, wait
- Fib anchor is stale (many bars since last structure break, levels not relevant) → skip
