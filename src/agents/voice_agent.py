"""Main voice agent controller that coordinates voice interactions with tools."""

import asyncio
from typing import Dict, Any, Optional, List
import logging

from ..openai.realtime_client import OpenAIRealtime
from ..tools.tool_manager import ToolManager
from .tool_coordinator import ToolCoordinator


class VoiceAgent:
    """Main voice agent that coordinates voice interactions with tool execution."""
    
    def __init__(self, 
                 openai_client: OpenAIRealtime,
                 tool_manager: ToolManager = None,
                 tool_coordinator: ToolCoordinator = None):
        
        self.openai_client = openai_client
        self.tool_manager = tool_manager or ToolManager()
        self.tool_coordinator = tool_coordinator or ToolCoordinator(self.tool_manager)
        self.logger = logging.getLogger(__name__)
        
        # Agent state
        self.is_initialized = False
        self.current_session = None
        self.active_user = None
        self.active_channel = None
    
    async def initialize(self, connect_openai: bool = True) -> bool:
        """Initialize the voice agent and its components."""
        try:
            print("🤖 Initializing Voice Agent...")
            
            # Initialize tool coordinator
            await self.tool_coordinator.validate_tools_configuration()
            
            # Only connect to OpenAI if requested
            if connect_openai:
                if not self.openai_client.is_connected:
                    await self.openai_client.connect()
                # Enable tools in OpenAI client
                self.openai_client.enable_tools(True)
                print("🔗 OpenAI connected and tools enabled")
            else:
                print("⏸️  OpenAI connection deferred until voice session starts")
            
            self.is_initialized = True
            print("✅ Voice Agent initialized successfully")
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to initialize Voice Agent: {e}")
            self.is_initialized = False
            return False
    
    async def start_voice_session(self, user_id: str, channel_id: str = None) -> bool:
        """Start a voice interaction session for a user."""
        try:
            if not self.is_initialized:
                await self.initialize(connect_openai=False)
            
            # Connect to OpenAI and enable tools for this session
            print("🔗 Connecting to OpenAI Realtime API for voice session...")
            if not self.openai_client.is_connected:
                await self.openai_client.connect()
            
            # Enable tools and set user context
            self.openai_client.enable_tools(True)
            self.openai_client.set_user_context(user_id, channel_id)
            
            # Update agent state
            self.active_user = user_id
            self.active_channel = channel_id
            
            # Create execution context
            self.current_session = self.tool_manager.create_context(user_id, channel_id)
            
            print(f"🎤 Started voice session for user {user_id}")
            print("🔧 Tools enabled and ready for voice interactions")
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to start voice session: {e}")
            return False
    
    async def handle_voice_input(self, audio_data, duration: float) -> bool:
        """Handle incoming voice input from user."""
        try:
            if not self.is_initialized:
                print("❌ Voice agent not initialized")
                return False
            
            if not self.active_user:
                print("❌ No active voice session")
                return False
            
            print(f"🎤 Processing voice input ({duration:.1f}s) for user {self.active_user}")
            
            # Send to OpenAI for processing (includes tool calling)
            await self.openai_client.send_voice_message(audio_data, duration)
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to handle voice input: {e}")
            return False
    
    async def end_voice_session(self) -> None:
        """End the current voice session."""
        try:
            if self.active_user:
                print(f"🔚 Ending voice session for user {self.active_user}")
                
                # Disconnect from OpenAI to clear context
                if self.openai_client.is_connected:
                    await self.openai_client.disconnect()
                    print("🔌 Disconnected from OpenAI Realtime API")
                
                # Clean up execution context
                if self.current_session:
                    context_id = f"{self.active_user}_{self.active_channel}" if self.active_channel else self.active_user
                    # Context cleanup is handled by tool manager
                
                # Reset agent state
                self.active_user = None
                self.active_channel = None
                self.current_session = None
                
                print("✅ Voice session ended and context cleared")
            
        except Exception as e:
            print(f"❌ Error ending voice session: {e}")
    
    def get_session_info(self) -> Dict[str, Any]:
        """Get information about the current session."""
        return {
            "initialized": self.is_initialized,
            "active_user": self.active_user,
            "active_channel": self.active_channel,
            "session_active": self.current_session is not None,
            "openai_connected": self.openai_client.is_connected,
            "tools_enabled": self.openai_client.tools_enabled
        }
    
    def get_available_tools(self, user_id: str = None) -> List[Dict[str, Any]]:
        """Get available tools for current user or specified user."""
        # Use provided user_id, or active_user, or default to showing all tools
        target_user = user_id or self.active_user
        
        return self.tool_coordinator.get_tool_descriptions(target_user)
    
    async def execute_manual_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Manually execute a tool (for testing/debugging)."""
        try:
            if not self.active_user:
                return {
                    "success": False,
                    "error": "No active session",
                    "message": "Start a voice session first"
                }
            
            result = await self.tool_manager.execute_tool(
                tool_name,
                parameters,
                self.current_session
            )
            
            return {
                "success": result.success,
                "data": result.data,
                "error": result.error,
                "message": result.message
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Manual tool execution failed: {str(e)}",
                "message": "Failed to execute tool manually"
            }
    
    async def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status."""
        try:
            # Get tool validation
            tool_validation = await self.tool_coordinator.validate_tools_configuration()
            
            # Get tool usage stats
            tool_stats = self.tool_coordinator.get_tool_usage_stats()
            
            return {
                "voice_agent": self.get_session_info(),
                "tools": {
                    "validation": tool_validation,
                    "usage_stats": tool_stats
                },
                "openai": {
                    "connected": self.openai_client.is_connected,
                    "tools_enabled": self.openai_client.tools_enabled
                }
            }
            
        except Exception as e:
            return {
                "error": f"Failed to get system status: {str(e)}",
                "voice_agent": self.get_session_info() if hasattr(self, 'get_session_info') else {}
            }
    
    def enable_tools(self, enabled: bool = True) -> None:
        """Enable or disable tools for voice interactions."""
        self.openai_client.enable_tools(enabled)
        
        if enabled:
            print("🔧 Tools enabled for voice interactions")
        else:
            print("🚫 Tools disabled for voice interactions")
    
    async def cleanup(self) -> None:
        """Cleanup resources when shutting down."""
        try:
            # End current session
            await self.end_voice_session()
            
            # Cleanup old execution contexts
            self.tool_manager.cleanup_old_contexts()
            
            print("🧹 Voice Agent cleanup completed")
            
        except Exception as e:
            print(f"❌ Error during cleanup: {e}")