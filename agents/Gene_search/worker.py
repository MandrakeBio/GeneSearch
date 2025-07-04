#!/usr/bin/env python3
"""
Gene search agent for GeneSearch - Based on protein search agent pattern
"""

import os
from openai import AzureOpenAI
from dotenv import load_dotenv
from agents.Gene_search.models import (
    GeneSearchResult, GeneHit, GWASHit, GOAnnot, Pathway, PubMedSummary,
    ToolExecutionMetadata
)
from agents.Gene_search.tooling import (
    pubmed_search,
    pubmed_fetch_summaries,
    ensembl_search_genes,
    ensembl_gene_info,
    ensembl_orthologs,
    gramene_gene_symbol_search,
    gramene_gene_search,
    gramene_gene_lookup,
    gwas_hits,
    gwas_trait_search,
    gwas_advanced_search,
    gwas_trait_info,
    quickgo_annotations,
    kegg_pathways,
    ALL_TOOLS_DICT
)
from agents.Gene_search.prompts import PLANNER_SYSTEM_PROMPT, EXPLAINER_PROMPT
from agents.Gene_search.openai_tooling_dict import TOOLING_DICT
import asyncio
import json
import time
import logging
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

logger = logging.getLogger(__name__)

load_dotenv()

# Tool selection prompt - determines which tools to use based on user query
TOOL_SELECTION_PROMPT = f"""
You are an expert plant genomics research assistant. Based on the user query, determine which tools to use for the best results.

Available tools: {list(ALL_TOOLS_DICT.keys())}

Tool Selection Guidelines:
- pubmed_search: Always use for literature evidence on any gene/trait query
- pubmed_fetch_summaries: Use only if you have specific PMIDs from pubmed_search
- ensembl_search_genes: For gene discovery by keywords, symbols, or trait terms
- ensembl_gene_info: When you need detailed information about specific Ensembl gene IDs
- ensembl_orthologs: For finding orthologous genes across species
- gramene_gene_symbol_search: For plant-specific gene symbol searches
- gramene_gene_search: For comprehensive plant gene searches with multiple approaches
- gramene_gene_lookup: For detailed information about specific Gramene gene IDs
- gwas_hits: For statistical evidence when you have specific gene names
- gwas_trait_search: For GWAS associations by trait terms
- gwas_advanced_search: For complex GWAS searches with multiple filters
- gwas_trait_info: For trait ontology information
- quickgo_annotations: For functional GO annotations of genes
- kegg_pathways: For pathway context of genes

CRITICAL: Always select multiple tools (3-8 tools) to provide comprehensive evidence from different sources.
Always include both literature tools (pubmed_search) AND gene-specific tools.
Choose tools that will gather evidence from multiple angles: discovery, functional annotation, statistical evidence, and literature.

Return only the tool names as a list.
"""

class ToolsToUseResult:
    """Simple class to hold tool selection results"""
    def __init__(self, tools_to_use: List[str]):
        self.tools_to_use = tools_to_use

class GeneSearchAgent:
    def __init__(self):
        self.client = AzureOpenAI(
            api_version="2024-12-01-preview",
            azure_endpoint="https://tanay-mcn037n5-eastus2.cognitiveservices.azure.com/",
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        )
        
    def determine_tools_to_use(self, query: str) -> List[str]:
        """
        Determine which tools to use based on the user query
        Uses LLM to intelligently select the most appropriate tools
        """
        try:
            completion = self.client.chat.completions.create(
                model="gpt-4.1",
                messages=[
                    {"role": "system", "content": TOOL_SELECTION_PROMPT},
                    {"role": "user", "content": f"User query: {query}"}
                ],
                temperature=0.2,
                max_tokens=200
            )
            
            # Parse the response to extract tool names
            response_text = completion.choices[0].message.content
            
            # Extract tool names from the response
            available_tools = list(ALL_TOOLS_DICT.keys())
            selected_tools = []
            
            for tool in available_tools:
                if tool in response_text:
                    selected_tools.append(tool)
            
            # Fallback: if no tools were selected, use a comprehensive set
            if not selected_tools:
                selected_tools = [
                    "pubmed_search",
                    "gramene_gene_search", 
                    "ensembl_search_genes",
                    "gwas_trait_search",
                    "quickgo_annotations"
                ]
            
            # Ensure we always have pubmed_search for literature
            if "pubmed_search" not in selected_tools:
                selected_tools.insert(0, "pubmed_search")
                
            return selected_tools
            
        except Exception as e:
            logger.error(f"Error in tool selection: {e}")
            # Fallback to comprehensive search if tool selection fails
            return [
                "pubmed_search",
                "gramene_gene_search",
                "ensembl_search_genes", 
                "gwas_trait_search",
                "quickgo_annotations"
            ]
    
    def get_tool_arguments(self, query: str, tool_name: str) -> Dict[str, Any]:
        """
        Get the appropriate arguments for a specific tool based on the user query
        """
        try:
            if tool_name not in ALL_TOOLS_DICT:
                return {}
                
            # Use the OpenAI function calling to get proper arguments
            tool_config = ALL_TOOLS_DICT[tool_name]
            openai_tool = None
            
            # Find the corresponding OpenAI tool definition
            for tool_def in TOOLING_DICT["tools"]:
                if tool_def["function"]["name"] == tool_name:
                    openai_tool = tool_def
                    break
            
            if not openai_tool:
                # Fallback argument generation based on tool name
                return self._generate_fallback_arguments(query, tool_name)
            
            completion = self.client.chat.completions.create(
                model="gpt-4.1",
                messages=[
                    {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
                    {"role": "user", "content": f"Based on this query: '{query}', determine the arguments for the tool."}
                ],
                tools=[openai_tool],
                tool_choice={"type": "function", "function": {"name": tool_name}},
                temperature=0.2
            )
            
            if completion.choices[0].message.tool_calls:
                tool_call = completion.choices[0].message.tool_calls[0]
                return json.loads(tool_call.function.arguments)
            else:
                return self._generate_fallback_arguments(query, tool_name)
                
        except Exception as e:
            logger.error(f"Error getting tool arguments for {tool_name}: {e}")
            return self._generate_fallback_arguments(query, tool_name)
    
    def _generate_fallback_arguments(self, query: str, tool_name: str) -> Dict[str, Any]:
        """Generate fallback arguments when OpenAI tool calling fails"""
        
        # Extract potential gene symbols and trait terms from query
        query_lower = query.lower()
        
        if tool_name == "pubmed_search":
            return {"query": query, "max_hits": 20}
        elif tool_name == "ensembl_search_genes":
            return {"keyword": query, "species": "oryza_sativa", "limit": 20}
        elif tool_name == "gramene_gene_search":
            # Extract potential gene symbols from common salt tolerance genes
            gene_symbols = []
            if "salt" in query_lower:
                gene_symbols = ["HKT1", "NHX1", "SOS1", "SKC1", "HAK1"]
            elif "drought" in query_lower:
                gene_symbols = ["DREB1", "DREB2", "ERF", "ABA2"]
            elif "disease" in query_lower or "resistance" in query_lower:
                gene_symbols = ["Xa21", "Pi-ta", "Pib", "Pita"]
            
            return {
                "gene_symbols": gene_symbols,
                "trait_terms": [query],
                "limit": 30
            }
        elif tool_name == "gwas_trait_search":
            return {"trait_term": query, "max_hits": 30}
        elif tool_name == "gwas_hits":
            # Try to extract gene name from query
            words = query.split()
            gene_name = words[0] if words else "HKT1"
            return {"gene_name": gene_name, "max_hits": 30}
        elif tool_name == "quickgo_annotations":
            return {"gene_product_id": "HKT1", "evidence_codes": []}
        elif tool_name == "gwas_advanced_search":
            return {"trait_term": query, "max_hits": 30}
        elif tool_name == "gwas_trait_info":
            return {"trait_term": query, "max_hits": 10}
        else:
            return {}
    
    def execute_tool_parallel(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a single tool with given arguments
        Returns the result with metadata
        """
        start_time = time.time()
        
        try:
            if tool_name not in ALL_TOOLS_DICT:
                raise ValueError(f"Unknown tool: {tool_name}")
                
            tool_config = ALL_TOOLS_DICT[tool_name]
            result = tool_config["function"](**arguments)
            
            execution_time = time.time() - start_time
            
            return {
                "tool_name": tool_name,
                "success": True,
                "result": result,
                "arguments": arguments,
                "execution_time": execution_time,
                "error": None
            }
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Error executing {tool_name}: {e}")
            
            return {
                "tool_name": tool_name,
                "success": False,
                "result": None,
                "arguments": arguments,
                "execution_time": execution_time,
                "error": str(e)
            }
    
    def execute_tools_parallel(self, query: str, selected_tools: List[str]) -> List[Dict[str, Any]]:
        """
        Execute multiple tools in parallel for maximum efficiency
        """
        # Get arguments for each tool
        tool_executions = []
        for tool_name in selected_tools:
            arguments = self.get_tool_arguments(query, tool_name)
            tool_executions.append((tool_name, arguments))
        
        # Execute all tools in parallel using ThreadPoolExecutor
        results = []
        with ThreadPoolExecutor(max_workers=min(len(tool_executions), 8)) as executor:
            # Submit all tasks
            future_to_tool = {
                executor.submit(self.execute_tool_parallel, tool_name, args): tool_name 
                for tool_name, args in tool_executions
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_tool):
                result = future.result()
                results.append(result)
        
        return results
    
    def convert_to_structured_result(self, tool_results: List[Dict[str, Any]], query: str) -> GeneSearchResult:
        """
        Convert raw tool results to structured GeneSearchResult
        """
        result = GeneSearchResult(user_trait=query)
        seen_genes: Dict[str, GeneHit] = {}
        
        for tool_result in tool_results:
            tool_name = tool_result["tool_name"]
            success = tool_result["success"]
            raw_result = tool_result["result"]
            execution_time = tool_result["execution_time"]
            error_message = tool_result["error"]
            
            # Add metadata
            metadata = ToolExecutionMetadata(
                tool=tool_name,
                execution_time=execution_time,
                prompt_tokens=None,
                completion_tokens=None,
                rows_returned=len(raw_result) if isinstance(raw_result, list) else None,
            )
            result.add_metadata(metadata)
            
            if not success or not raw_result:
                logger.warning(f"Tool {tool_name} failed: {error_message}")
                continue
            
            # Process results based on tool type
            if tool_name in {"ensembl_search_genes", "gramene_gene_search", "gramene_gene_symbol_search"}:
                for entry in raw_result:
                    gene_id = entry.get("id") or entry.get("gene_id") or entry.get("_id")
                    if gene_id and gene_id not in seen_genes:
                        gh = GeneHit(
                            gene_id=gene_id,
                            symbol=entry.get("display_id") or entry.get("symbol") or entry.get("name"),
                            description=entry.get("description") or entry.get("name") or entry.get("title"),
                            species=entry.get("species") or entry.get("taxon", {}).get("scientific_name"),
                            chromosome=entry.get("seq_region_name") or entry.get("chromosome"),
                            start=entry.get("start") or entry.get("location", {}).get("start"),
                            end=entry.get("end") or entry.get("location", {}).get("end"),
                            source="ensembl" if tool_name.startswith("ensembl") else "gramene",
                        )
                        seen_genes[gene_id] = gh
            
            elif tool_name == "ensembl_gene_info":
                entry = raw_result
                gene_id = entry.get("id")
                if gene_id:
                    gh = seen_genes.get(gene_id) or GeneHit(gene_id=gene_id, source="ensembl")
                    gh.symbol = gh.symbol or entry.get("display_name")
                    gh.description = gh.description or entry.get("description")
                    gh.species = gh.species or entry.get("species")
                    gh.chromosome = gh.chromosome or entry.get("seq_region_name")
                    gh.start = gh.start or entry.get("start")
                    gh.end = gh.end or entry.get("end")
                    seen_genes[gene_id] = gh
            
            elif tool_name == "gramene_gene_lookup":
                entry = raw_result
                gene_id = entry.get("gene_id") or entry.get("id")
                if gene_id:
                    gh = seen_genes.get(gene_id) or GeneHit(gene_id=gene_id, source="gramene")
                    gh.symbol = gh.symbol or entry.get("symbol")
                    gh.description = gh.description or entry.get("name")
                    gh.species = gh.species or entry.get("taxon", {}).get("scientific_name")
                    seen_genes[gene_id] = gh
            
            elif tool_name == "ensembl_orthologs":
                for hom in raw_result.get("orthologs", []):
                    tgt = hom.get("target", {})
                    gene_id = tgt.get("id")
                    if gene_id and gene_id not in seen_genes:
                        gh = GeneHit(
                            gene_id=gene_id,
                            symbol=tgt.get("gene_symbol"),
                            species=tgt.get("species"),
                            chromosome=tgt.get("chromosome"),
                            start=tgt.get("start"),
                            end=tgt.get("end"),
                            source="ensembl",
                        )
                        seen_genes[gene_id] = gh
            
            elif tool_name == "pubmed_search":
                for pmid in raw_result:
                    result.pubmed_summaries.append(
                        PubMedSummary(pmid=pmid, title="", abstract="")
                    )
            
            elif tool_name == "pubmed_fetch_summaries":
                for entry in raw_result:
                    result.pubmed_summaries.append(
                        PubMedSummary(
                            pmid=entry.get("elocationid", ""),
                            title=entry.get("title", ""),
                            abstract=entry.get("abstract", ""),
                        )
                    )
            
            elif tool_name in {"gwas_hits", "gwas_trait_search", "gwas_advanced_search"}:
                for entry in raw_result:
                    result.gwas_hits.append(
                        GWASHit(
                            trait=entry.get("trait", ""),
                            p_value=entry.get("pvalue") or entry.get("p_value", 0.0),
                            odds_ratio=entry.get("odds_ratio", 0.0),
                            confidence_interval=entry.get("confidence_interval", ""),
                            study=entry.get("study_id") or entry.get("study", ""),
                            population="",
                        )
                    )
            
            elif tool_name == "quickgo_annotations":
                for entry in raw_result:
                    result.go_annotations.append(
                        GOAnnot(
                            term=entry.get("term", ""),
                            evidence=entry.get("evidence", ""),
                            aspect=entry.get("aspect", ""),
                            assigned_by=entry.get("assigned_by", ""),
                        )
                    )
            
            elif tool_name == "kegg_pathways":
                for pathway_id in raw_result:
                    result.pathways.append(
                        Pathway(
                            pathway_id=pathway_id,
                            name="",
                            description="",
                        )
                    )
        
        # Convert seen genes to list
        result.genes = list(seen_genes.values())
        return result
    
    def generate_explanation(self, structured_result: GeneSearchResult) -> str:
        """
        Generate explanation using the structured results
        """
        try:
            completion = self.client.chat.completions.create(
                model="gpt-4.1",
                messages=[
                    {"role": "system", "content": EXPLAINER_PROMPT},
                    {"role": "user", "content": f"Trait: {structured_result.user_trait}\n\nEvidence: {structured_result.model_dump_json()}"}
                ],
                temperature=0.3,
                max_tokens=800
            )
            
            return completion.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error generating explanation: {e}")
            return f"Analysis completed for {structured_result.user_trait}. Found {len(structured_result.genes)} genes, {len(structured_result.gwas_hits)} GWAS associations, {len(structured_result.go_annotations)} GO annotations, and {len(structured_result.pubmed_summaries)} literature references."
    
    def search(self, query: str) -> dict:
        """
        Main search method - orchestrates the entire workflow
        1. Determine which tools to use
        2. Execute tools in parallel
        3. Convert results to structured models
        4. Generate explanation
        5. Return comprehensive results
        """
        logger.info(f"🔍 Processing gene search query: {query}")
        
        start_time = time.time()
        
        try:
            # Step 1: Determine tools to use
            selected_tools = self.determine_tools_to_use(query)
            logger.info(f"📋 Selected tools: {selected_tools}")
            
            # Step 2: Execute tools in parallel
            logger.info(f"⚡ Executing {len(selected_tools)} tools in parallel...")
            raw_tool_results = self.execute_tools_parallel(query, selected_tools)
            
            # Step 3: Convert to structured results
            logger.info("📊 Converting to structured results...")
            structured_result = self.convert_to_structured_result(raw_tool_results, query)
            
            # Step 4: Generate explanation
            logger.info("📝 Generating explanation...")
            explanation = self.generate_explanation(structured_result)
            structured_result.explanation = explanation
            
            # Step 5: Add additional processing for compatibility
            # Add quickgo_results for backward compatibility
            quickgo_results = []
            if structured_result.genes:
                first_gene = structured_result.genes[0]
                gene_id = first_gene.gene_id or first_gene.symbol
                if gene_id:
                    try:
                        quickgo_results = quickgo_annotations(gene_id)
                    except Exception as e:
                        logger.warning(f"Failed to get quickgo results: {e}")
                        quickgo_results = []
            
            total_execution_time = time.time() - start_time
            
            # Count successful and failed tools
            successful_tools = sum(1 for r in raw_tool_results if r["success"])
            failed_tools = len(raw_tool_results) - successful_tools
            
            # Create response dict
            result_dict = structured_result.model_dump()
            result_dict["quickgo_results"] = quickgo_results
            result_dict["execution_summary"] = {
                "total_tools_used": len(selected_tools),
                "successful_tools": successful_tools,
                "failed_tools": failed_tools,
                "total_execution_time": total_execution_time,
                "tools_executed": [r["tool_name"] for r in raw_tool_results],
                "successful_tool_names": [r["tool_name"] for r in raw_tool_results if r["success"]],
                "failed_tool_names": [r["tool_name"] for r in raw_tool_results if not r["success"]]
            }
            
            # Summary
            logger.info(f"✅ Gene search completed successfully!")
            logger.info(f"   - Tools used: {len(selected_tools)}")
            logger.info(f"   - Successful tools: {successful_tools}")
            logger.info(f"   - Failed tools: {failed_tools}")
            logger.info(f"   - Genes found: {len(structured_result.genes)}")
            logger.info(f"   - GWAS hits: {len(structured_result.gwas_hits)}")
            logger.info(f"   - GO annotations: {len(structured_result.go_annotations)}")
            logger.info(f"   - Literature references: {len(structured_result.pubmed_summaries)}")
            logger.info(f"   - Total execution time: {total_execution_time:.2f}s")
            
            return result_dict
            
        except Exception as e:
            logger.error(f"❌ Error in gene search: {e}")
            total_execution_time = time.time() - start_time
            
            # Return error response
            return {
                "user_trait": query,
                "genes": [],
                "gwas_hits": [],
                "go_annotations": [],
                "pathways": [],
                "pubmed_summaries": [],
                "explanation": f"Search failed due to error: {str(e)}",
                "metadata": [],
                "quickgo_results": [],
                "execution_summary": {
                    "total_tools_used": 0,
                    "successful_tools": 0,
                    "failed_tools": 1,
                    "total_execution_time": total_execution_time,
                    "tools_executed": [],
                    "successful_tool_names": [],
                    "failed_tool_names": [],
                    "error": str(e)
                }
            }

# Example usage and testing
if __name__ == "__main__":
    agent = GeneSearchAgent()
    result = agent.search("salt tolerance genes in rice")
    print(json.dumps(result, indent=2, default=str)) 