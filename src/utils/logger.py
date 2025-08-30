"""Conversation logging utilities."""

import json
from pathlib import Path
from datetime import datetime


class ConversationLogger:
    """Log conversations with timestamps"""
    
    def __init__(self):
        self.log_dir = Path("conversation_logs")
        self.log_dir.mkdir(exist_ok=True)
        self.log_file = self.log_dir / f"conversation_{datetime.now().strftime('%Y%m%d')}.jsonl"
        
    def log_interaction(self, user_audio_file, ai_audio_file, user_transcript="", ai_transcript=""):
        """Log a complete interaction"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "user_audio": str(user_audio_file) if user_audio_file else None,
            "ai_audio": str(ai_audio_file) if ai_audio_file else None,
            "user_transcript": user_transcript,
            "ai_transcript": ai_transcript
        }
        
        try:
            with open(self.log_file, 'a') as f:
                json.dump(entry, f, ensure_ascii=False)
                f.write('\n')
        except Exception as e:
            print(f"❌ Error logging interaction: {e}")