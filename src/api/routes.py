"""
API routes for PerfectMPC server
"""

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import logging

# Import service dependencies (will be injected)
# These will be imported dynamically to avoid circular imports
MemoryService = None
CodeImprovementService = None
RAGService = None
Context7Service = None
PlaywrightService = None
SequentialThinkingService = None

logger = logging.getLogger(__name__)

# Create main router
api_router = APIRouter()

# Pydantic models for request/response
class SessionRequest(BaseModel):
    session_id: str

class ContextRequest(BaseModel):
    session_id: str
    context: str
    metadata: Optional[Dict[str, Any]] = None

class CodeAnalysisRequest(BaseModel):
    session_id: str
    code: str
    language: str
    file_path: Optional[str] = None

class DocumentSearchRequest(BaseModel):
    session_id: str
    query: str
    max_results: Optional[int] = 10

class DocumentUploadRequest(BaseModel):
    session_id: str
    title: str
    content: str
    doc_type: str = "text"
    metadata: Optional[Dict[str, Any]] = None

# Context7 Service Models
class ContextAddRequest(BaseModel):
    session_id: str
    content: str
    layer: int  # ContextLayer enum value
    priority: int = 2  # ContextPriority enum value
    metadata: Optional[Dict[str, Any]] = None

class ContextMergeRequest(BaseModel):
    session_id: str
    context_ids: List[str]
    target_layer: int

class ContextSwitchRequest(BaseModel):
    session_id: str
    new_context_id: str
    preserve_immediate: bool = True

# Playwright Service Models
class BrowserSessionRequest(BaseModel):
    session_id: str
    browser_type: str = "chromium"
    headless: bool = True
    viewport: Optional[Dict[str, int]] = None

class NavigateRequest(BaseModel):
    session_id: str
    url: str
    wait_until: str = "load"

class ClickRequest(BaseModel):
    session_id: str
    selector: str
    timeout: int = 30000

class TypeRequest(BaseModel):
    session_id: str
    selector: str
    text: str
    delay: int = 0

class ScreenshotRequest(BaseModel):
    session_id: str
    full_page: bool = False

class ExtractTextRequest(BaseModel):
    session_id: str
    selector: str = "body"

class JavaScriptRequest(BaseModel):
    session_id: str
    script: str

class WaitForElementRequest(BaseModel):
    session_id: str
    selector: str
    timeout: int = 30000

# Sequential Thinking Service Models
class ThinkingChainRequest(BaseModel):
    session_id: str
    problem: str
    reasoning_type: str = "systematic"
    context: Optional[Dict[str, Any]] = None

class ThinkingStepRequest(BaseModel):
    chain_id: str
    step_type: str
    content: str
    confidence: float = 0.5
    dependencies: Optional[List[str]] = None
    evidence: Optional[Dict[str, Any]] = None

class ValidateStepRequest(BaseModel):
    chain_id: str
    step_id: str
    validation_result: bool
    validation_notes: Optional[str] = None

class BranchThinkingRequest(BaseModel):
    chain_id: str
    step_id: str
    alternative_content: str
    reasoning_type: Optional[str] = None

class CompareChainsRequest(BaseModel):
    chain_ids: List[str]

# Dependency injection placeholders
# These will be set by the main application
memory_service: Optional[MemoryService] = None
code_improvement_service: Optional[CodeImprovementService] = None
rag_service: Optional[RAGService] = None
context7_service: Optional[Context7Service] = None
playwright_service: Optional[PlaywrightService] = None
sequential_thinking_service: Optional[SequentialThinkingService] = None

def get_memory_service() -> MemoryService:
    if memory_service is None:
        raise HTTPException(status_code=503, detail="Memory service not available")
    return memory_service

def get_code_improvement_service() -> CodeImprovementService:
    if code_improvement_service is None:
        raise HTTPException(status_code=503, detail="Code improvement service not available")
    return code_improvement_service

def get_rag_service() -> RAGService:
    if rag_service is None:
        raise HTTPException(status_code=503, detail="RAG service not available")
    return rag_service

def get_context7_service() -> Context7Service:
    if context7_service is None:
        raise HTTPException(status_code=503, detail="Context7 service not available")
    return context7_service

def get_playwright_service() -> PlaywrightService:
    if playwright_service is None:
        raise HTTPException(status_code=503, detail="Playwright service not available")
    return playwright_service

def get_sequential_thinking_service() -> SequentialThinkingService:
    if sequential_thinking_service is None:
        raise HTTPException(status_code=503, detail="Sequential Thinking service not available")
    return sequential_thinking_service

# Memory Service Routes
@api_router.post("/memory/session")
async def create_session(
    request: SessionRequest,
    service: MemoryService = Depends(get_memory_service)
):
    """Create a new memory session"""
    try:
        session_id = await service.create_session(request.session_id)
        return {"session_id": session_id, "status": "created"}
    except Exception as e:
        logger.error(f"Failed to create session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/memory/session/{session_id}")
async def get_session(
    session_id: str,
    service: MemoryService = Depends(get_memory_service)
):
    """Get session information"""
    try:
        session_data = await service.get_session(session_id)
        if not session_data:
            raise HTTPException(status_code=404, detail="Session not found")
        return session_data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/memory/context")
async def update_context(
    request: ContextRequest,
    service: MemoryService = Depends(get_memory_service)
):
    """Update session context"""
    try:
        await service.update_context(request.session_id, request.context, request.metadata)
        return {"status": "updated"}
    except Exception as e:
        logger.error(f"Failed to update context: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/memory/context/{session_id}")
async def get_context(
    session_id: str,
    service: MemoryService = Depends(get_memory_service)
):
    """Get current session context"""
    try:
        context = await service.get_context(session_id)
        if context is None:
            raise HTTPException(status_code=404, detail="Context not found")
        return {"session_id": session_id, "context": context}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get context: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/memory/history/{session_id}")
async def get_history(
    session_id: str,
    limit: int = 50,
    service: MemoryService = Depends(get_memory_service)
):
    """Get session history"""
    try:
        history = await service.get_history(session_id, limit)
        return {"session_id": session_id, "history": history}
    except Exception as e:
        logger.error(f"Failed to get history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.delete("/memory/session/{session_id}")
async def delete_session(
    session_id: str,
    service: MemoryService = Depends(get_memory_service)
):
    """Delete a session"""
    try:
        success = await service.delete_session(session_id)
        if not success:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"status": "deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Code Improvement Service Routes
@api_router.post("/code/analyze")
async def analyze_code(
    request: CodeAnalysisRequest,
    service: CodeImprovementService = Depends(get_code_improvement_service)
):
    """Analyze code for improvements"""
    try:
        analysis = await service.analyze_code(
            request.session_id,
            request.code,
            request.language,
            request.file_path
        )
        return analysis
    except Exception as e:
        logger.error(f"Failed to analyze code: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/code/suggest")
async def suggest_improvements(
    request: CodeAnalysisRequest,
    service: CodeImprovementService = Depends(get_code_improvement_service)
):
    """Get improvement suggestions for code"""
    try:
        suggestions = await service.suggest_improvements(
            request.session_id,
            request.code,
            request.language,
            request.file_path
        )
        return suggestions
    except Exception as e:
        logger.error(f"Failed to get suggestions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/code/metrics/{session_id}")
async def get_code_metrics(
    session_id: str,
    service: CodeImprovementService = Depends(get_code_improvement_service)
):
    """Get code quality metrics for session"""
    try:
        metrics = await service.get_metrics(session_id)
        return {"session_id": session_id, "metrics": metrics}
    except Exception as e:
        logger.error(f"Failed to get metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/code/history/{session_id}")
async def get_code_history(
    session_id: str,
    limit: int = 20,
    service: CodeImprovementService = Depends(get_code_improvement_service)
):
    """Get code improvement history"""
    try:
        history = await service.get_improvement_history(session_id, limit)
        return {"session_id": session_id, "history": history}
    except Exception as e:
        logger.error(f"Failed to get code history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# RAG/Documentation Service Routes
@api_router.post("/docs/search")
async def search_documents(
    request: DocumentSearchRequest,
    service: RAGService = Depends(get_rag_service)
):
    """Search documents using RAG"""
    try:
        results = await service.search_documents(
            request.session_id,
            request.query,
            request.max_results
        )
        return {"query": request.query, "results": results}
    except Exception as e:
        logger.error(f"Failed to search documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/docs/upload")
async def upload_document(
    request: DocumentUploadRequest,
    service: RAGService = Depends(get_rag_service)
):
    """Upload and index a document"""
    try:
        doc_id = await service.add_document(
            request.session_id,
            request.title,
            request.content,
            request.doc_type,
            request.metadata
        )
        return {"doc_id": doc_id, "status": "uploaded"}
    except Exception as e:
        logger.error(f"Failed to upload document: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/docs/upload-file")
async def upload_document_file(
    session_id: str,
    file: UploadFile = File(...),
    service: RAGService = Depends(get_rag_service)
):
    """Upload a document file"""
    try:
        content = await file.read()
        doc_id = await service.process_file(
            session_id,
            file.filename,
            content,
            file.content_type
        )
        return {"doc_id": doc_id, "filename": file.filename, "status": "uploaded"}
    except Exception as e:
        logger.error(f"Failed to upload file: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/docs/generate")
async def generate_documentation(
    request: CodeAnalysisRequest,
    service: RAGService = Depends(get_rag_service)
):
    """Generate documentation for code"""
    try:
        documentation = await service.generate_documentation(
            request.session_id,
            request.code,
            request.language,
            request.file_path
        )
        return documentation
    except Exception as e:
        logger.error(f"Failed to generate documentation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/docs/index/{session_id}")
async def get_document_index(
    session_id: str,
    service: RAGService = Depends(get_rag_service)
):
    """Get document index for session"""
    try:
        index = await service.get_document_index(session_id)
        return {"session_id": session_id, "documents": index}
    except Exception as e:
        logger.error(f"Failed to get document index: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.delete("/docs/{doc_id}")
async def delete_document(
    doc_id: str,
    service: RAGService = Depends(get_rag_service)
):
    """Delete a document"""
    try:
        success = await service.delete_document(doc_id)
        if not success:
            raise HTTPException(status_code=404, detail="Document not found")
        return {"status": "deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete document: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Context7 Service Routes
@api_router.post("/context7/add")
async def add_context(
    request: ContextAddRequest,
    service: Context7Service = Depends(get_context7_service)
):
    """Add context to a specific layer"""
    try:
        from services.context7_service import ContextLayer, ContextPriority

        context_id = await service.add_context(
            session_id=request.session_id,
            content=request.content,
            layer=ContextLayer(request.layer),
            priority=ContextPriority(request.priority),
            metadata=request.metadata
        )
        return {"context_id": context_id, "status": "added"}
    except Exception as e:
        logger.error(f"Failed to add context: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/context7/layered/{session_id}")
async def get_layered_context(
    session_id: str,
    max_tokens: int = 4000,
    include_layers: Optional[str] = None,
    service: Context7Service = Depends(get_context7_service)
):
    """Get layered context for a session"""
    try:
        from services.context7_service import ContextLayer

        layers = None
        if include_layers:
            layer_nums = [int(x) for x in include_layers.split(",")]
            layers = [ContextLayer(num) for num in layer_nums]

        context = await service.get_layered_context(
            session_id=session_id,
            max_tokens=max_tokens,
            include_layers=layers
        )
        return context
    except Exception as e:
        logger.error(f"Failed to get layered context: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/context7/merge")
async def merge_contexts(
    request: ContextMergeRequest,
    service: Context7Service = Depends(get_context7_service)
):
    """Merge multiple contexts"""
    try:
        from services.context7_service import ContextLayer

        merged_id = await service.merge_contexts(
            session_id=request.session_id,
            context_ids=request.context_ids,
            target_layer=ContextLayer(request.target_layer)
        )
        return {"merged_context_id": merged_id, "status": "merged"}
    except Exception as e:
        logger.error(f"Failed to merge contexts: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/context7/switch")
async def switch_context(
    request: ContextSwitchRequest,
    service: Context7Service = Depends(get_context7_service)
):
    """Switch to a different context"""
    try:
        result = await service.switch_context(
            session_id=request.session_id,
            new_context_id=request.new_context_id,
            preserve_immediate=request.preserve_immediate
        )
        return result
    except Exception as e:
        logger.error(f"Failed to switch context: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/context7/patterns/{session_id}")
async def analyze_context_patterns(
    session_id: str,
    service: Context7Service = Depends(get_context7_service)
):
    """Analyze context patterns for a session"""
    try:
        patterns = await service.analyze_context_patterns(session_id)
        return patterns
    except Exception as e:
        logger.error(f"Failed to analyze context patterns: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Playwright Service Routes
@api_router.post("/playwright/session")
async def create_browser_session(
    request: BrowserSessionRequest,
    service: PlaywrightService = Depends(get_playwright_service)
):
    """Create a new browser session"""
    try:
        from services.playwright_service import BrowserType

        browser_id = await service.create_browser_session(
            session_id=request.session_id,
            browser_type=BrowserType(request.browser_type),
            headless=request.headless,
            viewport=request.viewport
        )
        return {"browser_id": browser_id, "status": "created"}
    except Exception as e:
        logger.error(f"Failed to create browser session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/playwright/navigate")
async def navigate_browser(
    request: NavigateRequest,
    service: PlaywrightService = Depends(get_playwright_service)
):
    """Navigate to a URL"""
    try:
        result = await service.navigate(
            session_id=request.session_id,
            url=request.url,
            wait_until=request.wait_until
        )
        return result
    except Exception as e:
        logger.error(f"Failed to navigate: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/playwright/click")
async def click_element(
    request: ClickRequest,
    service: PlaywrightService = Depends(get_playwright_service)
):
    """Click an element"""
    try:
        result = await service.click_element(
            session_id=request.session_id,
            selector=request.selector,
            timeout=request.timeout
        )
        return result
    except Exception as e:
        logger.error(f"Failed to click element: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/playwright/type")
async def type_text(
    request: TypeRequest,
    service: PlaywrightService = Depends(get_playwright_service)
):
    """Type text into an element"""
    try:
        result = await service.type_text(
            session_id=request.session_id,
            selector=request.selector,
            text=request.text,
            delay=request.delay
        )
        return result
    except Exception as e:
        logger.error(f"Failed to type text: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/playwright/screenshot")
async def take_screenshot(
    request: ScreenshotRequest,
    service: PlaywrightService = Depends(get_playwright_service)
):
    """Take a screenshot"""
    try:
        result = await service.take_screenshot(
            session_id=request.session_id,
            full_page=request.full_page
        )
        return result
    except Exception as e:
        logger.error(f"Failed to take screenshot: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/playwright/extract-text")
async def extract_text(
    request: ExtractTextRequest,
    service: PlaywrightService = Depends(get_playwright_service)
):
    """Extract text from page or element"""
    try:
        result = await service.extract_text(
            session_id=request.session_id,
            selector=request.selector
        )
        return result
    except Exception as e:
        logger.error(f"Failed to extract text: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/playwright/links/{session_id}")
async def extract_links(
    session_id: str,
    service: PlaywrightService = Depends(get_playwright_service)
):
    """Extract all links from the page"""
    try:
        result = await service.extract_links(session_id)
        return result
    except Exception as e:
        logger.error(f"Failed to extract links: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/playwright/javascript")
async def evaluate_javascript(
    request: JavaScriptRequest,
    service: PlaywrightService = Depends(get_playwright_service)
):
    """Evaluate JavaScript on the page"""
    try:
        result = await service.evaluate_javascript(
            session_id=request.session_id,
            script=request.script
        )
        return result
    except Exception as e:
        logger.error(f"Failed to evaluate JavaScript: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/playwright/wait-element")
async def wait_for_element(
    request: WaitForElementRequest,
    service: PlaywrightService = Depends(get_playwright_service)
):
    """Wait for an element to appear"""
    try:
        result = await service.wait_for_element(
            session_id=request.session_id,
            selector=request.selector,
            timeout=request.timeout
        )
        return result
    except Exception as e:
        logger.error(f"Failed to wait for element: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/playwright/session/{session_id}")
async def get_session_info(
    session_id: str,
    service: PlaywrightService = Depends(get_playwright_service)
):
    """Get browser session information"""
    try:
        info = await service.get_session_info(session_id)
        return info
    except Exception as e:
        logger.error(f"Failed to get session info: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.delete("/playwright/session/{session_id}")
async def close_browser_session(
    session_id: str,
    service: PlaywrightService = Depends(get_playwright_service)
):
    """Close a browser session"""
    try:
        result = await service.close_session(session_id)
        return result
    except Exception as e:
        logger.error(f"Failed to close session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Sequential Thinking Service Routes
@api_router.post("/thinking/chain")
async def start_thinking_chain(
    request: ThinkingChainRequest,
    service: SequentialThinkingService = Depends(get_sequential_thinking_service)
):
    """Start a new thinking chain"""
    try:
        from services.sequential_thinking_service import ReasoningType

        chain_id = await service.start_thinking_chain(
            session_id=request.session_id,
            problem=request.problem,
            reasoning_type=ReasoningType(request.reasoning_type),
            context=request.context
        )
        return {"chain_id": chain_id, "status": "started"}
    except Exception as e:
        logger.error(f"Failed to start thinking chain: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/thinking/step")
async def add_thinking_step(
    request: ThinkingStepRequest,
    service: SequentialThinkingService = Depends(get_sequential_thinking_service)
):
    """Add a step to a thinking chain"""
    try:
        from services.sequential_thinking_service import ThinkingStep, ConfidenceLevel

        step_id = await service.add_thinking_step(
            chain_id=request.chain_id,
            step_type=ThinkingStep(request.step_type),
            content=request.content,
            confidence=ConfidenceLevel(request.confidence),
            dependencies=request.dependencies,
            evidence=request.evidence
        )
        return {"step_id": step_id, "status": "added"}
    except Exception as e:
        logger.error(f"Failed to add thinking step: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/thinking/validate")
async def validate_thinking_step(
    request: ValidateStepRequest,
    service: SequentialThinkingService = Depends(get_sequential_thinking_service)
):
    """Validate a thinking step"""
    try:
        result = await service.validate_step(
            chain_id=request.chain_id,
            step_id=request.step_id,
            validation_result=request.validation_result,
            validation_notes=request.validation_notes
        )
        return result
    except Exception as e:
        logger.error(f"Failed to validate step: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/thinking/synthesize/{chain_id}")
async def synthesize_solution(
    chain_id: str,
    service: SequentialThinkingService = Depends(get_sequential_thinking_service)
):
    """Synthesize a solution from thinking chain"""
    try:
        solution = await service.synthesize_solution(chain_id)
        return solution
    except Exception as e:
        logger.error(f"Failed to synthesize solution: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/thinking/branch")
async def branch_thinking(
    request: BranchThinkingRequest,
    service: SequentialThinkingService = Depends(get_sequential_thinking_service)
):
    """Create a branch in thinking"""
    try:
        from services.sequential_thinking_service import ReasoningType

        reasoning_type = None
        if request.reasoning_type:
            reasoning_type = ReasoningType(request.reasoning_type)

        branch_id = await service.branch_thinking(
            chain_id=request.chain_id,
            step_id=request.step_id,
            alternative_content=request.alternative_content,
            reasoning_type=reasoning_type
        )
        return {"branch_chain_id": branch_id, "status": "branched"}
    except Exception as e:
        logger.error(f"Failed to branch thinking: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/thinking/compare")
async def compare_thinking_chains(
    request: CompareChainsRequest,
    service: SequentialThinkingService = Depends(get_sequential_thinking_service)
):
    """Compare multiple thinking chains"""
    try:
        comparison = await service.compare_chains(request.chain_ids)
        return comparison
    except Exception as e:
        logger.error(f"Failed to compare chains: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/thinking/patterns/{session_id}")
async def get_thinking_patterns(
    session_id: str,
    service: SequentialThinkingService = Depends(get_sequential_thinking_service)
):
    """Get thinking patterns for a session"""
    try:
        patterns = await service.get_thinking_patterns(session_id)
        return patterns
    except Exception as e:
        logger.error(f"Failed to get thinking patterns: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Utility function to set service dependencies
def set_services(memory_svc, code_svc, rag_svc, context7_svc=None, playwright_svc=None, sequential_svc=None):
    """Set service dependencies for the API routes"""
    global memory_service, code_improvement_service, rag_service
    global context7_service, playwright_service, sequential_thinking_service
    memory_service = memory_svc
    code_improvement_service = code_svc
    rag_service = rag_svc
    context7_service = context7_svc
    playwright_service = playwright_svc
    sequential_thinking_service = sequential_svc
