# Eararchy: Voice-Driven Generic AI Agent

**Eararchy** is a prototype AI voice agent developed for Discord, built using `discord.py`, OpenAI Realtime API, and a custom multi-choice web-search MCP server. It enables seamless speech-to-speech AI conversations with real-time audio processing, continuous AI response streaming, and advanced knowledge retrieval.

## Demo

Watch the demo of Eararchy in action:  
[demo.mp4](./demo.mp4)

---

## Features

- **Realtime Voice Interaction:** Converse naturally with the AI through Discord voice channels.
- **Low-Latency Audio Pipeline:** Clean voice input is processed in real time, allowing smooth, natural AI engagement.
- **Continuous AI Response Streaming:** The agent delivers uninterrupted, natural conversational feedback, streaming responses directly into the voice channel.
- **Custom Multi-Choice Web Search:** Integrates with a [custom web-search MCP server](https://github.com/eararchy/custom_web_search), enabling flexible access to a variety of search engines and live web knowledge.

---

## Architecture Overview

1. **Audio Input:** User speech in Discord channels is captured and processed for clarity and speed.
2. **Real-Time AI Processing:** OpenAI’s API streams text and speech responses with minimal delay.
3. **Web Search Integration:** The agent dynamically sources information using the custom MCP web search server.
4. **Conversational Output:** AI responses are streamed back as voice, creating a seamless, voice-driven user experience.

---

## Related Projects

- [Custom Web-Search MCP Server](https://github.com/eararchy/custom_web_search): Modular search server powering Eararchy’s knowledge queries.

---

## About

This project demonstrates advanced real-time AI voice technology, integrating speech recognition, streaming dialogue, and live web knowledge into a unified Discord agent experience.

---

© 2025 Eararchy
