# Discord Bot (Python)

## Requirements
- Python 3.11+
- `discord.py` 2.x
- `python-dotenv`

## Setup
1. Create a `.env` file based on `.env.example` and put your `DISCORD_TOKEN` inside.

```bash
cp .env.example .env
# edit .env and add your token
```
2. Install dependencies:
```bash
pip install -r requirements.txt
```
3. Run the bot:
```bash
python main.py
```

## Docker
Build and run:
```bash
docker build -t discord-bot .
docker run --rm --env-file .env discord-bot
```

---
Feel free to add new commands in `main.py`.
