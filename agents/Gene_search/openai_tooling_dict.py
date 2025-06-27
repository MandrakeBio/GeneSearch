# Mandrake‑GeneSearch – OpenAI function‑calling manifest
# ------------------------------------------------------
# Each tool is a thin, deterministic wrapper around a public bioinformatics
# API that helps identify candidate genes underlying plant traits.
# The schema strictly follows the pattern expected by the OpenAI `tools=`
# parameter.

TOOLING_DICT = {
    "tools": [
        {
            "type": "function",
            "function": {
                "name": "pubmed_search",
                "description": (
                    "Search the PubMed database (NCBI E‑utilities ESearch) for plant‑biology "
                    "or trait‑relevant literature and return a list of PubMed IDs (PMIDs) "
                    "ordered by relevance."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Full‑text Boolean query or MeSH terms, e.g. 'salt tolerance rice gene'."
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
                            "description": "Search query for PubMed, e.g. 'salt tolerance rice gene'."
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
                    "Look up Ensembl Plant gene identifiers and basic metadata using the "
                    "xrefs/symbol endpoint. Accepts a species name (latin binomial) and a "
                    "gene symbol or keyword."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "keyword": {"type": "string", "description": "Gene symbol or free keyword."},
                        "species": {"type": "string", "description": "Latin binomial, e.g. 'Oryza sativa'."},
                        "limit": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 50,
                            "default": 20,
                            "description": "Maximum number of matching genes to return."
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
                    "across one or more target plant species."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "gene_id": {"type": "string", "description": "Reference Ensembl gene ID."},
                        "target_species": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional list of latin‑binomial species codes. Empty = all available plants.",
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
                "name": "gramene_trait_search",
                "description": (
                    "Search the Gramene Genes endpoint for plant genes annotated with a given "
                    "trait keyword or TO term and return matching Ensembl IDs."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "trait_term": {
                            "type": "string",
                            "description": "Trait keyword or Trait Ontology (TO) term, e.g. 'TO:0006001' or 'salt tolerance'."
                        },
                        "limit": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 100,
                            "default": 30,
                            "description": "Max genes to return."
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
                    "Search Gramene for specific gene symbols that are known to be associated with traits. "
                    "This is more reliable than trait-based searches as it uses exact gene symbols."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "gene_symbols": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of gene symbols to search for, e.g. ['HKT1', 'NHX1', 'SOS1'] for salt tolerance genes."
                        },
                        "limit": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 100,
                            "default": 30,
                            "description": "Max genes to return."
                        }
                    },
                    "required": ["gene_symbols"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "gramene_gene_lookup",
                "description": (
                    "Retrieve full Gramene record (genome, description, traits) for a specific "
                    "Ensembl gene ID."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "gene_id": {"type": "string", "description": "Ensembl gene ID recognised by Gramene."}
                    },
                    "required": ["gene_id"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "gwas_hits",
                "description": (
                    "Query the GWAS Catalog REST API for trait associations involving a gene "
                    "name (preferred) or genomic region (chr‑start‑end) in plants. Returns p‑value, trait, and PMID."
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
                            "description": "Trait term to search for (e.g., 'diabetes', 'obesity', 'salt tolerance')."
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
                            "description": "Trait term to search for (optional)."
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
                            "description": "Trait term to search for (e.g., 'diabetes', 'obesity')."
                        },
                        "max_hits": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 50,
                            "default": 10,
                            "description": "Maximum number of traits to return."
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
                    "Fetch Gene Ontology annotations for a UniProt or Ensembl gene product via "
                    "QuickGO, restricted to Experimental evidence by default."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "gene_product_id": {
                            "type": "string",
                            "description": "UniProt accession or Ensembl protein ID."
                        },
                        "evidence_codes": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional list of GO evidence codes (e.g. 'IDA','IMP'). Empty = EXP‑only.",
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
                            "description": "KEGG gene entry ID, e.g. 'osa:4326559' for rice genes."
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
                "name": "gramene_prioritized_search",
                "description": (
                    "Prioritized Gramene search: gene symbols → stable IDs → ontology/annotation codes → trait terms. "
                    "Tries up to 3 searches, combining queries where possible, and returns the first non-empty result."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "gene_symbols": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of gene symbols to search for, e.g. ['HKT1', 'NHX1', 'SOS1'] for salt tolerance genes."
                        },
                        "stable_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of stable Ensembl or Gramene gene IDs, e.g. ['AT3G52430', 'Os01g0100100']."
                        },
                        "ontology_codes": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of ontology or annotation codes, e.g. ['GO:0006814', 'TO:0006001', 'IPR001138']."
                        },
                        "trait_terms": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of trait terms, e.g. ['salt tolerance', 'drought resistance']."
                        },
                        "limit": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 100,
                            "default": 30,
                            "description": "Max genes to return."
                        }
                    },
                    "required": []
                }
            }
        }
    ]
}
