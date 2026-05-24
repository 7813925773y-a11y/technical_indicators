"""
Live test: run the exact same _demark_compute logic on real TV OHLCV data
and print the full brief + signal. Requires TV running on CDP :9222.
"""
import asyncio, json, sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

from tv_mcp_client import TVMCPClient
from brief_builder import _demark_compute, _demark_signal_from_ohlcv
import datetime

TV_JS = str(__import__("pathlib").Path(__file__).parent.parent.parent / "tradingview-mcp/src/server.js")


async def main():
    async with TVMCPClient(TV_JS) as tv:
        print("Connected to TV MCP")

        raw  = await tv.call("data_get_ohlcv", count=100)
        bars = raw.get("bars") or []
        print(f"Got {len(bars)} bars")

        if not bars:
            print("No bars returned!")
            return

        closes    = [b["close"] for b in bars]
        buy, sell = _demark_compute(closes)
        n         = len(bars)

        def ts(unix): return datetime.datetime.fromtimestamp(unix).strftime("%Y-%m-%d")

        print("\n=== ALL BARS WITH COUNT >= 7 ===")
        for i in range(n):
            b, s = buy[i], sell[i]
            if b >= 7 or s >= 7:
                lbl = f"Long {b}" if b in (9,13) else (str(b) if b >= 7 else f"Short {s}" if s in (9,13) else str(s))
                print(f"  {ts(bars[i]['time'])}  close={closes[i]:>8.2f}  buy={b:>2}  sell={s:>2}  → {lbl}")

        cur = bars[-1]
        print(f"\n=== CURRENT BAR ===")
        print(f"  {ts(cur['time'])}  close={cur['close']:.2f}")
        print(f"  buySetup={buy[-1]}  sellSetup={sell[-1]}")

        sig = _demark_signal_from_ohlcv(bars)
        print("\n=== SIGNAL OUTPUT ===")
        print(json.dumps(sig, indent=2))

asyncio.run(main())
