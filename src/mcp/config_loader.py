"""MCP server configuration loading and validation."""

import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
import logging


class MCPConfigLoader:
    """Loads and validates MCP server configurations."""
    
    def __init__(self, config_path: str = None):
        self.logger = logging.getLogger(__name__)
        self.config_path = Path(config_path or "config/mcp_servers.json")
        self._config = None
        self._servers = {}
    
    def load_config(self) -> Dict[str, Any]:
        """Load MCP server configuration from file."""
        try:
            if not self.config_path.exists():
                self.logger.warning(f"MCP config file not found: {self.config_path}")
                return self._get_default_config()
            
            with open(self.config_path, 'r') as f:
                self._config = json.load(f)
            
            self._validate_config()
            self.logger.info(f"Loaded MCP configuration from {self.config_path}")
            return self._config
            
        except Exception as e:
            self.logger.error(f"Failed to load MCP config: {e}")
            return self._get_default_config()
    
    def _validate_config(self):
        """Validate the loaded configuration."""
        if not isinstance(self._config, dict):
            raise ValueError("Configuration must be a dictionary")
        
        if "servers" not in self._config:
            raise ValueError("Configuration must contain 'servers' section")
        
        if "global_settings" not in self._config:
            self._config["global_settings"] = self._get_default_global_settings()
        
        if "permissions" not in self._config:
            self._config["permissions"] = self._get_default_permissions()
        
        # Validate each server config
        for server_name, server_config in self._config["servers"].items():
            self._validate_server_config(server_name, server_config)
    
    def _validate_server_config(self, name: str, config: Dict[str, Any]):
        """Validate individual server configuration."""
        required_fields = ["name", "description", "enabled", "connection", "capabilities"]
        
        for field in required_fields:
            if field not in config:
                raise ValueError(f"Server '{name}' missing required field: {field}")
        
        # Validate connection config
        connection = config["connection"]
        if connection["type"] not in ["stdio", "http", "websocket"]:
            raise ValueError(f"Invalid connection type for server '{name}': {connection['type']}")
        
        if connection["type"] == "stdio":
            if "command" not in connection:
                raise ValueError(f"STDIO server '{name}' missing 'command' field")
        
        elif connection["type"] == "http":
            required_http = ["host", "port", "protocol"]
            for field in required_http:
                if field not in connection:
                    raise ValueError(f"HTTP server '{name}' missing field: {field}")
    
    def get_enabled_servers(self) -> Dict[str, Dict[str, Any]]:
        """Get all enabled server configurations."""
        if not self._config:
            self.load_config()
        
        enabled_servers = {}
        for name, config in self._config["servers"].items():
            if config.get("enabled", False):
                enabled_servers[name] = config
        
        return enabled_servers
    
    def get_server_config(self, server_name: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific server."""
        if not self._config:
            self.load_config()
        
        return self._config["servers"].get(server_name)
    
    def get_global_settings(self) -> Dict[str, Any]:
        """Get global MCP settings."""
        if not self._config:
            self.load_config()
        
        return self._config.get("global_settings", self._get_default_global_settings())
    
    def get_user_permissions(self, user_id: str) -> Dict[str, Any]:
        """Get permissions for a specific user."""
        if not self._config:
            self.load_config()
        
        permissions = self._config.get("permissions", {})
        
        # Check for specific user permissions
        if user_id in permissions:
            return permissions[user_id]
        
        # Fall back to default permissions
        return permissions.get("default", self._get_default_permissions()["default"])
    
    def is_server_allowed_for_user(self, user_id: str, server_name: str) -> bool:
        """Check if user is allowed to use a specific server."""
        user_perms = self.get_user_permissions(user_id)
        allowed_servers = user_perms.get("allowed_servers", [])
        
        # Check if user has access to all servers or this specific server
        return "*" in allowed_servers or server_name in allowed_servers
    
    def is_capability_allowed_for_user(self, user_id: str, capability: str) -> bool:
        """Check if user is allowed to use a specific capability."""
        user_perms = self.get_user_permissions(user_id)
        allowed_capabilities = user_perms.get("allowed_capabilities", [])
        
        # Check if user has access to all capabilities or this specific capability
        return "*" in allowed_capabilities or capability in allowed_capabilities
    
    def update_server_status(self, server_name: str, enabled: bool) -> bool:
        """Update server enabled status."""
        try:
            if not self._config:
                self.load_config()
            
            if server_name not in self._config["servers"]:
                return False
            
            self._config["servers"][server_name]["enabled"] = enabled
            
            # Save to file
            with open(self.config_path, 'w') as f:
                json.dump(self._config, f, indent=2)
            
            self.logger.info(f"Updated server '{server_name}' status to {'enabled' if enabled else 'disabled'}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to update server status: {e}")
            return False
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration if no config file exists."""
        return {
            "servers": {},
            "global_settings": self._get_default_global_settings(),
            "permissions": self._get_default_permissions()
        }
    
    def _get_default_global_settings(self) -> Dict[str, Any]:
        """Get default global settings."""
        return {
            "max_concurrent_connections": 5,
            "connection_retry_attempts": 3,
            "connection_retry_delay": 2000,
            "health_check_interval": 30000,
            "log_level": "INFO",
            "enable_tool_discovery": True,
            "tool_execution_timeout": 60000,
            "sandbox_mode": True
        }
    
    def _get_default_permissions(self) -> Dict[str, Any]:
        """Get default permission settings."""
        return {
            "default": {
                "allowed_servers": [],
                "allowed_capabilities": [],
                "rate_limits": {
                    "requests_per_minute": 10,
                    "concurrent_operations": 2
                }
            }
        }
    
    def get_server_list(self) -> List[Dict[str, Any]]:
        """Get list of all servers with basic info."""
        if not self._config:
            self.load_config()
        
        servers = []
        for name, config in self._config["servers"].items():
            servers.append({
                "name": name,
                "display_name": config["name"],
                "description": config["description"],
                "enabled": config.get("enabled", False),
                "capabilities": config.get("capabilities", []),
                "connection_type": config["connection"]["type"]
            })
        
        return servers