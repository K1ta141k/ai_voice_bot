"""OpenAI Realtime API client for voice interactions."""

import websockets
import json
import base64
import asyncio
import numpy as np
import discord
import io
from ..audio.manager import AudioManager


class OpenAIRealtime:
    """OpenAI Realtime API client for voice processing"""
    
    def __init__(self, api_key):
        self.api_key = api_key
        self.ws = None
        self.is_connected = False
        self.audio_manager = AudioManager()
        self.current_response_audio = []
        self.current_response_text = ""
        self.response_complete = False
        self.is_streaming_audio = False
        self.streaming_audio_source = None
        
    async def connect(self):
        """Connect to OpenAI Realtime API"""
        try:
            print("🔗 Connecting to OpenAI Realtime API...")
            
            self.ws = await websockets.connect(
                "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01",
                additional_headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "OpenAI-Beta": "realtime=v1"
                }
            )
            
            # Configure session
            session_config = {
                "type": "session.update",
                "session": {
                    "modalities": ["text", "audio"],
                    "instructions": "You are a helpful AI assistant in a Discord voice chat. Keep responses conversational and natural. Respond with voice when possible.",
                    "voice": "alloy",
                    "input_audio_format": "pcm16",
                    "output_audio_format": "pcm16",
                    "input_audio_transcription": {
                        "model": "whisper-1"
                    }
                }
            }
            
            await self.ws.send(json.dumps(session_config))
            self.is_connected = True
            print("✅ Connected to OpenAI Realtime API")
            
            # Start listening for responses
            asyncio.create_task(self.listen_for_responses())
            
        except Exception as e:
            print(f"❌ Failed to connect to OpenAI: {e}")
            self.is_connected = False
            
    async def send_voice_message(self, audio_data, duration):
        """Send voice message to OpenAI"""
        if not self.is_connected:
            print("❌ Not connected to OpenAI")
            return
            
        try:
            # Add audio prefix to prevent Discord cutoff
            prefixed_audio = self._add_audio_prefix(audio_data)
            
            # Save user audio
            user_audio_file = self.audio_manager.save_audio_file(prefixed_audio, "user_input")
            
            # Convert to base64
            audio_b64 = base64.b64encode(prefixed_audio.tobytes()).decode()
            
            # Clear any previous response data
            self.current_response_audio = []
            self.current_response_text = ""
            self.response_complete = False
            self.is_streaming_audio = False
            
            # Send audio to OpenAI
            audio_message = {
                "type": "input_audio_buffer.append",
                "audio": audio_b64
            }
            await self.ws.send(json.dumps(audio_message))
            
            # Commit and request response
            await self.ws.send(json.dumps({"type": "input_audio_buffer.commit"}))
            await self.ws.send(json.dumps({"type": "response.create"}))
            
            print(f"📤 Sent {duration:.1f}s voice message to OpenAI")
            
        except Exception as e:
            print(f"❌ Error sending voice message: {e}")
            
    def _add_audio_prefix(self, audio_data):
        """Add silence + tone prefix to prevent Discord audio cutoff"""
        try:
            # 200ms of silence
            silence_samples = int(0.2 * 24000)
            silence = np.zeros(silence_samples, dtype=np.int16)
            
            # 50ms of quiet tone (1000Hz)
            tone_samples = int(0.05 * 24000)
            t = np.linspace(0, 0.05, tone_samples, False)
            tone = (np.sin(2 * np.pi * 1000 * t) * 1000).astype(np.int16)
            
            # Concatenate: silence + tone + audio
            prefixed = np.concatenate([silence, tone, audio_data])
            return prefixed
            
        except Exception as e:
            print(f"❌ Error adding audio prefix: {e}")
            return audio_data
            
    async def listen_for_responses(self):
        """Listen for responses from OpenAI"""
        try:
            async for message in self.ws:
                data = json.loads(message)
                await self.handle_message(data)
                
        except Exception as e:
            print(f"❌ Error listening for responses: {e}")
            self.is_connected = False
            
    async def handle_message(self, data):
        """Handle messages from OpenAI"""
        try:
            message_type = data.get("type", "")
            
            if message_type == "response.audio.delta":
                # Stream audio response as it arrives
                audio_b64 = data.get("delta", "")
                if audio_b64:
                    audio_chunk = base64.b64decode(audio_b64)
                    audio_array = np.frombuffer(audio_chunk, dtype=np.int16)
                    
                    # Accumulate for final logging
                    self.current_response_audio.append(audio_array)
                    
                    # Stream this chunk immediately to Discord
                    await self.stream_audio_chunk(audio_array)
                    
            elif message_type == "response.audio.done":
                # Audio streaming complete - play and save
                if self.current_response_audio:
                    combined_audio = np.concatenate(self.current_response_audio)
                    
                    # Play the audio response in Discord
                    await self.play_audio_response(combined_audio)
                    
                    # Save text response if we have any
                    if self.current_response_text.strip():
                        self.audio_manager.save_text_response(self.current_response_text.strip())
                    
                    # Finalize streaming
                    await self.finalize_audio_stream()
                    
                    # Reset for next response
                    self.current_response_audio = []
                    self.current_response_text = ""
                    self.is_streaming_audio = False
                    
            elif message_type == "input_audio_buffer.speech_started":
                print("👂 OpenAI detected speech start")
                
            elif message_type == "input_audio_buffer.speech_stopped":
                print("✋ OpenAI detected speech stop")
                
            elif message_type == "response.text.delta":
                # Accumulate text responses
                text = data.get("delta", "")
                if text:
                    self.current_response_text += text
                    print(f"🤖 AI: {text}", end="")
                    
            elif message_type == "error":
                print(f"❌ OpenAI Error: {data}")
                
        except Exception as e:
            print(f"❌ Error handling OpenAI message: {e}")
            
    async def play_audio_response(self, audio_data):
        """Play audio response through Discord"""
        try:
            # Get the bot instance - we'll need to inject this dependency
            bot = self._get_bot_instance()
            if not bot or not bot.voice_clients:
                print("❌ No voice client to play audio")
                return
                
            voice_client = bot.voice_clients[0]
            if not voice_client.is_connected():
                print("❌ Voice client not connected")
                return
                
            # Save AI response audio
            ai_audio_file = self.audio_manager.save_audio_file(audio_data, "ai_response")
            
            # Log the audio pair for conversation tracking
            print(f"💾 Audio pair logged - User & AI audio saved in session: {self.audio_manager.current_session_dir}")
            
            # Convert to audio source for Discord
            # Save as temporary WAV file for Discord compatibility
            import tempfile
            import wave
            
            try:
                # Create temporary WAV file
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                    temp_path = temp_file.name
                    
                # Write audio data as proper WAV file
                with wave.open(temp_path, 'wb') as wav_file:
                    wav_file.setnchannels(1)  # Mono
                    wav_file.setsampwidth(2)  # 16-bit
                    wav_file.setframerate(24000)  # 24kHz
                    wav_file.writeframes(audio_data.tobytes())
                
                print(f"🎵 Created temporary WAV file: {temp_path} ({len(audio_data)/24000:.1f}s)")
                
                # Create audio source from file
                audio_source = discord.PCMVolumeTransformer(
                    discord.FFmpegPCMAudio(temp_path),
                    volume=0.8
                )
                
                # Play audio
                if not voice_client.is_playing():
                    def playback_finished(error):
                        # Clean up temporary file after playback
                        try:
                            import os
                            os.unlink(temp_path)
                            print(f"🗑️ Cleaned up temporary file: {temp_path}")
                        except Exception as cleanup_error:
                            print(f"⚠️ Failed to clean up temp file: {cleanup_error}")
                        
                        if error:
                            print(f"❌ Playback error: {error}")
                        else:
                            print(f"✅ AI voice playback completed successfully ({len(audio_data)/24000:.1f}s)")
                    
                    voice_client.play(audio_source, after=playback_finished)
                    print(f"🔊 Started playing AI response in Discord voice channel ({len(audio_data)/24000:.1f}s)")
                else:
                    print("⚠️ Already playing audio, skipping")
                    # Clean up temp file if we're not using it
                    try:
                        import os
                        os.unlink(temp_path)
                    except:
                        pass
                    
            except Exception as e:
                print(f"❌ Error creating audio source: {e}")
                # Try to clean up temp file on error
                try:
                    import os
                    if 'temp_path' in locals():
                        os.unlink(temp_path)
                except:
                    pass
                
        except Exception as e:
            print(f"❌ Error playing audio response: {e}")
    
    async def stream_audio_chunk(self, audio_chunk):
        """Stream individual audio chunk to Discord as it arrives"""
        try:
            bot = self._get_bot_instance()
            if not bot or not bot.voice_clients:
                return
                
            voice_client = bot.voice_clients[0]
            if not voice_client.is_connected():
                return
            
            # If we're not already streaming, start streaming
            if not self.is_streaming_audio:
                await self.start_audio_stream(voice_client)
            
            # For now, we'll still accumulate and play complete responses
            # True streaming would require a different approach with audio queues
            # This is a placeholder for the streaming logic
            
        except Exception as e:
            print(f"❌ Error streaming audio chunk: {e}")
    
    async def start_audio_stream(self, voice_client):
        """Initialize audio streaming"""
        try:
            self.is_streaming_audio = True
            print("🎵 Started streaming audio response...")
        except Exception as e:
            print(f"❌ Error starting audio stream: {e}")
    
    async def finalize_audio_stream(self):
        """Finalize audio streaming"""
        try:
            if self.is_streaming_audio:
                print("✅ Audio streaming completed")
                self.is_streaming_audio = False
        except Exception as e:
            print(f"❌ Error finalizing audio stream: {e}")
    
    def _get_bot_instance(self):
        """Get bot instance - to be injected via dependency injection"""
        # This will be overridden by dependency injection
        return None
    
    def set_bot_instance(self, bot):
        """Set bot instance for audio playback"""
        self._bot = bot
        
    def _get_bot_instance(self):
        """Get bot instance"""
        return getattr(self, '_bot', None)

    async def disconnect(self):
        """Gracefully close the websocket connection to OpenAI Realtime"""
        try:
            if self.ws and not self.ws.closed:
                await self.ws.close()
                print("🔌 Disconnected from OpenAI Realtime API")
        except Exception as e:
            print(f"❌ Error during OpenAI disconnect: {e}")
        finally:
            self.is_connected = False