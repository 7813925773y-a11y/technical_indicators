# Workflow — TV Indicator Analyzer

## Phase 1: Preflight

Run these in order (sequential — each depends on the previous):

```
1. tv_health_check
   → if fails: stop, tell user to launch TV Desktop with CDP enabled

2. chart_set_symbol(symbol=TICKER)

3. chart_set_timeframe(timeframe=TV_VALUE)
   TV_VALUE: 4h→"240", day→"D", week→"W", month→"M"

4. chart_get_state
   → save entity IDs for all indicators
   → note which of the 5 indicators are currently on chart

5. quote_get
   → save current price as anchor for all briefs
```

## Phase 2: Ensure All 5 Indicators Are Present

After `chart_get_state`, check that each indicator appears in the returned study list. Compare by display name substring. If any are missing:

```
chart_manage_indicator(
  action: "add",
  indicator_name: "<FULL TITLE>"   ← use the full title from the roster table
)
```

Full titles:
- `"Market Cycle Projection Engine"`
- `"Harmonic Auto-Validator [GBB]"`
- `"Ichimoku Theories [LuxAlgo]"`
- `"Fibonacci Structure Engine [WillyAlgoTrader]"`
- `"Tom DeMark Sequential Heat Map"`

If `chart_manage_indicator` returns an error (indicator not found in TV's library — this happens if the script isn't saved to the user's account), warn the user:
> "⚠ [Indicator Name] is not in your TradingView saved scripts. Open TradingView Pine Editor, paste the script from `<folder>/<script>.script`, and add it to the chart manually. Proceeding without this indicator."

After adding, call `chart_get_state` again to confirm the indicator appears.

## Phase 3: Parallel Data Extraction

Spawn **5 Agent calls in a single message** (parallel). Each agent receives exact instructions for one indicator.

Pass to each agent:
- Symbol (e.g., "AAPL")
- TradingView timeframe string (e.g., "240")
- Today's date
- Current price (from quote_get)
- Which tools to call and with what parameters
- The brief template to fill in

Agent prompts are defined in the indicator playbooks:
- MCPE → `references/indicator-playbooks/mcpe.md`
- Harmonic → `references/indicator-playbooks/harmonic.md`
- Ichimoku → `references/indicator-playbooks/ichimoku.md`
- FibStruct → `references/indicator-playbooks/fibstruct.md`
- DeMark → `references/indicator-playbooks/demark.md`

Each agent returns a formatted brief (see template below) and a screenshot path.

## Brief Template

Each agent must return exactly this structure:

```markdown
## <INDICATOR_NAME> Brief
Symbol: <TICKER> | Timeframe: <TF> | Date: <YYYY-MM-DD> | Price: $<PRICE>

<structured data — see indicator playbook for exact fields>

Screenshot: <path returned by capture_screenshot>
```

If any tool returns empty/null data, write `[no data — indicator may not be visible on chart]` for that field rather than omitting it.

## Phase 4: Crew Kickoff

After all 5 briefs are assembled, call:

```
mcp__tv-indicator-crew__kickoff(
  topic = "<TICKER>",
  additional_context = {
    "timeframe":      "<4h|day|week|month>",
    "current_date":   "<YYYY-MM-DD>",
    "mcpe_brief":     "<full MCPE brief text>",
    "harmonic_brief": "<full HAV brief text>",
    "ichimoku_brief": "<full Ichimoku brief text>",
    "fibstruct_brief":"<full FibStruct brief text>",
    "demark_brief":   "<full DeMark brief text>"
  }
)
```

The crew runs 5 analysts in parallel, then the chief strategist synthesizes. Total wall-clock: ~max(5 analyst times) + synthesis time.

## Phase 5: Format and Present Output

After the crew returns, format the full report per `references/output-template.md`. Present:

1. The 5 indicator screenshots (embed screenshot paths as references)
2. The 5 per-indicator verdicts from the CrewAI analysts
3. The synthesized recommendation from the chief strategist

If the crew kickoff fails (server not running, YAML error, etc.), fall back to synthesizing directly from the 5 briefs without CrewAI. Note the fallback explicitly to the user.
