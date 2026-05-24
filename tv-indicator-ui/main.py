"""
TV Indicator Analyzer — FastAPI web server.

Endpoints:
  GET /                → serves index.html
  GET /analyze         → SSE stream: progress + per-indicator data + final analysis
  GET /screenshots/... → static file serving for TV screenshots
"""
import asyncio
import datetime
import json
import logging
import sys
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

# ── paths ─────────────────────────────────────────────────────────────────────
BASE        = Path(__file__).parent
ROOT        = BASE.parent                                  # tradingview_based_indicators/
TV_JS       = ROOT / "tradingview-mcp/src/server.js"
SCREENSHOTS = ROOT / "tradingview-mcp/screenshots"
AGENTS_YML  = ROOT / "tv_indicator_crew/agents.yml"
TASKS_YML   = ROOT / "tv_indicator_crew/tasks.yml"

TF_MAP = {"4h": "240", "day": "D", "week": "W", "month": "M"}

INDICATORS = [
    ("mcpe",      "MCPE",                        "Market Cycle Projection Engine"),
    ("harmonic",  "HAV",                         "Harmonic Auto-Validator [GBB]"),
    ("ichimoku",  "LuxAlgo - Ichimoku Theories",  "Ichimoku Theories [LuxAlgo]"),
    ("fibstruct", "FibStruct",                    "Fibonacci Structure Engine [WillyAlgoTrader]"),
    ("demark",    "TD heatmap",                   "Tom DeMark Sequential Heat Map"),
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("tv-ui")

# ── app ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="TV Indicator Analyzer")

SCREENSHOTS.mkdir(parents=True, exist_ok=True)
app.mount("/screenshots", StaticFiles(directory=str(SCREENSHOTS)), name="screenshots")


@app.get("/", response_class=HTMLResponse)
async def index():
    return (BASE / "templates/index.html").read_text()


@app.get("/analyze")
async def analyze(request: Request, ticker: str, timeframe: str = "day"):
    ticker  = ticker.upper().strip()
    tv_tf   = TF_MAP.get(timeframe, "D")
    today   = datetime.date.today().isoformat()

    async def stream():
        from tv_mcp_client import TVMCPClient
        from brief_builder  import build_brief
        from crew_runner    import run_crew_with_fallback

        def ev(event: str, **data):
            return {"event": event, "data": json.dumps(data)}

        try:
            # ── Phase 1: TV data gathering ────────────────────────────────────
            yield ev("status", phase=1, step="Checking TradingView connection…")

            async with TVMCPClient(str(TV_JS)) as tv:
                health = await tv.call("tv_health_check")
                if not health.get("success"):
                    yield ev("error", message=(
                        "TradingView not responding. "
                        "Start TV Desktop and run: bash tradingview-mcp/scripts/launch_tv_debug_mac.sh"
                    ))
                    return

                yield ev("status", phase=1, step=f"Setting chart → {ticker} / {timeframe}")
                await tv.call("chart_set_symbol", symbol=ticker)
                await tv.call("chart_set_timeframe", timeframe=tv_tf)

                quote  = await tv.call("quote_get")
                price  = quote.get("last") or quote.get("close") or "N/A"
                yield ev("price", ticker=ticker, price=str(price), timeframe=timeframe, date=today)

                yield ev("status", phase=1, step="Verifying chart state…")
                await tv.call("chart_get_state")   # entity IDs not needed — just confirms active chart

                briefs      = {}
                screenshots = {}
                signals     = {}

                for key, shorttitle, full_title in INDICATORS:
                    yield ev("status", phase=1, step=f"Reading {shorttitle}…")
                    try:
                        brief_text, screenshot_b64, signal = await build_brief(
                            tv, key, shorttitle, full_title,
                            ticker, timeframe, str(price), today
                        )
                        briefs[f"{key}_brief"] = brief_text
                        screenshots[key]       = screenshot_b64
                        signals[key]           = signal
                    except Exception as e:
                        logger.warning(f"{shorttitle} brief failed: {e}")
                        briefs[f"{key}_brief"] = f"[Data unavailable: {e}]"
                        screenshots[key]       = None
                        signals[key]           = {
                            "indicator": key, "signal": "ERROR",
                            "reasons": [str(e)], "key_values": {},
                        }

                    yield ev("indicator_ready",
                             key=key, title=shorttitle,
                             brief=briefs[f"{key}_brief"],
                             screenshot_b64=screenshots[key],
                             signal=signals[key])

            # ── Phase 2: CrewAI analysis ──────────────────────────────────────
            yield ev("status", phase=2, step="Launching 5-analyst CrewAI crew…")

            crew_inputs = {
                "timeframe":    timeframe,
                "current_date": today,
                **briefs,
            }

            loop   = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: run_crew_with_fallback(
                    str(AGENTS_YML), str(TASKS_YML), ticker, crew_inputs
                ),
            )

            yield ev("analysis_ready",
                     ticker=ticker, timeframe=timeframe, date=today, price=str(price),
                     signals=signals,
                     analysis=result.get("analysis", ""),
                     model_used=result.get("model_used", ""),
                     fallback_used=result.get("fallback_used", False),
                     crew_error=result.get("error"))

            yield ev("done", message="Analysis complete ✓")

        except Exception as e:
            logger.exception("Stream error")
            yield ev("error", message=str(e))

    return EventSourceResponse(stream())


# ── entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = 8765
    print(f"\n  TV Indicator Analyzer  →  http://localhost:{port}\n")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
