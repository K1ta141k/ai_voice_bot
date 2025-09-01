"""Base tool interface for the voice bot tool system."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class ToolParameter(BaseModel):
    """Tool parameter definition."""
    name: str = Field(..., description="Parameter name")
    type: str = Field(..., description="Parameter type (string, number, boolean, array, object)")
    description: str = Field(..., description="Parameter description")
    required: bool = Field(default=True, description="Whether parameter is required")
    default: Optional[Any] = Field(default=None, description="Default value if parameter is optional")
    enum: Optional[List[str]] = Field(default=None, description="Allowed values for enum parameters")


class ToolSchema(BaseModel):
    """Tool schema for OpenAI function calling."""
    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Tool description")
    parameters: List[ToolParameter] = Field(default_factory=list, description="Tool parameters")


@dataclass
class ToolResult:
    """Result from tool execution."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    message: Optional[str] = None


class BaseTool(ABC):
    """Abstract base class for all tools."""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self._parameters: List[ToolParameter] = []
    
    @property
    def schema(self) -> ToolSchema:
        """Get tool schema for OpenAI function calling."""
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=self._parameters
        )
    
    def add_parameter(self, 
                     name: str, 
                     param_type: str, 
                     description: str,
                     required: bool = True,
                     default: Optional[Any] = None,
                     enum: Optional[List[str]] = None) -> None:
        """Add a parameter to the tool."""
        param = ToolParameter(
            name=name,
            type=param_type,
            description=description,
            required=required,
            default=default,
            enum=enum
        )
        self._parameters.append(param)
    
    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """Execute the tool with given parameters."""
        pass
    
    def validate_parameters(self, params: Dict[str, Any]) -> ToolResult:
        """Validate parameters against tool schema."""
        errors = []
        
        # Check required parameters
        for param in self._parameters:
            if param.required and param.name not in params:
                errors.append(f"Missing required parameter: {param.name}")
        
        # Check enum values
        for param in self._parameters:
            if param.enum and param.name in params:
                if params[param.name] not in param.enum:
                    errors.append(f"Invalid value for {param.name}. Must be one of: {param.enum}")
        
        if errors:
            return ToolResult(
                success=False,
                error="Parameter validation failed",
                message="; ".join(errors)
            )
        
        return ToolResult(success=True)
    
    def to_openai_function(self) -> Dict[str, Any]:
        """Convert tool to OpenAI function calling format."""
        properties = {}
        required = []
        
        for param in self._parameters:
            prop_def = {
                "type": param.type,
                "description": param.description
            }
            
            if param.enum:
                prop_def["enum"] = param.enum
            
            properties[param.name] = prop_def
            
            if param.required:
                required.append(param.name)
        
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            }
        }