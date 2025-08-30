"""Discord voice sink for receiving audio data from voice channels."""

import discord.ext.voice_recv as voice_recv
import numpy as np


class DiscordAudioSink(voice_recv.AudioSink):
    """Custom audio sink to process Discord voice data"""
    
    def __init__(self, receiver):
        super().__init__()
        self.receiver = receiver
        print("🎯 DiscordAudioSink initialized")
        
    def wants_opus(self) -> bool:
        return False  # We want PCM data
        
    def write(self, user, data):
        """Called when audio data is received from Discord"""
        # Handle case where user might be None
        if user is None:
            print(f"🔍 SINK WRITE CALLED: user=None, data_type={type(data)}", flush=True)
            return  # Skip processing if user is None
            
        # Log ANY voice data received (including bots for debugging)
        print(f"🔍 SINK WRITE CALLED: user={user.display_name} (ID: {user.id}, bot: {user.bot}), data_type={type(data)}", flush=True)
        
        if user.bot:
            print(f"🤖 Ignoring bot audio from {user.display_name}", flush=True)
            return  # Ignore bot audio
        
        # Log first voice chunk from this user
        if not hasattr(self, f'_first_chunk_logged_{user.id}'):
            print(f"🎵 First voice chunk received from {user.display_name} (ID: {user.id})")
            setattr(self, f'_first_chunk_logged_{user.id}', True)
            
        # Convert Discord audio to our format (48kHz stereo -> 24kHz mono)
        try:
            # discord-ext-voice-recv provides decoded PCM data as bytes
            if hasattr(data, 'pcm') and data.pcm:
                # Convert bytes to int16 array
                audio_array = np.frombuffer(data.pcm, dtype=np.int16)
            else:
                # Skip if no audio data
                return
            
            # Discord audio is 48kHz stereo (2 channels)
            # Convert stereo to mono by taking left channel
            if len(audio_array) % 2 == 0:
                mono_audio = audio_array[::2]  # Take every other sample (left channel)
            else:
                mono_audio = audio_array
                
            # Downsample from 48kHz to 24kHz
            downsampled = mono_audio[::2]  # Simple downsampling
            
            # Only process if we have meaningful audio data
            if len(downsampled) > 0:
                self.receiver.add_audio_chunk(downsampled)
            
        except Exception as e:
            print(f"Audio sink error: {e}")
            # Debug info on first error
            if not hasattr(self, '_debug_printed'):
                print(f"VoiceData type: {type(data)}")
                print(f"VoiceData has pcm: {hasattr(data, 'pcm')}")
                if hasattr(data, 'pcm'):
                    print(f"PCM type: {type(data.pcm)}, length: {len(data.pcm) if data.pcm else 'None'}")
                self._debug_printed = True
            
    def cleanup(self):
        """Required abstract method - cleanup when sink is destroyed"""
        print("🧹 Audio sink cleanup")