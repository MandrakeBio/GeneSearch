#!/usr/bin/env python3
"""
Gene search agent for GeneSearch
"""

import asyncio
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List, Optional
from openai import AsyncOpenAI

from .models import (
    GeneSearchResult, GeneHit, GWASHit, GOAnnot, Pathway, PubMedSummary,
    ToolExecutionMetadata
)
from .tooling import ALL_TOOLS_DICT
from .prompts import PLANNER_SYSTEM_PROMPT, EXPLAINER_PROMPT
from .openai_tooling_dict import TOOLING_DICT

logger = logging.getLogger(__name__)

# Global thread pool for sync tool execution
_EXECUTOR = ThreadPoolExecutor(max_workers=10)

# =============================================================================
# Helper Functions
# =============================================================================

def _usage_to_meta(label: str, usage: Any) -> ToolExecutionMetadata:
    """Convert OpenAI usage to metadata"""
    return ToolExecutionMetadata(
        tool=label,
        execution_time=0.0,  # Will be set by caller
        prompt_tokens=usage.prompt_tokens if usage else None,
        completion_tokens=usage.completion_tokens if usage else None,
        rows_returned=None
    )

class _ToolCall(Dict[str, Any]):
    """Tool call specification"""
    pass

# =============================================================================
# Gene Search Agent
# =============================================================================

class GeneSearchAgent:
    def __init__(self,
                 model_planner: str = "gpt-4o-mini",
                 model_explainer: str = "gpt-4o") -> None:
        self.client = AsyncOpenAI()
        self.model_planner = model_planner
        self.model_explainer = model_explainer

    # ---------------------------------------------------------------------
    # 1. PLAN
    # ---------------------------------------------------------------------
    async def _plan_tool_calls(self, query: str) -> List[_ToolCall]:
        """Plan tool calls"""
        messages = [
            {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
            {"role": "user", "content": query},
        ]
        
        response = await self.client.chat.completions.create(
            model=self.model_planner,
            tools=TOOLING_DICT["tools"],
            tool_choice="auto",
            messages=messages,
            temperature=0.2,
            max_tokens=400,
        )
        
        calls: List[_ToolCall] = []
        for choice in response.choices:
            msg = choice.message
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    calls.append({"name": tc.function.name, "arguments": json.loads(tc.function.arguments)})
        
        # expose token usage so caller can log cost
        return calls, response.usage

    # ---------------------------------------------------------------------
    # 2. EXECUTE (sync wrappers off‑loaded to a thread pool)
    # ---------------------------------------------------------------------
    async def _execute_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute tool"""
        if name not in ALL_TOOLS_DICT:
            raise RuntimeError(f"Unknown tool: {name}")
        
        func = ALL_TOOLS_DICT[name]["function"]
        loop = asyncio.get_event_loop()
        
        start = time.perf_counter()
        result = await loop.run_in_executor(_EXECUTOR, lambda: func(**arguments))
        elapsed = time.perf_counter() - start
        
        return {
            "tool": name,
            "arguments": arguments,
            "result": result,
            "metadata": ToolExecutionMetadata(
                tool=name,
                execution_time=elapsed,
                prompt_tokens=None,
                completion_tokens=None,
                rows_returned=len(result) if isinstance(result, list) else None,
            ),
        }

    # ---------------------------------------------------------------------
    # 3. MAP raw data → Pydantic evidence models
    # ---------------------------------------------------------------------
    def _map_raw(self, executed: List[Dict[str, Any]]) -> GeneSearchResult:
        result = GeneSearchResult(user_trait="")  # user_trait filled later
        # keep a quick index so we merge, not multiply, identical gene hits
        seen: Dict[str, GeneHit] = {}

        for item in executed:
            name = item["tool"]
            data = item["result"]
            meta = item["metadata"]
            result.add_metadata(meta)

            # ── 1. Discovery tools ────────────────────────────────────
            if name in {"ensembl_search_genes", "gramene_trait_search", "gramene_prioritized_search"}:
                for entry in data:
                    gh = GeneHit(
                        gene_id=entry.get("id") or entry.get("gene_id"),
                        symbol=entry.get("display_id") or entry.get("symbol"),
                        description=entry.get("description") or entry.get("name"),
                        species=entry.get("species"),
                        chromosome=entry.get("seq_region_name"),
                        start=entry.get("start") or entry.get("location", {}).get("start"),
                        end=entry.get("end")   or entry.get("location", {}).get("end"),
                        source="ensembl" if name.startswith("ensembl") else "gramene",
                    )
                    if gh.gene_id and gh.gene_id not in seen:
                        seen[gh.gene_id] = gh

            # ── 1-b. Detailed lookup for a single gene ────────────────
            elif name == "ensembl_gene_info":
                entry = data  # single-dict payload
                gid = entry.get("id")
                gh = seen.get(gid) or GeneHit(gene_id=gid, source="ensembl")
                gh.symbol       = gh.symbol       or entry.get("display_name")
                gh.description  = gh.description  or entry.get("description")
                gh.species      = gh.species      or entry.get("species")
                gh.chromosome   = gh.chromosome   or entry.get("seq_region_name")
                gh.start        = gh.start        or entry.get("start")
                gh.end          = gh.end          or entry.get("end")
                seen[gid] = gh

            elif name == "gramene_gene_lookup":
                entry = data
                gid = entry.get("gene_id")
                gh = seen.get(gid) or GeneHit(gene_id=gid, source="gramene")
                gh.symbol       = gh.symbol       or entry.get("symbol")
                gh.description  = gh.description  or entry.get("name")
                gh.species      = gh.species      or entry.get("taxon", {}).get("scientific_name")
                seen[gid] = gh

            # ── 1-c. Ortholog expansion ───────────────────────────────
            elif name == "ensembl_orthologs":
                for hom in data.get("orthologs", []):
                    tgt = hom.get("target", {})
                    gid = tgt.get("id")
                    gh = GeneHit(
                        gene_id=gid,
                        symbol=tgt.get("gene_symbol"),
                        species=tgt.get("species"),
                        chromosome=tgt.get("chromosome"),
                        start=tgt.get("start"),
                        end=tgt.get("end"),
                        source="ensembl",
                    )
                    if gh.gene_id and gh.gene_id not in seen:
                        seen[gh.gene_id] = gh

            # ── 2. Literature tools ────────────────────────────────────
            elif name == "pubmed_search":
                # data is a list of PMIDs
                for pmid in data:
                    result.pubmed_summaries.append(
                        PubMedSummary(pmid=pmid, title="", abstract="")
                    )

            elif name == "pubmed_fetch_summaries":
                # data is a list of summary dicts
                for entry in data:
                    result.pubmed_summaries.append(
                        PubMedSummary(
                            pmid=entry.get("elocationid", ""),
                            title=entry.get("title", ""),
                            abstract=entry.get("", ""),
                        )
                    )

            elif name == "bioc_pmc_fetch_article":
                # data is a single BioC article
                # Extract text content and create PubMedSummary
                from .tooling import bioc_pmc_extract_text_content
                extracted = bioc_pmc_extract_text_content(data)
                if "error" not in extracted:
                    result.pubmed_summaries.append(
                        PubMedSummary(
                            pmid=item.get("arguments", {}).get("article_id", ""),
                            title=extracted.get("title", ""),
                            abstract=extracted.get("abstract", ""),
                        )
                    )

            elif name == "bioc_pmc_search_and_fetch":
                # data is a list of articles with BioC content or PubMed summaries
                from .tooling import bioc_pmc_extract_text_content
                for article in data:
                    pmid = article.get("pmid", "")
                    if article.get("success", False) and "bioc_content" in article:
                        # Extract text from BioC content
                        extracted = bioc_pmc_extract_text_content(article["bioc_content"])
                        if "error" not in extracted:
                            result.pubmed_summaries.append(
                                PubMedSummary(
                                    pmid=pmid,
                                    title=extracted.get("title", ""),
                                    abstract=extracted.get("abstract", ""),
                                )
                            )
                    elif "pubmed_summary" in article:
                        # Use fallback PubMed summary
                        summary = article["pubmed_summary"]
                        result.pubmed_summaries.append(
                            PubMedSummary(
                                pmid=pmid,
                                title=summary.get("title", ""),
                                abstract=summary.get("", ""),
                            )
                        )

            elif name == "bioc_pmc_extract_text_content":
                # This function is typically used in combination with other BioC functions
                # The extracted content is already handled in the calling functions
                pass

            # ── 3. Association tools ────────────────────────────────────
            elif name == "gwas_hits":
                for entry in data:
                    result.gwas_hits.append(
                        GWASHit(
                            trait=entry.get("trait", ""),
                            p_value=entry.get("p_value", 0.0),
                            odds_ratio=entry.get("odds_ratio", 0.0),
                            confidence_interval=entry.get("confidence_interval", ""),
                            study=entry.get("study", ""),
                            population=entry.get("population", ""),
                        )
                    )

            elif name in {"gwas_trait_search", "gwas_snp_search", "gwas_advanced_search"}:
                # Handle all the new GWAS functions that return association data
                for entry in data:
                    result.gwas_hits.append(
                        GWASHit(
                            trait=entry.get("trait", ""),
                            p_value=entry.get("pvalue", 0.0),
                            odds_ratio=entry.get("odds_ratio", 0.0),
                            confidence_interval=entry.get("confidence_interval", ""),
                            study=entry.get("study_id", ""),
                            population="",  # Not available in these endpoints
                        )
                    )

            elif name == "gwas_study_info":
                # This returns study metadata, not associations
                # Could be stored in a separate field or logged
                logger.info(f"GWAS study info: {data}")

            elif name == "gwas_trait_info":
                # This returns trait ontology information
                # Could be stored in a separate field or logged
                logger.info(f"GWAS trait info: {data}")

            elif name == "quickgo_annotations":
                for entry in data:
                    result.go_annotations.append(
                        GOAnnot(
                            term=entry.get("term", ""),
                            evidence=entry.get("evidence", ""),
                            aspect=entry.get("aspect", ""),
                            assigned_by=entry.get("assigned_by", ""),
                        )
                    )

            elif name == "kegg_pathways":
                for pathway_id in data:
                    result.pathways.append(
                        Pathway(
                            pathway_id=pathway_id,
                            name="",  # would need separate lookup
                            description="",
                        )
                    )

        # Convert seen genes to list
        result.genes = list(seen.values())
        return result

    # ---------------------------------------------------------------------
    # 4. EXPLAIN
    # ---------------------------------------------------------------------
    async def _explain(self, aggregated: GeneSearchResult, user_trait: str) -> str:
        """Explain results"""
        messages = [
            {"role": "system", "content": EXPLAINER_PROMPT},
            {"role": "user", "content": f"Trait: {user_trait}\n\nEvidence: {aggregated.model_dump_json()}"},
        ]
        response = await self.client.chat.completions.create(
            model=self.model_explainer,
            messages=messages,
            temperature=0.3,
            max_tokens=800,
        )
        
        return response.choices[0].message.content

    # ---------------------------------------------------------------------
    # 5. MAIN SEARCH METHOD
    # ---------------------------------------------------------------------
    async def search(self, query: str) -> dict:
        """Main search method (returns dict with extra quickgo_results field)"""
        
        try:
            # 1. PLAN
            calls, usage = await self._plan_tool_calls(query)
            
            # 2. EXECUTE
            executed = []
            for call in calls:
                result = await self._execute_tool(call["name"], call["arguments"])
                executed.append(result)
            
            # 3. MAP
            aggregated = self._map_raw(executed)
            aggregated.user_trait = query
            
            # 4. EXPLAIN
            explanation = await self._explain(aggregated, query)
            aggregated.explanation = explanation

            # 5. Add quickgo_results (raw output for first gene, if any)
            from .tooling import quickgo_annotations
            quickgo_results = []
            if aggregated.genes:
                first_gene = aggregated.genes[0]
                gene_id = first_gene.gene_id or first_gene.symbol
                if gene_id:
                    quickgo_results = quickgo_annotations(gene_id)
            
            # Return as dict with extra field
            result_dict = aggregated.model_dump()
            result_dict["quickgo_results"] = quickgo_results
            
            return result_dict
            
        except Exception as e:
            logger.error(f"Gene search failed: {e}")
            raise
