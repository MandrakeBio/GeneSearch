"""
models.py  —  unified data classes for the Web ⋄ Gene discovery pipeline.

Major additions for the new workflow
------------------------------------
• ResearchDump              – raw literature & expression harvest
• Hypothesis, HypothesisSet – ranked causal candidates
• ExecutedCall, UpdatedHypothesis, ValidationReport – tool-level evidence
• TraitAnalysis             – final executive report with evidence_map

Legacy web-search classes are retained unchanged so older code doesn't break.
Protein-specific types are deprecated but left in place to avoid import errors.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from enum import Enum

from pydantic import BaseModel, Field

# ───────────────────────────────────────────── legacy / unchanged ────────────
class SearchResult(BaseModel):
    title: str
    url: str
    abstract: str


class WebResearchResult(BaseModel):
    search_result: List[SearchResult]


class WebResearchAgentModel(BaseModel):
    query: str
    raw_result: str
    research_paper: WebResearchResult
    upnext_queries: List[str]


# ───────────────────────────────────────────── new gene-analysis artefacts ───

class ResearchDump(BaseModel):
    """Fire-hose output of the Research agent."""
    raw_dump: str
    geo_accessions: List[str]
    gene_symbols: List[str]
    ensembl_ids: List[str]


class Hypothesis(BaseModel):
    gene: str
    confidence: float  # 0-1
    reason: str
    supporting_refs: List[str]


class HypothesisSet(BaseModel):
    hypotheses: List[Hypothesis]


class ExecutedCall(BaseModel):
    tool: str
    arguments: Dict[str, Any]
    output: Any  # raw Python return serialised to JSON


class UpdatedHypothesis(BaseModel):
    gene: str
    validated: Optional[bool]  # True / False / None (inconclusive)
    evidence: str


class ValidationReport(BaseModel):
    executed_calls: List[ExecutedCall]
    updated_hypotheses: List[UpdatedHypothesis]


class TraitAnalysis(BaseModel):
    """
    Executive report produced by AnalysisService.
    """
    summary: str
    top_hits: List[str]
    open_questions: List[str]
    execution_time: float


# ───────────────────────────────────────────── optional combined wrapper ─────
class CombinedSearchResult(BaseModel):
    """
    Convenience wrapper if you still need to group raw tool outputs alongside
    the high-level analysis in a single object.
    """
    query: str

    # tool_name → raw result
    tool_results: Dict[str, Any] = Field(default_factory=dict)

    # high-level synthesis
    trait_analysis: Optional[TraitAnalysis] = None

    # metadata
    search_type: str  # 'web', 'gene', or 'combined'
    timestamp: datetime = Field(default_factory=datetime.now)
    success: bool = True
    error_message: str = ""
    total_execution_time: float = 0.0

    # quick helpers
    def has_web_results(self) -> bool:
        return "web_search_tool" in self.tool_results

    def has_gene_results(self) -> bool:
        gene_tools = [k for k in self.tool_results if k != "web_search_tool"]
        return any(self.tool_results.get(k) for k in gene_tools)

    def get_summary(self) -> str:
        parts = []
        if self.has_web_results():
            web = self.tool_results["web_search_tool"]
            n = len(web["research_paper"]["search_result"]) if web else 0
            parts.append(f"{n} web-paper hits")
        if self.has_gene_results():
            hits = [
                k for k in self.tool_results
                if k != "web_search_tool" and self.tool_results.get(k)
            ]
            parts.append(f"{len(hits)} gene-tool outputs")
        return "; ".join(parts) if parts else "No results"

    class Config:
        extra = "allow"
