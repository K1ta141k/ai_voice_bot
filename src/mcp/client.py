"""MCP client for communicating with MCP servers."""

import asyncio
import json
import logging
import subprocess
import time
from typing import Dict, Any, List, Optional, Callable
from pathlib import Path
import aiohttp


class MCPClient:
    """Client for communicating with MCP servers via different transports."""
    
    def __init__(self, server_config: Dict[str, Any]):
        self.server_config = server_config
        self.server_name = server_config.get("name", "unknown")
        self.connection_config = server_config["connection"]
        self.logger = logging.getLogger(f"{__name__}.{self.server_name}")
        
        self.is_connected = False
        self.connection = None
        self.process = None
        self.tools = {}
        self.resources = {}
        
        # Connection tracking
        self.last_health_check = 0
        self.connection_attempts = 0
        self.max_retries = server_config.get("connection_retry_attempts", 3)
    
    async def connect(self) -> bool:
        """Connect to the MCP server."""
        try:
            connection_type = self.connection_config["type"]
            
            if connection_type == "stdio":
                return await self._connect_stdio()
            elif connection_type == "http":
                return await self._connect_http()
            elif connection_type == "websocket":
                return await self._connect_websocket()
            else:
                self.logger.error(f"Unsupported connection type: {connection_type}")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to connect to MCP server: {e}")
            return False
    
    async def _connect_stdio(self) -> bool:
        """Connect via STDIO (subprocess)."""
        try:
            command = self.connection_config["command"]
            args = self.connection_config.get("args", [])
            cwd = self.connection_config.get("cwd", ".")
            timeout = self.connection_config.get("timeout", 30)
            
            # Build full command
            full_command = [command] + args
            
            self.logger.info(f"Starting MCP server process: {' '.join(full_command)}")
            
            # Start the process
            self.process = await asyncio.create_subprocess_exec(
                *full_command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd
            )
            
            # Wait for process to start and initialize
            await asyncio.sleep(1)
            
            if self.process.returncode is not None:
                stderr_output = await self.process.stderr.read()
                error_msg = stderr_output.decode() if stderr_output else "Process exited early"
                self.logger.error(f"MCP server process failed to start: {error_msg}")
                return False
            
            # Initialize MCP protocol
            if await self._initialize_mcp():
                self.is_connected = True
                self.logger.info(f"Successfully connected to MCP server via STDIO")
                return True
            else:
                await self.disconnect()
                return False
                
        except Exception as e:
            self.logger.error(f"STDIO connection failed: {e}")
            if self.process:
                try:
                    self.process.terminate()
                    await self.process.wait()
                except:
                    pass
            return False
    
    async def _connect_http(self) -> bool:
        """Connect via HTTP."""
        try:
            host = self.connection_config["host"]
            port = self.connection_config["port"]
            protocol = self.connection_config.get("protocol", "http")
            timeout = self.connection_config.get("timeout", 15)
            
            self.base_url = f"{protocol}://{host}:{port}"
            
            # Create HTTP session
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=timeout)
            )
            
            # Test connection with health check
            async with self.session.get(f"{self.base_url}/health") as response:
                if response.status == 200:
                    self.is_connected = True
                    self.logger.info(f"Successfully connected to MCP server via HTTP at {self.base_url}")
                    
                    # Initialize tools
                    await self._discover_tools_http()
                    return True
                else:
                    self.logger.error(f"HTTP health check failed: {response.status}")
                    await self.session.close()
                    return False
                    
        except Exception as e:
            self.logger.error(f"HTTP connection failed: {e}")
            if hasattr(self, 'session'):
                await self.session.close()
            return False
    
    async def _connect_websocket(self) -> bool:
        """Connect via WebSocket."""
        # WebSocket implementation would go here
        self.logger.warning("WebSocket connection not yet implemented")
        return False
    
    async def _initialize_mcp(self) -> bool:
        """Initialize MCP protocol and discover tools."""
        try:
            # Send initialization message
            init_message = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {},
                        "resources": {}
                    },
                    "clientInfo": {
                        "name": "ai-voice-bot",
                        "version": "1.0.0"
                    }
                }
            }
            
            response = await self._send_message(init_message)
            if not response or "error" in response:
                self.logger.error(f"MCP initialization failed: {response}")
                return False
            
            # Send initialized notification
            initialized_message = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {}
            }
            
            await self._send_notification(initialized_message)
            
            # Discover available tools
            await self._discover_tools()
            
            return True
            
        except Exception as e:
            self.logger.error(f"MCP initialization failed: {e}")
            return False
    
    async def _discover_tools(self) -> bool:
        """Discover available tools from the MCP server."""
        try:
            tools_message = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {}
            }
            
            response = await self._send_message(tools_message)
            if response and "result" in response:
                tools_list = response["result"].get("tools", [])
                
                for tool in tools_list:
                    tool_name = tool.get("name")
                    if tool_name:
                        self.tools[tool_name] = tool
                        self.logger.debug(f"Discovered tool: {tool_name}")
                
                self.logger.info(f"Discovered {len(self.tools)} tools from MCP server")
                return True
            else:
                self.logger.warning("No tools discovered from MCP server")
                return True  # Not necessarily an error
                
        except Exception as e:
            self.logger.error(f"Tool discovery failed: {e}")
            return False
    
    async def _discover_tools_http(self) -> bool:
        """Discover tools via HTTP endpoint."""
        try:
            async with self.session.get(f"{self.base_url}/tools") as response:
                if response.status == 200:
                    tools_data = await response.json()
                    tools_list = tools_data.get("tools", [])
                    
                    for tool in tools_list:
                        tool_name = tool.get("name")
                        if tool_name:
                            self.tools[tool_name] = tool
                    
                    self.logger.info(f"Discovered {len(self.tools)} tools via HTTP")
                    return True
                else:
                    self.logger.warning(f"HTTP tools discovery failed: {response.status}")
                    return True
                    
        except Exception as e:
            self.logger.error(f"HTTP tool discovery failed: {e}")
            return False
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool on the MCP server."""
        try:
            if not self.is_connected:
                return {
                    "success": False,
                    "error": "MCP client not connected"
                }
            
            if tool_name not in self.tools:
                return {
                    "success": False,
                    "error": f"Tool '{tool_name}' not found"
                }
            
            if hasattr(self, 'session'):  # HTTP connection
                return await self._call_tool_http(tool_name, arguments)
            else:  # STDIO connection
                return await self._call_tool_stdio(tool_name, arguments)
                
        except Exception as e:
            self.logger.error(f"Tool call failed: {e}")
            return {
                "success": False,
                "error": f"Tool execution failed: {str(e)}"
            }
    
    async def _call_tool_stdio(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call tool via STDIO connection."""
        message = {
            "jsonrpc": "2.0",
            "id": int(time.time() * 1000),
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }
        
        response = await self._send_message(message)
        
        if response and "result" in response:
            return {
                "success": True,
                "result": response["result"]
            }
        elif response and "error" in response:
            return {
                "success": False,
                "error": response["error"].get("message", "Unknown error")
            }
        else:
            return {
                "success": False,
                "error": "No response from MCP server"
            }
    
    async def _call_tool_http(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call tool via HTTP connection."""
        payload = {
            "name": tool_name,
            "arguments": arguments
        }
        
        async with self.session.post(
            f"{self.base_url}/tools/call",
            json=payload
        ) as response:
            if response.status == 200:
                result = await response.json()
                return {
                    "success": True,
                    "result": result
                }
            else:
                error_text = await response.text()
                return {
                    "success": False,
                    "error": f"HTTP {response.status}: {error_text}"
                }
    
    async def _send_message(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Send a message to the MCP server and wait for response."""
        if not self.process or self.process.returncode is not None:
            return None
        
        try:
            # Send message
            message_json = json.dumps(message) + "\n"
            self.process.stdin.write(message_json.encode())
            await self.process.stdin.drain()
            
            # Read response
            response_line = await asyncio.wait_for(
                self.process.stdout.readline(),
                timeout=30.0
            )
            
            if not response_line:
                return None
            
            response = json.loads(response_line.decode().strip())
            return response
            
        except Exception as e:
            self.logger.error(f"Message send/receive failed: {e}")
            return None
    
    async def _send_notification(self, message: Dict[str, Any]):
        """Send a notification (no response expected)."""
        if not self.process or self.process.returncode is not None:
            return
        
        try:
            message_json = json.dumps(message) + "\n"
            self.process.stdin.write(message_json.encode())
            await self.process.stdin.drain()
        except Exception as e:
            self.logger.error(f"Notification send failed: {e}")
    
    async def health_check(self) -> bool:
        """Perform health check on the connection."""
        try:
            if hasattr(self, 'session'):  # HTTP
                async with self.session.get(f"{self.base_url}/health") as response:
                    return response.status == 200
            else:  # STDIO
                if not self.process or self.process.returncode is not None:
                    return False
                
                # Send simple ping
                ping_message = {
                    "jsonrpc": "2.0",
                    "id": 999999,
                    "method": "ping",
                    "params": {}
                }
                
                response = await self._send_message(ping_message)
                return response is not None
                
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from the MCP server."""
        try:
            self.is_connected = False
            
            if hasattr(self, 'session'):
                await self.session.close()
            
            if self.process:
                try:
                    self.process.terminate()
                    await asyncio.wait_for(self.process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    self.process.kill()
                    await self.process.wait()
                except Exception:
                    pass
                finally:
                    self.process = None
            
            self.logger.info(f"Disconnected from MCP server")
            
        except Exception as e:
            self.logger.error(f"Disconnect failed: {e}")
    
    def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get list of available tools."""
        return list(self.tools.values())
    
    def get_tool_schema(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Get schema for a specific tool."""
        return self.tools.get(tool_name)