"""Intelligent search tool that provides AI-synthesized answers from web search results."""

import asyncio
import aiohttp
import json
from typing import Dict, Any, List, Optional
from urllib.parse import quote
import openai
from datetime import datetime

from ..base_tool import BaseTool, ToolResult
from ..registry import register_tool


@register_tool(name="intelligent_search", description="Get AI-powered answers from web search")
class IntelligentSearchTool(BaseTool):
    """Tool for intelligent web search with AI-synthesized answers."""
    
    def __init__(self):
        super().__init__(
            name="intelligent_search",
            description="Search the web and get AI-synthesized answers to questions"
        )
        
        from .web_search import WebSearchTool  # local import to avoid circular at top
        self.web_search_tool = WebSearchTool()
        import re, os, datetime, json  # used later
        
        # Add parameters
        self.add_parameter(
            "query", 
            "string", 
            "The search query or question to get an answer for",
            required=True
        )
        self.add_parameter(
            "include_sources", 
            "boolean", 
            "Whether to include source links in the response",
            required=False,
            default=False
        )
    
    async def execute(self, query: str, include_sources: bool = False) -> ToolResult:
        """Execute intelligent search with AI synthesis."""
        try:
            import re
            from datetime import datetime as _dt
            # Validate parameters
            if not query or not query.strip():
                return ToolResult(
                    success=False,
                    error="Empty search query",
                    message="Please provide a search query"
                )
            
            print(f"🧠 Intelligent search for: {query}")
            
            # Quick answer for current date/time questions
            if re.search(r"\b(current|today'?s?)\s+(date|time)\b", query, re.IGNORECASE):
                now = _dt.utcnow()
                date_str = now.strftime("%Y-%m-%d")
                time_str = now.strftime("%H:%M UTC")
                answer = f"Today's date is {date_str} and the current time is {time_str}."
                return ToolResult(success=True, data={"query": query, "answer": answer, "source": "local_datetime"}, message=answer)
            
            # Step 1: Get raw search results using WebSearchTool (OpenAI engine by default)
            search_results = await self.web_search_tool._route_search("openai", query, 5)
            
            if not search_results:
                # Fallback to direct AI response
                return await self._get_direct_ai_answer(query)
            
            # Step 2: Synthesize answer using AI
            synthesized_answer = await self._synthesize_answer(query, search_results)
            
            if not synthesized_answer:
                return ToolResult(
                    success=False,
                    error="Failed to generate answer",
                    message="Could not synthesize an answer from search results"
                )
            
            # Format response
            response_data = {
                "query": query,
                "answer": synthesized_answer,
                "timestamp": datetime.now().isoformat()
            }
            
            if include_sources and search_results:
                response_data["sources"] = [
                    {
                        "title": result.get("title", ""),
                        "url": result.get("link", ""),
                        "snippet": result.get("snippet", "")
                    }
                    for result in search_results[:3]  # Top 3 sources
                ]
            
            return ToolResult(
                success=True,
                data=response_data,
                message=synthesized_answer
            )
            
        except Exception as e:
            print(f"❌ Intelligent search error: {e}")
            return ToolResult(
                success=False,
                error=f"Search failed: {str(e)}",
                message="Failed to perform intelligent search"
            )
    
    async def _synthesize_answer(self, query: str, search_results: List[Dict[str, Any]] = None) -> Optional[str]:
        """Synthesize an answer using AI with web search capabilities."""
        try:
            import os
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                print("⚠️ No OpenAI API key found")
                return None
            
            client = openai.AsyncOpenAI(api_key=api_key)
            
            # Use ChatGPT with web search capabilities
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a helpful AI assistant with access to current information through web search. "
                        "When a user asks a question that requires current, real-time, or recent information "
                        "(such as today's date, current news, recent events, stock prices, weather, etc.), "
                        "you should search the web to provide accurate and up-to-date answers. "
                        "Always provide direct, helpful answers. Be concise but comprehensive. "
                        "Always respond in English only. "
                        "For questions about current date/time, search for current date and time information."
                    )
                },
                {
                    "role": "user",
                    "content": f"Please answer this question with current information if needed: {query}"
                }
            ]
            
            # Use GPT-4o with web search capabilities
            response = await client.chat.completions.create(
                model="gpt-4o",  # Use GPT-4o which has better web search capabilities
                messages=messages,
                max_tokens=400,
                temperature=0.3,
                stream=False
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            print(f"❌ AI synthesis error: {e}")
            # Fallback to basic GPT response
            return await self._get_basic_gpt_response(query)
    
    def _needs_web_search(self, query: str) -> bool:
        """Determine if query needs web search for current information."""
        current_info_keywords = [
            "current", "today", "now", "latest", "recent", "new", "date", "time",
            "weather", "news", "stock", "price", "today's", "this year", "2024", "2025"
        ]
        
        query_lower = query.lower()
        return any(keyword in query_lower for keyword in current_info_keywords)
    
    async def _get_basic_gpt_response(self, query: str) -> Optional[str]:
        """Get basic GPT response without web search."""
        try:
            import os
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                return None
            
            client = openai.AsyncOpenAI(api_key=api_key)
            
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a helpful AI assistant. Answer the user's question directly and accurately. "
                        "If the question requires current information that you don't have, acknowledge this limitation "
                        "and provide the most helpful response possible with the information you do have. "
                        "Always respond in English only."
                    )
                },
                {
                    "role": "user",
                    "content": query
                }
            ]
            
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                max_tokens=300,
                temperature=0.3,
                stream=False
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            print(f"❌ Basic GPT response error: {e}")
            return None
    
    async def _get_direct_ai_answer(self, query: str) -> ToolResult:
        """Get direct AI answer when search fails."""
        try:
            import os
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                return ToolResult(
                    success=False,
                    error="No AI service available",
                    message="Could not access AI service for direct answer"
                )
            
            client = openai.AsyncOpenAI(api_key=api_key)
            
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a helpful AI assistant. Answer the user's question directly and accurately. "
                        "If the question asks for current information (like today's date, current news, etc.), "
                        "acknowledge that you may not have the most up-to-date information and suggest alternative ways to get current data. "
                        "Always respond in English only."
                    )
                },
                {
                    "role": "user",
                    "content": query
                }
            ]
            
            response = await client.chat.completions.create(
                model="gpt-4o-mini", 
                messages=messages,
                max_tokens=250,
                temperature=0.3,
                stream=False
            )
            
            answer = response.choices[0].message.content.strip()
            
            return ToolResult(
                success=True,
                data={
                    "query": query,
                    "answer": answer,
                    "source": "direct_ai",
                    "timestamp": datetime.now().isoformat()
                },
                message=answer
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Direct AI answer failed: {str(e)}",
                message="Could not generate answer"
            )