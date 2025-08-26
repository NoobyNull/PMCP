"""
RAG (Retrieval-Augmented Generation) Service for PerfectMCP
Handles document indexing, search, and documentation generation
"""

import asyncio
import hashlib
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

import chromadb
from sentence_transformers import SentenceTransformer
import numpy as np

from utils.database import DatabaseManager
from utils.config import RAGConfig
from utils.logger import (
    EnhancedLoggerMixin, log_context, log_performance,
    log_function_call, log_async_function_call,
    log_database_operation
)


class RAGService(EnhancedLoggerMixin):
    """Enhanced RAG service with comprehensive logging for document retrieval and generation"""
    
    def __init__(self, db_manager: DatabaseManager, config: RAGConfig):
        self.db = db_manager
        self.config = config
        self.embedding_model = None
        self.chroma_client = None
        self.document_collection = None
        self.code_collection = None
        
    @log_async_function_call(level='INFO', performance=True)
    async def initialize(self):
        """Initialize the RAG service with comprehensive logging"""
        with log_context(operation="rag_initialization"):
            self.logger.info("Initializing RAG Service",
                           embedding_model=self.config.vector_db.embedding_model)

            # Initialize embedding model
            with log_performance("embedding_model_init", "rag_service"):
                await self._init_embedding_model()

            # Initialize ChromaDB
            with log_performance("chromadb_init", "rag_service"):
                await self._init_chromadb()

            self.logger.info("RAG Service initialized successfully")
    
    @log_async_function_call(level='DEBUG', performance=True)
    async def _init_embedding_model(self):
        """Initialize the sentence transformer model with logging"""
        model_name = self.config.vector_db.embedding_model

        with log_context(embedding_model=model_name):
            try:
                self.logger.debug(f"Loading embedding model", model=model_name)

                # Load model (this can be slow on first run)
                self.embedding_model = SentenceTransformer(model_name)

                # Get model info
                model_info = {
                    "model_name": model_name,
                    "max_seq_length": getattr(self.embedding_model, 'max_seq_length', 'unknown'),
                    "device": str(self.embedding_model.device) if hasattr(self.embedding_model, 'device') else 'unknown'
                }

                self.logger.info(f"Embedding model loaded successfully", **model_info)

            except Exception as e:
                self.log_error(f"Failed to load embedding model", e, model=model_name)
                raise
    
    async def _init_chromadb(self):
        """Initialize ChromaDB client and collections"""
        try:
            # Create persist directory if it doesn't exist
            persist_dir = Path("/opt/PerfectMPC/data/chromadb")
            persist_dir.mkdir(parents=True, exist_ok=True)
            
            # Initialize ChromaDB client
            self.chroma_client = chromadb.PersistentClient(path=str(persist_dir))
            
            # Get or create collections
            self.document_collection = self.chroma_client.get_or_create_collection(
                name="mpc_documents",
                metadata={"description": "Document embeddings for MPC server"}
            )
            
            self.code_collection = self.chroma_client.get_or_create_collection(
                name="mpc_code",
                metadata={"description": "Code embeddings for MPC server"}
            )
            
            self.logger.info("ChromaDB collections initialized")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize ChromaDB: {e}")
            raise
    
    async def add_document(self, session_id: str, title: str, content: str, 
                          doc_type: str = "text", metadata: Optional[Dict] = None) -> str:
        """Add a document to the knowledge base"""
        doc_id = str(uuid.uuid4())
        
        # Validate document size
        if len(content.encode('utf-8')) > self.config.documents.max_file_size:
            raise ValueError("Document too large")
        
        # Chunk the document
        chunks = await self._chunk_document(content)
        
        # Generate embeddings for chunks
        embeddings = await self._generate_embeddings(chunks)
        
        # Prepare metadata
        doc_metadata = {
            "session_id": session_id,
            "title": title,
            "doc_type": doc_type,
            "timestamp": datetime.utcnow().isoformat(),
            "chunk_count": len(chunks),
            **(metadata or {})
        }
        
        # Store in ChromaDB
        chunk_ids = []
        chunk_metadatas = []
        
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            chunk_id = f"{doc_id}_{i}"
            chunk_ids.append(chunk_id)
            
            chunk_metadata = {
                **doc_metadata,
                "doc_id": doc_id,
                "chunk_id": i,
                "chunk_text": chunk[:100] + "..." if len(chunk) > 100 else chunk
            }
            chunk_metadatas.append(chunk_metadata)
        
        # Add to ChromaDB
        self.document_collection.add(
            ids=chunk_ids,
            embeddings=embeddings.tolist(),
            documents=chunks,
            metadatas=chunk_metadatas
        )
        
        # Store document metadata in MongoDB
        document_record = {
            "doc_id": doc_id,
            "session_id": session_id,
            "title": title,
            "doc_type": doc_type,
            "content_hash": hashlib.sha256(content.encode()).hexdigest(),
            "metadata": doc_metadata,
            "created_at": datetime.utcnow().isoformat(),
            "chunk_count": len(chunks)
        }
        
        collection = self.db.get_collection_name("documents")
        await self.db.mongo_insert_one(collection, document_record)
        
        self.logger.info(f"Added document {doc_id} with {len(chunks)} chunks")
        return doc_id
    
    async def search_documents(self, session_id: str, query: str,
                              max_results: int = None) -> List[Dict[str, Any]]:
        """Search documents using semantic similarity"""
        if max_results is None:
            max_results = self.config.search.max_results

        # Generate query embedding
        query_embedding = await self._generate_embeddings([query])

        # Search in ChromaDB
        results = self.document_collection.query(
            query_embeddings=query_embedding.tolist(),
            n_results=max_results,
            where={"session_id": session_id} if session_id else None
        )

        # Format results
        search_results = []
        for i in range(len(results['ids'][0])):
            result = {
                "doc_id": results['metadatas'][0][i]['doc_id'],
                "chunk_id": results['metadatas'][0][i]['chunk_id'],
                "title": results['metadatas'][0][i]['title'],
                "content": results['documents'][0][i],
                "similarity": 1 - results['distances'][0][i],  # Convert distance to similarity
                "metadata": results['metadatas'][0][i]
            }

            # Filter by similarity threshold
            if result["similarity"] >= self.config.search.similarity_threshold:
                search_results.append(result)

        self.logger.debug(f"Found {len(search_results)} relevant documents for query")
        return search_results

    async def search_all_documents(self, query: str, max_results: int = None) -> List[Dict[str, Any]]:
        """Search documents across all sessions using semantic similarity"""
        if max_results is None:
            max_results = self.config.search.max_results

        # Generate query embedding
        query_embedding = await self._generate_embeddings([query])

        # Search in ChromaDB without session filter
        results = self.document_collection.query(
            query_embeddings=query_embedding.tolist(),
            n_results=max_results,
            where=None  # Search across all sessions
        )

        # Format results
        search_results = []
        for i in range(len(results['ids'][0])):
            result = {
                "doc_id": results['metadatas'][0][i]['doc_id'],
                "chunk_id": results['metadatas'][0][i]['chunk_id'],
                "title": results['metadatas'][0][i]['title'],
                "content": results['documents'][0][i],
                "similarity": 1 - results['distances'][0][i],  # Convert distance to similarity
                "metadata": results['metadatas'][0][i],
                "session_id": results['metadatas'][0][i].get('session_id', 'unknown')
            }

            # Filter by similarity threshold
            if result["similarity"] >= self.config.search.similarity_threshold:
                search_results.append(result)

        self.logger.debug(f"Found {len(search_results)} relevant documents across all sessions for query")
        return search_results
    
    async def generate_documentation(self, session_id: str, code: str, 
                                   language: str, file_path: Optional[str] = None) -> Dict[str, Any]:
        """Generate documentation for code"""
        # First, search for similar code patterns
        similar_docs = await self.search_documents(session_id, f"{language} code documentation")
        
        # Generate basic documentation structure
        doc_structure = await self._analyze_code_structure(code, language)
        
        # Create documentation content
        documentation = {
            "session_id": session_id,
            "file_path": file_path,
            "language": language,
            "timestamp": datetime.utcnow().isoformat(),
            "structure": doc_structure,
            "generated_docs": await self._generate_doc_content(code, language, doc_structure),
            "similar_examples": similar_docs[:3],  # Top 3 similar examples
            "suggestions": await self._generate_doc_suggestions(code, language)
        }
        
        # Store generated documentation
        await self._store_generated_docs(session_id, documentation)
        
        return documentation
    
    async def process_file(self, session_id: str, filename: str, 
                          content: bytes, content_type: str) -> str:
        """Process uploaded file and add to knowledge base"""
        # Determine file type and extract text
        text_content = await self._extract_text_from_file(content, content_type, filename)
        
        # Determine document type
        doc_type = self._determine_doc_type(filename, content_type)
        
        # Add to knowledge base
        return await self.add_document(
            session_id=session_id,
            title=filename,
            content=text_content,
            doc_type=doc_type,
            metadata={
                "filename": filename,
                "content_type": content_type,
                "file_size": len(content)
            }
        )
    
    async def get_document_index(self, session_id: str) -> List[Dict[str, Any]]:
        """Get index of documents for a session"""
        collection = self.db.get_collection_name("documents")
        documents = await self.db.mongo_find_many(
            collection,
            {"session_id": session_id},
            sort=[("created_at", -1)]
        )

        return documents

    async def get_all_documents(self) -> List[Dict[str, Any]]:
        """Get all documents across all sessions"""
        try:
            collection = self.db.get_collection_name("documents")
            documents = await self.db.mongo_find_many(
                collection,
                {},  # No filter - get all documents
                limit=1000,  # Reasonable limit
                sort=[("created_at", -1)]
            )

            self.logger.debug(f"Retrieved {len(documents)} documents from RAG service")
            return documents

        except Exception as e:
            self.logger.error(f"Failed to get all documents: {e}")
            return []
    
    async def delete_document(self, doc_id: str) -> bool:
        """Delete a document from the knowledge base"""
        try:
            # Get document info
            collection = self.db.get_collection_name("documents")
            doc_info = await self.db.mongo_find_one(collection, {"doc_id": doc_id})

            if not doc_info:
                return False

            # Delete from ChromaDB
            chunk_count = doc_info.get("chunk_count", 0)
            chunk_ids = [f"{doc_id}_{i}" for i in range(chunk_count)]

            try:
                self.document_collection.delete(ids=chunk_ids)
            except Exception as e:
                self.logger.warning(f"Failed to delete from ChromaDB: {e}")

            # Delete from MongoDB
            success = await self.db.mongo_delete_one(collection, {"doc_id": doc_id})

            self.logger.info(f"Deleted document {doc_id}")
            return success

        except Exception as e:
            self.logger.error(f"Failed to delete document {doc_id}: {e}")
            return False

    async def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get document details by ID"""
        try:
            # Get document metadata from MongoDB
            collection = self.db.get_collection_name("documents")
            doc_info = await self.db.mongo_find_one(collection, {"doc_id": doc_id})

            if not doc_info:
                return None

            # Get document chunks from ChromaDB
            chunk_count = doc_info.get("chunk_count", 0)
            chunk_ids = [f"{doc_id}_{i}" for i in range(chunk_count)]

            try:
                chunks_result = self.document_collection.get(ids=chunk_ids)
                chunks = chunks_result.get("documents", [])
                full_content = "\n\n".join(chunks) if chunks else ""
            except Exception as e:
                self.logger.warning(f"Failed to get chunks from ChromaDB: {e}")
                full_content = "Content not available"

            # Combine metadata and content
            document = {
                **doc_info,
                "content": full_content,
                "content_preview": full_content[:500] + "..." if len(full_content) > 500 else full_content
            }

            return document

        except Exception as e:
            self.logger.error(f"Failed to get document {doc_id}: {e}")
            return None

    async def reindex_document(self, doc_id: str) -> bool:
        """Reindex a document (delete and re-add with same content)"""
        try:
            # Get document info
            document = await self.get_document(doc_id)
            if not document:
                return False

            # Store original content and metadata
            content = document.get("content", "")
            session_id = document.get("session_id", "")
            title = document.get("title", "")
            doc_type = document.get("doc_type", "text")
            metadata = document.get("metadata", {})

            # Delete existing document
            await self.delete_document(doc_id)

            # Re-add with same doc_id
            await self._add_document_with_id(
                doc_id=doc_id,
                session_id=session_id,
                title=title,
                content=content,
                doc_type=doc_type,
                metadata=metadata
            )

            self.logger.info(f"Reindexed document {doc_id}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to reindex document {doc_id}: {e}")
            return False

    async def _add_document_with_id(self, doc_id: str, session_id: str, title: str,
                                   content: str, doc_type: str = "text",
                                   metadata: Optional[Dict] = None) -> str:
        """Add a document with a specific ID (for reindexing)"""
        # Validate document size
        if len(content.encode('utf-8')) > self.config.documents.max_file_size:
            raise ValueError("Document too large")

        # Chunk the document
        chunks = await self._chunk_document(content)

        # Generate embeddings for chunks
        embeddings = await self._generate_embeddings(chunks)

        # Prepare metadata
        doc_metadata = {
            "session_id": session_id,
            "title": title,
            "doc_type": doc_type,
            "timestamp": datetime.utcnow().isoformat(),
            "chunk_count": len(chunks),
            **(metadata or {})
        }

        # Store in ChromaDB
        chunk_ids = []
        chunk_metadatas = []

        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            chunk_id = f"{doc_id}_{i}"
            chunk_ids.append(chunk_id)

            chunk_metadata = {
                **doc_metadata,
                "doc_id": doc_id,
                "chunk_id": i,
                "chunk_text": chunk[:100] + "..." if len(chunk) > 100 else chunk
            }
            chunk_metadatas.append(chunk_metadata)

        # Add to ChromaDB
        self.document_collection.add(
            ids=chunk_ids,
            embeddings=embeddings.tolist(),
            documents=chunks,
            metadatas=chunk_metadatas
        )

        # Store document metadata in MongoDB
        document_record = {
            "doc_id": doc_id,
            "session_id": session_id,
            "title": title,
            "doc_type": doc_type,
            "content_hash": hashlib.sha256(content.encode()).hexdigest(),
            "metadata": doc_metadata,
            "created_at": datetime.utcnow().isoformat(),
            "chunk_count": len(chunks)
        }

        collection = self.db.get_collection_name("documents")
        await self.db.mongo_insert_one(collection, document_record)

        self.logger.info(f"Re-added document {doc_id} with {len(chunks)} chunks")
        return doc_id
    
    async def _chunk_document(self, content: str) -> List[str]:
        """Split document into chunks for embedding"""
        chunk_size = self.config.documents.chunk_size
        chunk_overlap = self.config.documents.chunk_overlap
        
        # Simple chunking by sentences/paragraphs
        paragraphs = content.split('\n\n')
        chunks = []
        current_chunk = ""
        
        for paragraph in paragraphs:
            if len(current_chunk) + len(paragraph) <= chunk_size:
                current_chunk += paragraph + "\n\n"
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = paragraph + "\n\n"
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        # Handle overlap
        if chunk_overlap > 0 and len(chunks) > 1:
            overlapped_chunks = []
            for i, chunk in enumerate(chunks):
                if i > 0:
                    # Add overlap from previous chunk
                    prev_chunk = chunks[i-1]
                    overlap_text = prev_chunk[-chunk_overlap:] if len(prev_chunk) > chunk_overlap else prev_chunk
                    chunk = overlap_text + "\n" + chunk
                overlapped_chunks.append(chunk)
            chunks = overlapped_chunks
        
        return chunks
    
    async def _generate_embeddings(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for text chunks"""
        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(
            None, 
            self.embedding_model.encode, 
            texts
        )
        return embeddings
    
    async def _extract_text_from_file(self, content: bytes, content_type: str, filename: str) -> str:
        """Extract text content from various file types"""
        try:
            if content_type.startswith('text/') or filename.endswith(('.txt', '.md', '.py', '.js', '.html', '.css')):
                return content.decode('utf-8')
            elif filename.endswith('.pdf'):
                # Would use PyPDF2 or similar
                return "PDF content extraction not implemented"
            elif filename.endswith(('.doc', '.docx')):
                # Would use python-docx
                return "Word document extraction not implemented"
            else:
                # Try to decode as text
                return content.decode('utf-8', errors='ignore')
        except Exception as e:
            self.logger.error(f"Failed to extract text from file: {e}")
            return f"Error extracting content: {str(e)}"
    
    def _determine_doc_type(self, filename: str, content_type: str) -> str:
        """Determine document type from filename and content type"""
        if filename.endswith(('.py', '.js', '.ts', '.java', '.cpp', '.c', '.go', '.rs')):
            return "code"
        elif filename.endswith(('.md', '.txt')):
            return "documentation"
        elif filename.endswith(('.pdf', '.doc', '.docx')):
            return "document"
        elif content_type.startswith('text/'):
            return "text"
        else:
            return "unknown"
    
    async def _analyze_code_structure(self, code: str, language: str) -> Dict[str, Any]:
        """Analyze code structure for documentation generation"""
        structure = {
            "language": language,
            "functions": [],
            "classes": [],
            "imports": [],
            "complexity": "low"
        }
        
        if language == "python":
            try:
                import ast
                tree = ast.parse(code)
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        structure["functions"].append({
                            "name": node.name,
                            "line": node.lineno,
                            "args": [arg.arg for arg in node.args.args],
                            "docstring": ast.get_docstring(node)
                        })
                    elif isinstance(node, ast.ClassDef):
                        structure["classes"].append({
                            "name": node.name,
                            "line": node.lineno,
                            "docstring": ast.get_docstring(node)
                        })
                    elif isinstance(node, (ast.Import, ast.ImportFrom)):
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                structure["imports"].append(alias.name)
                        else:
                            structure["imports"].append(node.module)
            except Exception as e:
                self.logger.debug(f"Failed to parse Python code: {e}")
        
        return structure
    
    async def _generate_doc_content(self, code: str, language: str, structure: Dict[str, Any]) -> Dict[str, str]:
        """Generate documentation content"""
        docs = {
            "overview": f"This {language} code contains {len(structure['functions'])} functions and {len(structure['classes'])} classes.",
            "functions": {},
            "classes": {},
            "usage_examples": []
        }
        
        # Generate function documentation
        for func in structure["functions"]:
            if not func.get("docstring"):
                docs["functions"][func["name"]] = f"Function {func['name']} with parameters: {', '.join(func['args'])}"
        
        # Generate class documentation
        for cls in structure["classes"]:
            if not cls.get("docstring"):
                docs["classes"][cls["name"]] = f"Class {cls['name']} defined at line {cls['line']}"
        
        return docs
    
    async def _generate_doc_suggestions(self, code: str, language: str) -> List[str]:
        """Generate documentation improvement suggestions"""
        suggestions = []
        
        # Check for missing docstrings
        if language == "python":
            if "def " in code and '"""' not in code and "'''" not in code:
                suggestions.append("Consider adding docstrings to functions and classes")
        
        # Check for complex code
        if len(code.splitlines()) > 50:
            suggestions.append("Consider breaking down large functions into smaller, documented units")
        
        # Check for comments
        comment_chars = {"python": "#", "javascript": "//", "java": "//", "cpp": "//"}
        comment_char = comment_chars.get(language, "#")
        
        if comment_char not in code:
            suggestions.append("Consider adding inline comments to explain complex logic")
        
        return suggestions
    
    async def _store_generated_docs(self, session_id: str, documentation: Dict[str, Any]):
        """Store generated documentation"""
        collection = self.db.get_collection_name("documents")
        doc_record = {
            "session_id": session_id,
            "type": "generated_documentation",
            "content": documentation,
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.db.mongo_insert_one(collection, doc_record)
