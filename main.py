from dotenv import load_dotenv
load_dotenv()
#!/usr/bin/env python3
"""
Main FastAPI application for GeneSearch
"""
from fastapi import FastAPI
app = FastAPI()

@app.get("/healthz")
def health():
    return {"status": "ok"}

import logging
from typing import Dict, Any
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
            "research": "/research"
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
async def analysis(request: AnalysisRequest) -> Dict[str, Any]:
    """Perform analysis of combined results"""
    try:
        logger.info("Analysis request received")
        
        # Convert dict results back to models
        from agents.Gene_search.models import GeneSearchResult
        from agents.web_search.models import WebResearchAgentModel
        
        gene_results = GeneSearchResult(**request.gene_search_results)
        web_results = WebResearchAgentModel(**request.web_research_results)
        
        # Perform analysis
        result = await analysis_service.analyze_results(gene_results, web_results)
        
        return {
            "success": True,
            "result": result
        }
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Keep the old /research endpoint for backward compatibility
@app.post("/research")
def research(request: ResearchRequest) -> Dict[str, Any]:
    """Legacy endpoint - use /search instead"""
    try:
        logger.info(f"Legacy research request: {request.query}")
        
        # Perform gene search
        gene_results = gene_search_agent.search(request.query)
        
        return gene_results
        
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 