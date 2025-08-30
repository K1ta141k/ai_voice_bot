"""Audio file management for saving and organizing voice recordings."""

import wave
import numpy as np
from pathlib import Path
from datetime import datetime


class AudioManager:
    """Manage audio file operations"""
    
    def __init__(self):
        self.base_audio_dir = Path("audio_logs")
        self.base_audio_dir.mkdir(exist_ok=True)
        self.current_session_dir = None
        self.exchange_counter = 0  # Counter for voice exchanges in current session
        
    def get_or_create_session_dir(self):
        """Get or create timestamp-based session directory"""
        if self.current_session_dir is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.current_session_dir = self.base_audio_dir / timestamp
            self.current_session_dir.mkdir(exist_ok=True)
            print(f"📁 Created session directory: {self.current_session_dir}")
        return self.current_session_dir
        
    def save_audio_file(self, audio_data, filename_prefix, sample_rate=24000):
        """Save audio data to WAV file in timestamp folder"""
        session_dir = self.get_or_create_session_dir()
        
        # If this is the start of a new exchange, increment counter
        if filename_prefix == "user_input":
            self.exchange_counter += 1
        
        # Create numbered filename
        filename = f"{self.exchange_counter:03d}_{filename_prefix}.wav"
        filepath = session_dir / filename
        
        try:
            with wave.open(str(filepath), 'wb') as wav_file:
                wav_file.setnchannels(1)  # Mono
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(audio_data.tobytes())
            
            print(f"💾 Audio saved: {filepath}")
            return filepath
        except Exception as e:
            print(f"❌ Error saving audio: {e}")
            return None
            
    def save_text_response(self, text_content):
        """Save text response to session folder"""
        session_dir = self.get_or_create_session_dir()
        filename = f"{self.exchange_counter:03d}_ai_response.txt"
        filepath = session_dir / filename
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(text_content)
            print(f"📝 Text response saved: {filepath}")
            return filepath
        except Exception as e:
            print(f"❌ Error saving text response: {e}")
            return None
            
    def new_session(self):
        """Start a new session (create new timestamp folder)"""
        self.current_session_dir = None
        self.exchange_counter = 0
        print("🆕 Starting new audio session")