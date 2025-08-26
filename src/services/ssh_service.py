"""
SSH/SFTP Service for PerfectMPC
Provides SSH and SFTP access to the MPC server functionality
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Optional, Dict, Any

import asyncssh
from asyncssh import SSHServerSession, SSHServerChannel, SFTPServer

from utils.config import SSHConfig
from utils.logger import LoggerMixin


class MPCSSHServer(asyncssh.SSHServer):
    """Custom SSH server for MPC functionality"""
    
    def __init__(self, memory_service, code_service, rag_service):
        self.memory_service = memory_service
        self.code_service = code_service
        self.rag_service = rag_service
    
    def connection_made(self, conn):
        """Called when SSH connection is established"""
        print(f"SSH connection from {conn.get_extra_info('peername')}")
    
    def connection_lost(self, exc):
        """Called when SSH connection is lost"""
        if exc:
            print(f"SSH connection error: {exc}")
        else:
            print("SSH connection closed")
    
    def begin_auth(self, username):
        """Begin authentication process"""
        # No authentication required as specified
        return True
    
    def password_auth_supported(self):
        """Whether password authentication is supported"""
        return False
    
    def public_key_auth_supported(self):
        """Whether public key authentication is supported"""
        return False
    
    def session_requested(self):
        """Handle session request"""
        return MPCSSHSession(self.memory_service, self.code_service, self.rag_service)
    
    def sftp_requested(self):
        """Handle SFTP request"""
        return MPCSFTPServer(self.memory_service, self.code_service, self.rag_service)


class MPCSSHSession(SSHServerSession):
    """SSH session handler for MPC commands"""
    
    def __init__(self, memory_service, code_service, rag_service):
        self.memory_service = memory_service
        self.code_service = code_service
        self.rag_service = rag_service
        self.session_id = None
    
    def connection_made(self, chan):
        """Called when session channel is established"""
        self.chan = chan
    
    def shell_requested(self):
        """Handle shell request"""
        return True
    
    def exec_requested(self, command):
        """Handle command execution request"""
        asyncio.create_task(self._handle_command(command))
        return True
    
    async def _handle_command(self, command: str):
        """Handle MPC commands"""
        try:
            parts = command.strip().split()
            if not parts:
                await self._send_response({"error": "No command provided"})
                return
            
            cmd = parts[0].lower()
            args = parts[1:]
            
            if cmd == "mpc":
                await self._handle_mpc_command(args)
            elif cmd == "session":
                await self._handle_session_command(args)
            elif cmd == "analyze":
                await self._handle_analyze_command(args)
            elif cmd == "search":
                await self._handle_search_command(args)
            elif cmd == "help":
                await self._send_help()
            else:
                await self._send_response({"error": f"Unknown command: {cmd}"})
        
        except Exception as e:
            await self._send_response({"error": str(e)})
        finally:
            self.chan.exit(0)
    
    async def _handle_mcp_command(self, args):
        """Handle MCP-specific commands"""
        if not args:
            await self._send_response({
                "message": "PerfectMCP Server",
                "version": "1.0.0",
                "services": ["memory", "code_improvement", "rag"]
            })
            return

        subcommand = args[0].lower()

        if subcommand == "status":
            status = {
                "memory_service": self.memory_service is not None,
                "code_service": self.code_service is not None,
                "rag_service": self.rag_service is not None,
                "active_session": self.session_id
            }
            await self._send_response(status)

        elif subcommand == "version":
            await self._send_response({"version": "1.0.0", "build": "development"})

        else:
            await self._send_response({"error": f"Unknown MCP command: {subcommand}"})
    
    async def _handle_session_command(self, args):
        """Handle session management commands"""
        if not args:
            await self._send_response({"error": "Session command requires arguments"})
            return
        
        subcommand = args[0].lower()
        
        if subcommand == "create":
            session_id = args[1] if len(args) > 1 else None
            self.session_id = await self.memory_service.create_session(session_id)
            await self._send_response({"session_id": self.session_id, "status": "created"})
        
        elif subcommand == "get":
            if not self.session_id:
                await self._send_response({"error": "No active session"})
                return
            
            session_data = await self.memory_service.get_session(self.session_id)
            await self._send_response(session_data)
        
        elif subcommand == "context":
            if len(args) < 2:
                await self._send_response({"error": "Context command requires content"})
                return
            
            if not self.session_id:
                self.session_id = await self.memory_service.create_session()
            
            context = " ".join(args[1:])
            await self.memory_service.update_context(self.session_id, context)
            await self._send_response({"status": "context_updated"})
        
        else:
            await self._send_response({"error": f"Unknown session command: {subcommand}"})
    
    async def _handle_analyze_command(self, args):
        """Handle code analysis commands"""
        if len(args) < 2:
            await self._send_response({"error": "Analyze command requires language and code"})
            return
        
        if not self.session_id:
            self.session_id = await self.memory_service.create_session()
        
        language = args[0]
        code = " ".join(args[1:])
        
        try:
            analysis = await self.code_service.analyze_code(
                self.session_id, code, language
            )
            await self._send_response(analysis)
        except Exception as e:
            await self._send_response({"error": f"Analysis failed: {str(e)}"})
    
    async def _handle_search_command(self, args):
        """Handle document search commands"""
        if not args:
            await self._send_response({"error": "Search command requires query"})
            return
        
        if not self.session_id:
            self.session_id = await self.memory_service.create_session()
        
        query = " ".join(args)
        
        try:
            results = await self.rag_service.search_documents(self.session_id, query)
            await self._send_response({"query": query, "results": results})
        except Exception as e:
            await self._send_response({"error": f"Search failed: {str(e)}"})
    
    async def _send_help(self):
        """Send help information"""
        help_text = """
PerfectMPC SSH Interface Commands:

mpc                    - Show server information
mpc status            - Show service status
mpc version           - Show version information

session create [id]   - Create new session
session get           - Get current session info
session context <text> - Update session context

analyze <lang> <code> - Analyze code
search <query>        - Search documents

help                  - Show this help message
        """
        await self._send_response({"help": help_text.strip()})
    
    async def _send_response(self, data: Dict[str, Any]):
        """Send JSON response"""
        response = json.dumps(data, indent=2)
        self.chan.write(response + "\n")


class MCPSFTPServer(SFTPServer):
    """SFTP server for file operations"""

    def __init__(self, memory_service, code_service, rag_service):
        super().__init__()
        self.memory_service = memory_service
        self.code_service = code_service
        self.rag_service = rag_service
        self.base_path = Path("/opt/PerfectMCP/data/sftp")
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    async def open(self, path, pflags, attrs):
        """Open file for SFTP operations"""
        # Resolve path relative to base directory
        full_path = self.base_path / path.lstrip('/')
        
        # Ensure path is within base directory
        try:
            full_path.resolve().relative_to(self.base_path.resolve())
        except ValueError:
            raise asyncssh.SFTPError(asyncssh.FX_PERMISSION_DENIED, "Access denied")
        
        # Create parent directories if needed
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Open file
        mode = 'rb' if pflags & asyncssh.FXF_READ else 'wb'
        if pflags & asyncssh.FXF_APPEND:
            mode = 'ab'
        
        try:
            return open(full_path, mode)
        except IOError as e:
            raise asyncssh.SFTPError(asyncssh.FX_FAILURE, str(e))
    
    async def stat(self, path):
        """Get file/directory statistics"""
        full_path = self.base_path / path.lstrip('/')
        
        try:
            stat_result = full_path.stat()
            return asyncssh.SFTPAttrs(
                size=stat_result.st_size,
                uid=stat_result.st_uid,
                gid=stat_result.st_gid,
                permissions=stat_result.st_mode,
                atime=stat_result.st_atime,
                mtime=stat_result.st_mtime
            )
        except FileNotFoundError:
            raise asyncssh.SFTPError(asyncssh.FX_NO_SUCH_FILE, "File not found")
    
    async def listdir(self, path):
        """List directory contents"""
        full_path = self.base_path / path.lstrip('/')
        
        try:
            entries = []
            for item in full_path.iterdir():
                stat_result = item.stat()
                attrs = asyncssh.SFTPAttrs(
                    size=stat_result.st_size,
                    uid=stat_result.st_uid,
                    gid=stat_result.st_gid,
                    permissions=stat_result.st_mode,
                    atime=stat_result.st_atime,
                    mtime=stat_result.st_mtime
                )
                entries.append(asyncssh.SFTPName(item.name, attrs=attrs))
            return entries
        except FileNotFoundError:
            raise asyncssh.SFTPError(asyncssh.FX_NO_SUCH_FILE, "Directory not found")
    
    async def mkdir(self, path, attrs):
        """Create directory"""
        full_path = self.base_path / path.lstrip('/')
        
        try:
            full_path.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise asyncssh.SFTPError(asyncssh.FX_FAILURE, str(e))
    
    async def remove(self, path):
        """Remove file"""
        full_path = self.base_path / path.lstrip('/')
        
        try:
            full_path.unlink()
        except FileNotFoundError:
            raise asyncssh.SFTPError(asyncssh.FX_NO_SUCH_FILE, "File not found")
        except OSError as e:
            raise asyncssh.SFTPError(asyncssh.FX_FAILURE, str(e))
    
    async def rmdir(self, path):
        """Remove directory"""
        full_path = self.base_path / path.lstrip('/')
        
        try:
            full_path.rmdir()
        except FileNotFoundError:
            raise asyncssh.SFTPError(asyncssh.FX_NO_SUCH_FILE, "Directory not found")
        except OSError as e:
            raise asyncssh.SFTPError(asyncssh.FX_FAILURE, str(e))


class SSHService(LoggerMixin):
    """SSH/SFTP service for MPC server"""
    
    def __init__(self, config: SSHConfig, memory_service, code_service, rag_service):
        self.config = config
        self.memory_service = memory_service
        self.code_service = code_service
        self.rag_service = rag_service
        self.server = None
        self._host_key = None
    
    async def start(self):
        """Start SSH server"""
        if not self.config.enabled:
            self.logger.info("SSH service disabled")
            return
        
        self.logger.info("Starting SSH service")
        
        # Generate or load host key
        await self._setup_host_key()
        
        # Create SSH server
        self.server = await asyncssh.create_server(
            lambda: MPCSSHServer(self.memory_service, self.code_service, self.rag_service),
            host=self.config.host,
            port=self.config.port,
            server_host_keys=[self._host_key],
            process_factory=None,  # Disable process creation
            allow_scp=False,  # Disable SCP for security
            sftp_factory=True,  # Enable SFTP
            agent_forwarding=False,  # Disable agent forwarding
            x11_forwarding=False,  # Disable X11 forwarding
            compression_algs=None  # Disable compression
        )
        
        self.logger.info(f"SSH server started on {self.config.host}:{self.config.port}")
    
    async def stop(self):
        """Stop SSH server"""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            self.logger.info("SSH server stopped")
    
    async def _setup_host_key(self):
        """Setup SSH host key"""
        host_key_path = Path(self.config.host_key_path)
        
        if host_key_path.exists():
            # Load existing key
            self._host_key = asyncssh.read_private_key(str(host_key_path))
            self.logger.info("Loaded existing SSH host key")
        else:
            # Generate new key
            self.logger.info("Generating new SSH host key")
            self._host_key = asyncssh.generate_private_key('ssh-rsa', key_size=2048)
            
            # Save key
            host_key_path.parent.mkdir(parents=True, exist_ok=True)
            with open(host_key_path, 'wb') as f:
                f.write(self._host_key.export_private_key())
            
            # Set secure permissions
            os.chmod(host_key_path, 0o600)
            
            self.logger.info(f"Generated and saved SSH host key to {host_key_path}")
