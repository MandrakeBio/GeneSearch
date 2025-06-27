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

class WebResearchRequest(BaseModel):
    query: str

class AnalysisRequest(BaseModel):
    gene_search_results: Dict[str, Any]
    web_research_results: Dict[str, Any]

class ResearchRequest(BaseModel):
    query: str

# =============================================================================
# API Endpoints
# =============================================================================

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "GeneSearch API",
        "version": "1.0.0",
        "endpoints": {
            "gene_search": "/gene-search",
            "web_research": "/web-research", 
            "analysis": "/analysis",
            "research": "/research"
        }
    }

@app.post("/gene-search")
async def gene_search(request: GeneSearchRequest) -> Dict[str, Any]:
    """Perform gene search"""
    try:
        logger.info(f"Gene search request: {request.query}")
        result = await gene_search_agent.search(request.query)
        return {
            "success": True,
            "result": result
        }
    except Exception as e:
        logger.error(f"Gene search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/web-research")
async def web_research(request: WebResearchRequest) -> Dict[str, Any]:
    """Perform web research"""
    try:
        logger.info(f"Web research request: {request.query}")
        result = await web_research_agent.research(request.query)
        return {
            "success": True,
            "result": result.model_dump()
        }
    except Exception as e:
        logger.error(f"Web research failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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

@app.post("/research")
async def research(request: ResearchRequest) -> Dict[str, Any]:
    """Perform complete research workflow"""
    try:
        logger.info(f"Research request: {request.query}")
        
        # Perform gene search
        gene_results = await gene_search_agent.search(request.query)
        
        # Perform web research
        web_results = await web_research_agent.research(request.query)
        
        # Perform analysis
        from agents.Gene_search.models import GeneSearchResult
        
        gene_model = GeneSearchResult(**gene_results)
        analysis_result = await analysis_service.analyze_results(gene_model, web_results)
        
        return {
            "success": True,
            "gene_search": gene_results,
            "web_research": web_results.model_dump(),
            "analysis": analysis_result
        }
    except Exception as e:
        logger.error(f"Research failed: {e}")
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