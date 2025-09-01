"""Text-based AI agent for chat interactions with tool support."""

import asyncio
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from ..tools.tool_manager import ToolManager
from .tool_coordinator import ToolCoordinator
from ..mcp.server_manager import get_mcp_manager


class TextAgent:
    """Text-based AI agent that handles chat messages with tool integration."""
    
    def __init__(self, openai_client, tool_manager: ToolManager = None, tool_coordinator: ToolCoordinator = None):
        self.openai_client = openai_client
        self.tool_manager = tool_manager or ToolManager()
        self.tool_coordinator = tool_coordinator or ToolCoordinator(self.tool_manager)
        self.logger = logging.getLogger(__name__)
        
        # Agent state
        self.is_initialized = False
        self.conversation_history = {}  # per-user conversation history
        self.active_users = set()
        
        # MCP integration
        self.mcp_manager = None
        
        # Rate limiting
        self.last_message_times = {}
        self.min_message_interval = 1.0  # seconds between messages
        
    async def initialize(self) -> bool:
        """Initialize the text agent."""
        try:
            print("💬 Initializing Text Agent...")
            
            # Initialize tool coordinator
            await self.tool_coordinator.validate_tools_configuration()
            
            # Initialize MCP manager
            try:
                self.mcp_manager = await get_mcp_manager()
                if self.mcp_manager.is_initialized:
                    print("🔗 MCP servers connected for text agent")
                else:
                    print("⚠️  MCP servers not available for text agent")
            except Exception as e:
                print(f"⚠️  MCP initialization failed: {e}")
                self.mcp_manager = None
            
            self.is_initialized = True
            print("✅ Text Agent initialized successfully")
            return True
            
        except Exception as e:
            print(f"❌ Failed to initialize Text Agent: {e}")
            self.is_initialized = False
            return False
    
    async def handle_message(self, message_content: str, user_id: str, channel_id: str, username: str) -> Optional[str]:
        """Handle a text message and generate AI response."""
        try:
            if not self.is_initialized:
                await self.initialize()
                if not self.is_initialized:
                    return "❌ Text AI is not available right now."
            
            # Rate limiting check
            current_time = asyncio.get_event_loop().time()
            if user_id in self.last_message_times:
                time_diff = current_time - self.last_message_times[user_id]
                if time_diff < self.min_message_interval:
                    return None  # Skip response due to rate limiting
            
            self.last_message_times[user_id] = current_time
            
            print(f"💭 Processing text message from {username}: {message_content[:100]}{'...' if len(message_content) > 100 else ''}")
            
            # Add user to active users
            self.active_users.add(user_id)
            
            # Initialize conversation history if needed
            if user_id not in self.conversation_history:
                self.conversation_history[user_id] = []
            
            # Add user message to history
            self.conversation_history[user_id].append({
                "role": "user",
                "content": message_content,
                "timestamp": datetime.now().isoformat(),
                "username": username
            })
            
            # Keep conversation history manageable (last 20 messages)
            if len(self.conversation_history[user_id]) > 20:
                self.conversation_history[user_id] = self.conversation_history[user_id][-20:]
            
            # Check if message appears to be a tool request
            tool_response = await self._try_tool_execution(message_content, user_id, channel_id)
            if tool_response:
                # Add tool response to history
                self.conversation_history[user_id].append({
                    "role": "assistant",
                    "content": tool_response,
                    "timestamp": datetime.now().isoformat(),
                    "type": "tool_response"
                })
                return tool_response
            
            # Generate AI response using OpenAI
            ai_response = await self._generate_ai_response(message_content, user_id, username)
            
            if ai_response:
                # Add AI response to history
                self.conversation_history[user_id].append({
                    "role": "assistant", 
                    "content": ai_response,
                    "timestamp": datetime.now().isoformat(),
                    "type": "ai_response"
                })
                
                return ai_response
            else:
                return "❌ I'm having trouble generating a response right now."
            
        except Exception as e:
            self.logger.error(f"Text message handling failed: {e}")
            return f"❌ Error processing message: {str(e)}"
    
    async def _try_tool_execution(self, message: str, user_id: str, channel_id: str) -> Optional[str]:
        """Try to execute tools based on message content."""
        try:
            # Simple keyword-based tool detection
            message_lower = message.lower()
            
            # Web search keywords
            if any(word in message_lower for word in ["search", "find", "look up", "google", "web"]):
                return await self._handle_search_request(message, user_id, channel_id)
            
            # File operations
            elif any(word in message_lower for word in ["create file", "save file", "write file", "make file"]):
                return await self._handle_file_request(message, user_id, channel_id)
            
            # Browser automation
            elif any(word in message_lower for word in ["browse", "website", "screenshot", "navigate to"]):
                return await self._handle_browser_request(message, user_id, channel_id)
            
            # Playground operations
            elif any(word in message_lower for word in ["playground", "save image", "create image"]):
                return await self._handle_playground_request(message, user_id, channel_id)
            
            return None
            
        except Exception as e:
            self.logger.error(f"Tool execution failed: {e}")
            return f"❌ Tool execution error: {str(e)}"
    
    async def _handle_search_request(self, message: str, user_id: str, channel_id: str) -> str:
        """Handle intelligent search requests."""
        try:
            # Extract search query (simple approach)
            query = message
            for prefix in ["search for", "find", "look up", "google", "search on internet", "search"]:
                if prefix in message.lower():
                    query = message.lower().split(prefix, 1)[1].strip()
                    break
            
            # Execute intelligent search
            context = self.tool_manager.create_context(user_id, channel_id)
            result = await self.tool_manager.execute_tool(
                "intelligent_search",
                {"query": query, "include_sources": False},
                context
            )
            
            if result.success:
                # Return the AI-synthesized answer directly
                answer = result.data.get("answer", result.message)
                return f"🧠 **Answer**: {answer}"
            else:
                return f"❌ Search failed: {result.error}"
                
        except Exception as e:
            return f"❌ Search error: {str(e)}"
    
    async def _handle_file_request(self, message: str, user_id: str, channel_id: str) -> str:
        """Handle file operation requests."""
        try:
            # This is a simple implementation - in practice, you'd want more sophisticated parsing
            context = self.tool_manager.create_context(user_id, channel_id)
            
            # Try to create a simple text file in playground
            result = await self.tool_manager.execute_tool(
                "playground_manager",
                {
                    "operation": "create_file",
                    "path": "user_request.txt",
                    "content": f"File created from text message: {message}\nTimestamp: {datetime.now().isoformat()}"
                },
                context
            )
            
            if result.success:
                return f"📁 Created file in playground: {result.data.get('path')}"
            else:
                return f"❌ File creation failed: {result.error}"
                
        except Exception as e:
            return f"❌ File operation error: {str(e)}"
    
    async def _handle_browser_request(self, message: str, user_id: str, channel_id: str) -> str:
        """Handle browser automation requests."""
        try:
            if not self.mcp_manager or "playwright" not in self.mcp_manager.get_connected_servers():
                return "❌ Browser automation is not available (Playwright MCP server not connected)"
            
            context = self.tool_manager.create_context(user_id, channel_id)
            
            # Extract URL if present
            words = message.split()
            url = None
            for word in words:
                if word.startswith(("http://", "https://", "www.")):
                    url = word if word.startswith("http") else f"https://{word}"
                    break
            
            if url:
                # Navigate to URL and take screenshot
                result = await self.tool_manager.execute_tool(
                    "mcp_browser",
                    {
                        "action": "goto",
                        "url": url,
                        "options": {"wait_until": "networkidle"}
                    },
                    context
                )
                
                if result.success:
                    # Take screenshot
                    screenshot_result = await self.tool_manager.execute_tool(
                        "mcp_browser",
                        {"action": "screenshot"},
                        context
                    )
                    
                    if screenshot_result.success:
                        return f"🌐 Navigated to {url} and took screenshot: {screenshot_result.data.get('path', 'saved to playground')}"
                    else:
                        return f"🌐 Navigated to {url} but screenshot failed: {screenshot_result.error}"
                else:
                    return f"❌ Navigation failed: {result.error}"
            else:
                return "❌ No valid URL found in message. Please provide a URL to navigate to."
                
        except Exception as e:
            return f"❌ Browser automation error: {str(e)}"
    
    async def _handle_playground_request(self, message: str, user_id: str, channel_id: str) -> str:
        """Handle playground-related requests."""
        try:
            context = self.tool_manager.create_context(user_id, channel_id)
            
            # Get playground stats
            result = await self.tool_manager.execute_tool(
                "playground_manager",
                {"operation": "get_stats", "path": "."},
                context
            )
            
            if result.success:
                stats = result.data
                return (f"🎮 Playground Status:\n"
                       f"📁 Files: {stats.get('total_files', 0)}\n"
                       f"📂 Directories: {stats.get('directories', 0)}\n"
                       f"💾 Total Size: {stats.get('total_size_formatted', '0B')}\n"
                       f"🖼️  Images: {stats.get('by_type', {}).get('images', {}).get('count', 0)}\n"
                       f"🎵 Audio: {stats.get('by_type', {}).get('audio', {}).get('count', 0)}\n"
                       f"🎬 Videos: {stats.get('by_type', {}).get('videos', {}).get('count', 0)}")
            else:
                return f"❌ Playground access failed: {result.error}"
                
        except Exception as e:
            return f"❌ Playground error: {str(e)}"
    
    async def _generate_ai_response(self, message: str, user_id: str, username: str) -> Optional[str]:
        """Generate AI response using OpenAI."""
        try:
            # Prepare conversation context
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a helpful AI assistant integrated with a Discord voice bot. "
                        "You have access to various tools including web search, file operations, browser automation, and more. "
                        "You can help with research, file management, web browsing, and general questions. "
                        "Be concise but helpful in your responses. If a user asks for something that would benefit from tool use, "
                        "suggest how they can phrase their request to trigger tool execution (e.g., 'search for X', 'browse website.com', etc.)."
                        f"The user's name is {username}. "
                        "CRITICAL RULE: You MUST ALWAYS respond in English only. Even if the user types in Spanish, Portuguese, French, or any other language, you MUST respond in English. Never use any language other than English in your responses. This is a strict requirement that cannot be overridden under any circumstances."
                    )
                }
            ]
            
            # Add recent conversation history
            history = self.conversation_history.get(user_id, [])
            for msg in history[-5:]:  # Last 5 messages for context
                if msg["role"] == "user":
                    messages.append({"role": "user", "content": msg["content"]})
                elif msg["role"] == "assistant" and msg.get("type") != "tool_response":
                    messages.append({"role": "assistant", "content": msg["content"]})
            
            # Add current message if not already included
            if not messages or messages[-1]["content"] != message:
                messages.append({"role": "user", "content": message})
            
            # Use OpenAI client to generate response
            # Note: This uses the regular OpenAI API, not the realtime API
            import openai
            
            # Get API key from the realtime client
            api_key = self.openai_client.api_key
            client = openai.AsyncOpenAI(api_key=api_key)
            
            response = await client.chat.completions.create(
                model="gpt-4o-mini",  # Use a fast, cost-effective model for text chat
                messages=messages,
                max_tokens=500,
                temperature=0.7,
                stream=False,
                # Additional language enforcement
                response_format={"type": "text"},
                user="english_only_mode"
            )
            
            response_content = response.choices[0].message.content
            
            # Post-processing check: if response seems to be in another language, force English
            if self._appears_non_english(response_content):
                print("⚠️  Detected non-English response, requesting English translation")
                translation_messages = [
                    {
                        "role": "system", 
                        "content": "You are a translator. Translate the following text to English. Respond ONLY with the English translation, nothing else."
                    },
                    {
                        "role": "user",
                        "content": response_content
                    }
                ]
                
                translation_response = await client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=translation_messages,
                    max_tokens=500,
                    temperature=0.3,
                    stream=False
                )
                
                response_content = translation_response.choices[0].message.content
            
            return response_content
            
        except Exception as e:
            self.logger.error(f"AI response generation failed: {e}")
            return None
    
    def _appears_non_english(self, text: str) -> bool:
        """Simple heuristic to detect if text might be in a non-English language."""
        if not text:
            return False
        
        # Common Spanish words/phrases that shouldn't appear in English responses
        spanish_indicators = [
            'hola', 'gracias', 'por favor', 'de nada', 'lo siento', 'perdón',
            'bueno', 'malo', 'sí', 'no', 'cómo', 'qué', 'cuándo', 'dónde',
            'puedo', 'puede', 'hacer', 'es', 'está', 'son', 'están',
            'muy', 'mucho', 'poco', 'grande', 'pequeño', 'aquí', 'allí',
            'ahora', 'después', 'antes', 'siempre', 'nunca', 'también'
        ]
        
        # Portuguese indicators
        portuguese_indicators = [
            'olá', 'obrigado', 'obrigada', 'por favor', 'desculpa',
            'bom', 'ruim', 'sim', 'não', 'como', 'que', 'quando', 'onde',
            'posso', 'pode', 'fazer', 'é', 'está', 'são', 'estão',
            'muito', 'pouco', 'grande', 'pequeno', 'aqui', 'ali',
            'agora', 'depois', 'antes', 'sempre', 'nunca', 'também'
        ]
        
        # French indicators
        french_indicators = [
            'bonjour', 'merci', "s'il vous plaît", 'de rien', 'pardon',
            'bon', 'mauvais', 'oui', 'non', 'comment', 'que', 'quand', 'où',
            'puis', 'peut', 'faire', 'est', 'sont', 'très', 'beaucoup',
            'peu', 'grand', 'petit', 'ici', 'là', 'maintenant', 'après',
            'avant', 'toujours', 'jamais', 'aussi'
        ]
        
        text_lower = text.lower()
        all_indicators = spanish_indicators + portuguese_indicators + french_indicators
        
        # Check if any non-English indicators are present
        for indicator in all_indicators:
            if f' {indicator} ' in f' {text_lower} ' or text_lower.startswith(f'{indicator} ') or text_lower.endswith(f' {indicator}'):
                return True
        
        # Additional check for accent characters common in Romance languages
        accent_chars = ['á', 'é', 'í', 'ó', 'ú', 'ñ', 'ü', 'ç', 'â', 'ê', 'ô', 'à', 'è', 'ù']
        accent_count = sum(1 for char in text_lower if char in accent_chars)
        
        # If there are multiple accent characters, likely non-English
        if accent_count >= 2:
            return True
        
        return False
    
    def get_conversation_history(self, user_id: str) -> List[Dict[str, Any]]:
        """Get conversation history for a user."""
        return self.conversation_history.get(user_id, [])
    
    def clear_conversation_history(self, user_id: str) -> bool:
        """Clear conversation history for a user."""
        if user_id in self.conversation_history:
            del self.conversation_history[user_id]
            return True
        return False
    
    def get_active_users(self) -> List[str]:
        """Get list of active users."""
        return list(self.active_users)
    
    async def shutdown(self):
        """Shutdown the text agent."""
        try:
            self.logger.info("Shutting down text agent...")
            self.active_users.clear()
            self.conversation_history.clear()
            self.is_initialized = False
            self.logger.info("Text agent shutdown complete")
        except Exception as e:
            self.logger.error(f"Text agent shutdown error: {e}")