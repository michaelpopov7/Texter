"""
LangChain Tools for SMS AI Agent

This module provides various tools that the AI agent can use to enhance
its responses, including web search, weather information, and utilities.
"""

import json
import time
from typing import Any, Dict, List, Optional, Type
from datetime import datetime
import requests

import structlog
from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from .exceptions import ExternalAPIError
from .config import Config


logger = structlog.get_logger(__name__)


class WebSearchInput(BaseModel):
    """Input schema for web search tool."""
    query: str = Field(description="Search query to look up current information")
    max_results: int = Field(default=3, description="Maximum number of search results")


class WebSearchTool(BaseTool):
    """Tool for searching the web for current information."""
    
    name = "web_search"
    description = (
        "Search the web for current information, news, facts, or recent events. "
        "Use this when the user asks about current events, latest news, or "
        "information that might have changed recently."
    )
    args_schema: Type[BaseModel] = WebSearchInput
    
    def __init__(self, config: Config):
        super().__init__()
        self.config = config
    
    def _run(self, query: str, max_results: int = 3) -> str:
        """Execute web search."""
        try:
            # Simple web search using requests (would use proper search API in production)
            logger.info("Executing web search", query=query, max_results=max_results)
            
            # For demo purposes, return a placeholder response
            # In production, integrate with Google Search API, SerpAPI, etc.
            return (
                f"I searched for '{query}' but my web search capability is "
                "currently limited. For the most current information, "
                "I recommend checking recent news sources or official websites."
            )
            
        except Exception as e:
            logger.error("Web search failed", query=query, error=str(e))
            raise ExternalAPIError(f"Web search failed: {e}")
    
    async def _arun(self, query: str, max_results: int = 3) -> str:
        """Async version of web search."""
        return self._run(query, max_results)


class WeatherInput(BaseModel):
    """Input schema for weather tool."""
    location: str = Field(description="City, state/country for weather information")


class WeatherTool(BaseTool):
    """Tool for getting weather information."""
    
    name = "get_weather"
    description = (
        "Get current weather information for a specific location. "
        "Provide city name and optionally state/country for accurate results."
    )
    args_schema: Type[BaseModel] = WeatherInput
    
    def __init__(self, config: Config):
        super().__init__()
        self.config = config
        self.api_key = config.openweather_api_key
    
    def _run(self, location: str) -> str:
        """Get weather information for location."""
        if not self.api_key:
            return (
                "Weather information is not available right now. "
                "Please check a weather app or website for current conditions."
            )
        
        try:
            logger.info("Getting weather information", location=location)
            
            # OpenWeatherMap API call
            base_url = "http://api.openweathermap.org/data/2.5/weather"
            params = {
                'q': location,
                'appid': self.api_key,
                'units': 'imperial'  # Fahrenheit
            }
            
            response = requests.get(base_url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # Extract weather information
            temp = data['main']['temp']
            feels_like = data['main']['feels_like']
            humidity = data['main']['humidity']
            description = data['weather'][0]['description']
            city = data['name']
            
            weather_info = (
                f"Weather in {city}: {description.title()}\n"
                f"Temperature: {temp:.0f}°F (feels like {feels_like:.0f}°F)\n"
                f"Humidity: {humidity}%"
            )
            
            logger.info("Weather information retrieved", location=location)
            return weather_info
            
        except requests.exceptions.RequestException as e:
            logger.error("Weather API request failed", location=location, error=str(e))
            return f"Sorry, I couldn't get weather information for {location}. Please try again later."
        
        except Exception as e:
            logger.error("Weather tool error", location=location, error=str(e))
            raise ExternalAPIError(f"Weather lookup failed: {e}")
    
    async def _arun(self, location: str) -> str:
        """Async version of weather lookup."""
        return self._run(location)


class TimeInput(BaseModel):
    """Input schema for time tool."""
    timezone: Optional[str] = Field(default=None, description="Timezone (optional)")


class TimeTool(BaseTool):
    """Tool for getting current time and date."""
    
    name = "get_current_time"
    description = (
        "Get the current date and time. Useful when users ask about "
        "the current time, date, day of the week, etc."
    )
    args_schema: Type[BaseModel] = TimeInput
    
    def _run(self, timezone: Optional[str] = None) -> str:
        """Get current time and date."""
        try:
            logger.info("Getting current time", timezone=timezone)
            
            now = datetime.now()
            
            # Format the time nicely
            formatted_time = now.strftime("%A, %B %d, %Y at %I:%M %p")
            
            return f"Current time: {formatted_time}"
            
        except Exception as e:
            logger.error("Time tool error", error=str(e))
            return "Sorry, I couldn't get the current time right now."
    
    async def _arun(self, timezone: Optional[str] = None) -> str:
        """Async version of time lookup."""
        return self._run(timezone)


class CalculatorInput(BaseModel):
    """Input schema for calculator tool."""
    expression: str = Field(description="Mathematical expression to calculate")


class CalculatorTool(BaseTool):
    """Tool for basic mathematical calculations."""
    
    name = "calculator"
    description = (
        "Perform basic mathematical calculations. Use this for arithmetic "
        "operations like addition, subtraction, multiplication, division, "
        "percentages, etc. Provide the mathematical expression."
    )
    args_schema: Type[BaseModel] = CalculatorInput
    
    def _run(self, expression: str) -> str:
        """Perform calculation."""
        try:
            logger.info("Performing calculation", expression=expression)
            
            # Basic safety checks
            if any(word in expression.lower() for word in ['import', 'exec', 'eval', '__']):
                return "Sorry, I can only perform basic mathematical calculations."
            
            # Only allow safe mathematical operations
            allowed_chars = set('0123456789+-*/().,% ')
            if not all(c in allowed_chars for c in expression):
                return "Please use only numbers and basic mathematical operators (+, -, *, /, %, parentheses)."
            
            # Replace % with /100 for percentage calculations
            expression = expression.replace('%', '/100')
            
            # Evaluate the expression safely
            result = eval(expression, {"__builtins__": {}}, {})
            
            return f"{expression.replace('/100', '%')} = {result}"
            
        except ZeroDivisionError:
            return "Error: Division by zero is not allowed."
        except SyntaxError:
            return "Error: Invalid mathematical expression."
        except Exception as e:
            logger.error("Calculator error", expression=expression, error=str(e))
            return "Sorry, I couldn't calculate that. Please check your expression."
    
    async def _arun(self, expression: str) -> str:
        """Async version of calculator."""
        return self._run(expression)


class HelpTool(BaseTool):
    """Tool for providing help and information about the agent's capabilities."""
    
    name = "help"
    description = (
        "Provide help information about what the AI assistant can do. "
        "Use this when users ask about capabilities, features, or need help."
    )
    
    def _run(self, query: str = "") -> str:
        """Provide help information."""
        help_text = """
I'm an AI assistant that can help you with:

🔍 Web Search - Ask me about current events or recent information
🌤️ Weather - Get weather information for any city
🧮 Math - Perform calculations and solve math problems
⏰ Time - Get current date and time
💬 Conversation - Have natural conversations and get assistance

Just text me naturally! For example:
- "What's the weather in New York?"
- "Calculate 15% of 250"
- "What time is it?"
- "Tell me about recent news"

I remember our conversation, so you can refer to previous messages.
"""
        return help_text.strip()
    
    async def _arun(self, query: str = "") -> str:
        """Async version of help."""
        return self._run(query)


class ToolManager:
    """Manages all available tools for the agent."""
    
    def __init__(self, config: Config):
        """Initialize tool manager with configuration."""
        self.config = config
        self.tools = self._initialize_tools()
    
    def _initialize_tools(self) -> List[BaseTool]:
        """Initialize all available tools."""
        tools = []
        
        # Always available tools
        tools.extend([
            TimeTool(),
            CalculatorTool(),
            HelpTool()
        ])
        
        # Weather tool (if API key available)
        if self.config.openweather_api_key:
            tools.append(WeatherTool(self.config))
            logger.info("Weather tool enabled")
        else:
            logger.info("Weather tool disabled (no API key)")
        
        # Web search tool (if configured)
        tools.append(WebSearchTool(self.config))
        logger.info("Web search tool enabled")
        
        logger.info(f"Initialized {len(tools)} tools", tool_names=[t.name for t in tools])
        return tools
    
    def get_tools(self) -> List[BaseTool]:
        """Get list of all available tools."""
        return self.tools
    
    def get_tool_descriptions(self) -> str:
        """Get formatted descriptions of all available tools."""
        descriptions = []
        for tool in self.tools:
            descriptions.append(f"- {tool.name}: {tool.description}")
        
        return "\n".join(descriptions)
    
    def get_tool_by_name(self, name: str) -> Optional[BaseTool]:
        """Get a specific tool by name."""
        for tool in self.tools:
            if tool.name == name:
                return tool
        return None 