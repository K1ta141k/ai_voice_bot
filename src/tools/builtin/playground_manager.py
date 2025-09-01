"""Playground file management tool for safe AI file operations."""

import os
import json
import asyncio
import shutil
import mimetypes
from pathlib import Path
from typing import Dict, Any, List, Optional, Union

from ..base_tool import BaseTool, ToolResult
from ..registry import register_tool


@register_tool(name="playground_manager", description="Safe file and media operations within playground directory")
class PlaygroundManagerTool(BaseTool):
    """Tool for managing files and media within the playground directory."""
    
    def __init__(self):
        super().__init__(
            name="playground_manager",
            description="Create, edit, delete files and manage media (images, videos, music) within the safe playground directory"
        )
        
        # Add parameters
        self.add_parameter(
            "operation",
            "string",
            "The operation to perform",
            required=True,
            enum=[
                "create_file", "edit_file", "delete_file", "copy_file", "move_file",
                "create_dir", "delete_dir", "list_dir",
                "save_image", "save_audio", "save_video", "save_binary",
                "get_media_info", "cleanup", "get_stats"
            ]
        )
        self.add_parameter(
            "path",
            "string",
            "Path within playground (relative to playground/)",
            required=True
        )
        self.add_parameter(
            "content",
            "string", 
            "File content, base64 data, or source path",
            required=False
        )
        self.add_parameter(
            "encoding",
            "string",
            "File encoding for text files (default: utf-8)",
            required=False,
            default="utf-8"
        )
        self.add_parameter(
            "format",
            "string",
            "Media format/extension (auto-detected if not provided)",
            required=False
        )
        self.add_parameter(
            "metadata",
            "object",
            "Additional metadata for media files",
            required=False
        )
        
        # Initialize playground directory
        self.playground_root = Path.cwd() / "playground"
        try:
            self.playground_root.mkdir(exist_ok=True)
        except FileExistsError:
            # Directory already exists, which is fine
            pass
        
        # Create subdirectories
        self.media_dirs = {
            "images": self.playground_root / "images",
            "audio": self.playground_root / "audio", 
            "videos": self.playground_root / "videos",
            "documents": self.playground_root / "documents",
            "temp": self.playground_root / "temp"
        }
        
        for dir_path in self.media_dirs.values():
            try:
                dir_path.mkdir(exist_ok=True)
            except FileExistsError:
                # Directory already exists, which is fine
                pass
    
    async def execute(self, 
                     operation: str,
                     path: str,
                     content: str = None,
                     encoding: str = "utf-8",
                     format: str = None,
                     metadata: Dict[str, Any] = None) -> ToolResult:
        """Execute playground operation."""
        try:
            # Validate and normalize path
            playground_path = self._get_playground_path(path)
            if not playground_path:
                return ToolResult(
                    success=False,
                    error="Invalid path",
                    message=f"Path '{path}' is not within playground directory"
                )
            
            print(f"🎮 Playground operation: {operation} on {playground_path}")
            
            # Execute operation
            if operation == "create_file":
                return await self._create_file(playground_path, content or "", encoding)
            elif operation == "edit_file":
                return await self._edit_file(playground_path, content or "", encoding)
            elif operation == "delete_file":
                return await self._delete_file(playground_path)
            elif operation == "copy_file":
                return await self._copy_file(playground_path, content)
            elif operation == "move_file":
                return await self._move_file(playground_path, content)
            elif operation == "create_dir":
                return await self._create_directory(playground_path)
            elif operation == "delete_dir":
                return await self._delete_directory(playground_path)
            elif operation == "list_dir":
                return await self._list_directory(playground_path)
            elif operation == "save_image":
                return await self._save_media(playground_path, content, "image", format, metadata)
            elif operation == "save_audio":
                return await self._save_media(playground_path, content, "audio", format, metadata)
            elif operation == "save_video":
                return await self._save_media(playground_path, content, "video", format, metadata)
            elif operation == "save_binary":
                return await self._save_binary(playground_path, content, metadata)
            elif operation == "get_media_info":
                return await self._get_media_info(playground_path)
            elif operation == "cleanup":
                return await self._cleanup_playground()
            elif operation == "get_stats":
                return await self._get_playground_stats()
            else:
                return ToolResult(
                    success=False,
                    error="Invalid operation",
                    message=f"Operation '{operation}' is not supported"
                )
                
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Playground operation failed: {str(e)}",
                message=f"Failed to {operation} in playground"
            )
    
    def _get_playground_path(self, path: str) -> Optional[Path]:
        """Get validated playground path."""
        try:
            # Remove leading slash if present
            if path.startswith('/'):
                path = path[1:]
            
            # Create full path
            full_path = self.playground_root / path
            
            # Resolve and check it's within playground
            resolved_path = full_path.resolve()
            playground_resolved = self.playground_root.resolve()
            
            # Ensure path is within playground
            try:
                resolved_path.relative_to(playground_resolved)
                return resolved_path
            except ValueError:
                return None
                
        except Exception:
            return None
    
    async def _create_file(self, path: Path, content: str, encoding: str) -> ToolResult:
        """Create a new file."""
        try:
            if path.exists():
                return ToolResult(
                    success=False,
                    error="File already exists",
                    message=f"File {path.name} already exists. Use edit_file to modify existing files."
                )
            
            # Create parent directory if needed
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write file
            await asyncio.to_thread(path.write_text, content, encoding=encoding)
            
            file_size = path.stat().st_size
            
            return ToolResult(
                success=True,
                data={
                    "path": str(path.relative_to(self.playground_root)),
                    "size": file_size,
                    "encoding": encoding,
                    "type": "text"
                },
                message=f"Created file {path.name} ({file_size} bytes)"
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to create file: {str(e)}",
                message=f"Could not create {path.name}"
            )
    
    async def _edit_file(self, path: Path, content: str, encoding: str) -> ToolResult:
        """Edit an existing file or create if it doesn't exist."""
        try:
            # Create parent directory if needed
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # Backup existing file if it exists
            backup_path = None
            if path.exists():
                backup_path = path.with_suffix(path.suffix + '.backup')
                shutil.copy2(path, backup_path)
            
            # Write new content
            await asyncio.to_thread(path.write_text, content, encoding=encoding)
            
            file_size = path.stat().st_size
            
            result_data = {
                "path": str(path.relative_to(self.playground_root)),
                "size": file_size,
                "encoding": encoding,
                "type": "text"
            }
            
            if backup_path:
                result_data["backup"] = str(backup_path.relative_to(self.playground_root))
            
            action = "Modified" if backup_path else "Created"
            return ToolResult(
                success=True,
                data=result_data,
                message=f"{action} file {path.name} ({file_size} bytes)"
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to edit file: {str(e)}",
                message=f"Could not edit {path.name}"
            )
    
    async def _save_media(self, path: Path, content: str, media_type: str, format: str = None, metadata: Dict = None) -> ToolResult:
        """Save media file (image, audio, video)."""
        try:
            if not content:
                return ToolResult(
                    success=False,
                    error="No content provided",
                    message="Media content is required"
                )
            
            # Determine appropriate subdirectory
            if media_type == "image":
                base_dir = self.media_dirs["images"]
            elif media_type == "audio":
                base_dir = self.media_dirs["audio"] 
            elif media_type == "video":
                base_dir = self.media_dirs["videos"]
            else:
                base_dir = self.playground_root
            
            # If path is just filename, put it in appropriate media dir
            if '/' not in str(path.relative_to(self.playground_root)):
                path = base_dir / path.name
            
            # Create parent directory
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # Handle base64 content
            if content.startswith('data:') or content.startswith('base64:'):
                # Remove data URL prefix if present
                if content.startswith('data:'):
                    content = content.split(',', 1)[1]
                elif content.startswith('base64:'):
                    content = content[7:]  # Remove 'base64:' prefix
                
                # Decode base64
                import base64
                binary_data = base64.b64decode(content)
                
                # Write binary data
                await asyncio.to_thread(path.write_bytes, binary_data)
            else:
                # Assume it's a file path to copy from
                source_path = Path(content)
                if source_path.exists():
                    await asyncio.to_thread(shutil.copy2, source_path, path)
                else:
                    return ToolResult(
                        success=False,
                        error="Source file not found",
                        message=f"Source file {content} does not exist"
                    )
            
            file_size = path.stat().st_size
            
            # Create metadata file
            if metadata:
                metadata_path = path.with_suffix('.json')
                metadata_content = {
                    "filename": path.name,
                    "type": media_type,
                    "format": format or mimetypes.guess_type(str(path))[0],
                    "size": file_size,
                    "created": path.stat().st_ctime,
                    **metadata
                }
                await asyncio.to_thread(
                    metadata_path.write_text, 
                    json.dumps(metadata_content, indent=2)
                )
            
            return ToolResult(
                success=True,
                data={
                    "path": str(path.relative_to(self.playground_root)),
                    "type": media_type,
                    "size": file_size,
                    "format": format or mimetypes.guess_type(str(path))[0],
                    "has_metadata": metadata is not None
                },
                message=f"Saved {media_type} file {path.name} ({file_size} bytes)"
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to save media: {str(e)}",
                message=f"Could not save {media_type} file"
            )
    
    async def _save_binary(self, path: Path, content: str, metadata: Dict = None) -> ToolResult:
        """Save binary file."""
        try:
            # Create parent directory
            path.parent.mkdir(parents=True, exist_ok=True)
            
            if content.startswith('base64:'):
                # Decode base64
                import base64
                binary_data = base64.b64decode(content[7:])
                await asyncio.to_thread(path.write_bytes, binary_data)
            else:
                # Assume it's a file path to copy from
                source_path = Path(content)
                if source_path.exists():
                    await asyncio.to_thread(shutil.copy2, source_path, path)
                else:
                    return ToolResult(
                        success=False,
                        error="Source file not found", 
                        message=f"Source file {content} does not exist"
                    )
            
            file_size = path.stat().st_size
            
            return ToolResult(
                success=True,
                data={
                    "path": str(path.relative_to(self.playground_root)),
                    "type": "binary",
                    "size": file_size
                },
                message=f"Saved binary file {path.name} ({file_size} bytes)"
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to save binary: {str(e)}",
                message=f"Could not save binary file"
            )
    
    async def _copy_file(self, dest_path: Path, source_path: str) -> ToolResult:
        """Copy file within playground."""
        try:
            source = self._get_playground_path(source_path)
            if not source or not source.exists():
                return ToolResult(
                    success=False,
                    error="Source file not found",
                    message=f"Source file {source_path} not found in playground"
                )
            
            # Create parent directory
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy file
            await asyncio.to_thread(shutil.copy2, source, dest_path)
            
            file_size = dest_path.stat().st_size
            
            return ToolResult(
                success=True,
                data={
                    "source": str(source.relative_to(self.playground_root)),
                    "destination": str(dest_path.relative_to(self.playground_root)),
                    "size": file_size
                },
                message=f"Copied {source.name} to {dest_path.name}"
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to copy file: {str(e)}",
                message="Could not copy file"
            )
    
    async def _move_file(self, dest_path: Path, source_path: str) -> ToolResult:
        """Move file within playground."""
        try:
            source = self._get_playground_path(source_path)
            if not source or not source.exists():
                return ToolResult(
                    success=False,
                    error="Source file not found",
                    message=f"Source file {source_path} not found in playground"
                )
            
            # Create parent directory
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Move file
            await asyncio.to_thread(shutil.move, source, dest_path)
            
            file_size = dest_path.stat().st_size
            
            return ToolResult(
                success=True,
                data={
                    "source": source_path,
                    "destination": str(dest_path.relative_to(self.playground_root)),
                    "size": file_size
                },
                message=f"Moved {Path(source_path).name} to {dest_path.name}"
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to move file: {str(e)}",
                message="Could not move file"
            )
    
    async def _delete_file(self, path: Path) -> ToolResult:
        """Delete a file."""
        try:
            if not path.exists():
                return ToolResult(
                    success=False,
                    error="File not found",
                    message=f"File {path.name} does not exist"
                )
            
            if not path.is_file():
                return ToolResult(
                    success=False,
                    error="Not a file",
                    message=f"{path.name} is not a file"
                )
            
            file_name = path.name
            await asyncio.to_thread(path.unlink)
            
            # Delete associated metadata file if exists
            metadata_path = path.with_suffix('.json')
            if metadata_path.exists():
                await asyncio.to_thread(metadata_path.unlink)
            
            return ToolResult(
                success=True,
                data={"path": str(path.relative_to(self.playground_root))},
                message=f"Deleted file {file_name}"
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to delete file: {str(e)}",
                message=f"Could not delete {path.name}"
            )
    
    async def _create_directory(self, path: Path) -> ToolResult:
        """Create a directory."""
        try:
            path.mkdir(parents=True, exist_ok=True)
            
            return ToolResult(
                success=True,
                data={"path": str(path.relative_to(self.playground_root))},
                message=f"Created directory {path.name}"
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to create directory: {str(e)}",
                message=f"Could not create directory {path.name}"
            )
    
    async def _delete_directory(self, path: Path) -> ToolResult:
        """Delete a directory."""
        try:
            if not path.exists():
                return ToolResult(
                    success=False,
                    error="Directory not found",
                    message=f"Directory {path.name} does not exist"
                )
            
            if not path.is_dir():
                return ToolResult(
                    success=False,
                    error="Not a directory",
                    message=f"{path.name} is not a directory"
                )
            
            # Count items for confirmation
            items = list(path.rglob("*"))
            if items:
                await asyncio.to_thread(shutil.rmtree, path)
                message = f"Deleted directory {path.name} and {len(items)} items"
            else:
                await asyncio.to_thread(path.rmdir)
                message = f"Deleted empty directory {path.name}"
            
            return ToolResult(
                success=True,
                data={
                    "path": str(path.relative_to(self.playground_root)),
                    "items_deleted": len(items)
                },
                message=message
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to delete directory: {str(e)}",
                message=f"Could not delete directory {path.name}"
            )
    
    async def _list_directory(self, path: Path) -> ToolResult:
        """List directory contents."""
        try:
            if not path.exists():
                path = self.playground_root  # Default to playground root
            
            if not path.is_dir():
                return ToolResult(
                    success=False,
                    error="Not a directory",
                    message=f"{path.name} is not a directory"
                )
            
            items = []
            for item in path.iterdir():
                try:
                    stat = item.stat()
                    item_info = {
                        "name": item.name,
                        "path": str(item.relative_to(self.playground_root)),
                        "type": "directory" if item.is_dir() else "file",
                        "size": stat.st_size if item.is_file() else None,
                        "modified": stat.st_mtime
                    }
                    
                    # Add media type for known extensions
                    if item.is_file():
                        mime_type = mimetypes.guess_type(str(item))[0]
                        if mime_type:
                            if mime_type.startswith('image/'):
                                item_info["media_type"] = "image"
                            elif mime_type.startswith('audio/'):
                                item_info["media_type"] = "audio"
                            elif mime_type.startswith('video/'):
                                item_info["media_type"] = "video"
                    
                    items.append(item_info)
                except Exception:
                    continue
            
            # Sort by type then name
            items.sort(key=lambda x: (x["type"], x["name"].lower()))
            
            return ToolResult(
                success=True,
                data={
                    "path": str(path.relative_to(self.playground_root)),
                    "items": items,
                    "count": len(items)
                },
                message=f"Listed {len(items)} items in {path.name or 'playground'}"
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to list directory: {str(e)}",
                message=f"Could not list directory"
            )
    
    async def _get_media_info(self, path: Path) -> ToolResult:
        """Get detailed media file information."""
        try:
            if not path.exists():
                return ToolResult(
                    success=False,
                    error="File not found",
                    message=f"File {path.name} does not exist"
                )
            
            stat = path.stat()
            mime_type = mimetypes.guess_type(str(path))[0]
            
            info = {
                "path": str(path.relative_to(self.playground_root)),
                "name": path.name,
                "size": stat.st_size,
                "created": stat.st_ctime,
                "modified": stat.st_mtime,
                "mime_type": mime_type,
                "extension": path.suffix.lower()
            }
            
            # Check for metadata file
            metadata_path = path.with_suffix('.json')
            if metadata_path.exists():
                try:
                    metadata_content = await asyncio.to_thread(
                        metadata_path.read_text, encoding="utf-8"
                    )
                    metadata = json.loads(metadata_content)
                    info["metadata"] = metadata
                except Exception:
                    info["metadata_error"] = "Could not read metadata file"
            
            return ToolResult(
                success=True,
                data=info,
                message=f"Retrieved info for {path.name}"
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to get media info: {str(e)}",
                message=f"Could not get info for {path.name}"
            )
    
    async def _cleanup_playground(self) -> ToolResult:
        """Clean up playground directory."""
        try:
            deleted_count = 0
            temp_dir = self.media_dirs["temp"]
            
            # Clean temp directory
            if temp_dir.exists():
                for item in temp_dir.rglob("*"):
                    if item.is_file():
                        await asyncio.to_thread(item.unlink)
                        deleted_count += 1
            
            # Remove empty directories
            for item in self.playground_root.rglob("*"):
                if item.is_dir() and not any(item.iterdir()):
                    try:
                        await asyncio.to_thread(item.rmdir)
                    except Exception:
                        pass
            
            return ToolResult(
                success=True,
                data={"deleted_files": deleted_count},
                message=f"Cleaned playground, deleted {deleted_count} temporary files"
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to cleanup: {str(e)}",
                message="Could not cleanup playground"
            )
    
    async def _get_playground_stats(self) -> ToolResult:
        """Get playground directory statistics."""
        try:
            stats = {
                "total_files": 0,
                "total_size": 0,
                "directories": 0,
                "by_type": {
                    "images": {"count": 0, "size": 0},
                    "audio": {"count": 0, "size": 0},
                    "videos": {"count": 0, "size": 0},
                    "documents": {"count": 0, "size": 0},
                    "other": {"count": 0, "size": 0}
                }
            }
            
            for item in self.playground_root.rglob("*"):
                if item.is_file():
                    size = item.stat().st_size
                    stats["total_files"] += 1
                    stats["total_size"] += size
                    
                    # Categorize by type
                    mime_type = mimetypes.guess_type(str(item))[0] or ""
                    if mime_type.startswith('image/'):
                        stats["by_type"]["images"]["count"] += 1
                        stats["by_type"]["images"]["size"] += size
                    elif mime_type.startswith('audio/'):
                        stats["by_type"]["audio"]["count"] += 1
                        stats["by_type"]["audio"]["size"] += size
                    elif mime_type.startswith('video/'):
                        stats["by_type"]["videos"]["count"] += 1
                        stats["by_type"]["videos"]["size"] += size
                    elif mime_type.startswith('text/') or item.suffix in ['.txt', '.md', '.json', '.csv']:
                        stats["by_type"]["documents"]["count"] += 1
                        stats["by_type"]["documents"]["size"] += size
                    else:
                        stats["by_type"]["other"]["count"] += 1
                        stats["by_type"]["other"]["size"] += size
                        
                elif item.is_dir():
                    stats["directories"] += 1
            
            # Convert sizes to human readable
            def format_size(bytes_size):
                for unit in ['B', 'KB', 'MB', 'GB']:
                    if bytes_size < 1024:
                        return f"{bytes_size:.1f}{unit}"
                    bytes_size /= 1024
                return f"{bytes_size:.1f}TB"
            
            stats["total_size_formatted"] = format_size(stats["total_size"])
            
            return ToolResult(
                success=True,
                data=stats,
                message=f"Playground contains {stats['total_files']} files in {stats['directories']} directories ({stats['total_size_formatted']})"
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to get stats: {str(e)}",
                message="Could not get playground statistics"
            )