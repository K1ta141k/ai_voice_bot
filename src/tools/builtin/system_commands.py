"""System commands tool for executing safe system operations."""

import asyncio
import subprocess
import shutil
import platform
from typing import Dict, Any, List, Optional
from pathlib import Path

from ..base_tool import BaseTool, ToolResult
from ..registry import register_tool


@register_tool(name="system_commands", description="Execute safe system commands and operations")
class SystemCommandsTool(BaseTool):
    """Tool for executing safe system commands and getting system information."""
    
    def __init__(self):
        super().__init__(
            name="system_commands",
            description="Execute safe system commands, get system information, and perform basic system operations"
        )
        
        # Add parameters
        self.add_parameter(
            "operation",
            "string",
            "The system operation to perform",
            required=True,
            enum=["info", "disk_usage", "process_list", "network_info", "execute_safe", "which", "env_var"]
        )
        self.add_parameter(
            "command",
            "string",
            "Command to execute (for execute_safe operation)",
            required=False
        )
        self.add_parameter(
            "args",
            "string",
            "Command arguments (for execute_safe operation)",
            required=False
        )
        self.add_parameter(
            "path",
            "string",
            "Path for disk usage or directory operations",
            required=False
        )
        self.add_parameter(
            "variable",
            "string",
            "Environment variable name (for env_var operation)",
            required=False
        )
        self.add_parameter(
            "timeout",
            "number",
            "Command timeout in seconds (default: 30)",
            required=False,
            default=30
        )
        
        # Define safe commands that are allowed to execute
        self.safe_commands = {
            "ls", "dir", "pwd", "whoami", "date", "echo", "cat", "head", "tail",
            "grep", "find", "wc", "sort", "uniq", "du", "df", "free", "uptime",
            "uname", "hostname", "ps", "top", "netstat", "ping", "curl", "wget",
            "git", "python", "node", "npm", "pip", "which", "where", "type"
        }
    
    async def execute(self,
                     operation: str,
                     command: str = None,
                     args: str = None,
                     path: str = None,
                     variable: str = None,
                     timeout: int = 30) -> ToolResult:
        """Execute system operation."""
        try:
            print(f"⚡ System operation: {operation}")
            
            if operation == "info":
                return await self._get_system_info()
            elif operation == "disk_usage":
                return await self._get_disk_usage(path)
            elif operation == "process_list":
                return await self._get_process_list()
            elif operation == "network_info":
                return await self._get_network_info()
            elif operation == "execute_safe":
                return await self._execute_safe_command(command, args, timeout)
            elif operation == "which":
                return await self._which_command(command)
            elif operation == "env_var":
                return await self._get_env_var(variable)
            else:
                return ToolResult(
                    success=False,
                    error="Invalid operation",
                    message=f"Operation '{operation}' is not supported"
                )
                
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"System operation failed: {str(e)}",
                message=f"Failed to execute {operation}"
            )
    
    async def _get_system_info(self) -> ToolResult:
        """Get basic system information."""
        try:
            info = {
                "platform": platform.platform(),
                "system": platform.system(),
                "node": platform.node(),
                "release": platform.release(),
                "version": platform.version(),
                "machine": platform.machine(),
                "processor": platform.processor(),
                "python_version": platform.python_version(),
                "cwd": str(Path.cwd())
            }
            
            return ToolResult(
                success=True,
                data=info,
                message="Retrieved system information"
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to get system info: {str(e)}",
                message="Could not retrieve system information"
            )
    
    async def _get_disk_usage(self, path: str = None) -> ToolResult:
        """Get disk usage information."""
        try:
            target_path = Path(path) if path else Path.cwd()
            
            if not target_path.exists():
                return ToolResult(
                    success=False,
                    error="Path not found",
                    message=f"Path {target_path} does not exist"
                )
            
            # Get disk usage
            if hasattr(shutil, 'disk_usage'):
                total, used, free = shutil.disk_usage(target_path)
                
                usage_info = {
                    "path": str(target_path),
                    "total_bytes": total,
                    "used_bytes": used,
                    "free_bytes": free,
                    "total_gb": round(total / (1024**3), 2),
                    "used_gb": round(used / (1024**3), 2),
                    "free_gb": round(free / (1024**3), 2),
                    "usage_percent": round((used / total) * 100, 2) if total > 0 else 0
                }
                
                return ToolResult(
                    success=True,
                    data=usage_info,
                    message=f"Retrieved disk usage for {target_path}"
                )
            else:
                return ToolResult(
                    success=False,
                    error="Disk usage not available",
                    message="Disk usage information is not available on this system"
                )
                
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to get disk usage: {str(e)}",
                message="Could not retrieve disk usage information"
            )
    
    async def _get_process_list(self) -> ToolResult:
        """Get basic process list information."""
        try:
            # Use ps command on Unix-like systems, tasklist on Windows
            if platform.system().lower() == "windows":
                cmd = ["tasklist", "/fo", "csv"]
            else:
                cmd = ["ps", "aux"]
            
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            stdout, stderr = await result.communicate()
            
            if result.returncode == 0:
                output = stdout.decode('utf-8', errors='ignore')
                lines = output.split('\n')[:20]  # Limit to first 20 processes
                
                return ToolResult(
                    success=True,
                    data={
                        "command": " ".join(cmd),
                        "process_count": len(lines) - 1,  # Minus header
                        "output": lines
                    },
                    message=f"Retrieved process list ({len(lines) - 1} processes shown)"
                )
            else:
                error = stderr.decode('utf-8', errors='ignore')
                return ToolResult(
                    success=False,
                    error=f"Command failed: {error}",
                    message="Could not retrieve process list"
                )
                
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to get process list: {str(e)}",
                message="Could not retrieve process information"
            )
    
    async def _get_network_info(self) -> ToolResult:
        """Get basic network information."""
        try:
            # Get hostname
            hostname = platform.node()
            
            # Try to get IP information using a safe command
            if platform.system().lower() == "windows":
                cmd = ["ipconfig"]
            else:
                cmd = ["hostname", "-I"]
            
            try:
                result = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                
                stdout, stderr = await result.communicate()
                
                if result.returncode == 0:
                    ip_info = stdout.decode('utf-8', errors='ignore').strip()
                else:
                    ip_info = "Not available"
                    
            except Exception:
                ip_info = "Not available"
            
            network_info = {
                "hostname": hostname,
                "ip_info": ip_info,
                "platform": platform.system()
            }
            
            return ToolResult(
                success=True,
                data=network_info,
                message="Retrieved network information"
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to get network info: {str(e)}",
                message="Could not retrieve network information"
            )
    
    async def _execute_safe_command(self, command: str, args: str = None, timeout: int = 30) -> ToolResult:
        """Execute a safe command."""
        try:
            if not command:
                return ToolResult(
                    success=False,
                    error="No command provided",
                    message="Please specify a command to execute"
                )
            
            # Check if command is in safe list
            base_command = command.split()[0] if ' ' in command else command
            if base_command not in self.safe_commands:
                return ToolResult(
                    success=False,
                    error="Command not allowed",
                    message=f"Command '{base_command}' is not in the list of safe commands"
                )
            
            # Prepare command
            cmd_parts = command.split()
            if args:
                cmd_parts.extend(args.split())
            
            print(f"🔧 Executing safe command: {' '.join(cmd_parts)}")
            
            # Execute command with timeout
            result = await asyncio.create_subprocess_exec(
                *cmd_parts,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=Path.cwd()
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    result.communicate(),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                result.kill()
                await result.wait()
                return ToolResult(
                    success=False,
                    error="Command timeout",
                    message=f"Command timed out after {timeout} seconds"
                )
            
            # Process results
            output = stdout.decode('utf-8', errors='ignore')
            error_output = stderr.decode('utf-8', errors='ignore')
            
            if result.returncode == 0:
                return ToolResult(
                    success=True,
                    data={
                        "command": ' '.join(cmd_parts),
                        "return_code": result.returncode,
                        "output": output,
                        "error": error_output if error_output else None
                    },
                    message=f"Command executed successfully (return code: {result.returncode})"
                )
            else:
                return ToolResult(
                    success=False,
                    data={
                        "command": ' '.join(cmd_parts),
                        "return_code": result.returncode,
                        "output": output if output else None,
                        "error": error_output
                    },
                    error=f"Command failed with return code {result.returncode}",
                    message=f"Command execution failed: {error_output[:200]}..."
                )
                
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to execute command: {str(e)}",
                message="Could not execute the command"
            )
    
    async def _which_command(self, command: str) -> ToolResult:
        """Find the location of a command."""
        try:
            if not command:
                return ToolResult(
                    success=False,
                    error="No command provided",
                    message="Please specify a command to locate"
                )
            
            # Use shutil.which for cross-platform compatibility
            location = shutil.which(command)
            
            if location:
                return ToolResult(
                    success=True,
                    data={
                        "command": command,
                        "location": location,
                        "exists": True
                    },
                    message=f"Command '{command}' found at: {location}"
                )
            else:
                return ToolResult(
                    success=True,
                    data={
                        "command": command,
                        "location": None,
                        "exists": False
                    },
                    message=f"Command '{command}' not found in PATH"
                )
                
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to locate command: {str(e)}",
                message="Could not locate the command"
            )
    
    async def _get_env_var(self, variable: str) -> ToolResult:
        """Get environment variable value."""
        try:
            if not variable:
                return ToolResult(
                    success=False,
                    error="No variable provided",
                    message="Please specify an environment variable name"
                )
            
            import os
            value = os.environ.get(variable)
            
            return ToolResult(
                success=True,
                data={
                    "variable": variable,
                    "value": value,
                    "exists": value is not None
                },
                message=f"Environment variable '{variable}' {'found' if value else 'not found'}"
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to get environment variable: {str(e)}",
                message="Could not retrieve environment variable"
            )