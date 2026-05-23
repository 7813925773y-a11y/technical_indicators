"""
Run the tv_indicator_crew CrewAI workflow with model fallback.

Fallback chain:
  1. gpt-5.4-mini   (requested)
  2. gpt-4o-mini    (standard fallback)
  3. gpt-4o         (last CrewAI attempt)
  4. Direct LiteLLM synthesis without CrewAI (gpt-4o-mini → gpt-4o)
"""
import logging
import sys
import yaml
from pathlib import Path
from crewai import Agent, Task, Crew, Process

logger = logging.getLogger(__name__)

PRIMARY_MODEL  = "gpt-5.4-mini"
CREW_FALLBACKS = ["gpt-4o-mini", "gpt-4o"]
DIRECT_MODELS  = ["gpt-4o-mini", "gpt-4o"]


# ── error classification ──────────────────────────────────────────────────────

def _is_retryable_api_error(e: Exception) -> bool:
    msg = str(e).lower()
    return any(kw in msg for kw in [
        "model", "invalid_model", "does not exist", "not found",
        "no such model", "authentication", "api_key", "apikey",
        "rate_limit", "quota", "billing", "badrequest",
        "400", "401", "404", "openai",
    ])


# ── crew loader ───────────────────────────────────────────────────────────────

def _load_crew(agents_yml: str, tasks_yml: str, ticker: str,
               variables: dict, model: str) -> Crew:
    with open(agents_yml) as f:
        agents_data = yaml.safe_load(f)
    with open(tasks_yml) as f:
        tasks_data = yaml.safe_load(f)

    all_vars = {"topic": ticker, **variables}

    def fmt(s: str) -> str:
        if not s or "{" not in s:
            return s or ""
        try:
            return s.format_map(_SafeDict(all_vars))
        except Exception as ex:
            logger.debug(f"Template format warning: {ex}")
            return s

    # Build agents
    agents_dict: dict[str, Agent] = {}
    for name, cfg in (agents_data or {}).items():
        if not isinstance(cfg, dict):
            continue
        agents_dict[name] = Agent(
            name=name,
            role=fmt(cfg.get("role", "")),
            goal=fmt(cfg.get("goal", "")),
            backstory=fmt(cfg.get("backstory", "")),
            llm=model,
            verbose=False,
            allow_delegation=False,
        )

    # Build tasks (order matters — context tasks must be defined first)
    tasks_list: list[Task] = []
    tasks_by_name: dict[str, Task] = {}
    for name, cfg in (tasks_data or {}).items():
        if not isinstance(cfg, dict):
            continue
        agent_name = cfg.get("agent")
        if agent_name not in agents_dict:
            raise ValueError(f"Task '{name}' references unknown agent '{agent_name}'")

        context_tasks = [
            tasks_by_name[t] for t in (cfg.get("context") or [])
            if t in tasks_by_name
        ]
        task_kwargs = dict(
            description=fmt(cfg.get("description", "")),
            expected_output=fmt(cfg.get("expected_output", "")),
            agent=agents_dict[agent_name],
            async_execution=bool(cfg.get("async_execution", False)),
        )
        if context_tasks:
            task_kwargs["context"] = context_tasks

        task = Task(**task_kwargs)
        if cfg.get("output_file"):
            task.output_file = cfg["output_file"]

        tasks_list.append(task)
        tasks_by_name[name] = task

    return Crew(
        agents=list(agents_dict.values()),
        tasks=tasks_list,
        process=Process.sequential,
        verbose=False,
    )


# ── direct synthesis fallback ─────────────────────────────────────────────────

def _direct_synthesis(ticker: str, variables: dict, model: str) -> str:
    """Skip CrewAI entirely — one-shot LiteLLM call with all 5 briefs."""
    import litellm

    briefs = "\n\n".join(
        f"**{k.replace('_brief', '').upper()} BRIEF:**\n{v}"
        for k, v in variables.items()
        if k.endswith("_brief")
    )
    timeframe = variables.get("timeframe", "unknown")
    date = variables.get("current_date", "")

    prompt = f"""You are a multi-methodology technical analyst. Analyze **{ticker}** ({timeframe} timeframe, {date}) using these 5 indicator readings:

{briefs}

Provide a structured analysis:

## MCPE Verdict — Wyckoff Cycle
[~150 words: phase + position + projection + key levels + trade implication]

## Harmonic Verdict
[~150 words: patterns detected or absent + PRZ zones + entry implication]

## Ichimoku Verdict
[~150 words: kumo status + TK cross + time cycle + wave + targets]

## FibStruct Verdict
[~150 words: structure bias + BOS/CHoCH + confluence + entry zone + target]

## DeMark Verdict
[~100 words: current count + 9/13 signals + exhaustion read]

---

## Synthesized Recommendation — ${ticker} ({timeframe})

### Bottom Line
[ONE sentence: direction + conviction 1-5 or "Stand aside"]

### Confluences
[Bullets: what 2+ indicators agree on]

### Execution
[Entry zone / Stop / Target 1 / Target 2 / R:R]

### Invalidation
[ONE sentence]

### Divergences
[Where indicators disagree and why]"""

    resp = litellm.completion(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=3000,
    )
    return resp.choices[0].message.content


# ── public interface ──────────────────────────────────────────────────────────

def run_crew_with_fallback(
    agents_yml: str,
    tasks_yml: str,
    ticker: str,
    variables: dict,
) -> dict:
    """
    Run CrewAI crew with model fallback.
    Returns: {"analysis": str, "model_used": str, "fallback_used": bool, "error": str|None}
    """
    models = [PRIMARY_MODEL] + CREW_FALLBACKS
    last_crew_error = None

    for i, model in enumerate(models):
        try:
            logger.info(f"CrewAI attempt {i+1}/{len(models)} with model: {model}")
            crew = _load_crew(agents_yml, tasks_yml, ticker, variables, model)
            result = crew.kickoff()
            analysis = str(result) if not isinstance(result, str) else result
            return {
                "analysis": analysis,
                "model_used": model,
                "fallback_used": i > 0,
                "error": None,
            }
        except Exception as e:
            last_crew_error = e
            logger.warning(f"Model {model} failed: {type(e).__name__}: {e}")
            if i < len(models) - 1 and _is_retryable_api_error(e):
                logger.info(f"Retrying with next model...")
                continue
            # Non-retryable or last model — break to direct synthesis
            break

    # ── Direct synthesis fallback ─────────────────────────────────────────────
    logger.warning(f"All CrewAI attempts failed. Last error: {last_crew_error}. Falling back to direct LiteLLM synthesis.")
    for direct_model in DIRECT_MODELS:
        try:
            logger.info(f"Direct synthesis with: {direct_model}")
            analysis = _direct_synthesis(ticker, variables, direct_model)
            return {
                "analysis": analysis,
                "model_used": direct_model,
                "fallback_used": True,
                "error": f"CrewAI failed ({last_crew_error}), used direct synthesis",
            }
        except Exception as e2:
            logger.warning(f"Direct synthesis with {direct_model} failed: {e2}")
            continue

    return {
        "analysis": (
            f"⚠ All analysis methods failed.\n\n"
            f"Last CrewAI error: {last_crew_error}\n\n"
            f"The 5 indicator briefs were gathered successfully. "
            f"Please check your OpenAI API key and model access."
        ),
        "model_used": "none",
        "fallback_used": True,
        "error": str(last_crew_error),
    }


# ── helpers ───────────────────────────────────────────────────────────────────

class _SafeDict(dict):
    """dict.format_map() with missing-key safety."""
    def __missing__(self, key):
        return f"{{{key}}}"
