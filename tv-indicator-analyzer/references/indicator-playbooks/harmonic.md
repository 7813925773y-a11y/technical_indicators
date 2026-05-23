# Playbook — HAV (Harmonic Auto-Validator)

## Methodology Summary

HAV detects six Scott Carney harmonic patterns by checking strict Fibonacci ratios at each of five pivot points (X, A, B, C, D). The D point defines the Potential Reversal Zone (PRZ) — a convergence of multiple Fibonacci projections. The indicator scores each pattern 0–10 based on:
- **Ratio precision** — how close B and D are to their ideal levels
- **PRZ tightness** — how narrow the convergence zone is relative to ATR
- **Confluence count** — how many projections land inside the zone
- **AB=CD presence** — patterns missing AB=CD get a -2 penalty and a ⚠ marker

Pattern ratios:
| Pattern | B/XA | D/XA |
|---|---|---|
| Gartley | 0.618 | 0.786 |
| Bat | ~0.5 | 0.886 |
| Alt Bat | 0.382 | 1.13 |
| Butterfly | 0.786 | 1.272 |
| Crab | ~0.5 | 1.618 |
| Deep Crab | 0.886 | 1.618 |

---

## Data Extraction

### Agent prompt (exact tools to call)

```
1. data_get_pine_labels(study_filter="HAV", max_labels=50)
   → Pattern labels: type, direction (Bullish/Bearish), score, AB=CD flag
   → Also captures the X/A/B/C/D pivot prices if encoded in the label text

2. data_get_pine_boxes(study_filter="HAV")
   → PRZ zone: {high, low} for each detected pattern

3. capture_screenshot(region="chart")
   → Save screenshot path
```

---

## Brief Template

```markdown
## HAV (Harmonic Auto-Validator) Brief
Symbol: <TICKER> | Timeframe: <TF> | Date: <DATE> | Price: $<PRICE>

Confirmed Patterns: <count or "None">

<For each pattern detected, repeat this block:>
Pattern <N>:
- Type: <Bullish/Bearish> <Gartley/Bat/Alt Bat/Butterfly/Crab/Deep Crab>
- Score: <X.X>/10
- AB=CD Convergence: <Yes ✓ / No ⚠>
- PRZ Zone: $<low> – $<high>
- Price vs PRZ: <above / inside / below / approaching>
- Pattern age: <bars since D printed or label timestamp>

<If no patterns:>
- No confirmed harmonic patterns on this chart at this timeframe.
- Borderline patterns (score 4.0–5.9): <list if visible, else "none">

Screenshot: <path>
```

---

## Interpretation Guide (for CrewAI analyst)

### Score Thresholds
- **8–10**: Textbook geometry. High-conviction PRZ. Trade with full size.
- **6–7.9**: Good geometry, minor imprecision. Trade with standard size. Default filter is 6.
- **4–5.9**: Borderline. Shown as dashed lines. Use only as confluence confirmation — do NOT trade standalone.
- **< 4**: Noise. Ignored by default.

### AB=CD Convergence
- AB=CD **present** (✓): Carney's primary validation. PRZ has at least two projections converging. Strongest signal.
- AB=CD **absent** (⚠): Incomplete geometry per Carney's books. Reduce size, require additional confirmation from other indicators.

### PRZ Logic
- Bullish pattern: price trades DOWN into the PRZ → long entry zone. The PRZ is support.
- Bearish pattern: price trades UP into the PRZ → short entry zone. The PRZ is resistance.
- Price **approaching** the PRZ: anticipate the zone, place limit orders. This is the Forming Mode workflow.
- Price **inside** PRZ: highest probability zone — wait for rejection confirmation (engulfing, wick rejection) before entry.
- Price **through** the PRZ: pattern failed. No entry. The D level was violated.

### PRZ Tightness
- Tight PRZ (high, low within 0.5–1× ATR of each other): high-quality setup, multiple projections converged.
- Wide PRZ (> 2× ATR spread): low precision, wait for price to reach midpoint of zone before entry.

### When HAV signals a trade
- Confirmed pattern (score ≥ 6) + AB=CD ✓ + price approaching or inside PRZ → trade setup
- Multiple pattern types at the same PRZ zone → extremely strong confluence
- Pattern completing inside MCPE accumulation or distribution zone → stronger setup

### When HAV does NOT signal a trade
- No confirmed patterns visible → harmonic analysis offers no edge on this TF
- Pattern score < 6 → insufficient geometry, skip or use as minor confluence only
- Price has already blown through the PRZ → missed entry, do not chase
- Pattern is very old (D point many bars ago) → PRZ is stale, flag to chief strategist
