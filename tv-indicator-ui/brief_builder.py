"""
Extract structured data from each TradingView indicator and format as a brief.
Each build_* function returns (brief_text: str, screenshot_path: str | None).
"""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# ── helpers ──────────────────────────────────────────────────────────────────

def _first_study(data: dict) -> dict:
    studies = data.get("studies") or []
    return studies[0] if studies else {}


def _table_rows(data: dict) -> list:
    study = _first_study(data)
    tables = study.get("tables") or []
    return tables[0].get("rows") or [] if tables else []


def _parse_dashboard(rows: list) -> dict:
    """Parse 'Key | Value' rows into a dict."""
    d = {}
    for row in rows:
        parts = [p.strip() for p in str(row).split("|")]
        if len(parts) >= 2:
            d[parts[0]] = parts[1]
    return d


def _labels(data: dict) -> list:
    return (_first_study(data).get("labels") or [])


def _levels(data: dict) -> list:
    return (_first_study(data).get("horizontal_levels") or [])


def _zones(data: dict) -> list:
    return (_first_study(data).get("zones") or [])


def _screenshot_path(data: dict) -> str | None:
    return data.get("file_path") if data.get("success") else None


def _fmt_labels(labels: list, n: int = 15) -> str:
    if not labels:
        return "  (none)"
    return "\n".join(
        f"  - {l.get('text','?')} @ ${l.get('price','?')}"
        for l in labels[-n:]
    )


# ── public entry point ────────────────────────────────────────────────────────

async def build_brief(
    tv,
    key: str,
    shorttitle: str,
    full_title: str,
    ticker: str,
    timeframe: str,
    price: str,
    date: str,
) -> tuple:
    """Return (brief_text, screenshot_path)."""
    # Try to ensure indicator is on chart (best-effort — may fail for saved scripts)
    add_result = await tv.call("chart_manage_indicator", action="add", indicator=full_title)
    if not add_result.get("success"):
        logger.debug(f"chart_manage_indicator for {shorttitle} returned: {add_result}")

    screenshot_data = await tv.call(
        "capture_screenshot", region="chart",
        filename=f"{ticker}_{timeframe}_{key}"
    )
    screenshot = _screenshot_path(screenshot_data)

    header = (
        f"## {shorttitle} Brief\n"
        f"Symbol: {ticker} | Timeframe: {timeframe} | Date: {date} | Price: ${price}\n\n"
    )

    try:
        dispatch = {
            "mcpe":     _mcpe,
            "harmonic": _harmonic,
            "ichimoku": _ichimoku,
            "fibstruct": _fibstruct,
            "demark":   _demark,
        }
        body = await dispatch[key](tv)
    except Exception as e:
        logger.error(f"brief_builder error for {key}: {e}")
        body = f"[Data extraction failed: {e}]"

    return header + body, screenshot


# ── per-indicator extractors ──────────────────────────────────────────────────

async def _mcpe(tv) -> str:
    tables  = await tv.call("data_get_pine_tables",  study_filter="MCPE")
    labels  = await tv.call("data_get_pine_labels",  study_filter="MCPE", max_labels=50)
    lines   = await tv.call("data_get_pine_lines",   study_filter="MCPE")

    rows    = _table_rows(tables)
    dash    = _parse_dashboard(rows)
    lbls    = _labels(labels)
    levels  = _levels(lines)

    phase   = dash.get("Cycle Phase") or dash.get("Phase") or "Unknown"
    pos     = dash.get("Cycle Position") or dash.get("Position") or "Unknown"
    vol     = dash.get("Volatility") or dash.get("Volatility Status") or "Unknown"
    volume  = dash.get("Volume") or "Unknown"

    if len(levels) >= 3:
        lvl_str = (
            f"  Cycle High: ${levels[0]}\n"
            f"  Cycle Mid:  ${levels[len(levels)//2]}\n"
            f"  Cycle Low:  ${levels[-1]}"
        )
    elif levels:
        lvl_str = "\n".join(f"  Level: ${l}" for l in levels)
    else:
        lvl_str = "  [not visible — indicator may not be on chart]"

    proj_lbls = [l for l in lbls if any(w in str(l.get("text","")).upper()
                                        for w in ["PROJ","TARGET","↑","↓","UP","DOWN"])]
    proj_str = _fmt_labels(proj_lbls, 3) if proj_lbls else "  None detected"

    return f"""Dashboard:
  Cycle Phase:    {phase}
  Cycle Position: {pos}
  Volatility:     {vol}
  Volume:         {volume}

Key Levels:
{lvl_str}

Recent Labels:
{_fmt_labels(lbls, 10)}

Projection Labels:
{proj_str}
"""


async def _harmonic(tv) -> str:
    labels = await tv.call("data_get_pine_labels", study_filter="HAV", max_labels=50)
    boxes  = await tv.call("data_get_pine_boxes",  study_filter="HAV")

    lbls   = _labels(labels)
    zones  = _zones(boxes)

    lbl_str  = _fmt_labels(lbls, 30) if lbls else "  No pattern labels detected"
    zone_str = "\n".join(f"  PRZ: ${z['low']} – ${z['high']}" for z in zones[:6]) \
               if zones else "  No PRZ zones detected"

    return f"""Pattern Labels:
{lbl_str}

PRZ Zones (box boundaries):
{zone_str}

Summary: {len(lbls)} labels, {len(zones)} PRZ zones detected
Note: 'No pattern labels' means no confirmed harmonic patterns on this chart/timeframe.
"""


async def _ichimoku(tv) -> str:
    study_vals = await tv.call("data_get_study_values")
    labels     = await tv.call("data_get_pine_labels", study_filter="LuxAlgo - Ichimoku Theories", max_labels=100)
    lines      = await tv.call("data_get_pine_lines",  study_filter="LuxAlgo - Ichimoku Theories")

    # Find Ichimoku study in all study values
    all_studies = study_vals.get("studies") or []
    ichi_study  = next((s for s in all_studies if "ichimoku" in s.get("name","").lower()), {})
    values      = ichi_study.get("values") or {}

    val_str = "\n".join(f"  {k}: {v}" for k, v in list(values.items())[:10]) if values else "  [No numeric values — may not be visible]"

    lbls    = _labels(labels)
    levels  = _levels(lines)

    lbl_str   = _fmt_labels(lbls, 20)
    level_str = "\n".join(f"  ${l}" for l in levels[:12]) if levels else "  [No lines detected]"

    return f"""Ichimoku Line Values:
{val_str}

Wave/Time Cycle Labels:
{lbl_str}

Forecast / Price Target Lines:
{level_str}
"""


async def _fibstruct(tv) -> str:
    tables = await tv.call("data_get_pine_tables", study_filter="FibStruct")
    labels = await tv.call("data_get_pine_labels", study_filter="FibStruct", max_labels=100)
    lines  = await tv.call("data_get_pine_lines",  study_filter="FibStruct")
    boxes  = await tv.call("data_get_pine_boxes",  study_filter="FibStruct")

    rows   = _table_rows(tables)
    dash   = _parse_dashboard(rows)
    lbls   = _labels(labels)
    levels = _levels(lines)
    zones  = _zones(boxes)

    bias       = dash.get("Bias") or dash.get("Structure Bias") or "Unknown"
    fib_dir    = dash.get("Fib Dir") or "Unknown"
    confluence = dash.get("Confluence") or "Unknown"
    zone       = dash.get("Zone") or dash.get("Current Zone") or "Unknown"
    near_fib   = dash.get("Near Fib") or "Unknown"
    atr        = dash.get("ATR") or dash.get("ATR(14)") or "Unknown"
    liquidity  = dash.get("Liquidity") or "Unknown"

    lbl_str   = _fmt_labels(lbls, 15)
    level_str = "\n".join(f"  ${l}" for l in levels[:10]) if levels else "  [None]"
    zone_str  = "\n".join(f"  ${z['low']} – ${z['high']}" for z in zones[:4]) if zones else "  [None]"

    return f"""Dashboard:
  Structure Bias: {bias}
  Fib Direction:  {fib_dir}
  Confluence:     {confluence}
  Zone:           {zone}
  Near Fib:       {near_fib}
  ATR(14):        {atr}
  Liquidity:      {liquidity}

Recent Labels (BOS/CHoCH/HH/HL/Signals):
{lbl_str}

Fibonacci Levels:
{level_str}

Zones (Golden/Target):
{zone_str}
"""


async def _demark(tv) -> str:
    labels = await tv.call("data_get_pine_labels", study_filter="TD heatmap", max_labels=100)
    lbls   = _labels(labels)

    # Separate 9/13 exhaustion signals from count labels
    exhaustion = [l for l in lbls if any(w in str(l.get("text",""))
                                         for w in ["Long","Short","long","short"])]
    count_lbls = [l for l in lbls if str(l.get("text","")).strip().lstrip("-").isdigit()]

    exhaust_str = _fmt_labels(exhaustion, 10) if exhaustion else "  None detected"
    recent_str  = _fmt_labels(lbls, 20)

    return f"""TD 9 / TD 13 Exhaustion Signals:
{exhaust_str}

Recent Count Labels (last 20):
{recent_str}

Total labels: {len(lbls)} | Exhaustion signals: {len(exhaustion)}
Interpretation: 'Long 9/13' = downward exhaustion (buy zone); 'Short 9/13' = upward exhaustion (sell zone)
"""
