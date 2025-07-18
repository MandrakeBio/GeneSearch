from dotenv import load_dotenv
load_dotenv()
#!/usr/bin/env python3
"""
Main FastAPI application for GeneSearch
"""
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import json
app = FastAPI()

@app.get("/healthz")
def health():
    return {"status": "ok"}

import logging
from typing import Dict, Any, List
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agents.Gene_search.worker import GeneSearchAgent
from agents.web_search.worker import WebResearchAgent
from agents.analysis_service import AnalysisService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="GeneSearch API",
    description="Comprehensive gene and trait research platform",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize agents
gene_search_agent = GeneSearchAgent()
web_research_agent = WebResearchAgent()
analysis_service = AnalysisService()

# Simple in-memory chat history storage
# In production, you'd want to use a proper database
chat_histories = {}

import uuid
from datetime import datetime

# =============================================================================
# Request/Response Models
# =============================================================================

class GeneSearchRequest(BaseModel):
    query: str

class WebSearchRequest(BaseModel):
    query: str

class SearchRequest(BaseModel):
    query: str
    include_web: bool = True
    include_gene: bool = True

class AnalysisRequest(BaseModel):
    gene_search_results: Dict[str, Any]
    web_research_results: Dict[str, Any]

class ResearchRequest(BaseModel):
    query: str

class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str
    timestamp: str = None

class ChatRequest(BaseModel):
    message: str
    conversation_id: str = None
    chat_history: List[ChatMessage] = []

class ChatResponse(BaseModel):
    response: str
    conversation_id: str
    chat_history: List[ChatMessage]
    success: bool

class CombinedSearchResult(BaseModel):
    query: str
    tool_results: Dict[str, Any]
    trait_analysis: Dict[str, Any] = None
    search_type: str
    success: bool
    total_execution_time: float

# =============================================================================
# API Endpoints
# =============================================================================

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "GeneSearch API",
        "version": "2.0.0",
        "endpoints": {
            "web_search": "/web-search",
            "gene_search": "/gene-search", 
            "search": "/search",
            "analysis": "/analysis",
            "research": "/research",
            "stream_research": "/stream-research",
            "chat": "/chat"
        }
    }

@app.post("/gene-search")
def gene_search(request: GeneSearchRequest) -> Dict[str, Any]:
    """Perform gene search"""
    try:
        logger.info(f"Gene search request: {request.query}")
        result = gene_search_agent.search(request.query)
        return {
            "success": True,
            "result": result
        }
    except Exception as e:
        logger.error(f"Gene search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/web-search")
async def web_search(request: WebSearchRequest) -> Dict[str, Any]:
    """Perform web search (literature agent only)"""
    try:
        logger.info(f"Web search request: {request.query}")
        result = web_research_agent.search(request.query)
        return {
            "success": True,
            "result": result.model_dump()
        }
    except Exception as e:
        logger.error(f"Web search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/search")
def search(request: SearchRequest) -> CombinedSearchResult:
    """Combined: literature + gene pipeline + analysis"""
    import time
    start_time = time.time()
    
    try:
        logger.info(f"Combined search request: {request.query}")
        
        tool_results = {}
        search_type_parts = []
        
        # Perform web search if requested
        if request.include_web:
            logger.info("Performing web search...")
            web_results = web_research_agent.search(request.query)
            tool_results["web_search"] = web_results.model_dump()
            search_type_parts.append("web")
        
        # Perform gene search if requested
        if request.include_gene:
            logger.info("Performing gene search...")
            gene_results = gene_search_agent.search(request.query)
            tool_results["gene_search"] = gene_results
            search_type_parts.append("gene")
        
        search_type = "+".join(search_type_parts) if search_type_parts else "none"
        total_execution_time = time.time() - start_time
        
        # Create trait analysis summary
        trait_analysis = None
        if request.include_gene and "gene_search" in tool_results:
            gene_data = tool_results["gene_search"]
            trait_analysis = {
                "analysis_markdown": gene_data.get("explanation", ""),
                "top_hits": [gene.get("symbol", gene.get("gene_id", "")) for gene in gene_data.get("genes", [])[:5]],
                "open_questions": [],
                "evidence_map": {}
            }
        
        return CombinedSearchResult(
            query=request.query,
            tool_results=tool_results,
            trait_analysis=trait_analysis,
            search_type=search_type,
            success=True,
            total_execution_time=total_execution_time
        )
        
    except Exception as e:
        logger.error(f"Combined search failed: {e}")
        total_execution_time = time.time() - start_time
        return CombinedSearchResult(
            query=request.query,
            tool_results={},
            trait_analysis=None,
            search_type="error",
            success=False,
            total_execution_time=total_execution_time
        )

@app.post("/analysis")
def analysis(request: AnalysisRequest) -> Dict[str, Any]:
    """Perform analysis of combined results"""
    try:
        logger.info("Analysis request received")
        
        # Convert dict results back to models
        from agents.Gene_search.models import GeneSearchResult
        from agents.web_search.models import WebResearchAgentModel
        
        gene_results = GeneSearchResult(**request.gene_search_results)
        web_results = WebResearchAgentModel(**request.web_research_results)
        
        # Perform analysis
        result = analysis_service.analyze_results(gene_results, web_results)
        
        return {
            "success": True,
            "result": result
        }
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Updated /research endpoint with analysis service
@app.post("/research")
def research(request: ResearchRequest) -> Dict[str, Any]:
    """Research endpoint with comprehensive analysis"""
    try:
        logger.info(f"Research request: {request.query}")
        
        # Perform gene search
        logger.info("Performing gene search...")
        gene_search_results = gene_search_agent.search(request.query)
        
        # Perform web research
        logger.info("Performing web research...")
        web_research_results = web_research_agent.search(request.query)
        
        # Convert dict results to models for analysis
        from agents.Gene_search.models import GeneSearchResult
        from agents.web_search.models import WebResearchAgentModel
        
        # Check if gene_search_results is already a GeneSearchResult object
        if isinstance(gene_search_results, dict):
            # Create GeneSearchResult object from dict
            gene_results = GeneSearchResult(**gene_search_results)
        else:
            # It's already a GeneSearchResult object
            gene_results = gene_search_results
        
        # Use web research results directly
        web_results = web_research_results
        
        # Use analysis service to generate comprehensive analysis
        logger.info("Performing comprehensive analysis...")
        analysis_result = analysis_service.analyze_results(gene_results, web_results)
        
        # Add web research results to the analysis
        web_sources_count = len(web_research_results.research_paper.search_result) if hasattr(web_research_results, 'research_paper') and web_research_results.research_paper else 0
        
        analysis_result["web_research_results"] = {
            "query": web_research_results.query,
            "raw_result": web_research_results.raw_result,
            "research_papers": web_research_results.research_paper.search_result if hasattr(web_research_results, 'research_paper') and web_research_results.research_paper else [],
            "upnext_queries": web_research_results.upnext_queries if hasattr(web_research_results, 'upnext_queries') else []
        }
        
        # Update sources summary with web research count
        if "sources_analyzed" in analysis_result:
            analysis_result["sources_analyzed"]["web_sources"] = web_sources_count
        
        return {
            "success": True,
            "result": analysis_result
        }
        
    except Exception as e:
        logger.error(f"Research failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/web-research")
async def web_research(request: WebSearchRequest) -> Dict[str, Any]:
    """Web research endpoint - alias for /web-search"""
    try:
        logger.info(f"Web research request: {request.query}")
        result = web_research_agent.search(request.query)
        return {
            "success": True,
            "result": result.model_dump()
        }
    except Exception as e:
        logger.error(f"Web research failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/stream-research")
async def stream_research(request: ResearchRequest):
    """Stream research analysis in real-time"""
    
    def generate_analysis():
        try:
            # Send initial status
            yield f"data: {json.dumps({'type': 'status', 'message': 'Starting gene search...'})}\n\n"
            
            # Perform gene search
            logger.info(f"Stream research request: {request.query}")
            gene_search_results = gene_search_agent.search(request.query)
            
            genes_count = len(gene_search_results.get("genes", []))
            yield f"data: {json.dumps({'type': 'status', 'message': f'Gene search completed. Found {genes_count} genes. Starting web research...'})}\n\n"
            
            # Perform web research
            web_research_results = web_research_agent.search(request.query)
            
            yield f"data: {json.dumps({'type': 'status', 'message': 'Web research completed. Starting AI analysis...'})}\n\n"
            
            # Convert results to models
            from agents.Gene_search.models import GeneSearchResult
            from agents.web_search.models import WebResearchAgentModel
            
            if isinstance(gene_search_results, dict):
                gene_results = GeneSearchResult(**gene_search_results)
            else:
                gene_results = gene_search_results
                
            web_results = web_research_results
            
            # Stream analysis
            yield f"data: {json.dumps({'type': 'analysis_start', 'message': 'AI Analysis Results:'})}\n\n"
            
            # Stream the AI analysis output
            for chunk in analysis_service.stream_analysis(gene_results, web_results):
                # Format the chunk for better display
                formatted_chunk = chunk.replace('"', '**').replace('[', '<a href="').replace('](', '" target="_blank">').replace(')', '</a>')
                yield f"data: {json.dumps({'type': 'analysis_chunk', 'content': formatted_chunk})}\n\n"
            
            # Send completion status
            yield f"data: {json.dumps({'type': 'complete', 'message': 'Analysis completed successfully!'})}\n\n"
            
        except Exception as e:
            logger.error(f"Stream research failed: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': f'Analysis failed: {str(e)}'})}\n\n"
    
    return StreamingResponse(
        generate_analysis(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )

# =============================================================================
# Health Check
# =============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "agents": {
            "gene_search": "initialized",
            "web_research": "initialized", 
            "analysis": "initialized"
        }
    }

@app.post("/test-research")
def test_research(request: ResearchRequest) -> Dict[str, Any]:
    """Test research endpoint without analysis service"""
    try:
        logger.info(f"Test research request: {request.query}")
        
        # Perform gene search only
        logger.info("Performing gene search...")
        gene_search_results = gene_search_agent.search(request.query)
        
        # Return raw results without analysis
        return {
            "success": True,
            "result": {
                "gene_search_results": gene_search_results,
                "message": "Gene search completed successfully"
            }
        }
        
    except Exception as e:
        logger.error(f"Test research failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat")
async def chat(request: ChatRequest) -> ChatResponse:
    """Chat endpoint with multi-turn conversation support"""
    try:
        logger.info(f"Chat request: {request.message}")
        
        # Generate conversation ID if not provided
        conversation_id = request.conversation_id or str(uuid.uuid4())
        
        # Get or create chat history
        if conversation_id not in chat_histories:
            chat_histories[conversation_id] = []
        
        # Add user message to history
        current_time = datetime.now().isoformat()
        user_message = ChatMessage(
            role="user",
            content=request.message,
            timestamp=current_time
        )
        
        # Combine provided chat history with stored history
        full_history = chat_histories[conversation_id] + request.chat_history + [user_message]
        
        # Prepare messages for Azure OpenAI (following the example format)
        messages = [
            {
                "role": "system", 
                "content": "You are a helpful gene research assistant. You can help users with gene search, trait analysis, and biological research questions. When users ask about genes or traits, you can search for relevant information and provide detailed analysis."
            }
        ]
        
        # Add conversation history
        for msg in full_history:
            messages.append({
                "role": msg.role,
                "content": msg.content
            })
        
        # Get response from Azure OpenAI
        from openai import AzureOpenAI
        import os
        
        client = AzureOpenAI(
            api_version="2024-12-01-preview",
            azure_endpoint="https://tanay-mcn037n5-eastus2.cognitiveservices.azure.com/",
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        )
        
        response = client.chat.completions.create(
            messages=messages,
            max_completion_tokens=100000,
            model="o4-mini"
        )
        
        assistant_response = response.choices[0].message.content
        
        # Create assistant message
        assistant_message = ChatMessage(
            role="assistant",
            content=assistant_response,
            timestamp=datetime.now().isoformat()
        )
        
        # Update chat history
        chat_histories[conversation_id].extend([user_message, assistant_message])
        
        # Keep only last 20 messages to prevent memory issues
        if len(chat_histories[conversation_id]) > 20:
            chat_histories[conversation_id] = chat_histories[conversation_id][-20:]
        
        return ChatResponse(
            response=assistant_response,
            conversation_id=conversation_id,
            chat_history=chat_histories[conversation_id],
            success=True
        )
        
    except Exception as e:
        logger.error(f"Chat failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 