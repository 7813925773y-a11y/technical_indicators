"""
Async wrapper around the TradingView MCP stdio server.
Keeps a single persistent session per context-manager scope.
"""
import json
import logging
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)


class TVMCPClient:
    def __init__(self, server_js_path: str):
        self.params = StdioServerParameters(command="node", args=[server_js_path])
        self._stdio_ctx = None
        self._session_ctx = None
        self._session = None

    async def __aenter__(self):
        self._stdio_ctx = stdio_client(self.params)
        read, write = await self._stdio_ctx.__aenter__()
        self._session_ctx = ClientSession(read, write)
        self._session = await self._session_ctx.__aenter__()
        await self._session.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        for ctx in (self._session_ctx, self._stdio_ctx):
            if ctx:
                try:
                    await ctx.__aexit__(exc_type, exc_val, exc_tb)
                except Exception as e:
                    logger.debug(f"Cleanup error: {e}")

    async def call(self, tool_name: str, **kwargs) -> dict:
        """Call a TV MCP tool. Returns parsed JSON dict or empty dict on failure."""
        args = {k: v for k, v in kwargs.items() if v is not None}
        try:
            result = await self._session.call_tool(tool_name, args)
            for item in result.content or []:
                if hasattr(item, "text"):
                    try:
                        return json.loads(item.text)
                    except json.JSONDecodeError:
                        return {"raw": item.text, "success": True}
            return {}
        except Exception as e:
            logger.warning(f"[TV] {tool_name} failed: {e}")
            return {"success": False, "error": str(e)}
