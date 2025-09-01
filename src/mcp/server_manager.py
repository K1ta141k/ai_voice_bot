"""MCP server management and coordination."""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path

from .config_loader import MCPConfigLoader
from .client import MCPClient
from ..tools.base_tool import BaseTool, ToolResult
from ..tools.registry import register_tool


class MCPServerManager:
    """Manages multiple MCP server connections and coordinates tool execution."""
    
    def __init__(self, config_path: str = None):
        self.logger = logging.getLogger(__name__)
        self.config_loader = MCPConfigLoader(config_path)
        self.clients: Dict[str, MCPClient] = {}
        self.is_initialized = False
        
        # Health monitoring
        self.health_check_task = None
        self.health_check_interval = 30  # seconds
    
    async def initialize(self) -> bool:
        """Initialize the MCP server manager."""
        try:
            self.logger.info("Initializing MCP server manager...")
            
            # Load configuration
            config = self.config_loader.load_config()
            if not config:
                self.logger.error("Failed to load MCP configuration")
                return False
            
            # Get global settings
            global_settings = self.config_loader.get_global_settings()
            self.health_check_interval = global_settings.get("health_check_interval", 30000) // 1000
            
            # Connect to enabled servers
            enabled_servers = self.config_loader.get_enabled_servers()
            
            if not enabled_servers:
                self.logger.warning("No MCP servers are enabled")
                self.is_initialized = True
                return True
            
            connection_tasks = []
            for server_name, server_config in enabled_servers.items():
                task = self._connect_server(server_name, server_config)
                connection_tasks.append(task)
            
            # Wait for all connections (with some allowed failures)
            results = await asyncio.gather(*connection_tasks, return_exceptions=True)
            
            successful_connections = sum(1 for result in results if result is True)
            total_servers = len(enabled_servers)
            
            self.logger.info(f"Connected to {successful_connections}/{total_servers} MCP servers")
            
            # Start health monitoring
            if self.clients:
                self.health_check_task = asyncio.create_task(self._health_monitor())
            
            self.is_initialized = True
            return successful_connections > 0
            
        except Exception as e:
            self.logger.error(f"MCP server manager initialization failed: {e}")
            return False
    
    async def _connect_server(self, server_name: str, server_config: Dict[str, Any]) -> bool:
        """Connect to a single MCP server."""
        try:
            self.logger.info(f"Connecting to MCP server: {server_name}")
            
            client = MCPClient(server_config)
            
            if await client.connect():
                self.clients[server_name] = client
                self.logger.info(f"Successfully connected to {server_name}")
                
                # Register MCP tools with our tool system
                await self._register_mcp_tools(server_name, client)
                
                return True
            else:
                self.logger.error(f"Failed to connect to {server_name}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error connecting to {server_name}: {e}")
            return False
    
    async def _register_mcp_tools(self, server_name: str, client: MCPClient):
        """Register MCP server tools with our tool registry."""
        try:
            tools = client.get_available_tools()
            
            for tool_info in tools:
                tool_name = tool_info.get("name")
                if not tool_name:
                    continue
                
                # Create a dynamic tool class for this MCP tool
                mcp_tool_class = self._create_mcp_tool_class(
                    server_name, 
                    tool_name, 
                    tool_info, 
                    client
                )
                
                # Register the tool
                full_tool_name = f"{server_name}_{tool_name}"
                register_tool(
                    name=full_tool_name,
                    description=tool_info.get("description", f"MCP tool: {tool_name}")
                )(mcp_tool_class)
                
                self.logger.debug(f"Registered MCP tool: {full_tool_name}")
            
            self.logger.info(f"Registered {len(tools)} tools from {server_name}")
            
        except Exception as e:
            self.logger.error(f"Failed to register tools from {server_name}: {e}")
    
    def _create_mcp_tool_class(self, server_name: str, tool_name: str, tool_info: Dict[str, Any], client: MCPClient):
        """Dynamically create a tool class for an MCP tool."""
        
        class MCPTool(BaseTool):
            def __init__(self):
                full_name = f"{server_name}_{tool_name}"
                description = tool_info.get("description", f"MCP tool: {tool_name} from {server_name}")
                
                super().__init__(name=full_name, description=description)
                
                self.server_name = server_name
                self.mcp_tool_name = tool_name
                self.mcp_client = client
                
                # Add parameters from tool schema
                input_schema = tool_info.get("inputSchema", {})
                properties = input_schema.get("properties", {})
                required_fields = input_schema.get("required", [])
                
                for param_name, param_info in properties.items():
                    param_type = param_info.get("type", "string")
                    param_description = param_info.get("description", f"Parameter: {param_name}")
                    is_required = param_name in required_fields
                    
                    self.add_parameter(
                        param_name,
                        param_type,
                        param_description,
                        required=is_required
                    )
            
            async def execute(self, **kwargs) -> ToolResult:
                """Execute the MCP tool."""
                try:
                    # Call the MCP server
                    result = await self.mcp_client.call_tool(self.mcp_tool_name, kwargs)
                    
                    if result.get("success", False):
                        return ToolResult(
                            success=True,
                            data=result.get("result", {}),
                            message=f"MCP tool {self.mcp_tool_name} executed successfully"
                        )
                    else:
                        return ToolResult(
                            success=False,
                            error=result.get("error", "Unknown MCP error"),
                            message=f"MCP tool {self.mcp_tool_name} failed"
                        )
                        
                except Exception as e:
                    return ToolResult(
                        success=False,
                        error=f"MCP tool execution failed: {str(e)}",
                        message=f"Failed to execute MCP tool {self.mcp_tool_name}"
                    )
        
        return MCPTool
    
    async def _health_monitor(self):
        """Monitor health of connected MCP servers."""
        while True:
            try:
                await asyncio.sleep(self.health_check_interval)
                
                # Check each client
                disconnected_servers = []
                
                for server_name, client in self.clients.items():
                    if not await client.health_check():
                        self.logger.warning(f"Health check failed for {server_name}")
                        disconnected_servers.append(server_name)
                
                # Handle disconnected servers
                for server_name in disconnected_servers:
                    await self._handle_disconnected_server(server_name)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Health monitor error: {e}")
    
    async def _handle_disconnected_server(self, server_name: str):
        """Handle a disconnected MCP server."""
        try:
            self.logger.info(f"Attempting to reconnect to {server_name}")
            
            # Get server config
            server_config = self.config_loader.get_server_config(server_name)
            if not server_config or not server_config.get("enabled", False):
                # Server was disabled, remove it
                if server_name in self.clients:
                    await self.clients[server_name].disconnect()
                    del self.clients[server_name]
                return
            
            # Attempt reconnection
            old_client = self.clients.get(server_name)
            if old_client:
                await old_client.disconnect()
            
            # Create new client and attempt connection
            if await self._connect_server(server_name, server_config):
                self.logger.info(f"Successfully reconnected to {server_name}")
            else:
                self.logger.error(f"Failed to reconnect to {server_name}")
                # Remove failed client
                if server_name in self.clients:
                    del self.clients[server_name]
                    
        except Exception as e:
            self.logger.error(f"Error handling disconnected server {server_name}: {e}")
    
    async def call_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any], user_id: str = None) -> ToolResult:
        """Call a tool on a specific MCP server."""
        try:
            # Check permissions
            if user_id:
                if not self.config_loader.is_server_allowed_for_user(user_id, server_name):
                    return ToolResult(
                        success=False,
                        error="Access denied",
                        message=f"User {user_id} not allowed to use server {server_name}"
                    )
            
            # Get client
            client = self.clients.get(server_name)
            if not client or not client.is_connected:
                return ToolResult(
                    success=False,
                    error="Server not available",
                    message=f"MCP server {server_name} is not connected"
                )
            
            # Call tool
            result = await client.call_tool(tool_name, arguments)
            
            if result.get("success", False):
                return ToolResult(
                    success=True,
                    data=result.get("result", {}),
                    message=f"MCP tool executed successfully"
                )
            else:
                return ToolResult(
                    success=False,
                    error=result.get("error", "Unknown error"),
                    message=f"MCP tool execution failed"
                )
                
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"MCP tool call failed: {str(e)}",
                message="Failed to execute MCP tool"
            )
    
    def get_connected_servers(self) -> List[str]:
        """Get list of connected server names."""
        return [name for name, client in self.clients.items() if client.is_connected]
    
    def get_server_info(self, server_name: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific server."""
        client = self.clients.get(server_name)
        if not client:
            return None
        
        return {
            "name": server_name,
            "connected": client.is_connected,
            "tools_count": len(client.tools),
            "tools": list(client.tools.keys())
        }
    
    def get_all_mcp_tools(self, user_id: str = None) -> List[Dict[str, Any]]:
        """Get all available MCP tools."""
        all_tools = []
        
        for server_name, client in self.clients.items():
            if not client.is_connected:
                continue
            
            # Check permissions
            if user_id and not self.config_loader.is_server_allowed_for_user(user_id, server_name):
                continue
            
            for tool_name, tool_info in client.tools.items():
                all_tools.append({
                    "server": server_name,
                    "name": tool_name,
                    "full_name": f"{server_name}_{tool_name}",
                    "description": tool_info.get("description", ""),
                    "schema": tool_info
                })
        
        return all_tools
    
    async def shutdown(self):
        """Shutdown all MCP connections."""
        try:
            self.logger.info("Shutting down MCP server manager...")
            
            # Cancel health monitoring
            if self.health_check_task:
                self.health_check_task.cancel()
                try:
                    await self.health_check_task
                except asyncio.CancelledError:
                    pass
            
            # Disconnect all clients
            disconnect_tasks = []
            for client in self.clients.values():
                disconnect_tasks.append(client.disconnect())
            
            if disconnect_tasks:
                await asyncio.gather(*disconnect_tasks, return_exceptions=True)
            
            self.clients.clear()
            self.is_initialized = False
            
            self.logger.info("MCP server manager shutdown complete")
            
        except Exception as e:
            self.logger.error(f"MCP server manager shutdown error: {e}")


# Global MCP server manager instance
mcp_manager: Optional[MCPServerManager] = None


async def get_mcp_manager(config_path: str = None) -> MCPServerManager:
    """Get or create the global MCP server manager instance."""
    global mcp_manager
    
    if mcp_manager is None:
        mcp_manager = MCPServerManager(config_path)
        await mcp_manager.initialize()
    
    return mcp_manager