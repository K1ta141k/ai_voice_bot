"""MCP (Model Context Protocol) integration tool."""

import asyncio
from typing import Dict, Any, List, Optional
from pathlib import Path

from ..base_tool import BaseTool, ToolResult
from ..registry import register_tool
from ...mcp.server_manager import get_mcp_manager


@register_tool(name="mcp_browser", description="Browser automation via Playwright MCP server")
class MCPBrowserTool(BaseTool):
    """Tool for browser automation using Playwright MCP server."""
    
    def __init__(self):
        super().__init__(
            name="mcp_browser",
            description="Perform browser automation tasks like navigation, clicking, form filling, and screenshots"
        )
        
        # Add parameters
        self.add_parameter(
            "action",
            "string",
            "Browser action to perform",
            required=True,
            enum=[
                "launch", "goto", "click", "fill", "screenshot",
                "get_text", "wait_for_selector", "evaluate", 
                "close_page", "close_browser", "new_page"
            ]
        )
        self.add_parameter(
            "url",
            "string",
            "URL to navigate to (for goto action)",
            required=False
        )
        self.add_parameter(
            "selector",
            "string", 
            "CSS selector for element operations",
            required=False
        )
        self.add_parameter(
            "text",
            "string",
            "Text to fill or search for",
            required=False
        )
        self.add_parameter(
            "options",
            "object",
            "Additional options for the browser action",
            required=False
        )
        self.add_parameter(
            "browser_type",
            "string",
            "Browser type (chromium, firefox, webkit)",
            required=False,
            default="chromium"
        )
        self.add_parameter(
            "headless",
            "boolean",
            "Run browser in headless mode",
            required=False,
            default=True
        )
        
        self.mcp_manager = None
    
    async def execute(self,
                     action: str,
                     url: str = None,
                     selector: str = None,
                     text: str = None,
                     options: Dict[str, Any] = None,
                     browser_type: str = "chromium",
                     headless: bool = True) -> ToolResult:
        """Execute browser automation action."""
        try:
            # Get MCP manager
            if not self.mcp_manager:
                self.mcp_manager = await get_mcp_manager()
            
            if not self.mcp_manager.is_initialized:
                return ToolResult(
                    success=False,
                    error="MCP not available",
                    message="MCP server manager is not initialized"
                )
            
            # Check if playwright server is connected
            connected_servers = self.mcp_manager.get_connected_servers()
            if "playwright" not in connected_servers:
                return ToolResult(
                    success=False,
                    error="Playwright server not available",
                    message="Playwright MCP server is not connected. Please ensure it's running and configured."
                )
            
            print(f"🌐 Browser action: {action}")
            
            # Map our action to MCP tool calls
            if action == "launch":
                return await self._launch_browser(browser_type, headless, options)
            elif action == "goto":
                return await self._navigate_to_url(url, options)
            elif action == "click":
                return await self._click_element(selector, options)
            elif action == "fill":
                return await self._fill_element(selector, text, options)
            elif action == "screenshot":
                return await self._take_screenshot(selector, options)
            elif action == "get_text":
                return await self._get_text(selector, options)
            elif action == "wait_for_selector":
                return await self._wait_for_selector(selector, options)
            elif action == "evaluate":
                return await self._evaluate_script(text, options)
            elif action == "new_page":
                return await self._new_page(options)
            elif action == "close_page":
                return await self._close_page(options)
            elif action == "close_browser":
                return await self._close_browser(options)
            else:
                return ToolResult(
                    success=False,
                    error="Invalid action",
                    message=f"Action '{action}' is not supported"
                )
                
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Browser automation failed: {str(e)}",
                message=f"Failed to execute browser action: {action}"
            )
    
    async def _launch_browser(self, browser_type: str, headless: bool, options: Dict = None) -> ToolResult:
        """Launch a new browser instance."""
        args = {
            "browser": browser_type,
            "headless": headless,
            "record_video": True,  # Enable video recording
            "video_dir": str(Path.cwd() / "playground" / "browser_recordings")
        }
        
        if options:
            args.update(options)
        
        result = await self.mcp_manager.call_tool("playwright", "launch_browser", args)
        
        if result.success:
            browser_id = result.data.get("browser_id")
            return ToolResult(
                success=True,
                data={"browser_id": browser_id, "browser_type": browser_type},
                message=f"Successfully launched {browser_type} browser (ID: {browser_id})"
            )
        else:
            return result
    
    async def _navigate_to_url(self, url: str, options: Dict = None) -> ToolResult:
        """Navigate to a URL."""
        if not url:
            return ToolResult(
                success=False,
                error="URL required",
                message="URL parameter is required for navigation"
            )
        
        args = {"url": url}
        if options:
            if "page_id" in options:
                args["page_id"] = options["page_id"]
            if "wait_until" in options:
                args["wait_until"] = options["wait_until"]
        
        result = await self.mcp_manager.call_tool("playwright", "goto", args)
        
        if result.success:
            return ToolResult(
                success=True,
                data=result.data,
                message=f"Successfully navigated to {url}"
            )
        else:
            return result
    
    async def _click_element(self, selector: str, options: Dict = None) -> ToolResult:
        """Click an element."""
        if not selector:
            return ToolResult(
                success=False,
                error="Selector required",
                message="CSS selector is required for clicking"
            )
        
        args = {"selector": selector}
        if options:
            args.update(options)
        
        result = await self.mcp_manager.call_tool("playwright", "click", args)
        
        if result.success:
            return ToolResult(
                success=True,
                data=result.data,
                message=f"Successfully clicked element: {selector}"
            )
        else:
            return result
    
    async def _fill_element(self, selector: str, text: str, options: Dict = None) -> ToolResult:
        """Fill a form element with text."""
        if not selector or text is None:
            return ToolResult(
                success=False,
                error="Selector and text required",
                message="Both selector and text are required for filling"
            )
        
        args = {"selector": selector, "value": text}
        if options:
            args.update(options)
        
        result = await self.mcp_manager.call_tool("playwright", "fill", args)
        
        if result.success:
            return ToolResult(
                success=True,
                data=result.data,
                message=f"Successfully filled element {selector} with text"
            )
        else:
            return result
    
    async def _take_screenshot(self, selector: str = None, options: Dict = None) -> ToolResult:
        """Take a screenshot of the page or element."""
        args = {}
        if selector:
            args["selector"] = selector
        if options:
            args.update(options)
        
        # Ensure screenshots go to playground
        if "path" not in args:
            screenshot_dir = Path.cwd() / "playground" / "screenshots"
            screenshot_dir.mkdir(parents=True, exist_ok=True)
            args["path"] = str(screenshot_dir / f"screenshot_{int(asyncio.get_event_loop().time())}.png")
        
        result = await self.mcp_manager.call_tool("playwright", "screenshot", args)
        
        if result.success:
            return ToolResult(
                success=True,
                data=result.data,
                message=f"Screenshot saved to {args.get('path', 'default location')}"
            )
        else:
            return result
    
    async def _get_text(self, selector: str, options: Dict = None) -> ToolResult:
        """Get text content from an element."""
        if not selector:
            return ToolResult(
                success=False,
                error="Selector required",
                message="CSS selector is required for getting text"
            )
        
        args = {"selector": selector}
        if options:
            args.update(options)
        
        result = await self.mcp_manager.call_tool("playwright", "get_text", args)
        
        if result.success:
            text_content = result.data.get("text", "")
            return ToolResult(
                success=True,
                data={"text": text_content, "selector": selector},
                message=f"Retrieved text from {selector}: {text_content[:100]}{'...' if len(text_content) > 100 else ''}"
            )
        else:
            return result
    
    async def _wait_for_selector(self, selector: str, options: Dict = None) -> ToolResult:
        """Wait for an element to appear."""
        if not selector:
            return ToolResult(
                success=False,
                error="Selector required",
                message="CSS selector is required for waiting"
            )
        
        args = {"selector": selector}
        if options:
            args.update(options)
        
        result = await self.mcp_manager.call_tool("playwright", "wait_for_selector", args)
        
        if result.success:
            return ToolResult(
                success=True,
                data=result.data,
                message=f"Element appeared: {selector}"
            )
        else:
            return result
    
    async def _evaluate_script(self, script: str, options: Dict = None) -> ToolResult:
        """Execute JavaScript in the browser."""
        if not script:
            return ToolResult(
                success=False,
                error="Script required",
                message="JavaScript code is required for evaluation"
            )
        
        args = {"expression": script}
        if options:
            args.update(options)
        
        result = await self.mcp_manager.call_tool("playwright", "evaluate", args)
        
        if result.success:
            return ToolResult(
                success=True,
                data=result.data,
                message="JavaScript executed successfully"
            )
        else:
            return result
    
    async def _new_page(self, options: Dict = None) -> ToolResult:
        """Create a new page in the browser."""
        args = {}
        if options:
            args.update(options)
        
        result = await self.mcp_manager.call_tool("playwright", "new_page", args)
        
        if result.success:
            page_id = result.data.get("page_id")
            return ToolResult(
                success=True,
                data={"page_id": page_id},
                message=f"Created new page (ID: {page_id})"
            )
        else:
            return result
    
    async def _close_page(self, options: Dict = None) -> ToolResult:
        """Close a browser page."""
        args = {}
        if options:
            args.update(options)
        
        result = await self.mcp_manager.call_tool("playwright", "close_page", args)
        
        if result.success:
            return ToolResult(
                success=True,
                data=result.data,
                message="Page closed successfully"
            )
        else:
            return result
    
    async def _close_browser(self, options: Dict = None) -> ToolResult:
        """Close the browser."""
        args = {}
        if options:
            args.update(options)
        
        result = await self.mcp_manager.call_tool("playwright", "close_browser", args)
        
        if result.success:
            return ToolResult(
                success=True,
                data=result.data,
                message="Browser closed successfully"
            )
        else:
            return result


@register_tool(name="mcp_manager", description="Manage MCP server connections and tools")
class MCPManagerTool(BaseTool):
    """Tool for managing MCP servers and their connections."""
    
    def __init__(self):
        super().__init__(
            name="mcp_manager",
            description="Manage MCP server connections, view available tools, and check server status"
        )
        
        self.add_parameter(
            "action",
            "string",
            "Management action to perform",
            required=True,
            enum=["list_servers", "list_tools", "server_info", "health_check", "reconnect"]
        )
        self.add_parameter(
            "server_name",
            "string",
            "Name of specific server (for server_info, health_check, reconnect actions)",
            required=False
        )
        
        self.mcp_manager = None
    
    async def execute(self, action: str, server_name: str = None) -> ToolResult:
        """Execute MCP management action."""
        try:
            # Get MCP manager
            if not self.mcp_manager:
                self.mcp_manager = await get_mcp_manager()
            
            if not self.mcp_manager.is_initialized:
                return ToolResult(
                    success=False,
                    error="MCP not available",
                    message="MCP server manager is not initialized"
                )
            
            print(f"🔧 MCP management: {action}")
            
            if action == "list_servers":
                return await self._list_servers()
            elif action == "list_tools":
                return await self._list_tools()
            elif action == "server_info":
                return await self._server_info(server_name)
            elif action == "health_check":
                return await self._health_check(server_name)
            elif action == "reconnect":
                return await self._reconnect_server(server_name)
            else:
                return ToolResult(
                    success=False,
                    error="Invalid action",
                    message=f"Action '{action}' is not supported"
                )
                
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"MCP management failed: {str(e)}",
                message=f"Failed to execute MCP action: {action}"
            )
    
    async def _list_servers(self) -> ToolResult:
        """List all configured and connected MCP servers."""
        try:
            connected_servers = self.mcp_manager.get_connected_servers()
            server_list = self.mcp_manager.config_loader.get_server_list()
            
            servers_info = []
            for server in server_list:
                server_info = {
                    **server,
                    "connected": server["name"] in connected_servers
                }
                if server_info["connected"]:
                    detailed_info = self.mcp_manager.get_server_info(server["name"])
                    if detailed_info:
                        server_info.update({
                            "tools_count": detailed_info.get("tools_count", 0),
                            "available_tools": detailed_info.get("tools", [])
                        })
                servers_info.append(server_info)
            
            return ToolResult(
                success=True,
                data={
                    "total_servers": len(server_list),
                    "connected_count": len(connected_servers),
                    "servers": servers_info
                },
                message=f"Found {len(server_list)} configured servers, {len(connected_servers)} connected"
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to list servers: {str(e)}",
                message="Could not retrieve server list"
            )
    
    async def _list_tools(self) -> ToolResult:
        """List all available MCP tools."""
        try:
            all_tools = self.mcp_manager.get_all_mcp_tools()
            
            # Group tools by server
            tools_by_server = {}
            for tool in all_tools:
                server = tool["server"]
                if server not in tools_by_server:
                    tools_by_server[server] = []
                tools_by_server[server].append({
                    "name": tool["name"],
                    "description": tool["description"],
                    "full_name": tool["full_name"]
                })
            
            return ToolResult(
                success=True,
                data={
                    "total_tools": len(all_tools),
                    "servers_with_tools": len(tools_by_server),
                    "tools_by_server": tools_by_server,
                    "all_tools": all_tools
                },
                message=f"Found {len(all_tools)} available MCP tools across {len(tools_by_server)} servers"
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to list tools: {str(e)}",
                message="Could not retrieve tool list"
            )
    
    async def _server_info(self, server_name: str) -> ToolResult:
        """Get detailed information about a specific server."""
        if not server_name:
            return ToolResult(
                success=False,
                error="Server name required",
                message="Server name is required for server info"
            )
        
        try:
            server_info = self.mcp_manager.get_server_info(server_name)
            if not server_info:
                return ToolResult(
                    success=False,
                    error="Server not found",
                    message=f"Server '{server_name}' is not connected"
                )
            
            # Add configuration info
            server_config = self.mcp_manager.config_loader.get_server_config(server_name)
            if server_config:
                server_info["configuration"] = {
                    "enabled": server_config.get("enabled", False),
                    "connection_type": server_config["connection"]["type"],
                    "capabilities": server_config.get("capabilities", []),
                    "description": server_config.get("description", "")
                }
            
            return ToolResult(
                success=True,
                data=server_info,
                message=f"Retrieved information for server '{server_name}'"
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to get server info: {str(e)}",
                message=f"Could not retrieve info for server '{server_name}'"
            )
    
    async def _health_check(self, server_name: str) -> ToolResult:
        """Perform health check on a specific server or all servers."""
        try:
            if server_name:
                # Check specific server
                client = self.mcp_manager.clients.get(server_name)
                if not client:
                    return ToolResult(
                        success=False,
                        error="Server not found",
                        message=f"Server '{server_name}' is not connected"
                    )
                
                is_healthy = await client.health_check()
                
                return ToolResult(
                    success=True,
                    data={
                        "server": server_name,
                        "healthy": is_healthy,
                        "connected": client.is_connected
                    },
                    message=f"Server '{server_name}' is {'healthy' if is_healthy else 'unhealthy'}"
                )
            else:
                # Check all servers
                health_results = {}
                for name, client in self.mcp_manager.clients.items():
                    health_results[name] = {
                        "healthy": await client.health_check(),
                        "connected": client.is_connected
                    }
                
                healthy_count = sum(1 for r in health_results.values() if r["healthy"])
                total_count = len(health_results)
                
                return ToolResult(
                    success=True,
                    data={
                        "total_servers": total_count,
                        "healthy_servers": healthy_count,
                        "results": health_results
                    },
                    message=f"Health check complete: {healthy_count}/{total_count} servers healthy"
                )
                
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Health check failed: {str(e)}",
                message="Could not perform health check"
            )
    
    async def _reconnect_server(self, server_name: str) -> ToolResult:
        """Attempt to reconnect to a specific server."""
        if not server_name:
            return ToolResult(
                success=False,
                error="Server name required",
                message="Server name is required for reconnection"
            )
        
        try:
            # This would trigger the reconnection logic in the server manager
            await self.mcp_manager._handle_disconnected_server(server_name)
            
            # Check if reconnection was successful
            client = self.mcp_manager.clients.get(server_name)
            if client and client.is_connected:
                return ToolResult(
                    success=True,
                    data={"server": server_name, "connected": True},
                    message=f"Successfully reconnected to server '{server_name}'"
                )
            else:
                return ToolResult(
                    success=False,
                    error="Reconnection failed",
                    message=f"Failed to reconnect to server '{server_name}'"
                )
                
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Reconnection failed: {str(e)}",
                message=f"Could not reconnect to server '{server_name}'"
            )