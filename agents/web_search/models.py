from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class SearchResult(BaseModel):
    title: str
    url: str
    abstract: str

class WebResearchResult(BaseModel):
    search_result: list[SearchResult]

class UpNextQueries(BaseModel):
    queries: list[str]

class WebResearchAgentModel(BaseModel):
    query: str
    raw_result: str
    research_paper: WebResearchResult
    upnext_queries: list[str]
    biological_analysis: Optional[Any] = None  # BiologicalAnalysis type

class ResearchDump(BaseModel):
    raw_dump: str
    geo_accessions: List[str]
    gene_symbols: List[str]
    ensembl_ids: List[str]

class Hypothesis(BaseModel):
    gene: str
    confidence: float
    reason: str
    supporting_refs: List[str]

class HypothesisSet(BaseModel):
    hypotheses: List[Hypothesis]

class ExecutedCall(BaseModel):
    tool: str
    arguments: Dict[str, Any]
    output: Any

class UpdatedHypothesis(BaseModel):
    gene: str
    validated: Optional[bool]  # true / false / null (inconclusive)
    evidence: str

class ValidationReport(BaseModel):
    executed_calls: List[ExecutedCall]
    updated_hypotheses: List[UpdatedHypothesis]