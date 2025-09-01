"""OpenAI function calling handler for tool integration."""

import json
import asyncio
from typing import Dict, List, Any, Optional

from ..tools.tool_manager import ToolManager, ToolExecutionContext
from ..tools.base_tool import ToolResult


class FunctionCallingHandler:
    """Handles OpenAI function calling integration with tools."""
    
    def __init__(self, tool_manager: ToolManager = None):
        self.tool_manager = tool_manager or ToolManager()
        self.active_contexts: Dict[str, ToolExecutionContext] = {}
    
    def get_function_definitions(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get function definitions for OpenAI function calling."""
        return self.tool_manager.get_openai_functions_for_user(user_id)
    
    async def handle_function_call(self, 
                                 function_name: str, 
                                 arguments: str,
                                 user_id: Optional[str] = None,
                                 channel_id: Optional[str] = None) -> ToolResult:
        """Handle a function call from OpenAI."""
        try:
            # Parse arguments
            try:
                args = json.loads(arguments) if arguments else {}
            except json.JSONDecodeError as e:
                return ToolResult(
                    success=False,
                    error=f"Invalid JSON arguments: {e}",
                    message="Failed to parse function arguments"
                )
            
            # Create or get execution context
            context_key = f"{user_id}_{channel_id}" if user_id and channel_id else "default"
            if context_key not in self.active_contexts:
                self.active_contexts[context_key] = self.tool_manager.create_context(
                    user_id or "unknown", channel_id
                )
            
            context = self.active_contexts[context_key]
            
            # Execute the tool
            result = await self.tool_manager.execute_tool(
                function_name, 
                args, 
                context
            )
            
            return result
            
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Function call handler error: {str(e)}",
                message=f"Failed to handle function call: {function_name}"
            )
    
    async def handle_multiple_function_calls(self,
                                           function_calls: List[Dict[str, Any]],
                                           user_id: Optional[str] = None,
                                           channel_id: Optional[str] = None,
                                           parallel: bool = True) -> List[ToolResult]:
        """Handle multiple function calls."""
        try:
            # Convert to tool manager format
            tool_calls = []
            for call in function_calls:
                tool_calls.append({
                    "name": call.get("name", ""),
                    "params": json.loads(call.get("arguments", "{}"))
                })
            
            # Get or create context
            context_key = f"{user_id}_{channel_id}" if user_id and channel_id else "default"
            if context_key not in self.active_contexts:
                self.active_contexts[context_key] = self.tool_manager.create_context(
                    user_id or "unknown", channel_id
                )
            
            context = self.active_contexts[context_key]
            
            # Execute tools
            results = await self.tool_manager.execute_multiple_tools(
                tool_calls, context, parallel
            )
            
            return results
            
        except Exception as e:
            error_result = ToolResult(
                success=False,
                error=f"Multiple function call error: {str(e)}",
                message="Failed to handle multiple function calls"
            )
            return [error_result] * len(function_calls)
    
    def format_tool_result_for_openai(self, result: ToolResult, function_name: str) -> Dict[str, Any]:
        """Format tool result for OpenAI response."""
        if result.success:
            content = {
                "success": True,
                "data": result.data or {},
                "message": result.message or "Tool executed successfully"
            }
        else:
            content = {
                "success": False,
                "error": result.error or "Unknown error",
                "message": result.message or "Tool execution failed"
            }
        
        return {
            "type": "function",
            "function": {
                "name": function_name,
                "result": json.dumps(content)
            }
        }
    
    def cleanup_context(self, user_id: str, channel_id: str = None) -> None:
        """Clean up execution context."""
        context_key = f"{user_id}_{channel_id}" if channel_id else user_id
        if context_key in self.active_contexts:
            del self.active_contexts[context_key]
    
    def get_context_summary(self, user_id: str, channel_id: str = None) -> Optional[Dict[str, Any]]:
        """Get summary of execution context."""
        context_key = f"{user_id}_{channel_id}" if channel_id else user_id
        context = self.active_contexts.get(context_key)
        
        if not context:
            return None
        
        return {
            "user_id": context.user_id,
            "channel_id": context.channel_id,
            "start_time": context.start_time.isoformat(),
            "execution_count": len(context.execution_log),
            "successful_executions": sum(1 for log in context.execution_log if log["success"]),
            "failed_executions": sum(1 for log in context.execution_log if not log["success"])
        }