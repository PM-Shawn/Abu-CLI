"""MCP server lifecycle manager for Abu CLI.

Reads MCP server configs from ~/.abu/config.json or .abu/mcp.json,
connects on startup, injects tools into Agent, disconnects on exit.

Config format (in ~/.abu/config.json):
{
  "mcp_servers": {
    "filesystem": {
      "transport": "stdio",
      "command": ["npx", "-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
    },
    "my-api": {
      "transport": "http",
      "url": "http://localhost:3000/sse",
      "headers": {"Authorization": "Bearer xxx"}
    }
  }
}

Or per-project in .abu/mcp.json with the same structure.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentx.tools.decorator import ToolDefinition


class MCPManager:
    """Manages MCP server connections and tool collection."""

    def __init__(self) -> None:
        self._clients: list[Any] = []  # MCPClient instances
        self._context_managers: list[Any] = []  # for cleanup
        self._tools: list[ToolDefinition] = []
        self._server_names: dict[str, int] = {}  # name -> tool count

    @property
    def tools(self) -> list[ToolDefinition]:
        return self._tools

    @property
    def server_info(self) -> dict[str, int]:
        """Map of server name -> number of tools."""
        return dict(self._server_names)

    async def connect_from_config(
        self,
        global_config: dict,
        project_dir: Path | None = None,
        renderer: Any = None,
    ) -> None:
        """Connect to all configured MCP servers.

        Reads from global config and optional per-project .abu/mcp.json.
        """
        servers: dict[str, dict] = {}

        # Global MCP servers
        servers.update(global_config.get("mcp_servers", {}))

        # Per-project MCP servers (override global)
        if project_dir:
            project_mcp = project_dir / ".abu" / "mcp.json"
            if project_mcp.exists():
                try:
                    proj_cfg = json.loads(project_mcp.read_text())
                    servers.update(proj_cfg.get("mcp_servers", {}))
                except Exception:
                    pass

        if not servers:
            return

        for name, cfg in servers.items():
            await self._connect_server(name, cfg, renderer)

    async def _connect_server(
        self,
        name: str,
        cfg: dict,
        renderer: Any = None,
    ) -> None:
        """Connect to a single MCP server."""
        try:
            from agentx.mcp import MCPClient
        except ImportError:
            if renderer:
                renderer.render_error(
                    f"MCP not available. Install: pip install agentx[mcp]"
                )
            return

        transport = cfg.get("transport", "stdio")

        try:
            if transport == "stdio":
                command = cfg.get("command", [])
                env = cfg.get("env")
                if not command:
                    if renderer:
                        renderer.render_error(f"MCP '{name}': missing 'command'")
                    return

                # Manually enter the async context manager
                cm = MCPClient.stdio(command, env=env)
                client = await cm.__aenter__()
                self._context_managers.append(cm)

            elif transport == "http":
                url = cfg.get("url", "")
                headers = cfg.get("headers")
                if not url:
                    if renderer:
                        renderer.render_error(f"MCP '{name}': missing 'url'")
                    return

                cm = MCPClient.http(url, headers=headers)
                client = await cm.__aenter__()
                self._context_managers.append(cm)

            else:
                if renderer:
                    renderer.render_error(f"MCP '{name}': unknown transport '{transport}'")
                return

            # Get tools from the server
            tools = await client.list_tools()
            self._clients.append(client)
            self._tools.extend(tools)
            self._server_names[name] = len(tools)

            if renderer:
                renderer.render_info(
                    f"MCP '{name}': connected ({len(tools)} tools)"
                )

        except Exception as e:
            if renderer:
                renderer.render_error(f"MCP '{name}': {e}")

    async def disconnect_all(self) -> None:
        """Disconnect all MCP servers."""
        for cm in self._context_managers:
            try:
                await cm.__aexit__(None, None, None)
            except Exception:
                pass
        self._clients.clear()
        self._context_managers.clear()
        self._tools.clear()
        self._server_names.clear()
