# Output Template — TV Indicator Analyzer

## Full Report Structure

```markdown
# TV Indicator Analysis — $<TICKER> (<TIMEFRAME>) — <DATE>

> Current Price: $<PRICE> | Analysis as of <DATE>

---

## Chart Screenshots
- MCPE: [screenshot path]
- Harmonic: [screenshot path]
- Ichimoku: [screenshot path]
- FibStruct: [screenshot path]
- DeMark: [screenshot path]

---

## MCPE Verdict — Wyckoff Cycle Phase
[~200 words from mcpe_analyst CrewAI agent]
Sections: Current phase + what it means → Cycle position % → Projection direction/target → Key levels → Trading implication

---

## Harmonic Verdict
[~200 words from harmonic_analyst CrewAI agent]
Sections: Patterns detected (or "none confirmed") → PRZ zone(s) → Quality score(s) → Entry implication → Timeframe context

---

## Ichimoku Verdict
[~200 words from ichimoku_analyst CrewAI agent]
Sections: Kumo status (above/inside/below, bullish/bearish) → TK cross → Time cycle forecast → Wave structure → Price targets

---

## FibStruct Verdict
[~200 words from fibstruct_analyst CrewAI agent]
Sections: Structure bias (BOS/CHoCH context) → Current Fibonacci anchor → Confluence score → Premium/Discount zone → Entry signals → Target zone

---

## DeMark Verdict
[~150 words from demark_analyst CrewAI agent]
Sections: Current count + direction → Recent 9 or 13 signals → Exhaustion read → Trend context

---

## Synthesized Recommendation — $<TICKER> (<TIMEFRAME>)

### Bottom Line
ONE sentence: directional bias + instrument + conviction (1–5) — OR "Stand aside."
Example: "Bullish bias, long $AAPL common shares or Dec calls, conviction 3/5."

### Confluences
What ≥ 2 indicators agree on (the high-conviction signal clusters).
Format: bullet per confluence, tagging which indicators agree.
Example:
- [MCPE + FibStruct] Price in discount zone at cycle bottom — accumulation setup
- [Ichimoku + DeMark] TK cross + TD 9 exhaustion on same bar → reversal timing confluence

### Execution
- Entry zone: $X – $Y
- Stop / Invalidation: $X (aligns to [level])
- Target 1: $X ([source indicator level])
- Target 2: $X ([source indicator level])
- R:R at T1: X:1
- Instrument: [shares / call spread / etc.]

### Invalidation
ONE sentence: the specific price or event that kills the thesis.

### Divergences
Where the 5 indicators disagree, and which takes precedence for this timeframe.
Format: bullet per disagreement with brief reasoning.

### No-Trade Conditions
List any conditions that would suggest standing aside (e.g., all indicators in a neutral/conflicted state, DeMark exhaustion against the proposed direction, harmonic PRZ not yet reached).
```

---

## Per-Indicator Brief → Verdict Mapping

| Brief field | Used by analyst for |
|---|---|
| Cycle Phase + Position% | Primary directional call + caution zones |
| Projection direction/target | Price target anchoring |
| Harmonic pattern type + score | Entry quality and PRZ precision |
| Kumo position + color | Trend filter (above kumo = bull filter active) |
| Time cycle forecast | Timing — when the next turning point is expected |
| Wave structure | How many legs have printed vs. remaining |
| FibStruct bias + CHoCH | Structural trend direction |
| Confluence score + near Fib | Entry precision — how close to a key level |
| DeMark count + 9/13 signals | Exhaustion timing — is the current trend near its end? |

---

## Conviction Guide

| Conviction | Meaning |
|---|---|
| 5/5 | ≥4 indicators aligned, no divergence |
| 4/5 | 3-4 aligned, minor divergence |
| 3/5 | 3 aligned, 1-2 conflicting but not opposing |
| 2/5 | Only 2 aligned; useful for partial position sizing |
| 1/5 | Single-indicator signal only; generally stand aside |
| Stand aside | Indicators contradict each other OR all neutral |
