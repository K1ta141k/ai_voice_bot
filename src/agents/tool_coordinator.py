"""Tool coordination and selection logic for voice agents."""

import asyncio
from typing import Dict, List, Any, Optional, Tuple
import json
import logging

from ..tools.tool_manager import ToolManager, ToolExecutionContext
from ..tools.base_tool import ToolResult, BaseTool


class ToolCoordinator:
    """Coordinates tool selection and execution for voice agents."""
    
    def __init__(self, tool_manager: ToolManager = None):
        self.tool_manager = tool_manager or ToolManager()
        self.logger = logging.getLogger(__name__)
        
        # Initialize tools by discovering them
        self.initialize_tools()
    
    def initialize_tools(self):
        """Initialize and discover available tools."""
        try:
            print("🔍 Discovering available tools...")
            self.tool_manager.registry.discover_tools()
            
            available_tools = self.tool_manager.registry.list_tools()
            print(f"✅ Discovered {len(available_tools)} tools: {', '.join(available_tools)}")
            
            return available_tools
            
        except Exception as e:
            print(f"❌ Failed to initialize tools: {e}")
            return []
    
    def get_available_tools_for_user(self, user_id: str) -> List[BaseTool]:
        """Get tools available for a specific user."""
        return self.tool_manager.get_available_tools(user_id)
    
    def get_tool_descriptions(self, user_id: str = None) -> List[Dict[str, Any]]:
        """Get tool descriptions for display or selection."""
        tools = self.get_available_tools_for_user(user_id) if user_id else self.tool_manager.registry.get_all_tools()
        
        descriptions = []
        for tool in tools:
            descriptions.append({
                "name": tool.name,
                "description": tool.description,
                "parameters": [
                    {
                        "name": param.name,
                        "type": param.type,
                        "description": param.description,
                        "required": param.required
                    }
                    for param in tool._parameters
                ]
            })
        
        return descriptions
    
    async def execute_tool_by_intent(self,
                                   user_intent: str,
                                   extracted_params: Dict[str, Any],
                                   user_id: str,
                                   channel_id: str = None) -> Tuple[bool, List[ToolResult]]:
        """Execute tools based on user intent and parameters."""
        try:
            # Simple intent-to-tool mapping (this could be enhanced with NLP)
            tool_suggestions = self._map_intent_to_tools(user_intent)
            
            if not tool_suggestions:
                return False, [ToolResult(
                    success=False,
                    error="No matching tools",
                    message=f"Could not find tools for intent: {user_intent}"
                )]
            
            # Execute the first matching tool
            tool_name = tool_suggestions[0]
            context = self.tool_manager.create_context(user_id, channel_id)
            
            result = await self.tool_manager.execute_tool(
                tool_name,
                extracted_params,
                context
            )
            
            return True, [result]
            
        except Exception as e:
            error_result = ToolResult(
                success=False,
                error=f"Intent execution failed: {str(e)}",
                message="Failed to execute tools based on user intent"
            )
            return False, [error_result]
    
    def _map_intent_to_tools(self, intent: str) -> List[str]:
        """Simple intent-to-tool mapping."""
        intent_lower = intent.lower()
        
        # Web search keywords
        if any(word in intent_lower for word in ["search", "find", "look up", "google", "web", "internet"]):
            return ["intelligent_search"]
        
        # File operation keywords
        elif any(word in intent_lower for word in ["file", "read", "write", "save", "delete", "create", "folder", "directory"]):
            return ["file_operations"]
        
        # System command keywords
        elif any(word in intent_lower for word in ["system", "command", "execute", "run", "process", "disk", "info"]):
            return ["system_commands"]
        
        # Default: no specific tool mapping
        return []
    
    async def validate_tools_configuration(self) -> Dict[str, Any]:
        """Validate tool system configuration."""
        validation_results = {
            "total_tools": 0,
            "working_tools": [],
            "broken_tools": [],
            "validation_errors": []
        }
        
        try:
            all_tools = self.tool_manager.registry.get_all_tools()
            validation_results["total_tools"] = len(all_tools)
            
            for tool in all_tools:
                try:
                    # Test basic tool properties
                    if not tool.name:
                        raise ValueError("Tool missing name")
                    
                    if not tool.description:
                        raise ValueError("Tool missing description")
                    
                    # Test schema generation
                    schema = tool.schema
                    openai_function = tool.to_openai_function()
                    
                    validation_results["working_tools"].append({
                        "name": tool.name,
                        "description": tool.description,
                        "parameter_count": len(tool._parameters)
                    })
                    
                except Exception as e:
                    validation_results["broken_tools"].append({
                        "name": getattr(tool, 'name', 'unknown'),
                        "error": str(e)
                    })
            
            print(f"🔍 Tool validation: {len(validation_results['working_tools'])}/{validation_results['total_tools']} tools working")
            
            if validation_results["broken_tools"]:
                for broken in validation_results["broken_tools"]:
                    print(f"❌ Broken tool {broken['name']}: {broken['error']}")
            
            return validation_results
            
        except Exception as e:
            validation_results["validation_errors"].append(str(e))
            print(f"❌ Tool validation failed: {e}")
            return validation_results
    
    def get_tool_usage_stats(self) -> Dict[str, Any]:
        """Get tool usage statistics."""
        # This would be enhanced with actual usage tracking
        stats = {
            "available_tools": len(self.tool_manager.registry.list_tools()),
            "tool_list": self.tool_manager.registry.list_tools(),
            "execution_contexts": len(self.tool_manager.execution_contexts)
        }
        
        return stats
    
    async def test_tool_execution(self, tool_name: str, test_params: Dict[str, Any]) -> ToolResult:
        """Test a specific tool with given parameters."""
        try:
            context = ToolExecutionContext("test_user", "test_channel")
            result = await self.tool_manager.execute_tool(tool_name, test_params, context)
            
            print(f"🧪 Tool test - {tool_name}: {'✅ PASS' if result.success else '❌ FAIL'}")
            if not result.success:
                print(f"   Error: {result.error}")
            
            return result
            
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Test execution failed: {str(e)}",
                message=f"Failed to test tool {tool_name}"
            )


# Global tool coordinator instance - will be initialized when needed
tool_coordinator = None