"""models.py – Mandrake‑GeneSearch (enhanced)
================================================
Rich Pydantic schemas that capture *all* evidence layers and runtime
telemetry needed by the Mandrake gene‑discovery pipeline.

Why models matter
-----------------
* **Validation** – every tool wrapper returns raw Python; the API layer
  casts to these models so malformed data is caught early.
* **OpenAPI contract** – FastAPI auto‑generates docs from these classes;
  front‑end callers get a typed SDK for free.
* **Telemetry** – token counts, execution times and row counts are
  aggregated so you can monitor cost and performance without sprinkling
  logging everywhere.
"""
from __future__ import annotations

import datetime as _dt
from typing import List, Optional

from pydantic import BaseModel, Field, HttpUrl

# ---------------------------------------------------------------------------
# Runtime telemetry / cost tracking
# ---------------------------------------------------------------------------

class ToolExecutionMetadata(BaseModel):
    """Per‑tool runtime stats injected by the agent wrapper."""

    tool: str
    execution_time: float = Field(..., description="Seconds spent inside the wrapper function, retries included.")
    success: bool = True
    error: Optional[str] = None

    # Optional cost & size metrics (populated when available)
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    rows_returned: Optional[int] = None  # e.g. number of genes or GO terms

    timestamp: _dt.datetime = Field(default_factory=_dt.datetime.utcnow)

# ---------------------------------------------------------------------------
# Evidence‑layer payloads
# ---------------------------------------------------------------------------

class GeneHit(BaseModel):
    gene_id: str
    symbol: Optional[str] = None
    description: Optional[str] = None
    species: Optional[str] = None  # latin binomial
    chromosome: Optional[str] = None
    start: Optional[int] = None
    end: Optional[int] = None
    source: str = Field(..., description="Primary data source: 'ensembl' | 'gramene'.")


class GWASHit(BaseModel):
    gene_name: str
    pvalue: float
    trait: Optional[str] = None
    variant_id: Optional[str] = None
    effect_allele: Optional[str] = None
    sample_size: Optional[int] = None
    pubmed_id: Optional[str] = None
    study_accession: Optional[str] = None


class GOAnnot(BaseModel):
    go_id: Optional[str] = Field(None, description="GO identifier (e.g., GO:0006810)")
    term: Optional[str] = Field(None, description="GO term name")
    aspect: Optional[str] = Field(None, description="P (BP), F (MF) or C (CC)")
    evidence_code: Optional[str] = Field(None, description="Evidence code (e.g., IDA, IEA)")
    reference: Optional[str] = None  # PMID or GO_REF
    qualifier: Optional[str] = None


class Pathway(BaseModel):
    pathway_id: str
    description: Optional[str] = None
    database: Optional[str] = Field("KEGG", description="Source DB e.g. KEGG, Reactome")


class PubMedSummary(BaseModel):
    pmid: str
    title: str
    abstract: Optional[str] = None
    doi: Optional[str] = None
    url: Optional[HttpUrl] = None
    journal: Optional[str] = None
    pubdate: Optional[str] = None
    authors: Optional[List[str]] = None

# ---------------------------------------------------------------------------
# Aggregated response model returned by the FastAPI endpoint
# ---------------------------------------------------------------------------

class GeneSearchResult(BaseModel):
    """Primary response schema for the `/gene-search` route."""

    user_trait: str
    explanation: Optional[str] = Field(None, description="AI-generated explanation of the search results")

    genes: List[GeneHit] = []
    gwas_hits: List[GWASHit] = []
    go_annotations: List[GOAnnot] = []
    pathways: List[Pathway] = []
    pubmed_summaries: List[PubMedSummary] = []

    metadata: List[ToolExecutionMetadata] = []

    timestamp: _dt.datetime = Field(default_factory=_dt.datetime.utcnow)
    execution_time: float = 0.0  # wall‑clock seconds for the whole request

    # -------- convenience properties --------

    @property
    def total_prompt_tokens(self) -> int:
        return sum(m.prompt_tokens or 0 for m in self.metadata)

    @property
    def total_completion_tokens(self) -> int:
        return sum(m.completion_tokens or 0 for m in self.metadata)

    def add_metadata(self, meta: ToolExecutionMetadata) -> None:  # helper for agent code
        self.metadata.append(meta)


__all__ = [
    "ToolExecutionMetadata",
    "GeneHit",
    "GWASHit",
    "GOAnnot",
    "Pathway",
    "PubMedSummary",
    "GeneSearchResult",
]
