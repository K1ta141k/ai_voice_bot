"""Main Discord voice bot with modular architecture."""

import discord
from discord.ext import commands
import discord.ext.voice_recv as voice_recv
import logging

# Suppress verbose opus decoder errors
logging.getLogger('discord.ext.voice_recv.opus').setLevel(logging.ERROR)
logging.getLogger('discord.ext.voice_recv.router').setLevel(logging.ERROR)

from .utils.config import Config
from .openai.realtime_client import OpenAIRealtime
from .discord.voice_receiver import DiscordVoiceReceiver
from .discord.bot_commands import VoiceBotCommands
from .agents.voice_agent import VoiceAgent
from .agents.text_agent import TextAgent


class VoiceBot:
    """Main Discord Voice Bot class with dependency injection"""
    
    def __init__(self):
        # Load configuration
        self.config = Config()
        self.config.print_status()
        
        # Initialize Discord bot
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True

        # Initialize components first, some need the bot instance later
        self.openai_client = OpenAIRealtime(self.config.openai_api_key)
        self.voice_receiver = DiscordVoiceReceiver()
        self.voice_agent = VoiceAgent(self.openai_client)
        self.text_agent = TextAgent(self.openai_client)

        # Prepare commands cog (requires bot reference but we'll inject later)
        self.voice_commands = None  # placeholder; real instance created in setup_hook

        class CustomBot(commands.Bot):
            def __init__(self, outer, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._outer = outer

            async def setup_hook(self):
                # Instantiate cog now that 'self' (bot) exists
                outer = self._outer
                outer.voice_commands = VoiceBotCommands(self, outer.openai_client, outer.voice_receiver, outer.voice_agent, outer.text_agent)
                await self.add_cog(outer.voice_commands)
                
                # Initialize agents (but don't connect to OpenAI yet for voice)
                await outer.voice_agent.initialize(connect_openai=False)
                await outer.text_agent.initialize()

        # Disable nacl warnings
        voice_recv.VoiceRecvClient.warn_nacl = False

        self.bot = CustomBot(self, command_prefix="!", intents=intents)

        # Inject dependencies that require bot
        self.openai_client.set_bot_instance(self.bot)

        # Setup bot events & permissions
        self._setup_events()
        self._setup_permissions()
    
    def _setup_events(self):
        """Setup Discord bot events"""
        @self.bot.event
        async def on_ready():
            import sys
            print(f"🤖 Logged in as {self.bot.user} (ID: {self.bot.user.id})", flush=True)
            print("------", flush=True)
            sys.stdout.flush()
            sys.stderr.flush()
        
        @self.bot.event
        async def on_message(message):
            """Handle all messages including text AI for ai_general channel"""
            if message.author.bot:
                return
            
            import sys
            print(f"📩 RECEIVED MESSAGE: '{message.content}' from {message.author} (ID: {message.author.id})", flush=True)
            sys.stdout.flush()
            
            # Handle text AI for ai_general channel from _suiman
            if (message.channel.name == "ai_general" and 
                message.author.name == "_suiman" and 
                self.config.is_user_allowed(message.author.id)):
                
                try:
                    print(f"💬 Processing AI chat message from {message.author.name}")
                    response = await self.text_agent.handle_message(
                        message.content,
                        str(message.author.id),
                        str(message.channel.id), 
                        message.author.name
                    )
                    
                    if response:
                        # Split long responses to avoid Discord message limits
                        if len(response) > 2000:
                            chunks = [response[i:i+1900] for i in range(0, len(response), 1900)]
                            for chunk in chunks:
                                await message.channel.send(chunk)
                        else:
                            await message.channel.send(response)
                except Exception as e:
                    print(f"❌ Text AI error: {e}")
                    await message.channel.send(f"❌ Sorry, I encountered an error: {str(e)}")
                
                # Don't process as command if it's an AI chat message
                return
            
            # Process commands for other messages
            await self.bot.process_commands(message)
        
        @self.bot.event
        async def on_command(ctx):
            """Log when a command is invoked"""
            print(f"⚡ COMMAND INVOKED: '{ctx.command}' by {ctx.author} (ID: {ctx.author.id})")
        
        @self.bot.event
        async def on_command_error(ctx, error):
            """Log command errors"""
            print(f"❌ COMMAND ERROR: '{ctx.command}' failed with: {error}")
            await ctx.send(f"❌ Command error: {error}")
        
        @self.bot.event
        async def on_voice_state_update(member, before, after):
            """Monitor voice state changes"""
            if member.bot:
                return
            print(f"🎙️ VOICE STATE: {member.display_name} - before: {before.channel}, after: {after.channel}, self_mute: {after.self_mute}, self_deaf: {after.self_deaf}")
            if before.channel != after.channel:
                if after.channel:
                    print(f"🔊 {member.display_name} JOINED voice channel: {after.channel.name}")
                else:
                    print(f"🔇 {member.display_name} LEFT voice channel")
    
    def _setup_permissions(self):
        """Setup user permission checking"""
        @self.bot.check
        async def globally_allow_only_author(ctx: commands.Context) -> bool:
            return self.config.is_user_allowed(ctx.author.id)
    
    def run(self):
        """Start the Discord bot"""
        self.bot.run(self.config.discord_token)