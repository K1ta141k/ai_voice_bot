"""Configuration management for the voice bot."""

import os
from dotenv import load_dotenv


class Config:
    """Configuration settings for the voice bot"""
    
    def __init__(self):
        load_dotenv()
        self.discord_token = os.getenv("DISCORD_TOKEN")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.allowed_user_id = int(os.getenv("ALLOWED_USER_ID", "0"))
        
        # Validate required settings
        if not self.discord_token:
            raise RuntimeError("DISCORD_TOKEN environment variable not set")
        if not self.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY environment variable not set")
            
    def is_user_allowed(self, user_id):
        """Check if a user is allowed to use the bot"""
        if self.allowed_user_id == 0:
            return True  # Everyone allowed
        return user_id == self.allowed_user_id
        
    def print_status(self):
        """Print configuration status"""
        if self.allowed_user_id == 0:
            print("No allowed user ID set, everyone is allowed to use the bot")
        else:
            print(f"Only user ID {self.allowed_user_id} is allowed to use the bot")