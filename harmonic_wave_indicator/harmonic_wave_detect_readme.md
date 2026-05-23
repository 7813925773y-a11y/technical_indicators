Harmonic Auto-Validator [GBB]

I built this because every harmonic indicator I tried on TradingView was doing something weird with the math.

Some draw "Gartleys" where B sits at 0.5 of XA instead of 0.618. Some skip the AB=CD validation entirely. Some draw a single line for D instead of the actual PRZ zone Carney describes in his books. After spending too many evenings trying to reverse-engineer what a few popular ones were actually checking, I decided to write my own from scratch and stick to the methodology Scott Carney lays out in "Harmonic Trading Volume One" (2004) and "Volume Two" (2007).

This is the result. Six patterns, strict ratio checks, PRZ rendered as a real zone with outlier filtering, embedded AB=CD validation, and a 0-10 score that reflects how clean the geometry actually is.

What it detects

Gartley — B at 0.618 XA, D at 0.786 XA
Bat — B around 0.5, D at 0.886
Alt Bat — B shallow (0.382), D at 1.13 (extends past X)
Butterfly — B at 0.786, D at 1.272
Crab — B around 0.5, D at 1.618
Deep Crab — B at 0.886, D at 1.618


Three tolerance presets (Strict / Standard / Lenient) control how forgiving the ratio checks are. Standard uses tolerances close to what Carney published; Lenient widens by ~40% for charts where you want to see more candidates; Strict is for when you only want near-perfect geometry.

What's actually different about this one

PRZ as a zone, not a line. Most indicators draw D at a single Fibonacci level. Carney's actual methodology defines D as a Potential Reversal Zone — the convergence envelope of multiple projections (0.786 XA, 1.27 BC, 1.618 BC, AB=CD for Gartley; different sets per pattern). HAV computes that zone, filters outliers more than 3 ATR from the median projection, and draws the resulting box. When the zone is tight (projections converge), the score goes up. When it's wide, the score goes down. This is information you actually need before deciding whether to trade the pattern.

Embedded AB=CD validation. Carney is pretty firm in the books: a harmonic pattern without an AB=CD that lands inside the PRZ is incomplete. HAV checks this explicitly and applies a -2 score penalty when the AB=CD doesn't converge. Patterns missing this convergence get a ⚠ icon on the label so you can see at a glance which ones are textbook vs. which ones are partial.

0-10 quality score combining ratio precision (how close B and D are to their ideal Fibonacci levels), PRZ tightness (how narrow the convergence zone is relative to ATR), and confluence count (how many projections actually landed inside the zone). The default `Min Score` filter is 6, but you can raise it for higher-conviction-only scanning or lower it to see more candidates.

Confirmed-only display by default. No "forming" patterns that disappear when D doesn't print where projected. When HAV draws a pattern, the geometry is locked in. There's an opt-in **Borderline mode** that shows patterns scoring 4.0-5.9 with dashed lines and a (B) prefix on the label — useful for confluence with other tools or for educational purposes, but these never trigger alerts.

Diagnostics table showing exactly what the engine is doing: how many 5-pivot windows it tested, where each gate filtered candidates (direction / structure / XA size / each ratio band / confluence / score), how many of each pattern type were accepted. If you're wondering "why didn't HAV draw a Gartley on this chart that I can see with my eyes," the diagnostics will usually tell you which gate it failed.

Alerts

Two ways to get alerted when something fires.

Unified alert with JSON payload — set up one alert on "Any alert() function call" and you'll get structured JSON when any pattern of any direction confirms. The payload includes ticker, timeframe, pattern type, direction, score, AB=CD convergence status, PRZ top and bottom, all four ratios, and the prices and timestamps of all five pivots. Plug it into a webhook for Telegram, Discord, your own backend, whatever. This is what I use for scanning many charts at once and routing everything to a single notification stream.

12 named alert conditions — bullish/bearish × 6 patterns. If you just want "alert me on Crab patterns on this one chart" without messing with webhooks, these show up in TradingView's standard alert dialog.

Both fire on bar close only. No repainting.

Honest expectations on signal frequency

Harmonic patterns are rare on any single chart. Like, actually rare. Across my testing:
Daily timeframe, you might get 1-4 patterns per year on a single instrument
4H, maybe 5-15 patterns per month
Lower TFs (5m, 15m), dozens per week


This is by design — strict ratio checking filters out most of the 5-pivot zigzags that other indicators happily call "harmonic patterns." If you put HAV on one daily chart and stare at it for a week expecting signals, you will be disappointed.

The way this thing actually shines is across many charts at once. Drop it on 30+ instruments across daily and 4H, set up the unified JSON alert, route to a Telegram channel or Discord webhook, and let the patterns come to you. That's the workflow it's built for.

What it is and isn't

It is: a pattern detection and verification tool. A confluence/confirmation aid for traders who already have a setup and want to know if a harmonic pattern is also forming there. A teaching tool — the diagnostics show you exactly what's happening at every step.

It isn't: a complete trading system. There are no entry signals, no SL/TP automation, no win-rate claims. The decision to trade a pattern is yours, and Carney's books contain the actual entry/management methodology if you want to follow it strictly.

Settings worth knowing about

Tolerance Preset — start with Standard. If you're seeing too few patterns, try Lenient. If you're seeing too many low-quality ones, try Strict.

Min Score — default 6 keeps things clean. Drop to 4-5 if you want to see borderline geometry. Raise to 7-8 for highest-conviction-only.

Show Borderline Patterns — opt-in. Adds dashed/dimmed display for patterns that scored 4.0-5.9. Doesn't trigger alerts.

Log Scale — default Off. Carney's books and most charting tradition use linear-scale Fibonacci. If you're working on heavy long-term crypto charts where price moved by orders of magnitude, you might prefer "On" or "Auto."

Show Diagnostics Table — default On. Shows the detection statistics in the top-right. Toggle off if it's in the way of other indicators.

Show Distribution Stats — opt-in addition to the diagnostics. Useful if you're calibrating tolerances yourself or curious about an asset's natural retracement profile.

Patterns that aren't included

I deliberately didn't add Cypher, Shark, or 5-0 in this version. Cypher (Oglesbee) uses a completely different structural approach than the Carney patterns and didn't fit cleanly into the same scoring framework. Shark and 5-0 use OXABC labeling with C as the entry rather than D, which would have meant a parallel detection engine. Maybe in v1.1 if there's demand. The six patterns above cover the bulk of what shows up in real markets anyway.

Source notes

If you want to read the actual methodology this is implementing, the references are:

Scott M. Carney, "The Harmonic Trader" (1999) — the original self-published book where the framework first appeared, including the PRZ concept and the 0.886 retracement

Scott M. Carney, "Harmonic Trading Volume One" (2004, 2nd ed. 2010) — the formal Pearson/FT Press treatment, Bat pattern, ideal Gartley ratios, AB=CD requirements

Scott M. Carney, "Harmonic Trading Volume Two" (2007, 2nd ed. 2010) — Crab, Alt Bat, 5-0, RSI BAMM execution model, advanced patterns

Scott M. Carney, "Harmonic Trading Volume Three: Reaction vs Reversal" (2016) — execution refinement, Harmonic Strength Index, additional management strategies

H.M. Gartley's original 1935 "Profits in the Stock Market" is where the Gartley pattern itself was first described, but the specific Fibonacci ratios (0.618 / 0.786) were Carney's contribution decades later — Gartley used different proportions.


Feedback, bug reports, "this thing didn't draw a pattern that's clearly there" reports — all welcome in the comments. I'll be running this myself across crypto, forex, and indices, and the feedback loop is genuinely how this gets better.

The Good, the Bad and the Bitcoin
May 7
Release Notes
v1.1 update — Forming Mode

Multiple users on the v1.0 launch pointed out — fairly — that confirmed-only detection means you see the pattern AFTER price has already started moving away from the PRZ. The lag is structural to how pivot detection works, but it's still a real workflow problem.

Forming Mode addresses this. When toggled on, HAV projects the PRZ from X/A/B/C before D prints — so you can place limit orders at the projected zone rather than reacting after the fact. This is the canonical Carney workflow that the books actually describe. Forming patterns render with dotted lines, a "(F)" prefix, and a /8 score (since AB=CD convergence and r_XD precision can't be checked without D yet).

To enable: open the indicator settings and check "Show Forming Patterns" under the "Forming Mode (advanced)" group. The feature is OFF by default — you have to turn it on.

Forming patterns DO NOT trigger alerts. Alerts remain reserved for confirmed patterns — the alert stream stays high-conviction, and forming patterns are visible context for traders watching the chart.

When a forming pattern's D actually prints and validates, it transitions to confirmed and the regular alert fires. When D prints but doesn't validate the projected pattern type, the forming pattern is briefly marked failed (with an X glyph) before being removed.

