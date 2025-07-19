# Mandrake‑GeneSearch – OpenAI function‑calling manifest
# ------------------------------------------------------
# Each tool is a thin, deterministic wrapper around a public bioinformatics
# API that helps identify biological entities and mechanisms for any biological question.
# The schema strictly follows the pattern expected by the OpenAI `tools=`
# parameter.

TOOLING_DICT = {
    "tools": [
        {
            "type": "function",
            "function": {
                "name": "pubmed_search",
                "description": (
                    "Search the PubMed database (NCBI E‑utilities ESearch) for biological "
                    "literature and return a list of PubMed IDs (PMIDs) "
                    "ordered by relevance."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Full‑text Boolean query or MeSH terms, e.g. 'drought response mechanisms' or 'cancer pathway analysis'."
                        },
                        "max_hits": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 50,
                            "default": 20,
                            "description": "Maximum number of PMIDs to return."
                        }
                    },
                    "required": ["query"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "pubmed_fetch_summaries",
                "description": (
                    "Retrieve concise JSON summaries (NCBI E‑utilities ESummary) for a list "
                    "of PubMed IDs so the agent can extract titles, abstracts and journal info."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pmids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1,
                            "maxItems": 50,
                            "description": "List of PubMed IDs to summarise."
                        }
                    },
                    "required": ["pmids"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "bioc_pmc_fetch_article",
                "description": (
                    "Fetch a full-text article from PubMed Central (PMC) Open Access in BioC format. "
                    "This provides access to complete article content including full text, not just summaries. "
                    "BioC is a structured format designed for text mining and information extraction."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "article_id": {
                            "type": "string",
                            "description": "PubMed ID (e.g., '17299597') or PMC ID (e.g., 'PMC1790863')."
                        },
                        "format_type": {
                            "type": "string",
                            "enum": ["json", "xml"],
                            "default": "json",
                            "description": "Output format: 'json' (recommended) or 'xml'."
                        },
                        "encoding": {
                            "type": "string",
                            "enum": ["unicode", "ascii"],
                            "default": "unicode",
                            "description": "Text encoding: 'unicode' (recommended) or 'ascii'."
                        }
                    },
                    "required": ["article_id"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "bioc_pmc_search_and_fetch",
                "description": (
                    "Search PubMed for articles and fetch full-text content for PMC Open Access articles. "
                    "This combines PubMed search with BioC content retrieval, providing full-text access "
                    "when available, with fallback to regular PubMed summaries for non-PMC articles."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query for PubMed, e.g. 'drought response mechanisms' or 'cancer pathway analysis'."
                        },
                        "max_hits": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 10,
                            "default": 5,
                            "description": "Maximum number of articles to fetch (limited due to full-text processing)."
                        }
                    },
                    "required": ["query"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "bioc_pmc_extract_text_content",
                "description": (
                    "Extract readable text content from BioC format article. "
                    "Converts the structured BioC format into human-readable text with title, abstract, and full text."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "bioc_article": {
                            "type": "object",
                            "description": "Article in BioC format (output from bioc_pmc_fetch_article)."
                        }
                    },
                    "required": ["bioc_article"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "ensembl_search_genes",
                "description": (
                    "Look up Ensembl gene identifiers and basic metadata using the "
                    "xrefs/symbol endpoint. Accepts a species name (latin binomial) and a "
                    "gene symbol or keyword."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "keyword": {"type": "string", "description": "Gene symbol, protein name, or biological keyword."},
                        "species": {"type": "string", "description": "Latin binomial, e.g. 'Oryza sativa'."},
                        "limit": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 50,
                            "default": 20,
                            "description": "Maximum number of matching biological entities to return."
                        }
                    },
                    "required": ["keyword", "species"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "ensembl_gene_info",
                "description": (
                    "Fetch detailed Ensembl metadata (lookup/id?expand=1) for a single "
                    "Ensembl gene ID – genomic coordinates, transcripts, biotype, etc."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "gene_id": {"type": "string", "description": "Stable Ensembl gene identifier."}
                    },
                    "required": ["gene_id"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "ensembl_orthologs",
                "description": (
                    "Retrieve ortholog information (homology/id) for a given Ensembl gene ID "
                    "across one or more target species."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "gene_id": {"type": "string", "description": "Reference Ensembl gene ID."},
                        "target_species": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional list of latin‑binomial species codes. Empty = all available species.",
                            "default": []
                        }
                    },
                    "required": ["gene_id"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "uniprot_search",
                "description": (
                    "Search UniProt for proteins by query term and organism. "
                    "Returns protein records with accessions that can be used for QuickGO annotations."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search term (gene name, protein name, biological process, etc.)."
                        },
                        "organism": {
                            "type": "string",
                            "description": "Organism filter (e.g., 'human', 'mouse', 'drosophila', 'rice')."
                        },
                        "limit": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 100,
                            "default": 20,
                            "description": "Maximum results to return."
                        }
                    },
                    "required": ["query"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "uniprot_gene_mapping",
                "description": (
                    "Map gene symbols to UniProt accessions. CRITICAL: Use this function first "
                    "before calling quickgo_annotations as QuickGO only accepts UniProt accessions."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "gene_symbols": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of gene symbols to map to UniProt accessions."
                        },
                        "organism": {
                            "type": "string",
                            "description": "Organism filter (e.g., 'rice', 'arabidopsis', 'human')."
                        }
                    },
                    "required": ["gene_symbols"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "gramene_gene_search",
                "description": (
                    "Search for genes using Ensembl API. "
                    "Supports species-specific searches and biological process-based fallbacks."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search term for genes (name, description, biological process)."
                        },
                        "species": {
                            "type": "string",
                            "default": "homo_sapiens",
                            "description": "Species to search in (e.g., 'homo_sapiens' for human, 'mus_musculus' for mouse, 'oryza_sativa' for rice)."
                        },
                        "limit": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 100,
                            "default": 20,
                            "description": "Maximum results to return."
                        }
                    },
                    "required": ["query"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "gramene_gene_lookup",
                "description": (
                    "Get detailed gene information from Ensembl API. "
                    "Provides comprehensive gene metadata including coordinates and transcripts."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "gene_id": {"type": "string", "description": "Ensembl gene ID."}
                    },
                    "required": ["gene_id"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "gramene_trait_search",
                "description": (
                    "DEPRECATED: Legacy Gramene trait search. Use gramene_gene_search instead for "
                    "better gene discovery via Ensembl integration."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "trait_term": {
                            "type": "string",
                            "description": "Biological process or phenotype term, e.g. 'drought response' or 'cancer progression'."
                        },
                        "limit": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 100,
                            "default": 30,
                            "description": "Max biological entities to return."
                        }
                    },
                    "required": ["trait_term"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "gramene_gene_symbol_search",
                "description": (
                    "DEPRECATED: Legacy Gramene gene symbol search. Use gramene_gene_search instead "
                    "for better results via Ensembl integration."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "gene_symbols": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of gene symbols to search for, e.g. ['TP53', 'BRCA1', 'EGFR'] for cancer-related genes."
                        },
                        "limit": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 100,
                            "default": 30,
                            "description": "Max biological entities to return."
                        }
                    },
                    "required": ["gene_symbols"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "gwas_hits",
                "description": (
                    "Query the GWAS Catalog REST API for trait associations involving a gene "
                    "name (preferred) or genomic region (chr‑start‑end). Returns p‑value, trait, and PMID."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "gene_name": {"type": "string", "description": "Official gene symbol (case insensitive)."},
                        "pval_threshold": {
                            "type": "number",
                            "minimum": 0,
                            "default": 1e-4,
                            "description": "Return only associations with p‑value below this cutoff."
                        },
                        "max_hits": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 100,
                            "default": 30,
                            "description": "Maximum number of associations to return."
                        }
                    },
                    "required": ["gene_name"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "gwas_trait_search",
                "description": (
                    "Search GWAS associations by trait term using EFO (Experimental Factor Ontology). "
                    "Useful when you have a trait but no specific gene name."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "trait_term": {
                            "type": "string",
                            "description": "Trait term to search for (e.g., 'diabetes', 'obesity', 'cancer')."
                        },
                        "pval_threshold": {
                            "type": "number",
                            "minimum": 0,
                            "default": 1e-4,
                            "description": "Return only associations with p‑value below this cutoff."
                        },
                        "max_hits": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 100,
                            "default": 30,
                            "description": "Maximum number of associations to return."
                        }
                    },
                    "required": ["trait_term"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "gwas_snp_search",
                "description": (
                    "Search GWAS associations by SNP ID (e.g., rs123456). "
                    "Useful when working with specific genetic variants."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "snp_id": {
                            "type": "string",
                            "description": "SNP identifier (e.g., 'rs123456')."
                        },
                        "max_hits": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 100,
                            "default": 30,
                            "description": "Maximum number of associations to return."
                        }
                    },
                    "required": ["snp_id"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "gwas_advanced_search",
                "description": (
                    "Advanced GWAS search with multiple filter options. "
                    "Can search by gene name, trait term, and/or SNP ID simultaneously."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "gene_name": {
                            "type": "string",
                            "description": "Gene name to search for (optional)."
                        },
                        "trait_term": {
                            "type": "string",
                            "description": "Biological process or phenotype term to search for (optional)."
                        },
                        "snp_id": {
                            "type": "string",
                            "description": "SNP identifier to search for (optional)."
                        },
                        "pval_threshold": {
                            "type": "number",
                            "minimum": 0,
                            "default": 1e-4,
                            "description": "Return only associations with p‑value below this cutoff."
                        },
                        "max_hits": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 100,
                            "default": 30,
                            "description": "Maximum number of associations to return."
                        }
                    },
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "gwas_study_info",
                "description": (
                    "Get detailed information about a GWAS study by its accession ID. "
                    "Provides publication details, sample sizes, and study metadata."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "study_id": {
                            "type": "string",
                            "description": "GWAS study accession ID (e.g., 'GCST000001')."
                        }
                    },
                    "required": ["study_id"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "gwas_trait_info",
                "description": (
                    "Search for trait information in the EFO (Experimental Factor Ontology). "
                    "Helps find standardized trait terms and their relationships."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "trait_term": {
                            "type": "string",
                            "description": "Biological process or phenotype term to search for (e.g., 'diabetes', 'cancer')."
                        },
                        "max_hits": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 50,
                            "default": 10,
                            "description": "Maximum number of biological processes to return."
                        }
                    },
                    "required": ["trait_term"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "quickgo_annotations",
                "description": (
                    "Fetch Gene Ontology annotations for a UniProt protein ID via QuickGO. "
                    "CRITICAL: ONLY accepts UniProt accessions (e.g., P12345). "
                    "Must use uniprot_gene_mapping() first to convert gene symbols to UniProt IDs."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "gene_product_id": {
                            "type": "string",
                            "description": "UniProt accession ONLY (e.g., 'P12345', 'Q9UHC7'). Gene symbols will fail."
                        },
                        "evidence_codes": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional list of GO evidence codes (e.g. 'IDA','IMP'). Empty = all evidence.",
                            "default": []
                        }
                    },
                    "required": ["gene_product_id"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "kegg_pathways",
                "description": (
                    "Return KEGG pathways linked to a gene using the 'link pathway/genes' REST "
                    "operation so the agent can place the gene in metabolic context."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "gene_id": {"type": "string", "description": "KEGG gene entry ID, e.g. 'osa:4326559'."}
                    },
                    "required": ["gene_id"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "kegg_gene_info",
                "description": (
                    "Get detailed information about a KEGG gene including name, definition, "
                    "orthology, and associated pathways using the KEGG REST API."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "gene_id": {
                            "type": "string", 
                            "description": "KEGG gene entry ID, e.g. 'hsa:7157' for human genes."
                        }
                    },
                    "required": ["gene_id"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "kegg_convert_id",
                "description": (
                    "Convert between KEGG and external database identifiers using the KEGG REST API. "
                    "Useful for mapping between different gene ID systems."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "source_db": {
                            "type": "string",
                            "description": "Source database (e.g., 'ncbi-geneid', 'uniprot', 'hsa')."
                        },
                        "target_db": {
                            "type": "string", 
                            "description": "Target database (e.g., 'osa', 'hsa', 'ncbi-geneid')."
                        },
                        "entry_id": {
                            "type": "string",
                            "description": "Entry identifier to convert."
                        }
                    },
                    "required": ["source_db", "target_db", "entry_id"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "gramene_gene_search_legacy",
                "description": (
                    "DEPRECATED: Legacy comprehensive Gramene search function. "
                    "Use gramene_gene_search instead for Ensembl integration."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "gene_symbols": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of gene symbols to search for, e.g. ['TP53', 'BRCA1', 'EGFR'] for cancer-related genes."
                        },
                        "stable_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of stable Ensembl gene IDs, e.g. ['ENSG00000141510', 'ENSG00000139618']."
                        },
                        "ontology_codes": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of ontology or annotation codes, e.g. ['GO:0006814', 'TO:0006001', 'IPR001138']."
                        },
                        "trait_terms": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of biological processes, e.g. ['cancer progression', 'immune response']."
                        },
                        "limit": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 100,
                            "default": 30,
                            "description": "Max biological entities to return."
                        }
                    },
                    "required": []
                }
            }
        }
    ]
}
