"""Discord bot commands for voice interaction."""

import discord
from discord.ext import commands
import discord.ext.voice_recv as voice_recv
import asyncio


class VoiceBotCommands(commands.Cog):
    """Discord bot commands for voice functionality"""
    
    def __init__(self, bot, openai_client, voice_receiver, voice_agent=None, text_agent=None):
        self.bot = bot
        self.openai_client = openai_client
        self.voice_receiver = voice_receiver
        self.voice_agent = voice_agent
        self.text_agent = text_agent
    
    @commands.command(name="join")
    async def join_voice(self, ctx):
        """Join voice channel and start receiving audio"""
        if not ctx.author.voice:
            await ctx.send("❌ You need to be in a voice channel!")
            return
        
        channel = ctx.author.voice.channel
        
        # Check if already connected to this channel
        if ctx.voice_client and ctx.voice_client.channel == channel:
            await ctx.send(f"✅ Already connected to {channel.name}")
            return
        
        # Disconnect from any existing connection first
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
            await asyncio.sleep(1)
        
        try:
            # Try connecting with retry logic
            voice_client = None
            max_retries = 3
            
            for attempt in range(max_retries):
                try:
                    print(f"DEBUG: Connection attempt {attempt + 1}")
                    await ctx.send(f"🔄 Connecting to {channel.name}... (Attempt {attempt + 1})")
                    
                    # Use VoiceRecvClient for receiving audio
                    voice_client = await channel.connect(cls=voice_recv.VoiceRecvClient, timeout=15.0, reconnect=False)
                    
                    # Wait and verify connection
                    await asyncio.sleep(1)
                    
                    if voice_client.is_connected():
                        print(f"DEBUG: Voice client connected successfully")
                        break
                    else:
                        print(f"DEBUG: Voice client not connected after attempt {attempt + 1}")
                        await voice_client.disconnect(force=True)
                        voice_client = None
                        
                except Exception as e:
                    print(f"DEBUG: Connection attempt {attempt + 1} failed: {e}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2)
                    else:
                        await ctx.send(f"❌ Failed to connect after {max_retries} attempts: {e}")
                        return
            
            if not voice_client or not voice_client.is_connected():
                await ctx.send("❌ Could not establish voice connection")
                return

            await ctx.send(f"✅ Joined {channel.name}")

            # Start a new conversation session
            self.openai_client.audio_manager.new_session()

            # Start voice session with tools (this will connect to OpenAI)
            user_id = str(ctx.author.id)
            channel_id = str(ctx.channel.id) if ctx.channel else None
            
            if self.voice_agent:
                success = await self.voice_agent.start_voice_session(user_id, channel_id)
                if success:
                    print("✅ Voice session started with tools enabled")
                else:
                    print("⚠️ Voice session failed, falling back to basic connection")
                    # Fallback to basic OpenAI connection
                    if not self.openai_client.is_connected:
                        await self.openai_client.connect()

            # Start voice receiving for hands-free operation
            print("DEBUG: Starting voice receiver...")
            await self.voice_receiver.start_listening(self.openai_client, None, voice_client)
            await ctx.send("🎤 **Hands-free voice chat active with tools!** Just speak naturally - I'll respond when you're done!")
            
        except Exception as e:
            print(f"DEBUG: Join command error: {e}")
            await ctx.send(f"❌ Failed to join: {e}")

    @commands.command(name="leave")
    async def leave_voice(self, ctx):
        """Leave voice channel"""
        self.voice_receiver.stop_listening()
        
        if ctx.voice_client:
            await ctx.voice_client.disconnect()

            # End voice session (this will disconnect from OpenAI and clear context)
            if self.voice_agent:
                await self.voice_agent.end_voice_session()
            else:
                # Fallback: disconnect from OpenAI manually
                if self.openai_client.is_connected:
                    await self.openai_client.disconnect()
            
            await ctx.send("👋 Left voice channel and cleared context")
        else:
            await ctx.send("❌ Not in a voice channel")
    
    @commands.command(name="restart")
    async def restart_session(self, ctx):
        """Restart the voice session to clear context while staying in voice channel"""
        if not ctx.voice_client or not ctx.voice_client.is_connected():
            await ctx.send("❌ Not connected to a voice channel")
            return
        
        try:
            await ctx.send("🔄 Restarting voice session...")
            
            # End current session to clear context
            if self.voice_agent:
                await self.voice_agent.end_voice_session()
            else:
                # Fallback: disconnect from OpenAI manually
                if self.openai_client.is_connected:
                    await self.openai_client.disconnect()
            
            # Start new session
            user_id = str(ctx.author.id)
            channel_id = str(ctx.channel.id) if ctx.channel else None
            
            # Start a new conversation session
            self.openai_client.audio_manager.new_session()
            
            if self.voice_agent:
                success = await self.voice_agent.start_voice_session(user_id, channel_id)
                if success:
                    await ctx.send("✅ Voice session restarted with fresh context!")
                else:
                    await ctx.send("❌ Failed to restart voice session")
            else:
                # Fallback to basic OpenAI connection
                if not self.openai_client.is_connected:
                    await self.openai_client.connect()
                await ctx.send("✅ Basic voice session restarted")
                
        except Exception as e:
            await ctx.send(f"❌ Failed to restart session: {e}")
            print(f"❌ Restart command error: {e}")

    @commands.command(name="timeout")
    async def set_timeout(self, ctx, seconds: float = None):
        """Set voice timeout (default 2.0 seconds)"""
        if seconds is None:
            await ctx.send(f"Current timeout: {self.voice_receiver.voice_timeout}s")
        else:
            self.voice_receiver.set_timeout(seconds)
            await ctx.send(f"✅ Voice timeout set to {self.voice_receiver.voice_timeout}s")

    # ---------------- Push-to-Talk ----------------

    @commands.command(name="talk")
    async def push_to_talk(self, ctx, action: str = None):
        """Push-to-talk control. Usage: !talk start | stop | auto"""
        if action is None:
            await ctx.send("ℹ️ Usage: `!talk start`, `!talk stop`, or `!talk auto`")
            return

        action = action.lower()
        if action == "start":
            self.voice_receiver.start_push_to_talk()
            await ctx.send("🎙️ Push-to-talk recording started. Say your sentence then run `!talk stop`.")
        elif action == "stop":
            self.voice_receiver.stop_push_to_talk()
            await ctx.send("🛑 Push-to-talk stopped – sending audio to AI.")
        elif action == "auto":
            self.voice_receiver.auto_mode = True
            self.voice_receiver.ptt_active = False
            await ctx.send("🤖 Returned to automatic voice-detection mode.")
        else:
            await ctx.send("❌ Unknown action. Use `start`, `stop`, or `auto`.")

    @commands.command(name="ping")
    async def ping(self, ctx):
        print(f"🏓 PING COMMAND EXECUTED by {ctx.author}")
        await ctx.send("🏓 Pong!")
        print(f"🏓 PONG RESPONSE SENT to {ctx.author}")
    
    @commands.command(name="tools")
    async def tools_info(self, ctx, action: str = "list"):
        """Manage and view available tools"""
        try:
            if not self.voice_agent:
                await ctx.send("❌ Voice agent not available")
                return
            
            if action == "list":
                user_id = str(ctx.author.id)
                tools = self.voice_agent.get_available_tools(user_id)
                print(f"DEBUG: Found {len(tools) if tools else 0} tools for user {user_id}")
                
                # Debug tool manager and registry
                all_tools_registry = self.voice_agent.tool_manager.registry.list_tools()
                all_tools_objects = self.voice_agent.tool_manager.registry.get_all_tools()
                available_tools = self.voice_agent.tool_manager.get_available_tools(user_id)
                print(f"DEBUG: Registry list_tools: {all_tools_registry}")
                print(f"DEBUG: Registry get_all_tools: {len(all_tools_objects)}")
                print(f"DEBUG: Available tools for user: {len(available_tools)}")
                
                if not tools:
                    if all_tools_registry:
                        await ctx.send(f"🔧 Found {len(all_tools_registry)} tools in registry: {', '.join(all_tools_registry)}")
                        await ctx.send("⚠️ But tool descriptions are empty - checking tool objects...")
                        
                        # Try to show tools without descriptions
                        simple_tools = []
                        for tool_name in all_tools_registry:
                            tool = self.voice_agent.tool_manager.registry.get_tool(tool_name)
                            if tool:
                                simple_tools.append(f"{tool.name}: {tool.description[:50]}...")
                        
                        if simple_tools:
                            await ctx.send("🛠️ Tools found:\n" + "\n".join(simple_tools))
                    else:
                        await ctx.send("📋 No tools available")
                    return
                
                # Create embed with tools
                embed = discord.Embed(
                    title="🔧 Available Tools",
                    description=f"Found {len(tools)} tools",
                    color=0x00ff00
                )
                
                for tool in tools[:10]:  # Limit to 10 tools
                    param_count = len(tool.get("parameters", []))
                    embed.add_field(
                        name=tool["name"],
                        value=f"{tool['description'][:100]}...\n*{param_count} parameters*",
                        inline=False
                    )
                
                await ctx.send(embed=embed)
                
            elif action == "status":
                status = await self.voice_agent.get_system_status()
                
                embed = discord.Embed(
                    title="📊 Voice Agent Status",
                    color=0x0099ff
                )
                
                # Voice Agent Status
                va_status = status.get("voice_agent", {})
                embed.add_field(
                    name="Voice Agent",
                    value=f"Initialized: {'✅' if va_status.get('initialized') else '❌'}\n"
                          f"Active User: {va_status.get('active_user', 'None')}\n"
                          f"Tools Enabled: {'✅' if va_status.get('tools_enabled') else '❌'}",
                    inline=True
                )
                
                # Tools Status
                tools_info = status.get("tools", {})
                validation = tools_info.get("validation", {})
                embed.add_field(
                    name="Tools",
                    value=f"Total: {validation.get('total_tools', 0)}\n"
                          f"Working: {len(validation.get('working_tools', []))}\n"
                          f"Broken: {len(validation.get('broken_tools', []))}",
                    inline=True
                )
                
                # OpenAI Status
                openai_info = status.get("openai", {})
                embed.add_field(
                    name="OpenAI",
                    value=f"Connected: {'✅' if openai_info.get('connected') else '❌'}\n"
                          f"Tools: {'✅' if openai_info.get('tools_enabled') else '❌'}",
                    inline=True
                )
                
                await ctx.send(embed=embed)
                
            elif action == "test":
                # Test a simple tool
                if not tools:
                    await ctx.send("❌ No tools available to test")
                    return
                
                await ctx.send("🧪 Testing system_commands tool...")
                result = await self.voice_agent.execute_manual_tool(
                    "system_commands", 
                    {"operation": "info"}
                )
                
                if result["success"]:
                    await ctx.send("✅ Tool test successful!")
                else:
                    await ctx.send(f"❌ Tool test failed: {result['error']}")
                    
            else:
                await ctx.send("❌ Unknown action. Use: `list`, `status`, or `test`")
                
        except Exception as e:
            await ctx.send(f"❌ Error managing tools: {str(e)}")
            print(f"❌ Tools command error: {e}")
    
    @commands.command(name="text_ai")
    async def text_ai_info(self, ctx, action: str = "status"):
        """Manage text AI functionality"""
        try:
            if not self.text_agent:
                await ctx.send("❌ Text AI not available")
                return
            
            if action == "status":
                is_initialized = self.text_agent.is_initialized
                active_users = len(self.text_agent.get_active_users())
                
                embed = discord.Embed(
                    title="💬 Text AI Status",
                    description="Current status of the text-based AI system",
                    color=0x00ff00 if is_initialized else 0xff0000
                )
                
                embed.add_field(
                    name="Status",
                    value="🟢 Active" if is_initialized else "🔴 Inactive",
                    inline=True
                )
                
                embed.add_field(
                    name="Active Users", 
                    value=str(active_users),
                    inline=True
                )
                
                embed.add_field(
                    name="Channel",
                    value="#ai_general (for _suiman only)",
                    inline=True
                )
                
                embed.add_field(
                    name="Features",
                    value="• Web Search\n• File Operations\n• Browser Automation\n• Playground Management\n• General AI Chat",
                    inline=False
                )
                
                await ctx.send(embed=embed)
                
            elif action == "history":
                user_id = str(ctx.author.id)
                history = self.text_agent.get_conversation_history(user_id)
                
                if not history:
                    await ctx.send("📝 No conversation history found")
                    return
                
                # Show last 5 messages
                recent_history = history[-5:]
                response = "📝 **Recent Conversation History:**\n\n"
                
                for msg in recent_history:
                    timestamp = msg.get("timestamp", "unknown")
                    role = "🧑" if msg["role"] == "user" else "🤖"
                    content = msg["content"][:100] + ("..." if len(msg["content"]) > 100 else "")
                    response += f"{role} **{timestamp[:19]}**: {content}\n\n"
                
                if len(response) > 2000:
                    response = response[:1900] + "\n... (truncated)"
                
                await ctx.send(response)
                
            elif action == "clear":
                user_id = str(ctx.author.id)
                success = self.text_agent.clear_conversation_history(user_id)
                
                if success:
                    await ctx.send("🗑️ Conversation history cleared")
                else:
                    await ctx.send("📝 No history to clear")
                    
            else:
                await ctx.send("❌ Invalid action. Use: status, history, or clear")
                
        except Exception as e:
            print(f"❌ Text AI command error: {e}")
            await ctx.send(f"❌ Text AI command failed: {e}")
    
    @commands.command(name="help_text")
    async def help_text_ai(self, ctx):
        """Show help for text AI functionality"""
        embed = discord.Embed(
            title="💬 Text AI Help",
            description="Text-based AI chat in #ai_general channel (for _suiman only)",
            color=0x00ff00
        )
        
        embed.add_field(
            name="📝 Basic Chat",
            value="Just type any message in #ai_general and get AI responses",
            inline=False
        )
        
        embed.add_field(
            name="🔍 Web Search",
            value="• \"search for Python tutorials\"\n• \"find information about quantum computing\"\n• \"google latest news\"",
            inline=False
        )
        
        embed.add_field(
            name="🌐 Browser Automation", 
            value="• \"browse https://example.com\"\n• \"screenshot website.com\"\n• \"navigate to github.com\"",
            inline=False
        )
        
        embed.add_field(
            name="📁 File Operations",
            value="• \"create file with my notes\"\n• \"save this to playground\"\n• \"playground status\"",
            inline=False
        )
        
        embed.add_field(
            name="🔧 Management Commands",
            value="• `!text_ai status` - Check AI status\n• `!text_ai history` - View chat history\n• `!text_ai clear` - Clear history",
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    @commands.command(name="voice_session")
    async def voice_session(self, ctx, action: str = "info"):
        """Manage voice session"""
        try:
            if not self.voice_agent:
                await ctx.send("❌ Voice agent not available")
                return
                
            user_id = str(ctx.author.id)
            channel_id = str(ctx.channel.id) if ctx.channel else None
            
            if action == "start":
                success = await self.voice_agent.start_voice_session(user_id, channel_id)
                if success:
                    await ctx.send(f"✅ Voice session started for {ctx.author.mention}")
                else:
                    await ctx.send("❌ Failed to start voice session")
                    
            elif action == "end":
                await self.voice_agent.end_voice_session()
                await ctx.send(f"🔚 Voice session ended for {ctx.author.mention}")
                
            elif action == "info":
                session_info = self.voice_agent.get_session_info()
                
                embed = discord.Embed(
                    title="🎤 Voice Session Info",
                    color=0x00ff00 if session_info.get("session_active") else 0xff0000
                )
                
                embed.add_field(
                    name="Session Status",
                    value=f"Active: {'✅' if session_info.get('session_active') else '❌'}\n"
                          f"User: {session_info.get('active_user', 'None')}\n"
                          f"Channel: {session_info.get('active_channel', 'None')}",
                    inline=False
                )
                
                embed.add_field(
                    name="System Status",
                    value=f"Initialized: {'✅' if session_info.get('initialized') else '❌'}\n"
                          f"OpenAI: {'✅' if session_info.get('openai_connected') else '❌'}\n"
                          f"Tools: {'✅' if session_info.get('tools_enabled') else '❌'}",
                    inline=False
                )
                
                await ctx.send(embed=embed)
                
            else:
                await ctx.send("❌ Unknown action. Use: `start`, `end`, or `info`")
                
        except Exception as e:
            await ctx.send(f"❌ Error managing voice session: {str(e)}")
            print(f"❌ Voice session command error: {e}")
    
    @commands.command(name="tool")
    async def execute_tool(self, ctx, tool_name: str = None, *, params: str = None):
        """Execute a tool via chat. Usage: !tool <tool_name> <json_params>"""
        try:
            if not self.voice_agent:
                await ctx.send("❌ Voice agent not available")
                return
            
            if not tool_name:
                await ctx.send("❌ Please specify a tool name. Use `!tools list` to see available tools.")
                return
            
            # Parse parameters
            parameters = {}
            if params:
                try:
                    import json
                    parameters = json.loads(params)
                except json.JSONDecodeError:
                    await ctx.send("❌ Invalid JSON parameters. Example: `!tool web_search {\"query\": \"Python tutorials\"}`")
                    return
            
            # Get or create session context
            user_id = str(ctx.author.id)
            channel_id = str(ctx.channel.id)
            
            if not self.voice_agent.active_user:
                # Start a lightweight session for tool execution
                await self.voice_agent.start_voice_session(user_id, channel_id)
            
            await ctx.send(f"🔧 Executing tool: {tool_name}...")
            
            # Execute the tool
            result = await self.voice_agent.execute_manual_tool(tool_name, parameters)
            
            # Format result for Discord
            if result["success"]:
                embed = discord.Embed(
                    title=f"✅ Tool: {tool_name}",
                    description=result.get("message", "Tool executed successfully"),
                    color=0x00ff00
                )
                
                # Add result data if available
                if result.get("data"):
                    data = result["data"]
                    
                    # Handle different data types
                    if isinstance(data, dict):
                        for key, value in list(data.items())[:5]:  # Limit to 5 fields
                            if isinstance(value, (str, int, float, bool)):
                                embed.add_field(
                                    name=str(key).title(),
                                    value=str(value)[:1000],  # Limit field length
                                    inline=True
                                )
                            elif isinstance(value, list) and len(value) <= 3:
                                embed.add_field(
                                    name=str(key).title(),
                                    value="\n".join(str(item)[:100] for item in value),
                                    inline=False
                                )
                    
                await ctx.send(embed=embed)
                
                # If there's a lot of data, send as text file
                if result.get("data") and len(str(result["data"])) > 2000:
                    import tempfile
                    import json
                    
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                        json.dump(result["data"], f, indent=2)
                        temp_path = f.name
                    
                    await ctx.send(
                        "📄 Full result data:",
                        file=discord.File(temp_path, filename=f"{tool_name}_result.json")
                    )
                    
                    # Clean up temp file
                    import os
                    os.unlink(temp_path)
            else:
                embed = discord.Embed(
                    title=f"❌ Tool Failed: {tool_name}",
                    description=result.get("message", "Tool execution failed"),
                    color=0xff0000
                )
                
                if result.get("error"):
                    embed.add_field(
                        name="Error",
                        value=result["error"][:1000],
                        inline=False
                    )
                
                await ctx.send(embed=embed)
                
        except Exception as e:
            await ctx.send(f"❌ Error executing tool: {str(e)}")
            print(f"❌ Tool execution error: {e}")
    
    @commands.command(name="tool_info")
    async def tool_info(self, ctx, tool_name: str = None):
        """Get detailed information about a specific tool"""
        try:
            if not self.voice_agent:
                await ctx.send("❌ Voice agent not available")
                return
            
            if not tool_name:
                await ctx.send("❌ Please specify a tool name. Use `!tools list` to see available tools.")
                return
            
            # Get tool from registry
            tool = self.voice_agent.tool_manager.registry.get_tool(tool_name)
            if not tool:
                await ctx.send(f"❌ Tool '{tool_name}' not found. Use `!tools list` to see available tools.")
                return
            
            # Create detailed embed
            embed = discord.Embed(
                title=f"🔧 Tool: {tool.name}",
                description=tool.description,
                color=0x0099ff
            )
            
            # Add parameters information
            if tool._parameters:
                param_text = []
                for param in tool._parameters:
                    required_text = "**Required**" if param.required else "*Optional*"
                    default_text = f" (default: {param.default})" if param.default is not None else ""
                    enum_text = f" Options: {', '.join(param.enum)}" if param.enum else ""
                    
                    param_text.append(
                        f"• `{param.name}` ({param.type}) - {required_text}{default_text}\n"
                        f"  {param.description}{enum_text}"
                    )
                
                embed.add_field(
                    name="Parameters",
                    value="\n\n".join(param_text)[:1000],
                    inline=False
                )
            else:
                embed.add_field(
                    name="Parameters",
                    value="No parameters required",
                    inline=False
                )
            
            # Add usage examples
            examples = self._get_tool_examples(tool_name)
            if examples:
                embed.add_field(
                    name="Usage Examples",
                    value=examples,
                    inline=False
                )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ Error getting tool info: {str(e)}")
            print(f"❌ Tool info error: {e}")
    
    def _get_tool_examples(self, tool_name: str) -> str:
        """Get usage examples for a tool."""
        examples = {
            "web_search": """```
!tool web_search {"query": "Python tutorials"}
!tool web_search {"query": "weather today", "max_results": 3}
!tool web_search {"query": "AI news", "search_engine": "google"}
!tool web_search {"query": "programming", "search_engine": "openai"}
!tool web_search {"query": "latest tech", "search_engine": "perplexity"}
!tool web_search {"query": "best results", "search_engine": "auto"}
```""",
            "file_operations": """```
!tool file_operations {"operation": "list", "path": "."}
!tool file_operations {"operation": "read", "path": "README.md"}
!tool file_operations {"operation": "write", "path": "test.txt", "content": "Hello world"}
```""",
            "system_commands": """```
!tool system_commands {"operation": "info"}
!tool system_commands {"operation": "disk_usage", "path": "."}
!tool system_commands {"operation": "execute_safe", "command": "ls", "args": "-la"}
```"""
        }
        
        return examples.get(tool_name, "No examples available")
    
    @commands.command(name="help_tools")
    async def help_tools(self, ctx):
        """Show help for all tool-related commands"""
        embed = discord.Embed(
            title="🔧 Tool Commands Help",
            description="Available commands for using tools via chat:",
            color=0x00ff00
        )
        
        embed.add_field(
            name="📋 List Tools",
            value="`!tools list` - Show all available tools\n`!tools status` - System status\n`!tools test` - Test a tool",
            inline=False
        )
        
        embed.add_field(
            name="🔍 Tool Information",
            value="`!tool_info <tool_name>` - Get detailed info about a tool\nExample: `!tool_info web_search`",
            inline=False
        )
        
        embed.add_field(
            name="⚡ Execute Tools",
            value="`!tool <tool_name> <json_params>` - Execute a tool\nExample: `!tool web_search {\"query\": \"Python\"}`",
            inline=False
        )
        
        embed.add_field(
            name="🎤 Voice Sessions",
            value="`!voice_session start` - Start voice session\n`!voice_session info` - Session info\n`!voice_session end` - End session",
            inline=False
        )
        
        embed.add_field(
            name="🎯 Available Tools",
            value="• `web_search` - Search the web\n• `file_operations` - File/directory operations\n• `system_commands` - Safe system commands",
            inline=False
        )
        
        embed.add_field(
            name="💡 Pro Tips",
            value="• Use `!tool_info <tool_name>` to see parameters and examples\n• JSON parameters must be properly formatted\n• Tools can be used in voice chat or text chat",
            inline=False
        )
        
        await ctx.send(embed=embed)