"""File operations tool for reading, writing, and managing files."""

import os
import json
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional

from ..base_tool import BaseTool, ToolResult
from ..registry import register_tool


@register_tool(name="file_operations", description="Read, write, and manage files and directories")
class FileOperationsTool(BaseTool):
    """Tool for basic file and directory operations."""
    
    def __init__(self):
        super().__init__(
            name="file_operations",
            description="Perform file and directory operations like reading, writing, listing, and creating files"
        )
        
        # Add parameters
        self.add_parameter(
            "operation",
            "string",
            "The file operation to perform",
            required=True,
            enum=["read", "write", "list", "create_dir", "exists", "info", "delete"]
        )
        self.add_parameter(
            "path",
            "string",
            "The file or directory path",
            required=True
        )
        self.add_parameter(
            "content",
            "string",
            "Content to write (for write operation)",
            required=False
        )
        self.add_parameter(
            "encoding",
            "string",
            "File encoding (default: utf-8)",
            required=False,
            default="utf-8"
        )
        self.add_parameter(
            "max_size",
            "number",
            "Maximum file size to read in bytes (default: 1MB)",
            required=False,
            default=1048576  # 1MB
        )
        
        # Define safe directories (relative to project root)
        self.safe_directories = [
            "audio_logs",
            "conversation_logs", 
            "temp",
            "data",
            "output",
            "playground"
        ]
    
    async def execute(self, 
                     operation: str, 
                     path: str, 
                     content: str = None,
                     encoding: str = "utf-8",
                     max_size: int = 1048576) -> ToolResult:
        """Execute file operation."""
        try:
            # Validate and normalize path
            normalized_path = self._normalize_path(path)
            if not self._is_safe_path(normalized_path):
                return ToolResult(
                    success=False,
                    error="Path not allowed",
                    message=f"Access to path '{path}' is restricted for security reasons"
                )
            
            print(f"📁 File operation: {operation} on {normalized_path}")
            
            # Execute the operation
            if operation == "read":
                return await self._read_file(normalized_path, encoding, max_size)
            elif operation == "write":
                return await self._write_file(normalized_path, content or "", encoding)
            elif operation == "list":
                return await self._list_directory(normalized_path)
            elif operation == "create_dir":
                return await self._create_directory(normalized_path)
            elif operation == "exists":
                return await self._check_exists(normalized_path)
            elif operation == "info":
                return await self._get_info(normalized_path)
            elif operation == "delete":
                return await self._delete_path(normalized_path)
            else:
                return ToolResult(
                    success=False,
                    error="Invalid operation",
                    message=f"Operation '{operation}' is not supported"
                )
                
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"File operation failed: {str(e)}",
                message=f"Failed to {operation} {path}"
            )
    
    def _normalize_path(self, path: str) -> Path:
        """Normalize and resolve path."""
        # Convert to Path object and resolve
        path_obj = Path(path).expanduser().resolve()
        return path_obj
    
    def _is_safe_path(self, path: Path) -> bool:
        """Check if path is safe to access."""
        try:
            # Get current working directory
            cwd = Path.cwd()
            
            # Check if path is within current working directory
            try:
                path.relative_to(cwd)
                # Path is within cwd, check if it's in safe directories
                relative_path = path.relative_to(cwd)
                first_part = str(relative_path).split(os.sep)[0] if str(relative_path) != "." else "."
                
                # Allow access to safe directories or current directory files
                if first_part in self.safe_directories or first_part == "." or not os.sep in str(relative_path):
                    return True
                
            except ValueError:
                # Path is outside cwd, not allowed
                return False
            
            return False
            
        except Exception:
            return False
    
    async def _read_file(self, path: Path, encoding: str, max_size: int) -> ToolResult:
        """Read a file."""
        try:
            if not path.exists():
                return ToolResult(
                    success=False,
                    error="File not found",
                    message=f"File {path} does not exist"
                )
            
            if not path.is_file():
                return ToolResult(
                    success=False,
                    error="Not a file",
                    message=f"{path} is not a file"
                )
            
            # Check file size
            file_size = path.stat().st_size
            if file_size > max_size:
                return ToolResult(
                    success=False,
                    error="File too large",
                    message=f"File size ({file_size} bytes) exceeds maximum allowed size ({max_size} bytes)"
                )
            
            # Read file
            content = await asyncio.to_thread(path.read_text, encoding=encoding)
            
            return ToolResult(
                success=True,
                data={
                    "path": str(path),
                    "content": content,
                    "size": file_size,
                    "encoding": encoding
                },
                message=f"Successfully read file {path} ({file_size} bytes)"
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to read file: {str(e)}",
                message=f"Could not read {path}"
            )
    
    async def _write_file(self, path: Path, content: str, encoding: str) -> ToolResult:
        """Write content to a file."""
        try:
            # Create parent directory if it doesn't exist
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write file
            await asyncio.to_thread(path.write_text, content, encoding=encoding)
            
            file_size = path.stat().st_size
            
            return ToolResult(
                success=True,
                data={
                    "path": str(path),
                    "size": file_size,
                    "encoding": encoding
                },
                message=f"Successfully wrote {file_size} bytes to {path}"
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to write file: {str(e)}",
                message=f"Could not write to {path}"
            )
    
    async def _list_directory(self, path: Path) -> ToolResult:
        """List directory contents."""
        try:
            if not path.exists():
                return ToolResult(
                    success=False,
                    error="Directory not found",
                    message=f"Directory {path} does not exist"
                )
            
            if not path.is_dir():
                return ToolResult(
                    success=False,
                    error="Not a directory",
                    message=f"{path} is not a directory"
                )
            
            # List contents
            items = []
            for item in path.iterdir():
                try:
                    stat = item.stat()
                    items.append({
                        "name": item.name,
                        "path": str(item),
                        "type": "directory" if item.is_dir() else "file",
                        "size": stat.st_size if item.is_file() else None,
                        "modified": stat.st_mtime
                    })
                except Exception:
                    # Skip items we can't access
                    continue
            
            # Sort by name
            items.sort(key=lambda x: x["name"].lower())
            
            return ToolResult(
                success=True,
                data={
                    "path": str(path),
                    "items": items,
                    "count": len(items)
                },
                message=f"Listed {len(items)} items in {path}"
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to list directory: {str(e)}",
                message=f"Could not list {path}"
            )
    
    async def _create_directory(self, path: Path) -> ToolResult:
        """Create a directory."""
        try:
            path.mkdir(parents=True, exist_ok=True)
            
            return ToolResult(
                success=True,
                data={"path": str(path)},
                message=f"Successfully created directory {path}"
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to create directory: {str(e)}",
                message=f"Could not create {path}"
            )
    
    async def _check_exists(self, path: Path) -> ToolResult:
        """Check if path exists."""
        try:
            exists = path.exists()
            path_type = None
            
            if exists:
                if path.is_file():
                    path_type = "file"
                elif path.is_dir():
                    path_type = "directory"
                else:
                    path_type = "other"
            
            return ToolResult(
                success=True,
                data={
                    "path": str(path),
                    "exists": exists,
                    "type": path_type
                },
                message=f"Path {path} {'exists' if exists else 'does not exist'}"
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to check path: {str(e)}",
                message=f"Could not check {path}"
            )
    
    async def _get_info(self, path: Path) -> ToolResult:
        """Get path information."""
        try:
            if not path.exists():
                return ToolResult(
                    success=False,
                    error="Path not found",
                    message=f"Path {path} does not exist"
                )
            
            stat = path.stat()
            
            info = {
                "path": str(path),
                "name": path.name,
                "parent": str(path.parent),
                "exists": True,
                "type": "directory" if path.is_dir() else "file",
                "size": stat.st_size if path.is_file() else None,
                "created": stat.st_ctime,
                "modified": stat.st_mtime,
                "accessed": stat.st_atime
            }
            
            return ToolResult(
                success=True,
                data=info,
                message=f"Retrieved information for {path}"
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to get info: {str(e)}",
                message=f"Could not get info for {path}"
            )
    
    async def _delete_path(self, path: Path) -> ToolResult:
        """Delete a file or directory."""
        try:
            if not path.exists():
                return ToolResult(
                    success=False,
                    error="Path not found",
                    message=f"Path {path} does not exist"
                )
            
            if path.is_file():
                path.unlink()
                message = f"Deleted file {path}"
            elif path.is_dir():
                # Only delete if empty
                if any(path.iterdir()):
                    return ToolResult(
                        success=False,
                        error="Directory not empty",
                        message=f"Directory {path} is not empty. Only empty directories can be deleted."
                    )
                path.rmdir()
                message = f"Deleted directory {path}"
            else:
                return ToolResult(
                    success=False,
                    error="Unknown path type",
                    message=f"Cannot delete {path}: unknown path type"
                )
            
            return ToolResult(
                success=True,
                data={"path": str(path)},
                message=message
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to delete: {str(e)}",
                message=f"Could not delete {path}"
            )