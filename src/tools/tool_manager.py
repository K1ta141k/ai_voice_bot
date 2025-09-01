"""Tool manager for executing and coordinating tools."""

import asyncio
from typing import Dict, List, Optional, Any, Callable
import logging
from datetime import datetime

from .base_tool import BaseTool, ToolResult
from .registry import ToolRegistry


class ToolExecutionContext:
    """Context for tool execution with logging and permission checking."""
    
    def __init__(self, user_id: Optional[str] = None, channel_id: Optional[str] = None):
        self.user_id = user_id
        self.channel_id = channel_id
        self.start_time = datetime.now()
        self.execution_log: List[Dict[str, Any]] = []
    
    def log_execution(self, tool_name: str, params: Dict[str, Any], result: ToolResult):
        """Log tool execution details."""
        self.execution_log.append({
            "tool": tool_name,
            "params": params,
            "success": result.success,
            "error": result.error,
            "timestamp": datetime.now(),
            "duration": (datetime.now() - self.start_time).total_seconds()
        })


class ToolManager:
    """Manages tool execution, permissions, and coordination."""
    
    def __init__(self, registry: ToolRegistry = None):
        self.registry = registry or ToolRegistry()
        self.logger = logging.getLogger(__name__)
        self.execution_contexts: Dict[str, ToolExecutionContext] = {}
        self.permission_checker: Optional[Callable] = None
        self.max_concurrent_executions = 3
        self.execution_semaphore = asyncio.Semaphore(self.max_concurrent_executions)
    
    def set_permission_checker(self, checker: Callable[[str, str, str], bool]) -> None:
        """Set permission checker function."""
        self.permission_checker = checker
    
    def check_permission(self, user_id: str, tool_name: str, context_id: str = None) -> bool:
        """Check if user has permission to use tool."""
        if self.permission_checker:
            return self.permission_checker(user_id, tool_name, context_id)
        return True  # Default: allow all
    
    async def execute_tool(self, 
                          tool_name: str, 
                          params: Dict[str, Any],
                          context: Optional[ToolExecutionContext] = None) -> ToolResult:
        """Execute a single tool with permission checking and logging."""
        
        # Create context if not provided
        if context is None:
            context = ToolExecutionContext()
        
        # Check permissions
        if context.user_id and not self.check_permission(context.user_id, tool_name):
            result = ToolResult(
                success=False,
                error="Permission denied",
                message=f"User {context.user_id} not allowed to use tool '{tool_name}'"
            )
            context.log_execution(tool_name, params, result)
            return result
        
        # Execute with semaphore for concurrency control
        async with self.execution_semaphore:
            try:
                self.logger.info(f"Executing tool '{tool_name}' with params: {params}")
                result = await self.registry.execute_tool(tool_name, **params)
                
                # Log execution
                context.log_execution(tool_name, params, result)
                
                if result.success:
                    self.logger.info(f"Tool '{tool_name}' executed successfully")
                else:
                    self.logger.warning(f"Tool '{tool_name}' failed: {result.error}")
                
                return result
                
            except Exception as e:
                error_result = ToolResult(
                    success=False,
                    error=f"Tool manager execution error: {str(e)}",
                    message=f"Failed to execute {tool_name}"
                )
                context.log_execution(tool_name, params, error_result)
                self.logger.error(f"Tool execution error: {e}", exc_info=True)
                return error_result
    
    async def execute_multiple_tools(self,
                                   tool_calls: List[Dict[str, Any]],
                                   context: Optional[ToolExecutionContext] = None,
                                   parallel: bool = True) -> List[ToolResult]:
        """Execute multiple tools either in parallel or sequentially."""
        
        if context is None:
            context = ToolExecutionContext()
        
        if parallel:
            # Execute tools in parallel
            tasks = []
            for call in tool_calls:
                task = self.execute_tool(
                    call.get("name", ""),
                    call.get("params", {}),
                    context
                )
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Convert exceptions to ToolResult
            final_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    final_results.append(ToolResult(
                        success=False,
                        error=f"Execution exception: {str(result)}",
                        message=f"Tool {tool_calls[i].get('name', 'unknown')} failed"
                    ))
                else:
                    final_results.append(result)
            
            return final_results
        else:
            # Execute tools sequentially
            results = []
            for call in tool_calls:
                result = await self.execute_tool(
                    call.get("name", ""),
                    call.get("params", {}),
                    context
                )
                results.append(result)
                
                # Stop on first failure if needed
                if not result.success:
                    break
            
            return results
    
    def get_available_tools(self, user_id: Optional[str] = None) -> List[BaseTool]:
        """Get tools available to a specific user."""
        all_tools = self.registry.get_all_tools()
        
        if user_id is None:
            return all_tools
        
        # Filter by permissions
        allowed_tools = []
        for tool in all_tools:
            if self.check_permission(user_id, tool.name):
                allowed_tools.append(tool)
        
        return allowed_tools
    
    def get_openai_functions_for_user(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get OpenAI function definitions for a specific user."""
        allowed_tools = self.get_available_tools(user_id)
        return [tool.to_openai_function() for tool in allowed_tools]
    
    def create_context(self, user_id: str, channel_id: str = None) -> ToolExecutionContext:
        """Create and store execution context."""
        context_id = f"{user_id}_{datetime.now().timestamp()}"
        context = ToolExecutionContext(user_id, channel_id)
        self.execution_contexts[context_id] = context
        return context
    
    def cleanup_old_contexts(self, max_age_hours: int = 24) -> None:
        """Clean up old execution contexts."""
        cutoff_time = datetime.now().timestamp() - (max_age_hours * 3600)
        
        contexts_to_remove = []
        for context_id, context in self.execution_contexts.items():
            if context.start_time.timestamp() < cutoff_time:
                contexts_to_remove.append(context_id)
        
        for context_id in contexts_to_remove:
            del self.execution_contexts[context_id]
        
        if contexts_to_remove:
            self.logger.info(f"Cleaned up {len(contexts_to_remove)} old execution contexts")


# Global tool manager instance - will be initialized when imported
tool_manager = None