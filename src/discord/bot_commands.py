"""Discord bot commands for voice interaction."""

import discord
from discord.ext import commands
import discord.ext.voice_recv as voice_recv
import asyncio


class VoiceBotCommands(commands.Cog):
    """Discord bot commands for voice functionality"""
    
    def __init__(self, bot, openai_client, voice_receiver):
        self.bot = bot
        self.openai_client = openai_client
        self.voice_receiver = voice_receiver
    
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

            # Connect to OpenAI realtime AFTER we are in the voice channel
            print("DEBUG: Connecting to OpenAI...")
            if not self.openai_client.is_connected:
                await self.openai_client.connect()

            # Start voice receiving for hands-free operation
            print("DEBUG: Starting voice receiver...")
            await self.voice_receiver.start_listening(self.openai_client, None, voice_client)
            await ctx.send("🎤 **Hands-free voice chat active!** Just speak naturally - I'll respond when you're done!")
            
        except Exception as e:
            print(f"DEBUG: Join command error: {e}")
            await ctx.send(f"❌ Failed to join: {e}")

    @commands.command(name="leave")
    async def leave_voice(self, ctx):
        """Leave voice channel"""
        self.voice_receiver.stop_listening()
        
        if ctx.voice_client:
            await ctx.voice_client.disconnect()

            # Disconnect from OpenAI realtime once we leave the voice channel
            if self.openai_client.is_connected:
                await self.openai_client.disconnect()
            await ctx.send("👋 Left voice channel")
        else:
            await ctx.send("❌ Not in a voice channel")

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