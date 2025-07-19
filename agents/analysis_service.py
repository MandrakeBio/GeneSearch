#!/usr/bin/env python3
"""
Analysis service for GeneSearch
"""

import json
import logging
import os
from typing import Dict, Any, List, Optional, Iterator
from openai import AzureOpenAI
from dotenv import load_dotenv
from .web_search.models import WebResearchAgentModel
from .Gene_search.models import GeneSearchResult

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)

# System prompt for analysis
ANALYSIS_PROMPT = """
You are an expert biological data analyst specializing in gene-trait associations and pathway analysis.

Your task is to analyze gene search results and web research findings to provide a comprehensive scientific analysis.

Format your response with:
1. **Executive Summary** - Brief overview of findings
2. **Gene Rankings** - Ranked list of genes with evidence
3. **Key Findings** - Important discoveries from the analysis
4. **Biological Insights** - Mechanistic explanations
5. **Recommendations** - Actionable next steps

Use the following formatting guidelines:
- Put important terms and gene names in "quotes" for bold formatting
- Include clickable links in this format: [Link Text](URL)
- Use clear headers and bullet points
- Provide scientific explanations that are accessible

Focus on:
- Strength of association evidence (GWAS, literature, functional studies)
- Biological plausibility of mechanisms
- Cross-species conservation and validation
- Pathway involvement and network effects
- Clinical or agricultural relevance

Provide clear, scientifically sound explanations with proper citations and links.
"""

class AnalysisService:
    """Service for analyzing gene search and web research results"""
    
    def __init__(self, model: str = "o4-mini"):
        # Azure OpenAI configuration
        self.endpoint = "https://tanay-mcn037n5-eastus2.cognitiveservices.azure.com/"
        self.deployment = "o4-mini"
        self.api_version = "2024-12-01-preview"
        
        self.client = AzureOpenAI(
            api_version=self.api_version,
            azure_endpoint=self.endpoint,
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        )
        self.model = model
    
    def stream_analysis(self, 
                       gene_results: GeneSearchResult, 
                       web_results: WebResearchAgentModel) -> Iterator[str]:
        """Stream analysis output directly from the AI"""
        
        try:
            logger.info(f"Starting streaming analysis for trait: {gene_results.user_trait}")
            
            # Prepare comprehensive data for analysis
            analysis_data = self._prepare_analysis_data(gene_results, web_results)
            
            messages = [
                {"role": "system", "content": ANALYSIS_PROMPT},
                {"role": "user", "content": f"""
Analyze the following research data for the trait: {gene_results.user_trait}

Gene Search Results:
- Total genes found: {len(gene_results.genes)}
- GWAS associations: {len(gene_results.gwas_hits)}
- Publications: {len(gene_results.pubmed_summaries)}
- Pathways: {len(gene_results.pathways)}

Gene Details:
{json.dumps(analysis_data['gene_summaries'], indent=2)}

Web Research Context:
{web_results.raw_result[:2000]}...

Research Papers Found:
{json.dumps(analysis_data['research_papers'], indent=2)}

Please provide a comprehensive analysis with proper formatting:
- Use "quotes" around important terms and gene names for bold formatting
- Include clickable links where relevant using [Text](URL) format
- Structure your response with clear headers
- Provide scientific explanations and biological insights
- Include specific recommendations for gene editing or therapeutic targeting

Focus on practical applications and actionable insights.
"""}
            ]
            
            # Stream the response
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=messages,
                max_completion_tokens=2000,
                stream=True  # Enable streaming
            )
            
            # Yield each chunk as it arrives
            for chunk in response:
                if chunk.choices and len(chunk.choices) > 0 and chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            logger.error(f"Streaming analysis failed: {e}")
            yield f"Error in analysis: {str(e)}"
    
    def _prepare_analysis_data(self, gene_results: GeneSearchResult, 
                              web_results: WebResearchAgentModel) -> Dict[str, Any]:
        """Prepare comprehensive data for analysis"""
        
        # Prepare gene summaries
        gene_summaries = []
        for gene in gene_results.genes:
            gene_name = gene.symbol or gene.gene_id
            
            # Find associated evidence
            gwas_evidence = [hit for hit in gene_results.gwas_hits 
                           if hasattr(hit, 'gene_name') and hit.gene_name and 
                           gene_name.lower() in hit.gene_name.lower()]
            
            pub_evidence = [pub for pub in gene_results.pubmed_summaries 
                          if gene_name.lower() in pub.title.lower() or 
                          (pub.abstract and gene_name.lower() in pub.abstract.lower())]
            
            pathway_evidence = [path for path in gene_results.pathways 
                              if path.description and gene_name.lower() in path.description.lower()]
            
            gene_summary = {
                "gene_name": gene_name,
                "gene_id": gene.gene_id,
                "species": gene.species,
                "description": gene.description,
                "gwas_hits": len(gwas_evidence),
                "publications": len(pub_evidence),
                "pathways": len(pathway_evidence),
                "ensembl_link": f"https://www.ensembl.org/Multi/Search/Results?q={gene_name}",
                "ncbi_link": f"https://www.ncbi.nlm.nih.gov/gene/?term={gene_name}",
                "uniprot_link": f"https://www.uniprot.org/uniprot/?query={gene_name}&sort=score",
                "genecards_link": f"https://www.genecards.org/cgi-bin/carddisp.pl?gene={gene_name}" if gene.species == "homo_sapiens" else None
            }
            gene_summaries.append(gene_summary)
        
        # Prepare research papers summary
        research_papers = []
        try:
            if hasattr(web_results, 'research_paper') and web_results.research_paper:
                if hasattr(web_results.research_paper, 'search_result') and web_results.research_paper.search_result:
                    for paper in web_results.research_paper.search_result[:10]:  # Top 10 papers
                        research_papers.append({
                            "title": getattr(paper, 'title', 'No title'),
                            "url": getattr(paper, 'url', ''),
                            "abstract": getattr(paper, 'abstract', '')[:200] + "..." if len(getattr(paper, 'abstract', '')) > 200 else getattr(paper, 'abstract', '')
                        })
        except Exception as e:
            logger.warning(f"Error processing research papers: {e}")
            research_papers = []
        
        return {
            "gene_summaries": gene_summaries,
            "research_papers": research_papers,
            "trait": gene_results.user_trait
        }
    
    def analyze_results(self, 
                            gene_results: GeneSearchResult, 
                            web_results: WebResearchAgentModel) -> Dict[str, Any]:
        """Analyze combined results from gene search and web research"""
        
        try:
            logger.info(f"Starting analysis for trait: {gene_results.user_trait}")
            logger.info(f"Gene results: {len(gene_results.genes)} genes, {len(gene_results.gwas_hits)} GWAS hits")
            
            # Rank genes by priority
            ranked_genes = self._rank_genes_by_priority(gene_results, web_results)
            logger.info(f"Ranked genes: {len(ranked_genes)} genes ranked")
            
            # Generate analysis summary
            analysis_summary = self._generate_analysis_summary(gene_results, web_results)
            logger.info("Analysis summary generated")
            
            # Create final result
            result = {
                "ranked_genes": ranked_genes,
                "analysis_summary": analysis_summary,
                "sources_analyzed": self._get_sources_summary(gene_results, web_results)
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            raise
    
    def _rank_genes_by_priority(self, gene_results: GeneSearchResult, 
                                    web_results: WebResearchAgentModel) -> List[Dict[str, Any]]:
        """Rank genes by priority based on evidence and relevance"""
        
        if not gene_results.genes:
            logger.info("No genes found in gene_results, returning empty rankings")
            return []
        
        # Prepare gene data with associated evidence
        gene_data = []
        for gene in gene_results.genes:
            # Find associated GWAS hits
            gene_name = gene.symbol or gene.gene_id
            gwas_evidence = [hit for hit in gene_results.gwas_hits 
                           if hasattr(hit, 'gene_name') and hit.gene_name and 
                           gene_name.lower() in hit.gene_name.lower()]
            
            # Find associated publications
            pub_evidence = [pub for pub in gene_results.pubmed_summaries 
                          if gene_name.lower() in pub.title.lower() or 
                          gene_name.lower() in pub.abstract.lower() if pub.abstract]
            
            # Find associated pathways
            pathway_evidence = [path for path in gene_results.pathways 
                              if gene_name.lower() in path.description.lower() if path.description]
            
            gene_data.append({
                "gene": gene,
                "gwas_hits": gwas_evidence,
                "publications": pub_evidence,
                "pathways": pathway_evidence
            })
        
        # Use AI to rank genes and generate hypotheses
        ranked_genes = self._generate_gene_rankings(gene_data, gene_results.user_trait, web_results)
        
        return ranked_genes
    
    def _generate_gene_rankings(self, gene_data: List[Dict], trait: str, 
                                    web_results: WebResearchAgentModel) -> List[Dict[str, Any]]:
        """Generate AI-powered gene rankings with hypotheses"""
        
        # Prepare data for AI analysis
        gene_summaries = []
        for data in gene_data:
            gene = data["gene"]
            gene_name = gene.symbol or gene.gene_id
            summary = {
                "gene_name": gene_name,
                "gene_id": gene.gene_id,
                "species": gene.species,
                "description": gene.description,
                "gwas_hits": len(data["gwas_hits"]),
                "publications": len(data["publications"]),
                "pathways": len(data["pathways"]),
                "gwas_details": [{"trait": hit.trait, "p_value": getattr(hit, 'pvalue', None)} 
                               for hit in data["gwas_hits"][:3]],  # Top 3 GWAS hits
                "pub_titles": [pub.title for pub in data["publications"][:3]]  # Top 3 publications
            }
            gene_summaries.append(summary)
        
        messages = [
            {"role": "system", "content": ANALYSIS_PROMPT},
            {"role": "user", "content": f"""
Rank the following genes by their relevance to the trait: {trait}

Gene Data:
{json.dumps(gene_summaries, indent=2)}

Web Research Context:
{web_results.raw_result[:1000]}...

Please rank these genes from highest to lowest priority and provide:
1. Gene name and priority ranking
2. Key evidence supporting the association
3. Biological hypothesis explaining why this gene makes sense for the trait
4. Confidence level in the association

Return as a JSON array with this structure:
[
  {{
    "gene_name": "GENE1",
    "priority_rank": 1,
    "evidence_summary": "Key evidence points...",
    "biological_hypothesis": "Explanation of mechanism...",
    "confidence": "High/Medium/Low"
  }}
]
"""}
        ]
        
        response = self.client.chat.completions.create(
            model=self.deployment,
            messages=messages,
            max_completion_tokens=1500,
            stream=False  # Disable streaming for now
        )
        
        # Get response content
        full_response = response.choices[0].message.content
        
        try:
            # Try to extract JSON from the response
            import re
            json_match = re.search(r'\[.*\]', full_response, re.DOTALL)
            if json_match:
                ai_rankings = json.loads(json_match.group())
            else:
                ai_rankings = json.loads(full_response)
        except Exception as e:
            logger.warning(f"Failed to parse AI rankings JSON: {e}")
            logger.warning(f"AI response: {full_response[:500]}...")
            # Fallback: create rankings from gene data
            ai_rankings = []
            for i, data in enumerate(gene_data):
                gene_name = data["gene"].symbol or data["gene"].gene_id
                ai_rankings.append({
                    "gene_name": gene_name,
                    "priority_rank": i + 1,
                    "evidence_summary": f"Gene identified through database search with {len(data['publications'])} publications and {len(data['gwas_hits'])} GWAS hits",
                    "biological_hypothesis": f"Potential involvement in {trait} based on database evidence and literature support",
                    "confidence": "Medium"
                })
        
        # Combine AI rankings with detailed evidence
        final_rankings = []
        for ranking in ai_rankings:
            gene_name = ranking.get("gene_name", "")
            
            # Find the original gene data
            original_data = next((data for data in gene_data 
                                if (data["gene"].symbol or data["gene"].gene_id) == gene_name), None)
            
            if original_data:
                gene_info = {
                    "gene_name": gene_name,
                    "priority_rank": ranking.get("priority_rank", 0),
                    "evidence_summary": ranking.get("evidence_summary", ""),
                    "biological_hypothesis": ranking.get("biological_hypothesis", ""),
                    "confidence": ranking.get("confidence", "Medium"),
                    "references": self._format_references(original_data),
                    "hyperlinks": self._generate_hyperlinks(original_data["gene"]),
                    "detailed_evidence": {
                        "gwas_associations": len(original_data["gwas_hits"]),
                        "literature_support": len(original_data["publications"]),
                        "pathway_involvement": len(original_data["pathways"])
                    }
                }
                final_rankings.append(gene_info)
        
        return final_rankings
    
    def _format_references(self, gene_data: Dict) -> List[Dict[str, str]]:
        """Format references for a gene"""
        references = []
        
        # Add GWAS references
        for hit in gene_data["gwas_hits"][:5]:  # Top 5 GWAS hits
            references.append({
                "type": "GWAS",
                "description": f"GWAS association: {hit.trait}",
                "details": f"P-value: {getattr(hit, 'p_value', 'N/A')}"
            })
        
        # Add publication references
        for pub in gene_data["publications"][:5]:  # Top 5 publications
            references.append({
                "type": "Literature",
                "description": pub.title,
                "details": f"PMID: {pub.pmid}"
            })
        
        # Add pathway references
        for pathway in gene_data["pathways"][:3]:  # Top 3 pathways
            references.append({
                "type": "Pathway",
                "description": pathway.name,
                "details": f"ID: {pathway.pathway_id}"
            })
        
        return references
    
    def _generate_hyperlinks(self, gene) -> Dict[str, str]:
        """Generate relevant hyperlinks for a gene"""
        links = {}
        
        if gene.gene_id:
            # Ensembl link
            if gene.species == "homo_sapiens":
                links["Ensembl"] = f"https://www.ensembl.org/Homo_sapiens/Gene/Summary?g={gene.gene_id}"
            else:
                links["Ensembl"] = f"https://www.ensembl.org/Multi/Search/Results?q={gene.gene_id}"
        
        gene_name = gene.symbol or gene.gene_id
        if gene_name:
            # NCBI Gene link
            links["NCBI_Gene"] = f"https://www.ncbi.nlm.nih.gov/gene/?term={gene_name}"
            
            # UniProt link
            links["UniProt"] = f"https://www.uniprot.org/uniprot/?query={gene_name}&sort=score"
            
            # GeneCards link (for human genes)
            if gene.species == "homo_sapiens":
                links["GeneCards"] = f"https://www.genecards.org/cgi-bin/carddisp.pl?gene={gene_name}"
        
        return links
    
    def _generate_analysis_summary(self, gene_results: GeneSearchResult,
                                       web_results: WebResearchAgentModel) -> str:
        """Generate comprehensive analysis summary"""
        
        messages = [
            {"role": "system", "content": "You are a scientific analyst summarizing gene research results."},
            {"role": "user", "content": f"""
Provide a concise summary of the analysis performed for the trait: {gene_results.user_trait}

Data analyzed:
- {len(gene_results.genes)} genes identified
- {len(gene_results.gwas_hits)} GWAS associations found
- {len(gene_results.pubmed_summaries)} scientific publications reviewed
- {len(gene_results.pathways)} biological pathways identified

Web research summary:
{web_results.raw_result[:500]}...

Provide a 2-3 paragraph summary of what was analyzed and the overall findings.
"""}
        ]
        
        response = self.client.chat.completions.create(
            model=self.deployment,
            messages=messages,
            max_completion_tokens=400
        )
        
        return response.choices[0].message.content
    
    def _get_sources_summary(self, gene_results: GeneSearchResult,
                           web_results: WebResearchAgentModel) -> Dict[str, Any]:
        """Get summary of sources analyzed"""
        return {
            "databases_searched": [
                "Ensembl Genome Database",
                "GWAS Catalog",
                "PubMed Literature Database", 
                "KEGG Pathway Database",
                "QuickGO Gene Ontology"
            ],
            "total_genes_found": len(gene_results.genes),
            "total_publications": len(gene_results.pubmed_summaries),
            "total_gwas_hits": len(gene_results.gwas_hits),
            "total_pathways": len(gene_results.pathways),
            "web_sources": len(web_results.sources) if hasattr(web_results, 'sources') else 0,
            "query_analyzed": gene_results.user_trait
        }
