#!/usr/bin/env python3
"""
Analysis service for GeneSearch
"""

import json
import logging
from typing import Dict, Any, List, Optional
from openai import AsyncOpenAI
from .web_search.models import WebResearchAgentModel
from .Gene_search.models import GeneSearchResult

logger = logging.getLogger(__name__)

# System prompt for analysis
ANALYSIS_PROMPT = """
You are an expert biological data analyst specializing in gene-trait associations and pathway analysis.

Your task is to:
1. Analyze gene search results and web research findings
2. Identify patterns and connections between genes and traits
3. Evaluate the strength of evidence for gene-trait associations
4. Provide insights about biological mechanisms and pathways
5. Suggest potential research directions

Focus on:
- Statistical significance of associations
- Biological plausibility of mechanisms
- Cross-species conservation of gene function
- Pathway enrichment and network analysis
- Clinical and agricultural implications

Provide a comprehensive analysis with clear conclusions and recommendations.
"""

class AnalysisService:
    """Service for analyzing gene search and web research results"""
    
    def __init__(self, model: str = "gpt-4o"):
        self.client = AsyncOpenAI()
        self.model = model
    
    async def analyze_results(self, 
                            gene_results: GeneSearchResult, 
                            web_results: WebResearchAgentModel) -> Dict[str, Any]:
        """Analyze combined results from gene search and web research"""
        
        try:
            # Prepare data for analysis
            analysis_data = self._prepare_analysis_data(gene_results, web_results)
            
            # Analyze patterns in the data
            patterns = await self._analyze_patterns(analysis_data)
            
            # Analyze biological pathways
            pathways = await self._analyze_pathways(gene_results)
            
            # Evaluate strength of evidence
            evidence = await self._evaluate_evidence(gene_results, web_results)
            
            # Generate comprehensive analysis
            analysis_summary = await self._generate_analysis_summary(
                gene_results, web_results, patterns, pathways, evidence
            )
            
            # Create final result
            result = {
                "analysis_summary": analysis_summary,
                "patterns": patterns,
                "pathways": pathways,
                "evidence_strength": evidence,
                "recommendations": self._generate_recommendations(gene_results, web_results),
                "metadata": {
                    "genes_analyzed": len(gene_results.genes),
                    "publications_reviewed": len(gene_results.pubmed_summaries),
                    "pathways_identified": len(gene_results.pathways),
                    "gwas_hits": len(gene_results.gwas_hits)
                }
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            raise
    
    def _prepare_analysis_data(self, gene_results: GeneSearchResult, 
                              web_results: WebResearchAgentModel) -> Dict[str, Any]:
        """Prepare data for analysis"""
        return {
            "genes": [gene.model_dump() for gene in gene_results.genes],
            "gwas_hits": [hit.model_dump() for hit in gene_results.gwas_hits],
            "pathways": [path.model_dump() for path in gene_results.pathways],
            "publications": [pub.model_dump() for pub in gene_results.pubmed_summaries],
            "web_research": web_results.model_dump(),
            "query": gene_results.user_trait
        }
    
    async def _analyze_patterns(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Analyze patterns in the data"""
        patterns = []
        
        # Analyze gene distribution across species
        species_count = {}
        for gene in data["genes"]:
            species = gene.get("species", "Unknown")
            species_count[species] = species_count.get(species, 0) + 1
        
        if species_count:
            patterns.append({
                "type": "species_distribution",
                "description": f"Genes found across {len(species_count)} species",
                "data": species_count
            })
        
        # Analyze GWAS hit significance
        significant_hits = [hit for hit in data["gwas_hits"] if hit.get("p_value", 1) < 0.05]
        if significant_hits:
            patterns.append({
                "type": "gwas_significance",
                "description": f"{len(significant_hits)} significant GWAS associations found",
                "data": {"significant": len(significant_hits), "total": len(data["gwas_hits"])}
            })
        
        return patterns
    
    async def _analyze_pathways(self, gene_results: GeneSearchResult) -> List[Dict[str, Any]]:
        """Analyze biological pathways"""
        pathways = []
        
        for pathway in gene_results.pathways:
            pathways.append({
                "pathway_id": pathway.pathway_id,
                "name": pathway.name,
                "description": pathway.description,
                "genes_involved": len([g for g in gene_results.genes if g.gene_id])
            })
        
        return pathways
    
    async def _evaluate_evidence(self, gene_results: GeneSearchResult, 
                                web_results: WebResearchAgentModel) -> Dict[str, Any]:
        """Evaluate the strength of evidence"""
        evidence_score = 0
        factors = []
        
        # Factor 1: Number of genes found
        if gene_results.genes:
            evidence_score += min(len(gene_results.genes) * 10, 30)
            factors.append(f"Found {len(gene_results.genes)} genes")
        
        # Factor 2: GWAS associations
        if gene_results.gwas_hits:
            significant_hits = [h for h in gene_results.gwas_hits if h.p_value < 0.05]
            evidence_score += min(len(significant_hits) * 15, 30)
            factors.append(f"{len(significant_hits)} significant GWAS associations")
        
        # Factor 3: Literature support
        if gene_results.pubmed_summaries:
            evidence_score += min(len(gene_results.pubmed_summaries) * 5, 20)
            factors.append(f"{len(gene_results.pubmed_summaries)} publications")
        
        # Factor 4: Pathway involvement
        if gene_results.pathways:
            evidence_score += min(len(gene_results.pathways) * 10, 20)
            factors.append(f"{len(gene_results.pathways)} pathways involved")
        
        return {
            "score": evidence_score,
            "strength": "Strong" if evidence_score >= 70 else "Moderate" if evidence_score >= 40 else "Weak",
            "factors": factors
        }
    
    async def _generate_analysis_summary(self, gene_results: GeneSearchResult,
                                       web_results: WebResearchAgentModel,
                                       patterns: List[Dict[str, Any]],
                                       pathways: List[Dict[str, Any]],
                                       evidence: Dict[str, Any]) -> str:
        """Generate comprehensive analysis summary"""
        
        messages = [
            {"role": "system", "content": ANALYSIS_PROMPT},
            {"role": "user", "content": f"""
Analyze the following gene-trait research results:

Query: {gene_results.user_trait}

Gene Search Results:
- Genes found: {len(gene_results.genes)}
- GWAS hits: {len(gene_results.gwas_hits)}
- Publications: {len(gene_results.pubmed_summaries)}
- Pathways: {len(gene_results.pathways)}

Web Research Summary:
{web_results.research_summary}

Patterns Identified:
{json.dumps(patterns, indent=2)}

Evidence Strength: {evidence['strength']} ({evidence['score']}/100)

Provide a comprehensive analysis with insights and recommendations.
"""}
        ]
        
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.3,
            max_tokens=1200
        )
        
        return response.choices[0].message.content
    
    def _generate_recommendations(self, gene_results: GeneSearchResult,
                                 web_results: WebResearchAgentModel) -> List[str]:
        """Generate research recommendations"""
        recommendations = []
        
        if gene_results.genes:
            recommendations.append("Conduct functional validation studies for identified genes")
            recommendations.append("Perform expression analysis in relevant tissues")
        
        if gene_results.gwas_hits:
            recommendations.append("Validate GWAS associations in independent cohorts")
            recommendations.append("Investigate gene-environment interactions")
        
        if gene_results.pathways:
            recommendations.append("Analyze pathway enrichment in relevant biological contexts")
            recommendations.append("Study pathway crosstalk and regulation")
        
        if gene_results.pubmed_summaries:
            recommendations.append("Review recent literature for mechanistic insights")
            recommendations.append("Identify knowledge gaps for future research")
        
        return recommendations
