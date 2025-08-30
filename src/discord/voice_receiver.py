"""Discord voice receiver for handling voice activity detection and recording."""

import time
import asyncio
import numpy as np
from .voice_sink import DiscordAudioSink


class DiscordVoiceReceiver:
    """Receives audio directly from Discord voice channel using discord-ext-voice-recv"""
    
    def __init__(self):
        self.is_listening = False
        self.voice_timeout = 0.5
        # Push-to-talk state
        self.ptt_active = False  # True while user has pressed "talk"
        self.auto_mode = True    # If False, only record during push-to-talk
        self.openai_client = None
        self.recorder = None
        self.voice_client = None
        self.current_recording = []
        self.recording_start_time = None
        self.last_activity_time = None
        self.sink = None
        self.timeout_task = None  # Background task for monitoring timeout
        
    def set_timeout(self, timeout):
        """Set the silence timeout in seconds"""
        self.voice_timeout = max(0.5, min(10.0, timeout))
        print(f"🔧 Voice timeout set to {self.voice_timeout} seconds")
        
    async def start_listening(self, openai_client, recorder, voice_client):
        """Start listening for Discord voice activity"""
        self.openai_client = openai_client
        self.recorder = recorder
        self.voice_client = voice_client
        self.is_listening = True
        # Default to automatic mode; commands can switch to PTT only
        
        print(f"🎤 **Discord voice receiving started!**")
        print(f"💡 Speak in Discord voice channel - bot will auto-detect when you stop speaking!")
        
        # Create custom sink to process incoming Discord audio
        self.sink = DiscordAudioSink(self)
        
        # Start receiving voice from Discord
        self.voice_client.listen(self.sink)
        
        # Start the timeout monitoring task
        self._start_timeout_monitor()

        # Some versions of discord-ext-voice-recv require an explicit enable call
        if hasattr(self.voice_client, "enable_receiving"):
            try:
                await self.voice_client.enable_receiving()
                print("✅ Voice receiving explicitly enabled")
            except Exception as e:
                print(f"⚠️ Failed to enable voice receiving: {e}")
        else:
            print("ℹ️ Voice client doesn't have enable_receiving method")

        # Check what methods the voice client has
        print(f"🔧 Voice client methods: {[m for m in dir(self.voice_client) if not m.startswith('_')]}")
        print("🎧 Voice client listening started with custom sink")
        
    def add_audio_chunk(self, audio_data):
        """Add audio chunk from Discord voice channel"""
        try:
            # Skip processing if we are in PTT-only mode but not currently active
            if not self.auto_mode and not self.ptt_active:
                return

            current_time = time.time()

            # If this is the first chunk of a new recording, mark the start
            if not self.recording_start_time:
                self.recording_start_time = current_time
                self.current_recording = []
                print("🔴 Starting new voice recording session")

            # Always append incoming chunk (Discord already filters silence/comfort noise)
            self.current_recording.append(audio_data)
            self.last_activity_time = current_time
            
            # The timeout check is now handled by the background monitor task

        except Exception as e:
            print(f"Audio chunk processing error: {e}")

    # ---------------- Push-to-talk helpers ----------------

    def start_push_to_talk(self):
        """Enable push-to-talk recording (called by command)."""
        self.auto_mode = False
        self.ptt_active = True
        # Reset any previous buffers
        self.current_recording = []
        self.recording_start_time = None
        self.last_activity_time = None

    def stop_push_to_talk(self):
        """Manually stop push-to-talk and process recording immediately."""
        self.ptt_active = False
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self.process_recording())
            else:
                print("⚠️ Cannot process recording - event loop not running")
        except RuntimeError:
            print("⚠️ Cannot process recording - no event loop available")
            
    async def process_recording(self):
        """Process and send the completed recording"""
        if not self.current_recording:
            return
            
        try:
            # Combine all chunks
            combined_audio = np.concatenate(self.current_recording)
            duration = len(combined_audio) / 24000
            
            # Set minimum audio length threshold (e.g., 0.5 seconds)
            min_duration_threshold = 0.5
            
            if duration < min_duration_threshold:
                print(f"🔇 Recording too short ({duration:.1f}s < {min_duration_threshold}s), skipping OpenAI but saving as no_response")
                # Save the short audio but don't send to OpenAI
                if self.openai_client and self.openai_client.audio_manager:
                    self.openai_client.audio_manager.save_audio_file(combined_audio, "user_input_no_response")
            else:
                print(f"⏹️ Recording complete: {duration:.1f}s, sending to OpenAI...")
                # Send to OpenAI
                await self.openai_client.send_voice_message(combined_audio, duration)
            
        except Exception as e:
            print(f"❌ Error processing recording: {e}")
        finally:
            # Reset recording state
            self.current_recording = []
            self.recording_start_time = None
            self.last_activity_time = None
            
    def _start_timeout_monitor(self):
        """Start the background timeout monitoring task"""
        async def timeout_monitor():
            while self.is_listening:
                await asyncio.sleep(0.1)  # Check every 100ms
                
                if (self.auto_mode and self.last_activity_time and 
                    self.recording_start_time and self.current_recording):
                    
                    silence_duration = time.time() - self.last_activity_time
                    if silence_duration >= self.voice_timeout:
                        total_recording_time = time.time() - self.recording_start_time
                        print(f"⏰ Silence timeout ({self.voice_timeout}s) reached after {total_recording_time:.1f}s total recording")
                        await self.process_recording()
        
        # Start the background task
        try:
            loop = asyncio.get_event_loop()
            self.timeout_task = loop.create_task(timeout_monitor())
            print("✅ Background timeout monitor started")
        except Exception as e:
            print(f"⚠️ Could not start timeout monitor: {e}")
            
    def stop_listening(self):
        """Stop voice listening"""
        self.is_listening = False
        
        # Cancel the timeout monitoring task
        if self.timeout_task:
            self.timeout_task.cancel()
            self.timeout_task = None
            
        if self.sink and self.voice_client:
            try:
                self.voice_client.stop_listening()
            except:
                pass
        print("🔇 Discord voice receiving stopped")