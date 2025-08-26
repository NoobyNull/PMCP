"""
Plugin Manager for MCP plugins
Handles plugin installation, loading, and integration with MCP endpoints
"""

import asyncio
import json
import logging
import os
import importlib
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class PluginManager:
    """Manages MCP plugins - installation, loading, and integration"""
    
    def __init__(self, db_manager=None, services=None):
        self.db_manager = db_manager
        self.services = services or {}
        self.plugins_dir = Path("/opt/PerfectMCP/plugins")
        self.installed_plugins: Dict[str, Dict] = {}
        self.plugin_tools: Dict[str, Dict] = {}
        self.plugin_handlers: Dict[str, callable] = {}
        
        # Ensure plugins directory exists
        self.plugins_dir.mkdir(exist_ok=True)
        
        # Add plugins directory to Python path
        if str(self.plugins_dir) not in sys.path:
            sys.path.insert(0, str(self.plugins_dir))
    
    async def initialize(self):
        """Initialize plugin manager and load installed plugins"""
        try:
            logger.info("Initializing Plugin Manager")
            await self.load_installed_plugins()
            await self.register_plugin_tools()
            logger.info(f"Plugin Manager initialized with {len(self.installed_plugins)} plugins")
        except Exception as e:
            logger.error(f"Error initializing Plugin Manager: {e}")
    
    async def load_installed_plugins(self):
        """Load list of installed plugins from database"""
        try:
            if not self.db_manager:
                logger.warning("No database manager available for plugin loading")
                return
            
            # Get installed plugins from database
            plugins = await self.db_manager.mongo_find_many("installed_plugins", {})
            
            for plugin_data in plugins:
                plugin_id = plugin_data.get("plugin_id")
                if plugin_id:
                    self.installed_plugins[plugin_id] = plugin_data
                    logger.info(f"Loaded installed plugin: {plugin_id}")
            
            logger.info(f"Loaded {len(self.installed_plugins)} installed plugins")
            
        except Exception as e:
            logger.error(f"Error loading installed plugins: {e}")
    
    async def register_plugin_tools(self):
        """Register tools from installed plugins"""
        try:
            for plugin_id, plugin_data in self.installed_plugins.items():
                await self.load_plugin_module(plugin_id, plugin_data)
            
            logger.info(f"Registered {len(self.plugin_tools)} plugin tools")
            
        except Exception as e:
            logger.error(f"Error registering plugin tools: {e}")
    
    async def load_plugin_module(self, plugin_id: str, plugin_data: Dict):
        """Load a specific plugin module and register its tools"""
        try:
            plugin_path = self.plugins_dir / plugin_id
            
            if not plugin_path.exists():
                logger.warning(f"Plugin directory not found: {plugin_path}")
                return
            
            # Try to import the plugin module
            try:
                module_name = f"{plugin_id}.main"
                if module_name in sys.modules:
                    # Reload if already imported
                    importlib.reload(sys.modules[module_name])
                else:
                    importlib.import_module(module_name)
                
                plugin_module = sys.modules[module_name]
                
                # Get plugin tools and handlers
                if hasattr(plugin_module, 'get_tools'):
                    tools = plugin_module.get_tools()
                    for tool in tools:
                        tool_name = tool.get('name')
                        if tool_name:
                            self.plugin_tools[tool_name] = tool
                            logger.info(f"Registered tool: {tool_name} from plugin {plugin_id}")
                
                if hasattr(plugin_module, 'get_handlers'):
                    handlers = plugin_module.get_handlers()
                    for tool_name, handler in handlers.items():
                        self.plugin_handlers[tool_name] = handler
                        logger.info(f"Registered handler: {tool_name} from plugin {plugin_id}")
                
            except ImportError as e:
                logger.warning(f"Could not import plugin {plugin_id}: {e}")
            except Exception as e:
                logger.error(f"Error loading plugin {plugin_id}: {e}")
                
        except Exception as e:
            logger.error(f"Error loading plugin module {plugin_id}: {e}")
    
    async def install_plugin(self, plugin_id: str, plugin_info: Dict) -> Dict:
        """Install a plugin and register it"""
        try:
            logger.info(f"Installing plugin: {plugin_id}")
            
            # Create plugin directory
            plugin_path = self.plugins_dir / plugin_id
            plugin_path.mkdir(exist_ok=True)
            
            # Create basic plugin structure based on plugin type
            await self.create_plugin_files(plugin_id, plugin_info, plugin_path)
            
            # Save to database
            if self.db_manager:
                plugin_record = {
                    "plugin_id": plugin_id,
                    "name": plugin_info.get("name"),
                    "version": plugin_info.get("version"),
                    "author": plugin_info.get("author"),
                    "category": plugin_info.get("category"),
                    "description": plugin_info.get("description"),
                    "installed_at": datetime.utcnow().isoformat(),
                    "status": "active"
                }
                
                await self.db_manager.mongo_insert_one("installed_plugins", plugin_record)
                self.installed_plugins[plugin_id] = plugin_record
            
            # Load the plugin
            await self.load_plugin_module(plugin_id, plugin_info)
            
            logger.info(f"Successfully installed plugin: {plugin_id}")
            return {"success": True, "message": f"Plugin {plugin_id} installed successfully"}
            
        except Exception as e:
            logger.error(f"Error installing plugin {plugin_id}: {e}")
            return {"success": False, "error": str(e)}
    
    async def create_plugin_files(self, plugin_id: str, plugin_info: Dict, plugin_path: Path):
        """Create plugin files based on plugin type"""
        try:
            # Create __init__.py
            init_file = plugin_path / "__init__.py"
            init_file.write_text('"""MCP Plugin"""\n')
            
            # Create main.py with plugin implementation
            main_file = plugin_path / "main.py"
            
            # Generate plugin code based on category
            plugin_code = self.generate_plugin_code(plugin_id, plugin_info)
            main_file.write_text(plugin_code)
            
            # Create config.json
            config_file = plugin_path / "config.json"
            config_data = {
                "id": plugin_id,
                "name": plugin_info.get("name"),
                "version": plugin_info.get("version"),
                "description": plugin_info.get("description"),
                "author": plugin_info.get("author"),
                "category": plugin_info.get("category")
            }
            config_file.write_text(json.dumps(config_data, indent=2))
            
            logger.info(f"Created plugin files for {plugin_id}")
            
        except Exception as e:
            logger.error(f"Error creating plugin files for {plugin_id}: {e}")
            raise
    
    def generate_plugin_code(self, plugin_id: str, plugin_info: Dict) -> str:
        """Generate plugin code based on plugin type and category"""
        category = plugin_info.get("category", "general")
        name = plugin_info.get("name", plugin_id)
        description = plugin_info.get("description", "")
        
        if category == "ai":
            return self.generate_ai_plugin_code(plugin_id, name, description)
        elif category == "development":
            return self.generate_development_plugin_code(plugin_id, name, description)
        elif category == "data":
            return self.generate_data_plugin_code(plugin_id, name, description)
        elif category == "automation":
            return self.generate_automation_plugin_code(plugin_id, name, description)
        else:
            return self.generate_generic_plugin_code(plugin_id, name, description)
    
    def generate_ai_plugin_code(self, plugin_id: str, name: str, description: str) -> str:
        """Generate AI plugin code"""
        return f'''"""
{name} - AI Plugin
{description}
"""

import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

def get_tools() -> List[Dict]:
    """Return tools provided by this plugin"""
    return [
        {{
            "name": "{plugin_id}_analyze",
            "description": "AI analysis using {name}",
            "inputSchema": {{
                "type": "object",
                "properties": {{
                    "text": {{"type": "string"}},
                    "analysis_type": {{"type": "string"}}
                }},
                "required": ["text"]
            }}
        }}
    ]

def get_handlers() -> Dict[str, callable]:
    """Return tool handlers"""
    return {{
        "{plugin_id}_analyze": handle_analyze
    }}

async def handle_analyze(params: Dict) -> Dict:
    """Handle AI analysis request"""
    try:
        text = params.get("text", "")
        analysis_type = params.get("analysis_type", "general")
        
        logger.info(f"Performing {{analysis_type}} analysis on text: {{text[:50]}}...")
        
        # Mock AI analysis
        result = {{
            "analysis": f"AI analysis of '{{text[:50]}}...' using {name}",
            "type": analysis_type,
            "confidence": 0.85,
            "insights": [
                "This text appears to be well-structured",
                "Sentiment analysis shows neutral tone",
                "Key topics identified: technology, development"
            ]
        }}
        
        return {{"success": True, "result": result}}
        
    except Exception as e:
        logger.error(f"Error in {name} analysis: {{e}}")
        return {{"success": False, "error": str(e)}}
'''
    
    def generate_development_plugin_code(self, plugin_id: str, name: str, description: str) -> str:
        """Generate development plugin code"""
        return f'''"""
{name} - Development Plugin
{description}
"""

import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

def get_tools() -> List[Dict]:
    """Return tools provided by this plugin"""
    return [
        {{
            "name": "{plugin_id}_review",
            "description": "Code review using {name}",
            "inputSchema": {{
                "type": "object",
                "properties": {{
                    "code": {{"type": "string"}},
                    "language": {{"type": "string"}}
                }},
                "required": ["code"]
            }}
        }}
    ]

def get_handlers() -> Dict[str, callable]:
    """Return tool handlers"""
    return {{
        "{plugin_id}_review": handle_code_review
    }}

async def handle_code_review(params: Dict) -> Dict:
    """Handle code review request"""
    try:
        code = params.get("code", "")
        language = params.get("language", "unknown")
        
        logger.info(f"Reviewing {{language}} code: {{len(code)}} characters")
        
        # Mock code review
        result = {{
            "review": f"Code review completed using {name}",
            "language": language,
            "issues": [
                {{"type": "warning", "line": 5, "message": "Consider adding error handling"}},
                {{"type": "info", "line": 12, "message": "Good use of descriptive variable names"}}
            ],
            "score": 8.5,
            "suggestions": [
                "Add docstrings to functions",
                "Consider using type hints",
                "Add unit tests"
            ]
        }}
        
        return {{"success": True, "result": result}}
        
    except Exception as e:
        logger.error(f"Error in {name} code review: {{e}}")
        return {{"success": False, "error": str(e)}}
'''
    
    def generate_generic_plugin_code(self, plugin_id: str, name: str, description: str) -> str:
        """Generate generic plugin code"""
        return f'''"""
{name} - Generic Plugin
{description}
"""

import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

def get_tools() -> List[Dict]:
    """Return tools provided by this plugin"""
    return [
        {{
            "name": "{plugin_id}_execute",
            "description": "Execute {name} functionality",
            "inputSchema": {{
                "type": "object",
                "properties": {{
                    "action": {{"type": "string"}},
                    "parameters": {{"type": "object"}}
                }},
                "required": ["action"]
            }}
        }}
    ]

def get_handlers() -> Dict[str, callable]:
    """Return tool handlers"""
    return {{
        "{plugin_id}_execute": handle_execute
    }}

async def handle_execute(params: Dict) -> Dict:
    """Handle plugin execution request"""
    try:
        action = params.get("action", "default")
        parameters = params.get("parameters", {{}})
        
        logger.info(f"Executing {{action}} with parameters: {{parameters}}")
        
        # Mock execution
        result = {{
            "action": action,
            "parameters": parameters,
            "output": f"Executed {{action}} using {name}",
            "timestamp": "2024-01-01T00:00:00Z"
        }}
        
        return {{"success": True, "result": result}}
        
    except Exception as e:
        logger.error(f"Error executing {name}: {{e}}")
        return {{"success": False, "error": str(e)}}
'''
    
    def generate_data_plugin_code(self, plugin_id: str, name: str, description: str) -> str:
        """Generate data analysis plugin code"""
        return f'''"""
{name} - Data Analysis Plugin
{description}
"""

import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

def get_tools() -> List[Dict]:
    """Return tools provided by this plugin"""
    return [
        {{
            "name": "{plugin_id}_analyze_data",
            "description": "Analyze data using {name}",
            "inputSchema": {{
                "type": "object",
                "properties": {{
                    "data": {{"type": "array"}},
                    "analysis_type": {{"type": "string"}}
                }},
                "required": ["data"]
            }}
        }}
    ]

def get_handlers() -> Dict[str, callable]:
    """Return tool handlers"""
    return {{
        "{plugin_id}_analyze_data": handle_data_analysis
    }}

async def handle_data_analysis(params: Dict) -> Dict:
    """Handle data analysis request"""
    try:
        data = params.get("data", [])
        analysis_type = params.get("analysis_type", "summary")
        
        logger.info(f"Analyzing {{len(data)}} data points using {{analysis_type}} analysis")
        
        # Mock data analysis
        result = {{
            "analysis_type": analysis_type,
            "data_points": len(data),
            "summary": {{
                "mean": 42.5,
                "median": 40.0,
                "std_dev": 12.3,
                "min": 10,
                "max": 95
            }},
            "insights": [
                "Data shows normal distribution",
                "No significant outliers detected",
                "Trend analysis suggests upward movement"
            ]
        }}
        
        return {{"success": True, "result": result}}
        
    except Exception as e:
        logger.error(f"Error in {name} data analysis: {{e}}")
        return {{"success": False, "error": str(e)}}
'''
    
    def generate_automation_plugin_code(self, plugin_id: str, name: str, description: str) -> str:
        """Generate automation plugin code"""
        return f'''"""
{name} - Automation Plugin
{description}
"""

import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

def get_tools() -> List[Dict]:
    """Return tools provided by this plugin"""
    return [
        {{
            "name": "{plugin_id}_automate",
            "description": "Automate tasks using {name}",
            "inputSchema": {{
                "type": "object",
                "properties": {{
                    "task": {{"type": "string"}},
                    "schedule": {{"type": "string"}},
                    "parameters": {{"type": "object"}}
                }},
                "required": ["task"]
            }}
        }}
    ]

def get_handlers() -> Dict[str, callable]:
    """Return tool handlers"""
    return {{
        "{plugin_id}_automate": handle_automation
    }}

async def handle_automation(params: Dict) -> Dict:
    """Handle automation request"""
    try:
        task = params.get("task", "")
        schedule = params.get("schedule", "immediate")
        parameters = params.get("parameters", {{}})
        
        logger.info(f"Automating task: {{task}} with schedule: {{schedule}}")
        
        # Mock automation
        result = {{
            "task": task,
            "schedule": schedule,
            "parameters": parameters,
            "status": "scheduled",
            "automation_id": f"auto_{{task.replace(' ', '_')}}",
            "next_run": "2024-01-01T12:00:00Z"
        }}
        
        return {{"success": True, "result": result}}
        
    except Exception as e:
        logger.error(f"Error in {name} automation: {{e}}")
        return {{"success": False, "error": str(e)}}
'''
    
    async def uninstall_plugin(self, plugin_id: str) -> Dict:
        """Uninstall a plugin"""
        try:
            logger.info(f"Uninstalling plugin: {plugin_id}")
            
            # Remove from database
            if self.db_manager:
                await self.db_manager.mongo_delete_one("installed_plugins", {"plugin_id": plugin_id})
            
            # Remove from memory
            if plugin_id in self.installed_plugins:
                del self.installed_plugins[plugin_id]
            
            # Remove plugin tools and handlers
            tools_to_remove = [tool for tool in self.plugin_tools.keys() if tool.startswith(plugin_id)]
            for tool in tools_to_remove:
                del self.plugin_tools[tool]
                if tool in self.plugin_handlers:
                    del self.plugin_handlers[tool]
            
            # Remove plugin directory
            plugin_path = self.plugins_dir / plugin_id
            if plugin_path.exists():
                import shutil
                shutil.rmtree(plugin_path)
            
            logger.info(f"Successfully uninstalled plugin: {plugin_id}")
            return {"success": True, "message": f"Plugin {plugin_id} uninstalled successfully"}
            
        except Exception as e:
            logger.error(f"Error uninstalling plugin {plugin_id}: {e}")
            return {"success": False, "error": str(e)}
    
    def get_all_tools(self) -> List[Dict]:
        """Get all tools from core system and installed plugins"""
        # Core tools
        core_tools = [
            {
                "name": "memory_context_PerfectMCP_Server",
                "description": "Manage memory context for sessions",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"},
                        "context": {"type": "string"}
                    }
                }
            },
            {
                "name": "code_analysis_PerfectMCP_Server",
                "description": "Analyze code for improvements",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string"},
                        "language": {"type": "string"}
                    }
                }
            },
            {
                "name": "document_search_PerfectMCP_Server",
                "description": "Search documents using RAG",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "max_results": {"type": "integer"}
                    }
                }
            },
            {
                "name": "context7_analyze_PerfectMCP_Server",
                "description": "Analyze context using 7-layer context management",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"},
                        "content": {"type": "string"},
                        "context_type": {"type": "string"}
                    }
                }
            },
            {
                "name": "playwright_navigate_PerfectMCP_Server",
                "description": "Navigate web pages using Playwright automation",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string"},
                        "action": {"type": "string"},
                        "selector": {"type": "string"}
                    }
                }
            },
            {
                "name": "sequential_thinking_PerfectMCP_Server",
                "description": "Create and manage step-by-step reasoning chains",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"},
                        "problem": {"type": "string"},
                        "thinking_type": {"type": "string"}
                    }
                }
            },
            {
                "name": "ssh_execute_PerfectMCP_Server",
                "description": "Execute commands via SSH service",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string"},
                        "session_id": {"type": "string"}
                    }
                }
            }
        ]
        
        # Add plugin tools
        all_tools = core_tools + list(self.plugin_tools.values())

        logger.info(f"Returning {len(all_tools)} total tools ({len(core_tools)} core + {len(self.plugin_tools)} plugin)")
        return all_tools
    
    async def handle_tool_call(self, tool_name: str, arguments: Dict) -> Dict:
        """Handle a tool call, routing to appropriate handler"""
        try:
            if tool_name in self.plugin_handlers:
                logger.info(f"Calling plugin handler for tool: {tool_name}")
                return await self.plugin_handlers[tool_name](arguments)
            else:
                # Handle core tools
                logger.info(f"Handling core tool: {tool_name}")
                return await self._handle_core_tool(tool_name, arguments)

        except Exception as e:
            logger.error(f"Error handling tool call {tool_name}: {e}")
            return {"status": "error", "message": str(e)}

    async def _handle_core_tool(self, tool_name: str, arguments: Dict) -> Dict:
        """Handle core tool calls by routing to appropriate services"""
        try:
            if tool_name == "memory_context_PerfectMCP_Server":
                # Route to memory service
                memory_service = self.services.get('memory_service')
                if memory_service:
                    session_id = arguments.get('session_id', 'default')
                    context = arguments.get('context', '')
                    if context:
                        await memory_service.update_context(session_id, context)
                    return {
                        "status": "success",
                        "message": f"Memory context managed for session {session_id}",
                        "tool": "memory_context",
                        "arguments": arguments
                    }
                else:
                    return {"status": "error", "message": "Memory service not available"}

            elif tool_name == "code_analysis_PerfectMCP_Server":
                # Route to code improvement service
                code_service = self.services.get('code_improvement_service')
                if code_service:
                    code = arguments.get('code', '')
                    language = arguments.get('language', 'unknown')
                    # Perform actual code analysis
                    result = await code_service.analyze_code(code, language)
                    return {
                        "status": "success",
                        "message": f"Code analysis completed for {language} code",
                        "tool": "code_analysis",
                        "result": result,
                        "arguments": arguments
                    }
                else:
                    return {"status": "error", "message": "Code improvement service not available"}

            elif tool_name == "document_search_PerfectMCP_Server":
                # Route to RAG service
                rag_service = self.services.get('rag_service')
                if rag_service:
                    query = arguments.get('query', '')
                    max_results = arguments.get('max_results', 5)
                    # Perform actual document search
                    results = await rag_service.search_documents(query, max_results)
                    return {
                        "status": "success",
                        "message": f"Document search completed for query: {query}",
                        "tool": "document_search",
                        "results": results,
                        "arguments": arguments
                    }
                else:
                    return {"status": "error", "message": "RAG service not available"}

            elif tool_name == "context7_analyze_PerfectMCP_Server":
                # Route to Context7 service
                context7_service = self.services.get('context7_service')
                if context7_service:
                    session_id = arguments.get('session_id', 'default')
                    content = arguments.get('content', '')
                    context_type = arguments.get('context_type', 'general')
                    # Perform actual context analysis
                    result = await context7_service.analyze_context(session_id, content, context_type)
                    return {
                        "status": "success",
                        "message": f"Context7 analysis completed for session {session_id}",
                        "tool": "context7_analyze",
                        "result": result,
                        "arguments": arguments
                    }
                else:
                    return {"status": "error", "message": "Context7 service not available"}

            elif tool_name == "playwright_navigate_PerfectMCP_Server":
                # Route to Playwright service
                playwright_service = self.services.get('playwright_service')
                if playwright_service:
                    url = arguments.get('url', '')
                    action = arguments.get('action', 'navigate')
                    selector = arguments.get('selector', '')
                    # Perform actual web automation
                    result = await playwright_service.execute_action(url, action, selector)
                    return {
                        "status": "success",
                        "message": f"Playwright navigation to {url} completed",
                        "tool": "playwright_navigate",
                        "result": result,
                        "arguments": arguments
                    }
                else:
                    return {"status": "error", "message": "Playwright service not available"}

            elif tool_name == "sequential_thinking_PerfectMCP_Server":
                # Route to Sequential Thinking service
                sequential_service = self.services.get('sequential_thinking_service')
                if sequential_service:
                    session_id = arguments.get('session_id', 'default')
                    problem = arguments.get('problem', '')
                    thinking_type = arguments.get('thinking_type', 'general')
                    # Perform actual sequential thinking
                    result = await sequential_service.create_thinking_chain(session_id, problem, thinking_type)
                    return {
                        "status": "success",
                        "message": f"Sequential thinking chain created for session {session_id}",
                        "tool": "sequential_thinking",
                        "result": result,
                        "arguments": arguments
                    }
                else:
                    return {"status": "error", "message": "Sequential Thinking service not available"}

            elif tool_name == "ssh_execute_PerfectMCP_Server":
                # Route to SSH service
                ssh_service = self.services.get('ssh_service')
                if ssh_service:
                    command = arguments.get('command', '')
                    session_id = arguments.get('session_id', 'default')
                    # Execute SSH command
                    result = await ssh_service.execute_command(command, session_id)
                    return {
                        "status": "success",
                        "message": f"SSH command executed: {command}",
                        "tool": "ssh_execute",
                        "result": result,
                        "arguments": arguments
                    }
                else:
                    return {"status": "error", "message": "SSH service not available"}

            else:
                return {
                    "status": "error",
                    "message": f"Unknown tool: {tool_name}"
                }

        except Exception as e:
            logger.error(f"Error in core tool handler {tool_name}: {e}")
            return {"status": "error", "message": str(e)}
    
    def get_installed_plugins(self) -> List[Dict]:
        """Get list of installed plugins"""
        return list(self.installed_plugins.values())
