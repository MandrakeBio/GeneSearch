#!/usr/bin/env python3
"""
Analysis service for GeneSearch
"""

import json
import logging
import os
from typing import Dict, Any, List, Optional, Tuple
from openai import AsyncAzureOpenAI
from .web_search.models import WebResearchAgentModel
from .Gene_search.models import GeneSearchResult

logger = logging.getLogger(__name__)

# Enhanced system prompt for comprehensive analysis
ANALYSIS_PROMPT = """
You are an expert biological data analyst specializing in gene-trait associations and pathway analysis.

Your task is to provide a comprehensive, structured analysis that includes:

1. RESEARCH SUMMARY: Overview of data sources analyzed, key findings, and feasibility assessment
2. EVIDENCE-BASED SECTIONS: Detailed analysis with supporting evidence and references
3. RANKED CANDIDATES: Top genes with scoring rationale and evidence
4. RECOMMENDATIONS: Research priorities and knowledge gaps

Focus on:
- Statistical significance and biological plausibility
- Cross-species conservation and pathway context
- Literature evidence quality and consistency
- Clinical/agricultural implications
- Areas requiring further investigation

Provide detailed references, hyperlinks, and evidence quality assessments.
"""

class AnalysisService:
    """Enhanced service for comprehensive gene-trait analysis"""
    
    def __init__(self, model: str = "gpt-4.1"):
        self.client = AsyncAzureOpenAI(
            api_version="2024-12-01-preview",
            azure_endpoint="https://tanay-mcn037n5-eastus2.cognitiveservices.azure.com/",
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        )
        self.model = model
    
    async def analyze_results(self, 
                            gene_results: GeneSearchResult, 
                            web_results: WebResearchAgentModel) -> str:
        """Generate comprehensive text analysis report"""
        
        import time
        start_time = time.time()
        
        try:
            # Prepare comprehensive data for analysis
            analysis_data = self._prepare_comprehensive_data(gene_results, web_results)
            
            # Generate comprehensive text analysis
            comprehensive_analysis = await self._generate_comprehensive_text_analysis(gene_results, web_results, analysis_data)
            
            # Calculate execution time
            execution_time = time.time() - start_time
            
            # Log execution time for debugging
            logger.info(f"📊 Analysis completed in {execution_time:.2f}s")
            
            return comprehensive_analysis
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Comprehensive analysis failed after {execution_time:.2f}s: {e}")
            raise
    
    async def _generate_comprehensive_text_analysis(self, gene_results: GeneSearchResult,
                                                  web_results: WebResearchAgentModel,
                                                  analysis_data: Dict[str, Any]) -> str:
        """Generate a comprehensive text analysis report"""
        
        # Calculate key metrics
        total_genes = len(gene_results.genes)
        total_literature = len(gene_results.pubmed_summaries)
        total_gwas = len(gene_results.gwas_hits)
        total_pathways = len(gene_results.pathways)
        total_go_annotations = len(gene_results.go_annotations)
        
        # Prepare data sources information
        sources_analyzed = []
        if total_literature > 0:
            sources_analyzed.append(f"PubMed literature ({total_literature} papers)")
        if total_genes > 0:
            ensembl_count = len([g for g in gene_results.genes if g.gene_id.startswith("ENS")])
            if ensembl_count > 0:
                sources_analyzed.append(f"Ensembl gene database ({ensembl_count} genes)")
        if total_gwas > 0:
            sources_analyzed.append(f"GWAS catalog ({total_gwas} associations)")
        if total_pathways > 0:
            sources_analyzed.append(f"Pathway databases ({total_pathways} pathways)")
        if web_results.raw_result:
            sources_analyzed.append("Web research compilation")
        
        # Create gene ranking data
        gene_ranking_data = []
        for gene in gene_results.genes:
            literature_mentions = len([pub for pub in gene_results.pubmed_summaries 
                                     if gene.symbol and gene.symbol.lower() in pub.title.lower() + pub.abstract.lower()])
            
            gwas_support = len([hit for hit in gene_results.gwas_hits 
                               if gene.symbol and gene.symbol.lower() in hit.trait.lower()])
            
            pathway_involvement = len([path for path in gene_results.pathways 
                                     if gene.symbol and gene.symbol.lower() in path.pathway_name.lower()])
            
            go_annotations_count = len([ann for ann in gene_results.go_annotations 
                                       if gene.symbol and gene.symbol.lower() in ann.protein_name.lower()])
            
            # Calculate evidence score
            evidence_score = (literature_mentions * 5) + (gwas_support * 10) + (pathway_involvement * 5) + (go_annotations_count * 2)
            
            gene_ranking_data.append({
                'gene': gene,
                'evidence_score': evidence_score,
                'literature_mentions': literature_mentions,
                'gwas_support': gwas_support,
                'pathway_involvement': pathway_involvement,
                'go_annotations': go_annotations_count
            })
        
        # Sort by evidence score
        gene_ranking_data.sort(key=lambda x: x['evidence_score'], reverse=True)
        
        # Prepare comprehensive analysis prompt
        analysis_prompt = f"""
        Generate a comprehensive, flowing text analysis report for the query: "{gene_results.user_trait}"
        
        DATA OVERVIEW:
        - Data sources analyzed: {', '.join(sources_analyzed)}
        - Total genes identified: {total_genes}
        - Literature references: {total_literature}
        - GWAS associations: {total_gwas}
        - Biological pathways: {total_pathways}
        - GO annotations: {total_go_annotations}
        
        TOP CANDIDATE GENES (ranked by evidence):
        {self._format_gene_ranking_for_prompt(gene_ranking_data[:10])}
        
        LITERATURE EVIDENCE:
        {self._format_literature_for_prompt(gene_results.pubmed_summaries[:10])}
        
        PATHWAY INFORMATION:
        {self._format_pathways_for_prompt(gene_results.pathways[:10])}
        
        GWAS ASSOCIATIONS:
        {self._format_gwas_for_prompt(gene_results.gwas_hits[:10])}
        
        WEB RESEARCH CONTEXT:
        {web_results.raw_result[:1000] if web_results.raw_result else "No additional web research available"}
        
        Generate a comprehensive analysis report that includes:
        
        1. Executive Summary - Brief overview of findings and key insights
        2. Research Scope and Data Quality - Assessment of data sources and coverage
        3. Key Biological Findings - Major discoveries and mechanisms identified
        4. Top Candidate Genes - Detailed analysis of the most promising genes with evidence scores and rationale
        5. Pathway Analysis - Critical biological pathways and their relevance
        6. Literature Evidence - Key research findings and publication quality assessment
        7. Statistical Evidence - GWAS associations and their significance
        8. Knowledge Gaps - Areas requiring further investigation
        9. Research Recommendations - Priorities for future research
        10. Clinical/Agricultural Implications - Practical applications and potential impact
        
        Write this as a flowing, comprehensive text report with proper scientific language, including hyperlinks to relevant databases and references where appropriate. Use markdown formatting for structure and readability.
        
        Include specific gene symbols, pathway names, and statistical measures where available. Provide direct links to:
        - PubMed articles (https://pubmed.ncbi.nlm.nih.gov/PMID)
        - Ensembl genes (https://ensembl.org/Gene/Summary?g=GENE_ID)
        - GWAS catalog (https://www.ebi.ac.uk/gwas/)
        - GO terms (https://www.ebi.ac.uk/QuickGO/term/GO:TERM_ID)
        - KEGG pathways (https://www.genome.jp/kegg-bin/show_pathway?PATH_ID)
        
        Focus on biological plausibility, statistical significance, and practical applications.
        """
        
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": ANALYSIS_PROMPT},
                {"role": "user", "content": analysis_prompt}
            ],
            temperature=0.3,
            max_tokens=4000
        )
        
        return response.choices[0].message.content
    
    def _format_gene_ranking_for_prompt(self, gene_ranking_data: List[Dict]) -> str:
        """Format gene ranking data for the analysis prompt"""
        formatted_genes = []
        for i, gene_data in enumerate(gene_ranking_data, 1):
            gene = gene_data['gene']
            score = gene_data['evidence_score']
            lit = gene_data['literature_mentions']
            gwas = gene_data['gwas_support']
            pathway = gene_data['pathway_involvement']
            go = gene_data['go_annotations']
            
            formatted_genes.append(
                f"{i}. {gene.symbol} ({gene.gene_id}): Evidence Score {score} "
                f"(Literature: {lit}, GWAS: {gwas}, Pathways: {pathway}, GO: {go}) - {gene.description}"
            )
        
        return '\n'.join(formatted_genes) if formatted_genes else "No genes identified"
    
    def _format_literature_for_prompt(self, pubmed_summaries: List) -> str:
        """Format literature data for the analysis prompt"""
        formatted_lit = []
        for pub in pubmed_summaries:
            formatted_lit.append(f"- {pub.title} (PMID: {pub.pmid}): {pub.abstract[:200]}...")
        
        return '\n'.join(formatted_lit) if formatted_lit else "No literature references available"
    
    def _format_pathways_for_prompt(self, pathways: List) -> str:
        """Format pathway data for the analysis prompt"""
        formatted_pathways = []
        for pathway in pathways:
            formatted_pathways.append(f"- {pathway.pathway_name} ({pathway.pathway_id}): {pathway.description}")
        
        return '\n'.join(formatted_pathways) if formatted_pathways else "No pathway information available"
    
    def _format_gwas_for_prompt(self, gwas_hits: List) -> str:
        """Format GWAS data for the analysis prompt"""
        formatted_gwas = []
        for hit in gwas_hits:
            formatted_gwas.append(f"- {hit.trait}: {hit.gene_symbol} (P-value: {hit.p_value}, Effect: {hit.effect_size})")
        
        return '\n'.join(formatted_gwas) if formatted_gwas else "No GWAS associations available"
    
    def _prepare_comprehensive_data(self, gene_results: GeneSearchResult, 
                                   web_results: WebResearchAgentModel) -> Dict[str, Any]:
        """Prepare comprehensive data structure for analysis"""
        from datetime import datetime
        
        return {
            "query": gene_results.user_trait,
            "timestamp": datetime.now().isoformat(),
            "sources_count": {
                "pubmed": len(gene_results.pubmed_summaries),
                "ensembl": len([g for g in gene_results.genes if g.gene_id.startswith("ENS")]),
                "gramene": len([g for g in gene_results.genes if "gramene" in str(g).lower()]),
                "gwas": len(gene_results.gwas_hits),
                "pathways": len(gene_results.pathways),
                "web_research": 1 if web_results.raw_result else 0
            },
            "genes": [gene.model_dump() for gene in gene_results.genes],
            "gwas_hits": [hit.model_dump() for hit in gene_results.gwas_hits],
            "pathways": [path.model_dump() for path in gene_results.pathways],
            "publications": [pub.model_dump() for pub in gene_results.pubmed_summaries],
            "go_annotations": [ann.model_dump() for ann in gene_results.go_annotations],
            "web_research": web_results.model_dump()
        }
    
    async def _generate_research_summary(self, gene_results: GeneSearchResult,
                                        web_results: WebResearchAgentModel,
                                        analysis_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive research summary"""
        
        # Analyze data sources
        sources_analyzed = []
        if analysis_data["sources_count"]["pubmed"] > 0:
            sources_analyzed.append(f"PubMed literature ({analysis_data['sources_count']['pubmed']} papers)")
        if analysis_data["sources_count"]["ensembl"] > 0:
            sources_analyzed.append(f"Ensembl gene database ({analysis_data['sources_count']['ensembl']} genes)")
        if analysis_data["sources_count"]["gwas"] > 0:
            sources_analyzed.append(f"GWAS catalog ({analysis_data['sources_count']['gwas']} associations)")
        if analysis_data["sources_count"]["pathways"] > 0:
            sources_analyzed.append(f"Pathway databases ({analysis_data['sources_count']['pathways']} pathways)")
        if web_results.raw_result:
            sources_analyzed.append("Web research compilation")
        
        # Generate AI summary
        summary_prompt = f"""
        Generate a comprehensive research summary for the query: "{gene_results.user_trait}"
        
        Data Sources Analyzed: {', '.join(sources_analyzed)}
        
        Key Statistics:
        - Genes identified: {len(gene_results.genes)}
        - Literature references: {len(gene_results.pubmed_summaries)}
        - GWAS associations: {len(gene_results.gwas_hits)}
        - Biological pathways: {len(gene_results.pathways)}
        - GO annotations: {len(gene_results.go_annotations)}
        
        Provide:
        1. Overview of research scope and data quality
        2. Key biological findings and mechanisms
        3. Feasibility assessment for trait improvement
        4. Critical knowledge areas identified
        """
        
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": ANALYSIS_PROMPT},
                {"role": "user", "content": summary_prompt}
            ],
            temperature=0.3,
            max_tokens=800
        )
        
        return {
            "overview": response.choices[0].message.content,
            "data_sources": sources_analyzed,
            "scope_metrics": {
                "genes_analyzed": len(gene_results.genes),
                "literature_coverage": len(gene_results.pubmed_summaries),
                "pathway_coverage": len(gene_results.pathways),
                "statistical_evidence": len(gene_results.gwas_hits)
            }
        }
    
    async def _rank_candidate_genes(self, gene_results: GeneSearchResult,
                                   web_results: WebResearchAgentModel) -> List[Dict[str, Any]]:
        """Rank candidate genes with evidence scores and detailed rationale"""
        
        ranked_genes = []
        
        for gene in gene_results.genes:
            # Calculate evidence score
            evidence_score = 0
            evidence_factors = []
            references = []
            
            # Literature support (0-30 points)
            literature_mentions = len([pub for pub in gene_results.pubmed_summaries 
                                     if gene.symbol and gene.symbol.lower() in pub.title.lower() + pub.abstract.lower()])
            lit_score = min(literature_mentions * 5, 30)
            evidence_score += lit_score
            if lit_score > 0:
                evidence_factors.append(f"Literature support: {literature_mentions} publications")
                # Add PubMed references
                for pub in gene_results.pubmed_summaries:
                    if gene.symbol and gene.symbol.lower() in pub.title.lower() + pub.abstract.lower():
                        references.append({
                            "type": "PubMed",
                            "title": pub.title,
                            "pmid": pub.pmid,
                            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pub.pmid}/",
                            "relevance": "Direct gene mention in literature"
                        })
            
            # GWAS associations (0-25 points)
            gwas_hits = [hit for hit in gene_results.gwas_hits 
                        if gene.symbol and gene.symbol.lower() in str(hit).lower()]
            if gwas_hits:
                gwas_score = min(len(gwas_hits) * 10, 25)
                evidence_score += gwas_score
                evidence_factors.append(f"GWAS associations: {len(gwas_hits)} significant hits")
                for hit in gwas_hits:
                    references.append({
                        "type": "GWAS",
                        "trait": getattr(hit, 'trait', 'Unknown'),
                        "p_value": getattr(hit, 'p_value', 'N/A'),
                        "url": f"https://www.ebi.ac.uk/gwas/genes/{gene.symbol}",
                        "relevance": f"Statistical association (p={getattr(hit, 'p_value', 'N/A')})"
                    })
            
            # Pathway involvement (0-20 points)
            pathway_involvement = len([path for path in gene_results.pathways])
            if pathway_involvement > 0:
                path_score = min(pathway_involvement * 5, 20)
                evidence_score += path_score
                evidence_factors.append(f"Pathway involvement: {pathway_involvement} biological pathways")
                for pathway in gene_results.pathways:
                    references.append({
                        "type": "Pathway",
                        "pathway_name": pathway.name,
                        "pathway_id": pathway.pathway_id,
                        "url": f"https://www.kegg.jp/pathway/{pathway.pathway_id}",
                        "relevance": "Functional pathway membership"
                    })
            
            # GO annotations (0-15 points)
            go_annotations = [ann for ann in gene_results.go_annotations 
                            if gene.gene_id and gene.gene_id in str(ann)]
            if go_annotations:
                go_score = min(len(go_annotations) * 3, 15)
                evidence_score += go_score
                evidence_factors.append(f"GO annotations: {len(go_annotations)} functional annotations")
                for ann in go_annotations:
                    references.append({
                        "type": "GO",
                        "go_term": getattr(ann, 'go_term', 'Unknown'),
                        "go_id": getattr(ann, 'go_id', 'Unknown'),
                        "url": f"http://amigo.geneontology.org/amigo/term/{getattr(ann, 'go_id', '')}",
                        "relevance": "Functional annotation"
                    })
            
            # Database presence (0-10 points)
            if gene.gene_id:
                db_score = 10
                evidence_score += db_score
                evidence_factors.append("Confirmed gene database entry")
                if gene.gene_id.startswith("ENS"):
                    references.append({
                        "type": "Ensembl",
                        "gene_id": gene.gene_id,
                        "url": f"https://ensembl.org/id/{gene.gene_id}",
                        "relevance": "Primary gene database record"
                    })
            
            ranked_genes.append({
                "rank": 0,  # Will be set after sorting
                "gene_symbol": gene.symbol or "Unknown",
                "gene_id": gene.gene_id or "Unknown",
                "species": getattr(gene, 'species', 'Unknown'),
                "evidence_score": evidence_score,
                "confidence_level": "High" if evidence_score >= 60 else "Medium" if evidence_score >= 30 else "Low",
                "evidence_factors": evidence_factors,
                "supporting_references": references,
                "functional_description": getattr(gene, 'description', 'No description available'),
                "research_priority": "Critical" if evidence_score >= 70 else "Important" if evidence_score >= 40 else "Moderate"
            })
        
        # Sort by evidence score and assign ranks
        ranked_genes.sort(key=lambda x: x["evidence_score"], reverse=True)
        for i, gene in enumerate(ranked_genes):
            gene["rank"] = i + 1
        
        # Return top 10
        return ranked_genes[:10]
    
    async def _generate_evidence_sections(self, gene_results: GeneSearchResult,
                                         web_results: WebResearchAgentModel,
                                         analysis_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate detailed evidence-based sections"""
        
        sections = {}
        
        # Literature Evidence Section
        if gene_results.pubmed_summaries:
            sections["literature_evidence"] = {
                "summary": f"Analysis of {len(gene_results.pubmed_summaries)} peer-reviewed publications",
                "key_findings": await self._analyze_literature_patterns(gene_results.pubmed_summaries),
                "publication_quality": self._assess_publication_quality(gene_results.pubmed_summaries),
                "references": [
                    {
                        "title": pub.title,
                        "pmid": pub.pmid,
                        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pub.pmid}/",
                        "abstract": pub.abstract[:200] + "..." if len(pub.abstract) > 200 else pub.abstract
                    } for pub in gene_results.pubmed_summaries
                ]
            }
        
        # Genetic Evidence Section
        if gene_results.gwas_hits:
            sections["genetic_evidence"] = {
                "summary": f"Analysis of {len(gene_results.gwas_hits)} GWAS associations",
                "significant_associations": len([h for h in gene_results.gwas_hits if h.p_value < 0.05]),
                "statistical_summary": self._analyze_gwas_statistics(gene_results.gwas_hits),
                "associations": [
                    {
                        "trait": hit.trait,
                        "p_value": hit.p_value,
                        "effect_size": getattr(hit, 'effect_size', 'N/A'),
                        "url": f"https://www.ebi.ac.uk/gwas/variants/{getattr(hit, 'variant_id', '')}"
                    } for hit in gene_results.gwas_hits
                ]
            }
        
        # Pathway Evidence Section
        if gene_results.pathways:
            sections["pathway_evidence"] = {
                "summary": f"Analysis of {len(gene_results.pathways)} biological pathways",
                "pathway_categories": self._categorize_pathways(gene_results.pathways),
                "functional_networks": await self._analyze_pathway_networks(gene_results.pathways),
                "pathways": [
                    {
                        "name": pathway.name,
                        "pathway_id": pathway.pathway_id,
                        "description": pathway.description,
                        "url": f"https://www.kegg.jp/pathway/{pathway.pathway_id}",
                        "gene_count": len([g for g in gene_results.genes])  # Simplified
                    } for pathway in gene_results.pathways
                ]
            }
        
        # Functional Evidence Section
        if gene_results.go_annotations:
            sections["functional_evidence"] = {
                "summary": f"Analysis of {len(gene_results.go_annotations)} functional annotations",
                "go_categories": self._categorize_go_terms(gene_results.go_annotations),
                "functional_summary": await self._analyze_functional_patterns(gene_results.go_annotations),
                "annotations": [
                    {
                        "go_term": ann.go_term,
                        "go_id": ann.go_id,
                        "category": ann.namespace,
                        "url": f"http://amigo.geneontology.org/amigo/term/{ann.go_id}"
                    } for ann in gene_results.go_annotations
                ]
            }
        
        return sections
    
    async def _identify_gaps_and_recommendations(self, gene_results: GeneSearchResult,
                                                web_results: WebResearchAgentModel) -> Dict[str, Any]:
        """Identify knowledge gaps and generate research recommendations"""
        
        gaps = []
        recommendations = []
        
        # Assess data gaps
        if len(gene_results.genes) < 5:
            gaps.append("Limited gene candidates identified - broader search strategies needed")
            recommendations.append("Expand search to include orthologs and related species")
        
        if len(gene_results.gwas_hits) == 0:
            gaps.append("No GWAS associations found - genetic evidence limited")
            recommendations.append("Conduct genome-wide association studies for this trait")
        
        if len(gene_results.pathways) < 3:
            gaps.append("Limited pathway information - functional context unclear")
            recommendations.append("Perform pathway enrichment analysis with expanded gene sets")
        
        # Generate AI-powered recommendations
        rec_prompt = f"""
        Based on the analysis of {gene_results.user_trait}, identify critical research gaps and priorities:
        
        Current Evidence:
        - {len(gene_results.genes)} genes identified
        - {len(gene_results.gwas_hits)} GWAS associations
        - {len(gene_results.pathways)} pathways analyzed
        - {len(gene_results.pubmed_summaries)} publications reviewed
        
        Generate specific, actionable research recommendations focusing on:
        1. Experimental validation priorities
        2. Missing functional studies
        3. Required pathway analysis
        4. Population genetics studies needed
        5. Gene editing feasibility assessment
        """
        
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": ANALYSIS_PROMPT},
                {"role": "user", "content": rec_prompt}
            ],
            temperature=0.3,
            max_tokens=600
        )
        
        ai_recommendations = response.choices[0].message.content.split('\n')
        recommendations.extend([rec.strip() for rec in ai_recommendations if rec.strip()])
        
        return {
            "gaps": gaps,
            "recommendations": recommendations
        }
    
    async def _generate_executive_summary(self, gene_results: GeneSearchResult,
                                         web_results: WebResearchAgentModel) -> str:
        """Generate executive summary"""
        
        summary_prompt = f"""
        Generate an executive summary for {gene_results.user_trait} research analysis:
        
        Key Metrics:
        - Candidate genes: {len(gene_results.genes)}
        - Literature evidence: {len(gene_results.pubmed_summaries)} publications
        - Genetic associations: {len(gene_results.gwas_hits)} GWAS hits
        - Biological pathways: {len(gene_results.pathways)} pathways
        
        Provide a concise executive summary covering:
        1. Overall feasibility assessment
        2. Top genetic targets identified
        3. Strength of evidence
        4. Research readiness level
        5. Key next steps
        """
        
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": ANALYSIS_PROMPT},
                {"role": "user", "content": summary_prompt}
            ],
            temperature=0.3,
            max_tokens=400
        )
        
        return response.choices[0].message.content
    
    # Helper methods for analysis
    def _assess_data_quality(self, gene_results: GeneSearchResult, 
                           web_results: WebResearchAgentModel) -> Dict[str, Any]:
        """Assess overall data quality"""
        quality_score = 0
        factors = []
        
        if len(gene_results.genes) >= 5:
            quality_score += 25
            factors.append("Sufficient gene candidates identified")
        
        if len(gene_results.pubmed_summaries) >= 10:
            quality_score += 25
            factors.append("Strong literature support")
        
        if len(gene_results.gwas_hits) > 0:
            quality_score += 20
            factors.append("Genetic association evidence available")
        
        if len(gene_results.pathways) >= 3:
            quality_score += 15
            factors.append("Adequate pathway coverage")
        
        if web_results.raw_result and len(web_results.raw_result) > 500:
            quality_score += 15
            factors.append("Comprehensive web research")
        
        return {
            "overall_score": quality_score,
            "quality_level": "High" if quality_score >= 70 else "Medium" if quality_score >= 40 else "Low",
            "contributing_factors": factors
        }
    
    def _compile_references(self, gene_results: GeneSearchResult,
                           web_results: WebResearchAgentModel) -> List[Dict[str, Any]]:
        """Compile all references with proper formatting"""
        references = []
        
        # PubMed references
        for pub in gene_results.pubmed_summaries:
            references.append({
                "type": "PubMed",
                "title": pub.title,
                "pmid": pub.pmid,
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pub.pmid}/",
                "citation": f"{pub.title}. PMID: {pub.pmid}"
            })
        
        # Database references
        for gene in gene_results.genes:
            if gene.gene_id and gene.gene_id.startswith("ENS"):
                references.append({
                    "type": "Ensembl",
                    "gene_id": gene.gene_id,
                    "gene_symbol": gene.symbol,
                    "url": f"https://ensembl.org/id/{gene.gene_id}",
                    "citation": f"Ensembl Gene: {gene.symbol} ({gene.gene_id})"
                })
        
        return references
    
    def _calculate_overall_confidence(self, gene_results: GeneSearchResult,
                                    web_results: WebResearchAgentModel) -> float:
        """Calculate overall confidence score (0-100)"""
        score = 0
        
        # Gene evidence weight: 30%
        gene_score = min(len(gene_results.genes) * 5, 30)
        score += gene_score
        
        # Literature weight: 25%
        lit_score = min(len(gene_results.pubmed_summaries) * 2.5, 25)
        score += lit_score
        
        # GWAS weight: 20%
        gwas_score = min(len(gene_results.gwas_hits) * 10, 20)
        score += gwas_score
        
        # Pathway weight: 15%
        path_score = min(len(gene_results.pathways) * 5, 15)
        score += path_score
        
        # Web research weight: 10%
        web_score = 10 if web_results.raw_result and len(web_results.raw_result) > 500 else 5
        score += web_score
        
        return round(score, 1)
    
    # Additional helper methods for detailed analysis
    async def _analyze_literature_patterns(self, publications) -> List[str]:
        """Analyze patterns in literature"""
        patterns = []
        if len(publications) > 0:
            patterns.append(f"Recent research focus: {len(publications)} relevant publications")
            # Add more sophisticated analysis here
        return patterns
    
    def _assess_publication_quality(self, publications) -> Dict[str, Any]:
        """Assess quality of publications"""
        return {
            "total_publications": len(publications),
            "recent_publications": len([p for p in publications if "2020" in str(getattr(p, 'year', '')) or "2021" in str(getattr(p, 'year', '')) or "2022" in str(getattr(p, 'year', '')) or "2023" in str(getattr(p, 'year', '')) or "2024" in str(getattr(p, 'year', ''))]),
            "quality_indicators": ["Peer-reviewed", "Recent publications available"]
        }
    
    def _analyze_gwas_statistics(self, gwas_hits) -> Dict[str, Any]:
        """Analyze GWAS statistics"""
        if not gwas_hits:
            return {"message": "No GWAS data available"}
        
        significant = [h for h in gwas_hits if h.p_value < 0.05]
        return {
            "total_associations": len(gwas_hits),
            "significant_associations": len(significant),
            "significance_rate": len(significant) / len(gwas_hits) if gwas_hits else 0
        }
    
    def _categorize_pathways(self, pathways) -> Dict[str, int]:
        """Categorize pathways by function"""
        categories = {}
        for pathway in pathways:
            category = "General"  # Simplified categorization
            categories[category] = categories.get(category, 0) + 1
        return categories
    
    async def _analyze_pathway_networks(self, pathways) -> List[str]:
        """Analyze pathway networks"""
        return [f"Identified {len(pathways)} relevant biological pathways"]
    
    def _categorize_go_terms(self, go_annotations) -> Dict[str, int]:
        """Categorize GO terms"""
        categories = {}
        for ann in go_annotations:
            category = getattr(ann, 'namespace', 'Unknown')
            categories[category] = categories.get(category, 0) + 1
        return categories
    
    async def _analyze_functional_patterns(self, go_annotations) -> List[str]:
        """Analyze functional patterns in GO annotations"""
        return [f"Analyzed {len(go_annotations)} functional annotations"]
