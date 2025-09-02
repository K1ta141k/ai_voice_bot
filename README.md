# Discord Voice AI Bot

A Discord bot that enables voice conversations with AI using OpenAI's Realtime API. The bot joins voice channels, listens for user speech, and responds with AI-generated voice.

## Features

- **Voice Recognition**: Automatically detects when users start and stop speaking
- **AI Voice Response**: Uses OpenAI Realtime API for natural voice conversations
- **Conversation Logging**: Saves all voice exchanges with timestamped sessions
- **Push-to-Talk Mode**: Optional manual recording control
- **Configurable Timeouts**: Adjustable silence detection thresholds
- **Audio Filtering**: Filters out short/noise recordings to prevent unnecessary API calls

## Setup

### Prerequisites

- Python 3.8+
- Discord Bot Token
- OpenAI API Key with Realtime API access
- FFmpeg (for audio processing)

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd ai_voice_bot
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
Create a `.env` file with:
```
DISCORD_BOT_TOKEN=your_discord_bot_token
OPENAI_API_KEY=your_openai_api_key
ALLOWED_USER_ID=your_discord_user_id  # Optional: restrict to specific user
```

### Discord Bot Setup

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application and bot
3. Enable the following bot permissions:
   - Connect to Voice Channels
   - Speak in Voice Channels
   - Send Messages
   - Use Slash Commands
4. Add bot to your server with these permissions

## Usage

### Running the Bot

```bash
source venv/bin/activate
python main.py
```

### Discord Commands

- `!join` - Bot joins your current voice channel and starts listening
- `!leave` - Bot leaves the voice channel and stops listening
- `!timeout [seconds]` - Set voice silence timeout (default: 0.5s)
- `!talk start` - Start push-to-talk recording
- `!talk stop` - Stop push-to-talk and send to AI
- `!talk auto` - Return to automatic voice detection
- `!ping` - Test bot responsiveness

### Voice Interaction

1. Use `!join` to have the bot join your voice channel
2. Simply speak naturally - the bot will automatically detect when you start and stop
3. The bot responds with AI-generated voice after a brief silence
4. All conversations are saved in timestamped folders under `audio_logs/`

## Architecture

The bot uses a modular architecture:

- `src/bot.py` - Main bot class with Discord integration
- `src/discord/` - Discord-specific components (commands, voice handling)
- `src/openai/` - OpenAI Realtime API client
- `src/audio/` - Audio file management and logging
- `src/utils/` - Configuration and utility functions

## Audio Processing

- **Input**: Discord voice (48kHz stereo) → converted to 24kHz mono
- **Detection**: Configurable silence timeout for automatic recording
- **Filtering**: Recordings shorter than 0.5s are saved but not sent to API
- **Output**: AI voice responses are played back through Discord

## Logging

All voice interactions are saved in `audio_logs/` with:
- Timestamped session folders (one per `!join`)
- Numbered audio files (`001_user_input.wav`, `001_ai_response.wav`)
- Text transcriptions when available

## Configuration

Key settings can be adjusted in `src/utils/config.py`:
- Voice timeout thresholds
- Audio quality settings
- Logging preferences
- API endpoints

## Troubleshooting

### Common Issues

1. **Bot not responding to voice**: 
   - Check Discord permissions
   - Verify voice channel connection
   - Check console logs for errors

2. **API errors**:
   - Verify OpenAI API key and credits
   - Check internet connection
   - Monitor rate limits

3. **Audio playback issues**:
   - Ensure FFmpeg is installed
   - Check Discord voice permissions
   - Verify audio codec support

### Debug Mode

Enable detailed logging by checking console output. The bot logs:
- Voice data reception
- Recording sessions
- API interactions
- Audio playback status

## Development

### Adding Features

The modular architecture makes it easy to extend:
- Add new commands in `src/discord/bot_commands.py`
- Modify voice processing in `src/discord/voice_receiver.py`
- Extend audio management in `src/audio/manager.py`

### Testing

Use push-to-talk mode (`!talk start/stop`) for reliable testing without automatic detection.

