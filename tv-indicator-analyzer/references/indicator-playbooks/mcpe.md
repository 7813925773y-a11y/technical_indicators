# Playbook — MCPE (Market Cycle Projection Engine)

## Methodology Summary

MCPE classifies market structure into one of four Wyckoff-inspired phases using three factors computed on every bar close:
- **LR slope** (linear regression slope normalized by ATR) → directional momentum
- **ATR ratio** (current ATR / slow ATR) → expanding vs. contracting volatility
- **Price position** (close vs. cycle high/low range, 0–100%) → where in the range

Phase classification:
- **MARKUP** (green): slope > 0.1 AND atr_ratio > 1.1 — trending up with expanding volatility
- **MARKDOWN** (red): slope < -0.1 AND atr_ratio > 1.1 — trending down with expanding volatility
- **ACCUMULATION** (cyan): slope flat AND price_pos < 0.4 — consolidation in the lower range
- **DISTRIBUTION** (orange): slope flat AND price_pos ≥ 0.4 — consolidation in the upper range

---

## Data Extraction

### Agent prompt (exact tools to call)

```
1. data_get_pine_tables(study_filter="MCPE")
   → Dashboard rows: Cycle Phase, Cycle Position %, Volatility Status, Volume

2. data_get_pine_labels(study_filter="MCPE")
   → Phase transition labels, projection arrow label (direction + target price)

3. data_get_pine_lines(study_filter="MCPE")
   → Key level lines: Cycle High, Cycle Mid, Cycle Low

4. capture_screenshot(region="chart")
   → Save screenshot path
```

---

## Brief Template

```markdown
## MCPE Brief
Symbol: <TICKER> | Timeframe: <TF> | Date: <DATE> | Price: $<PRICE>

Dashboard:
- Cycle Phase: <ACCUMULATION / MARKUP / DISTRIBUTION / MARKDOWN>
- Cycle Position: <XX>% (<interpretation>)
- Volatility Status: <NORMAL / HIGH>
- Volume: <NORMAL / ELEVATED / LOW>

Key Levels:
- Cycle High: $<value>
- Cycle Mid:  $<value>
- Cycle Low:  $<value>

Recent Labels: <list phase transition labels and projection labels found>

Projection: <UP / DOWN / none> | Target: $<value> | Bars forward: <N>
Projection Basis: <Cycle Average / Last Cycle / ATR Multiple>

Screenshot: <path>
```

---

## Interpretation Guide (for CrewAI analyst)

### Cycle Position Zones
- **0–30%**: Lower range — classic accumulation zone. Institutions build longs quietly. Best risk/reward for long entries.
- **30–60%**: Middle range — continuation zone. Markup/markdown likely to extend.
- **60–70%**: Upper middle — late markup or early distribution. Reduce size, tighten stops.
- **70–100%**: Upper range — distribution zone. Smart money offloading. Avoid new longs.

### Phase Transitions (strongest signals)
- **Accumulation → Markup**: Slope breaking above 0.1 threshold while coming from low price position. BUY signal.
- **Distribution → Markdown**: Slope breaking below -0.1 from upper range. SELL signal.
- **Markup → Distribution**: Slope flattening at high cycle position. Take profits, don't add.
- **Markdown → Accumulation**: Slope flattening at low position. Watch for next Markup trigger.

### Projection
- Projection amplitude = average of last two swing ranges. Statistical expectation, not a guarantee.
- Valid only when a phase transition has just occurred (fresh projection arrow).
- If projection arrow is old (many bars since last transition), weight it less.

### Volatility State
- HIGH volatility (ATR > 1.3× SMA) during MARKUP/MARKDOWN = confirmed trending phase, signals are higher conviction.
- HIGH volatility during ACCUMULATION/DISTRIBUTION = false breakout risk or transition imminent.

### When MCPE signals a trade
- Accumulation with HIGH volume + transition label → long entry zone
- MARKUP continuation at 30–60% position → long add-on
- Distribution at >70% position + declining volume → short or exit longs
- MARKDOWN continuation at <70% position → short

### When MCPE does NOT signal a trade
- Phase stuck in Accumulation/Distribution for many bars with no projection arrow → wait
- Phase oscillating rapidly between Markup/Distribution → noisy chart, reduce conviction
- Cycle High/Mid/Low levels very close together (narrow cycle range) → low signal reliability
