import os
from dotenv import load_dotenv
import discord
from discord.ext import commands
import json
from datetime import datetime
from pathlib import Path

# LangGraph / LangChain imports
try:
    from langchain.chat_models import ChatOpenAI  # langchain >=0.1.8 w/ deferred imports
except ModuleNotFoundError:
    # For newer langchain versions that move providers to langchain_community
    from langchain_community.chat_models import ChatOpenAI
from langgraph.graph import StateGraph

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID", "0"))

if ALLOWED_USER_ID == 0:
    print("No allowed user ID set, everyone is allowed to use the bot")
else:
    print(f"Only user ID {ALLOWED_USER_ID} is allowed to use the bot")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents, description="Example Discord Bot")

# --- Simple JSONL logging ---

LOG_PATH = Path("messages_log.jsonl")

# --- Build LangGraph pipeline once at startup ---

llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0.3)


def _build_graph():
    graph = StateGraph()

    @graph.node
    def generate(state):
        prompt = state["prompt"]
        result = llm.invoke(prompt)
        state["response"] = result.content  # ChatMessage -> str
        return state

    graph.set_entry_point(generate)
    return graph.compile()


_langgraph_pipeline = _build_graph()


def process_prompt_langgraph(prompt: str) -> str:
    """Run prompt through LangGraph pipeline and return the response string."""
    output_state = _langgraph_pipeline({"prompt": prompt})
    return output_state["response"]


def log_interaction(author_id: int, prompt: str, response: str) -> None:
    """Append a log entry as JSON to LOG_PATH (one line per record)."""
    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "author_id": author_id,
        "prompt": prompt,
        "response": response,
    }
    with LOG_PATH.open("a", encoding="utf-8") as f:
        json.dump(entry, f, ensure_ascii=False)
        f.write("\n")


# Global check to allow commands only from ALLOWED_USER_ID (if configured)


@bot.check
async def globally_allow_only_author(ctx: commands.Context) -> bool:
    """Return True only if invoker matches ALLOWED_USER_ID.

    If ALLOWED_USER_ID is 0, allow everyone.
    """
    if ALLOWED_USER_ID == 0:
        return True
    return ctx.author.id == ALLOWED_USER_ID

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("------")

@bot.command(name="ping", help="Responds with Pong!")
async def ping(ctx: commands.Context):
    await ctx.send("Pong!")


# Mention-based AI conversation handler


@bot.event
async def on_message(message: discord.Message):
    """Listen for messages that mention the bot and reply.

    Any message that starts with a mention of the bot will be treated as a prompt.
    The bot will reply with a placeholder AI response (echo) but you can integrate
    an LLM call here (e.g., OpenAI) later.
    """
    # Ignore own messages or other bots
    if message.author.bot:
        return

    # Respect allowed user restriction
    if ALLOWED_USER_ID != 0 and message.author.id != ALLOWED_USER_ID:
        return

    if message.content.startswith(bot.user.mention):
        prompt = message.content.replace(bot.user.mention, "", 1).strip()

        if not prompt:
            return  # nothing to answer

        # Process the prompt through LangGraph pipeline
        response_text = process_prompt_langgraph(prompt)

        # Log the interaction locally
        log_interaction(message.author.id, prompt, response_text)

    # Ensure commands still work
    await bot.process_commands(message)

if __name__ == "__main__":
    if TOKEN is None:
        raise RuntimeError("DISCORD_TOKEN environment variable not set")
    bot.run(TOKEN)
