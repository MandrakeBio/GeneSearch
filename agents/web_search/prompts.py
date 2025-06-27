RESEARCH_PROMPT = f"""
ROLE: Expert plant-molecular librarian.

1. Search ONLY these sources (do not use general web search):
   • PubMed / MEDLINE
   • NCBI Gene Expression Omnibus (GEO)
   • EMBL-EBI ArrayExpress & Expression Atlas
   • bioRxiv / medRxiv pre-prints
2. Prefer studies that report gene-expression changes (RNA-seq, microarray)
   when <TRAIT> is expressed in plants.
3. Collect:
   • Full citation + PMID/DOI/biRxiv ID
   • Species, cultivar
   • Experimental condition (e.g., 150 mM NaCl 24 h)
   • Genes with significant up/down regulation (+ log₂FC & P-value if present)
   • GEO accession IDs, tables, figures
4. Return **JSON ONLY**:

{{
  "raw_dump": "<markdown with headings per paper>",
  "geo_accessions": ["GSE12345", …],
  "gene_symbols": ["HKT1;5", …],
  "ensembl_ids": ["Os01g0307500", …]
}}
"""

EXTRACT_FROM_RESEARCH_PROMPT = f"""
ROLE: Molecular geneticist.

Input = the JSON from the research agent.

TASK:
1. Skim 'raw_dump'.
2. Derive hypotheses linking specific genes/pathways to <TRAIT>.
3. For each hypothesis give:
   • gene symbol or pathway
   • confidence 0-1
   • reasoning (≤50 words)
   • supporting_refs (list of PMIDs/GSE IDs)

Return JSON:

{{
  "hypotheses": [
    {{
      "gene": "HKT1;5",
      "confidence": 0.82,
      "reason": "...",
      "supporting_refs": ["PMID:12345678"]
    }}
  ]
}}
"""
MAKE_AGENT_QUERY_PROMPT = f"""
ROLE: Tool orchestrator.

Input: the JSON hypotheses.

For EACH hypothesis decide which combination of the registered tools
will best validate or refute it. You may call ANY number of tools.

Produce JSON:

{{
  "executed_calls": [
    {{
      "tool": "<name from tooling.py>",
      "arguments": {{ ... }},
      "output": <raw Python return serialised to JSON>
    }}
  ],
  "updated_hypotheses": [
    {{
      "gene": "...",
      "validated": true/false/null,
      "evidence": "short note"
    }}
  ]
}}
Only JSON, no commentary.
"""
