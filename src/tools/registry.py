"""Tool registry for managing and discovering tools."""

import os
import importlib
import inspect
from typing import Dict, List, Optional, Type, Any, Callable
from pathlib import Path

from .base_tool import BaseTool, ToolResult


class ToolRegistry:
    """Central registry for managing tools."""
    
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._tool_classes: Dict[str, Type[BaseTool]] = {}
        self._decorators: List[Callable] = []
    
    def register_tool(self, tool: BaseTool) -> None:
        """Register a tool instance."""
        self._tools[tool.name] = tool
        print(f"✅ Registered tool: {tool.name}")
    
    def register_tool_class(self, name: str, tool_class: Type[BaseTool]) -> None:
        """Register a tool class for lazy instantiation."""
        self._tool_classes[name] = tool_class
        print(f"📝 Registered tool class: {name}")
    
    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name."""
        if name in self._tools:
            return self._tools[name]
        
        # Try to instantiate from class
        if name in self._tool_classes:
            tool_class = self._tool_classes[name]
            tool = tool_class()
            self._tools[name] = tool
            return tool
        
        return None
    
    def list_tools(self) -> List[str]:
        """List all available tool names."""
        all_tools = set(self._tools.keys()) | set(self._tool_classes.keys())
        return sorted(list(all_tools))
    
    def get_all_tools(self) -> List[BaseTool]:
        """Get all tool instances."""
        tools = []
        for name in self.list_tools():
            tool = self.get_tool(name)
            if tool:
                tools.append(tool)
        return tools
    
    def get_openai_functions(self) -> List[Dict[str, Any]]:
        """Get all tools in OpenAI function calling format."""
        functions = []
        for tool in self.get_all_tools():
            functions.append(tool.to_openai_function())
        return functions
    
    def discover_tools(self, package_path: str = None) -> None:
        """Auto-discover tools from a package."""
        if package_path is None:
            # Default to builtin tools
            current_dir = Path(__file__).parent
            builtin_path = current_dir / "builtin"
            package_path = "src.tools.builtin"
        
        try:
            # Import the package
            package = importlib.import_module(package_path)
            package_dir = Path(package.__file__).parent
            
            # Find all Python files in the package
            for py_file in package_dir.glob("*.py"):
                if py_file.name.startswith("__"):
                    continue
                
                module_name = f"{package_path}.{py_file.stem}"
                try:
                    module = importlib.import_module(module_name)
                    
                    # Find tool classes in the module
                    for name, obj in inspect.getmembers(module):
                        if (inspect.isclass(obj) and 
                            issubclass(obj, BaseTool) and 
                            obj != BaseTool):
                            
                            # Check if class is decorated with @register_tool
                            if hasattr(obj, '_is_registered_tool'):
                                # Use decorator metadata
                                tool_name = getattr(obj, '_tool_name', name.lower())
                                tool_description = getattr(obj, '_tool_description', obj.__doc__ or "No description")
                                
                                try:
                                    # Instantiate with decorator metadata
                                    tool = obj()
                                    # Override name and description if decorator provided them
                                    tool.name = tool_name
                                    tool.description = tool_description
                                    self.register_tool(tool)
                                except Exception as e:
                                    print(f"⚠️  Failed to instantiate decorated tool {name}: {e}")
                                    self.register_tool_class(tool_name, obj)
                            else:
                                # Try to instantiate the tool normally
                                try:
                                    tool = obj()
                                    self.register_tool(tool)
                                except Exception as e:
                                    print(f"⚠️  Failed to instantiate tool {name}: {e}")
                                    # Register as class for later instantiation
                                    self.register_tool_class(name.lower(), obj)
                
                except Exception as e:
                    print(f"⚠️  Failed to import module {module_name}: {e}")
        
        except Exception as e:
            print(f"❌ Failed to discover tools from {package_path}: {e}")
    
    async def execute_tool(self, tool_name: str, **kwargs) -> ToolResult:
        """Execute a tool by name."""
        tool = self.get_tool(tool_name)
        if not tool:
            return ToolResult(
                success=False,
                error=f"Tool '{tool_name}' not found",
                message=f"Available tools: {', '.join(self.list_tools())}"
            )
        
        # Validate parameters
        validation_result = tool.validate_parameters(kwargs)
        if not validation_result.success:
            return validation_result
        
        # Execute tool
        try:
            result = await tool.execute(**kwargs)
            return result
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Tool execution failed: {str(e)}",
                message=f"Error occurred while executing {tool_name}"
            )


def register_tool(name: str = None, description: str = None):
    """Decorator for registering tools."""
    def decorator(cls: Type[BaseTool]):
        # Store metadata on the class
        cls._tool_name = name or cls.__name__.lower().replace("tool", "")
        cls._tool_description = description or cls.__doc__ or "No description provided"
        
        # Mark class as a registered tool
        cls._is_registered_tool = True
        
        return cls
    
    return decorator


# Global registry instance
tool_registry = ToolRegistry()