# PMCP - Perfect Model Context Protocol Server

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104.1-009688.svg)](https://fastapi.tiangolo.com/)

A comprehensive, production-ready Model Context Protocol (MCP) server with advanced AI capabilities, web-based administration, and extensive plugin ecosystem support.

## 🚀 Features

### Core Capabilities
- **🤖 AI Integration**: Support for OpenAI, Anthropic, and Google Gemini models
- **🔌 MCP Plugin Hub**: Discover, install, and manage MCP plugins with ease
- **💾 Multi-Database Support**: Redis for caching, MongoDB for persistence
- **🌐 Web Admin Interface**: Comprehensive dashboard for server management
- **🔒 SSH/SFTP Access**: Secure file operations and remote access
- **📊 Real-time Monitoring**: Live metrics, logs, and system status

### Advanced Services
- **🧠 Memory Management**: Persistent context and session handling
- **📚 RAG (Retrieval-Augmented Generation)**: Document indexing and semantic search
- **🔍 Code Analysis**: AI-powered code review and improvement suggestions
- **🎭 Playwright Integration**: Web automation and browser control
- **🔗 Sequential Thinking**: Chain-of-thought reasoning capabilities

### Administration & Monitoring
- **📈 Dashboard**: Real-time system metrics and performance monitoring
- **🗂️ File Management**: Web-based file browser and editor
- **👥 User Management**: Authentication and access control
- **🔧 Configuration**: Dynamic settings management
- **📋 Logging**: Comprehensive structured logging with multiple outputs

## 🛠️ Quick Start

### Prerequisites
- Python 3.8 or higher
- Redis server
- MongoDB server
- Git

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/NoobyNull/PMCP.git
   cd PMCP
   ```

2. **Set up Python environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure databases**
   ```bash
   # Install and start Redis
   sudo apt-get install redis-server
   sudo systemctl start redis-server

   # Install and start MongoDB
   sudo apt-get install mongodb
   sudo systemctl start mongodb
   ```

4. **Configure the server**
   ```bash
   cp config/server.yaml.example config/server.yaml
   # Edit config/server.yaml with your settings
   ```

5. **Start the server**
   ```bash
   # Development mode
   python admin_server.py

   # Production mode (systemd service)
   sudo ./setup_service.sh
   ```

### Access Points
- **Admin Interface**: http://localhost:8080
- **API Server**: http://localhost:8000
- **SSH/SFTP**: localhost:2222

## 📖 Documentation

### Quick Setup Guides
- [🚀 Deployment Guide](DEPLOYMENT_GUIDE.md) - Production deployment instructions
- [🔧 Admin Interface Guide](ADMIN_INTERFACE_GUIDE.md) - Web interface overview
- [🔌 MCP Hub Guide](MCP_HUB_FEATURE_SUMMARY.md) - Plugin management
- [🤖 Augment Integration](AUGMENT_MCP_SETUP.md) - AI assistant setup

### Advanced Configuration
- [🌐 LAN Access Setup](LAN_CONNECTION_INFO.md) - Network configuration
- [🔐 Service Management](SERVICE_MANAGEMENT.md) - Systemd service setup
- [📊 Logging Configuration](LOGGING_IMPROVEMENTS_SUMMARY.md) - Log management
- [🎨 UI/UX Customization](UI_UX_AUDIT_AND_FIXES.md) - Interface theming

## 🔌 MCP Plugin Ecosystem

PMCP includes a built-in plugin hub that provides access to the Model Context Protocol ecosystem:

### Featured Plugins
- **Filesystem MCP Server** - Secure file system operations
- **GitHub MCP Server** - Repository management and operations  
- **Brave Search MCP Server** - Web search capabilities
- **SQLite/PostgreSQL MCP Servers** - Database operations
- **And many more...**

### Plugin Management
- Browse and search available plugins
- One-click installation with progress tracking
- Automatic dependency management
- Plugin status monitoring and updates

## 🏗️ Architecture

```
PMCP Server
├── Admin Interface (Port 8080)
│   ├── Dashboard & Monitoring
│   ├── Plugin Management
│   ├── File Browser
│   └── Configuration
├── API Server (Port 8000)
│   ├── MCP Protocol Endpoints
│   ├── AI Service Integration
│   ├── Memory & Context Management
│   └── RAG & Document Processing
├── SSH/SFTP Server (Port 2222)
│   ├── Secure File Access
│   └── Remote Command Execution
└── Background Services
    ├── Plugin Manager
    ├── Database Connections
    ├── Logging System
    └── Monitoring Agents
```

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details.

### Development Setup
1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes and add tests
4. Run the test suite: `pytest`
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Model Context Protocol](https://modelcontextprotocol.io) - The open standard this server implements
- [FastAPI](https://fastapi.tiangolo.com/) - The web framework powering our APIs
- [Bootstrap](https://getbootstrap.com/) - UI framework for the admin interface
- The MCP community for their excellent plugins and contributions

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/NoobyNull/PMCP/issues)
- **Discussions**: [GitHub Discussions](https://github.com/NoobyNull/PMCP/discussions)
- **Documentation**: [Project Wiki](https://github.com/NoobyNull/PMCP/wiki)

---

**PMCP** - Empowering AI assistants with comprehensive context and capabilities 🚀
