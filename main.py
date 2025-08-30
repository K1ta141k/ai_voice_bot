"""Main entry point for the Discord Voice Bot."""

from src.bot import VoiceBot


def main():
    """Initialize and run the voice bot"""
    try:
        bot = VoiceBot()
        bot.run()
    except KeyboardInterrupt:
        print("\n👋 Bot shutting down...")
    except Exception as e:
        print(f"❌ Fatal error: {e}")


if __name__ == "__main__":
    main()
