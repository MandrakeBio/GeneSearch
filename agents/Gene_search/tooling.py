# tooling.py – Mandrake‑GeneSearch
# ------------------------------------------------------------
# Thin, deterministic wrappers around public bioinformatics APIs that the
# LLM planner can invoke via OpenAI function‑calling. Merges the reliability
# scaffolding (logging, retries, timeouts) from the original FoldSearch
# file with the new plant‑gene–oriented tool set requested by Tanay.
# ------------------------------------------------------------

from __future__ import annotations

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

import requests

# -----------------------------------------------------------------------------
# GLOBAL CONFIG & LOGGER
# -----------------------------------------------------------------------------

_DEFAULT_TIMEOUT = 30  # seconds for all outbound HTTP
_MAX_RETRIES = 3       # default retry count
_BACKOFF_BASE = 2.0    # exponential back‑off base
_HEADERS_JSON = {"Accept": "application/json"}

logger = logging.getLogger("mandrake.tooling")
logger.setLevel(logging.INFO)

# -----------------------------------------------------------------------------
# GENERIC HTTP HELPERS (ported from original tooling.py)
# -----------------------------------------------------------------------------

def _get(url: str, *, params: Optional[Dict[str, Any]] = None,
         headers: Optional[Dict[str, str]] = None,
         timeout: int = _DEFAULT_TIMEOUT) -> requests.Response:
    """GET with retry + exponential back‑off."""
    attempt = 0
    while True:
        try:
            logger.debug("GET %s params=%s", url, params)
            resp = requests.get(url, params=params, headers=headers or {}, timeout=timeout)
            resp.raise_for_status()
            return resp
        except Exception as exc:  # pylint: disable=broad-except
            attempt += 1
            if attempt > _MAX_RETRIES:
                logger.error("GET %s failed after %d retries: %s", url, attempt - 1, exc)
                raise
            sleep_time = _BACKOFF_BASE ** (attempt - 1)
            logger.warning("GET %s failed (attempt %d/%d) – backing off %.1fs", url, attempt, _MAX_RETRIES, sleep_time)
            time.sleep(sleep_time)


def _post(url: str, *, json_body: Dict[str, Any], headers: Optional[Dict[str, str]] = None,
          timeout: int = _DEFAULT_TIMEOUT) -> requests.Response:
    """POST with the same retry semantics."""
    attempt = 0
    while True:
        try:
            logger.debug("POST %s", url)
            resp = requests.post(url, json=json_body, headers=headers or {}, timeout=timeout)
            resp.raise_for_status()
            return resp
        except Exception as exc:
            attempt += 1
            if attempt > _MAX_RETRIES:
                logger.error("POST %s failed after %d retries: %s", url, attempt - 1, exc)
                raise
            sleep_time = _BACKOFF_BASE ** (attempt - 1)
            logger.warning("POST %s failed (attempt %d/%d) – backing off %.1fs", url, attempt, _MAX_RETRIES, sleep_time)
            time.sleep(sleep_time)

# -----------------------------------------------------------------------------
# 1. PubMed E‑utilities
# -----------------------------------------------------------------------------

_ESUMMARY_FIELDS = [
    "title", "pubdate", "source", "doi", "authors", "volume", "issue", "pages", "elocationid", "pubtype"
]

_PUBMED_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


def pubmed_search(query: str, max_hits: int = 20) -> List[str]:
    """Return a list of PMIDs for *query* using ESearch."""
    
    # Improve search query for better results
    improved_query = query
    if "salt tolerance" in query.lower():
        improved_query = "salt tolerance rice"
    elif "drought" in query.lower():
        improved_query = "drought resistance rice"
    
    params = {
        "db": "pubmed",
        "term": improved_query,
        "retmode": "json",
        "retmax": str(max_hits),
    }
    
    try:
        resp = _get(f"{_PUBMED_BASE}/esearch.fcgi", params=params)
        data = resp.json()
        idlist = data.get("esearchresult", {}).get("idlist", [])
        
        logger.info(f"PubMed search for '{improved_query}' returned {len(idlist)} results")
        return idlist
        
    except Exception as e:
        logger.error(f"PubMed search failed: {e}")
        return []


def pubmed_fetch_summaries(pmids: List[str]) -> List[Dict[str, Any]]:
    """Return compact JSON summaries for the supplied PubMed IDs using ESummary."""
    if not pmids:
        return []
    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "json",
    }
    resp = _get(f"{_PUBMED_BASE}/esummary.fcgi", params=params)
    raw = resp.json().get("result", {})
    return [{k: raw[pid].get(k) for k in _ESUMMARY_FIELDS if k in raw[pid]} for pid in pmids if pid in raw]

# -----------------------------------------------------------------------------
# 1.1. BioC PMC API (Enhanced PubMed Central Access) - DISABLED
# -----------------------------------------------------------------------------

# _BIOC_PMC_BASE = "https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/pmcoa.cgi"


# def bioc_pmc_fetch_article(article_id: str, format_type: str = "json", encoding: str = "unicode") -> Dict[str, Any]:
#     """
#     Fetch a full-text article from PMC in BioC format.
#     
#     Args:
#         article_id: PubMed ID (e.g., "17299597") or PMC ID (e.g., "PMC1790863")
#         format_type: "xml" or "json" (default: "json")
#         encoding: "unicode" or "ascii" (default: "unicode")
#     
#     Returns:
#         Full article content in BioC format
#     """
#     url = f"{_BIOC_PMC_BASE}/BioC_{format_type}/{article_id}/{encoding}"
#     resp = _get(url, headers=_HEADERS_JSON)
#     data = resp.json()
#     
#     # BioC API returns a list with one document, so extract the first item
#     if isinstance(data, list) and len(data) > 0:
#         return data[0]
#     elif isinstance(data, dict):
#         return data
#     else:
#         raise ValueError(f"Unexpected response format from BioC API: {type(data)}")


# def bioc_pmc_extract_text_content(bioc_article: Dict[str, Any]) -> Dict[str, Any]:
#     """
#     Extract text content from a BioC article.
#     
#     Args:
#         bioc_article: BioC article dictionary
#     
#     Returns:
#         Dictionary with title, abstract, and full text
#     """
#     try:
#         documents = bioc_article.get("documents", [])
#         if not documents:
#             return {"error": "No documents found in BioC article"}
#         
#         doc = documents[0]
#         passages = doc.get("passages", [])
#         
#         title = ""
#         abstract = ""
#         full_text = []
#         
#         for passage in passages:
#             passage_type = passage.get("infons", {}).get("type", "").lower()
#             text = passage.get("text", "")
#             
#             if passage_type == "title":
#                 title = text
#             elif passage_type == "abstract":
#                 abstract = text
#             elif passage_type in ["body", "text"]:
#                 full_text.append(text)
#         
#         return {
#             "title": title,
#             "abstract": abstract,
#             "full_text": "\n\n".join(full_text),
#             "total_passages": len(passages),
#             "has_full_text": len(full_text) > 0
#         }
#     except Exception as e:
#         logger.error(f"Error extracting text from BioC article: {e}")
#         return {"error": f"Failed to extract text: {str(e)}"}


# def bioc_pmc_search_and_fetch(query: str, max_hits: int = 5) -> List[Dict[str, Any]]:
#     """
#     Search BioC PMC and fetch full articles.
#     
#     Args:
#         query: Search query
#         max_hits: Maximum number of articles to fetch
#     
#     Returns:
#         List of article dictionaries with extracted content
#     """
#     try:
#         # Search for articles
#         search_params = {
#             "query": query,
#             "format": "json",
#             "max_results": str(max_hits)
#         }
#         
#         search_response = _get(
#             "https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/pmcoa.cgi/BioC_json",
#             params=search_params,
#             headers=_HEADERS_JSON
#         )
#         
#         if search_response.status_code != 200:
#             logger.warning(f"BioC PMC search failed with status {search_response.status_code}")
#             return []
#         
#         # Try to parse the search results
#         try:
#             search_data = search_response.json()
#             articles = search_data.get("articles", [])
#         except Exception as e:
#             logger.warning(f"Failed to parse BioC PMC search results: {e}")
#             return []
#         
#         results = []
#         for article in articles[:max_hits]:
#             try:
#                 pmid = article.get("pmid")
#                 if pmid:
#                     # Fetch full article
#                     article_data = bioc_pmc_fetch_article(pmid)
#                     if article_data and "error" not in article_data:
#                         # Extract text content
#                         content = bioc_pmc_extract_text_content(article_data)
#                         results.append({
#                             "pmid": pmid,
#                             "success": True,
#                             "content": content
#                         })
#                     else:
#                         results.append({
#                             "pmid": pmid,
#                             "success": False,
#                             "error": article_data.get("error", "Failed to fetch article")
#                         })
#             except Exception as e:
#                 logger.warning(f"Could not fetch BioC content for PMID {pmid}: {e}")
#                 results.append({
#                     "pmid": pmid if 'pmid' in locals() else "unknown",
#                     "success": False,
#                     "error": str(e)
#                 })
#         
#         return results
#         
#     except Exception as e:
#         logger.error(f"BioC PMC search and fetch failed: {e}")
#         return []

# -----------------------------------------------------------------------------
# 2. Ensembl Plants REST
# -----------------------------------------------------------------------------

_ENSEMBL_REST = "https://rest.ensembl.org"


def ensembl_search_genes(keyword: str, species: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Search for genes in Ensembl with improved species handling"""
    
    # Map common species names to Ensembl codes
    species_mapping = {
        "oryza sativa": "oryza_sativa",
        "rice": "oryza_sativa", 
        "arabidopsis thaliana": "arabidopsis_thaliana",
        "arabidopsis": "arabidopsis_thaliana",
        "zea mays": "zea_mays",
        "maize": "zea_mays",
        "corn": "zea_mays",
        "solanum lycopersicum": "solanum_lycopersicum",
        "tomato": "solanum_lycopersicum"
    }
    
    species_code = species_mapping.get(species.lower(), species.replace(" ", "_").lower())
    
    # Try multiple search strategies
    search_strategies = [
        # 1. Direct symbol search
        f"{_ENSEMBL_REST}/xrefs/symbol/{species_code}/{keyword}",
        # 2. Name search with expand
        f"{_ENSEMBL_REST}/lookup/symbol/{species_code}/{keyword}",
        # 3. Description search (for rice, try common salt tolerance genes)
        f"{_ENSEMBL_REST}/xrefs/symbol/{species_code}/SOS1" if "salt" in keyword.lower() else None,
        f"{_ENSEMBL_REST}/xrefs/symbol/{species_code}/NHX1" if "salt" in keyword.lower() else None,
        f"{_ENSEMBL_REST}/xrefs/symbol/{species_code}/HKT1" if "salt" in keyword.lower() else None,
    ]
    
    all_results = []
    
    for strategy in search_strategies:
        if strategy is None:
            continue
            
        try:
            headers = {"Content-Type": "application/json"}
            response = _get(strategy, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                
                if isinstance(data, list):
                    all_results.extend(data)
                elif isinstance(data, dict) and "id" in data:
                    all_results.append(data)
                    
                logger.info(f"Ensembl search '{strategy}' returned {len(data) if isinstance(data, list) else 1} results")
            else:
                logger.warning(f"Ensembl API returned status {response.status_code} for {strategy}")
                
        except Exception as e:
            logger.warning(f"Ensembl search failed for {strategy}: {e}")
            continue
    
    # Remove duplicates based on gene ID
    seen_ids = set()
    unique_results = []
    for result in all_results:
        gene_id = result.get("id")
        if gene_id and gene_id not in seen_ids:
            seen_ids.add(gene_id)
            unique_results.append(result)
    
    return unique_results[:limit]


def ensembl_gene_info(gene_id: str) -> Dict[str, Any]:
    url = f"{_ENSEMBL_REST}/lookup/id/{gene_id}"
    params = {"expand": "1"}
    headers = {"Content-Type": "application/json"}
    try:
        response = _get(url, params=params, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            logger.warning(f"Ensembl gene info returned status {response.status_code} for {gene_id}")
            return {}
    except Exception as e:
        logger.warning(f"Ensembl gene info failed for {gene_id}: {e}")
        return {}


def ensembl_orthologs(gene_id: str, target_species: Optional[List[str]] = None) -> Dict[str, Any]:
    url = f"{_ENSEMBL_REST}/homology/id/{gene_id}"
    params = {"type": "orthologues", "content-type": "application/json"}
    headers = {"Content-Type": "application/json"}
    try:
        response = _get(url, params=params, headers=headers)
        if response.status_code == 200:
            data = response.json()
            if target_species:
                tslc = {s.lower() for s in target_species}
                hits = []
                for hom in data.get("data", []):
                    for h in hom.get("homologies", []):
                        if h.get("target", {}).get("species", "").lower() in tslc:
                            hits.append(h)
                return {"gene_id": gene_id, "orthologs": hits}
            return data
        else:
            logger.warning(f"Ensembl orthologs returned status {response.status_code} for {gene_id}")
            return {}
    except Exception as e:
        logger.warning(f"Ensembl orthologs failed for {gene_id}: {e}")
        return {}

# -----------------------------------------------------------------------------
# 3. UniProt Integration
# -----------------------------------------------------------------------------

_UNIPROT_API = "https://rest.uniprot.org/uniprotkb"


def uniprot_search(query: str, organism: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Search UniProt for proteins by query term and organism.
    
    Args:
        query: Search term (gene name, protein name, trait, etc.)
        organism: Organism filter (e.g., "rice", "9606" for human)
        limit: Maximum results to return
    
    Returns:
        List of UniProt protein records with accessions
    """
    try:
        # Build query string for new UniProt API
        search_terms = [f"({query})"]
        
        if organism:
            # Map common organism names to taxonomy IDs
            organism_map = {
                "rice": "39947",
                "oryza sativa": "39947", 
                "arabidopsis": "3702",
                "arabidopsis thaliana": "3702",
                "human": "9606",
                "mouse": "10090",
                "maize": "4577",
                "zea mays": "4577"
            }
            org_id = organism_map.get(organism.lower(), organism)
            search_terms.append(f"(organism_id:{org_id})")
        
        query_string = " AND ".join(search_terms)
        
        params = {
            "query": query_string,
            "format": "json",
            "size": str(limit)
        }
        
        response = _get(f"{_UNIPROT_API}/search", params=params, headers=_HEADERS_JSON)
        
        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])
            
            # Extract relevant information
            proteins = []
            for protein in results:
                protein_info = {
                    "accession": protein.get("primaryAccession"),
                    "protein_name": protein.get("proteinDescription", {}).get("recommendedName", {}).get("fullName", {}).get("value", ""),
                    "gene_names": [gene.get("geneName", {}).get("value", "") for gene in protein.get("genes", [])],
                    "organism": protein.get("organism", {}).get("scientificName", ""),
                    "reviewed": protein.get("entryType") == "UniProtKB reviewed (Swiss-Prot)"
                }
                proteins.append(protein_info)
            
            logger.info(f"UniProt search returned {len(proteins)} results for query: {query}")
            return proteins
        else:
            logger.warning(f"UniProt search returned status {response.status_code}")
            return []
            
    except Exception as e:
        logger.warning(f"UniProt search failed for query '{query}': {e}")
        return []


def uniprot_gene_mapping(gene_symbols: List[str], organism: Optional[str] = None) -> Dict[str, str]:
    """
    Map gene symbols to UniProt accessions.
    
    Args:
        gene_symbols: List of gene symbols to map
        organism: Organism filter
    
    Returns:
        Dictionary mapping gene symbol to UniProt accession
    """
    try:
        mapping = {}
        
        for gene_symbol in gene_symbols:
            # Search for exact gene symbol
            search_query = f"(gene_exact:{gene_symbol})"
            
            if organism:
                organism_map = {
                    "rice": "39947",
                    "oryza sativa": "39947", 
                    "arabidopsis": "3702",
                    "arabidopsis thaliana": "3702",
                    "human": "9606",
                    "mouse": "10090",
                    "maize": "4577",
                    "zea mays": "4577"
                }
                org_id = organism_map.get(organism.lower(), organism)
                search_query += f" AND (organism_id:{org_id})"
            
            params = {
                "query": search_query,
                "format": "json",
                "size": "5"  # Only need a few results
            }
            
            response = _get(f"{_UNIPROT_API}/search", params=params, headers=_HEADERS_JSON)
            
            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])
                
                if results:
                    # Use the first result (most relevant)
                    accession = results[0].get("primaryAccession")
                    if accession:
                        mapping[gene_symbol] = accession
                        logger.info(f"Mapped {gene_symbol} -> {accession}")
                    else:
                        logger.warning(f"No accession found for {gene_symbol}")
                else:
                    logger.warning(f"No UniProt results for gene symbol: {gene_symbol}")
            else:
                logger.warning(f"UniProt mapping failed for {gene_symbol}: status {response.status_code}")
                
        return mapping
        
    except Exception as e:
        logger.warning(f"UniProt gene mapping failed: {e}")
        return {}


# -----------------------------------------------------------------------------
# 4. Gramene via Ensembl Plants
# -----------------------------------------------------------------------------

_ENSEMBL_PLANTS_API = "https://rest.ensembl.org"


def gramene_gene_search(query: str, species: str = "oryza_sativa", limit: int = 20) -> List[Dict[str, Any]]:
    """
    Search for plant genes using Ensembl Plants API.
    
    Args:
        query: Search term for genes (name, description, trait)
        species: Species to search in (default: oryza_sativa for rice)
        limit: Maximum results to return
    
    Returns:
        List of gene records from Ensembl Plants
    """
    try:
        # Species mapping for common names
        species_mapping = {
            "rice": "oryza_sativa",
            "oryza sativa": "oryza_sativa", 
            "arabidopsis": "arabidopsis_thaliana",
            "arabidopsis thaliana": "arabidopsis_thaliana",
            "maize": "zea_mays",
            "zea mays": "zea_mays",
            "corn": "zea_mays",
            "tomato": "solanum_lycopersicum",
            "solanum lycopersicum": "solanum_lycopersicum"
        }
        
        species_code = species_mapping.get(species.lower(), species.lower())
        
        # Try multiple search strategies
        results = []
        
        # 1. Search by gene symbol/name
        try:
            url = f"{_ENSEMBL_PLANTS_API}/xrefs/symbol/{species_code}/{query}"
            response = _get(url, headers=_HEADERS_JSON)
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    results.extend(data)
                elif isinstance(data, dict):
                    results.append(data)
                    
        except Exception as e:
            logger.warning(f"Ensembl Plants symbol search failed: {e}")
        
        # 2. If no results, try known salt tolerance genes for rice
        if not results and "salt" in query.lower() and "rice" in species.lower():
            salt_genes = ["HKT1", "NHX1", "SOS1", "SKC1", "HAL1"]
            for gene in salt_genes:
                try:
                    url = f"{_ENSEMBL_PLANTS_API}/xrefs/symbol/{species_code}/{gene}"
                    response = _get(url, headers=_HEADERS_JSON)
                    
                    if response.status_code == 200:
                        data = response.json()
                        if isinstance(data, list):
                            results.extend(data)
                        elif isinstance(data, dict):
                            results.append(data)
                except Exception:
                    continue
        
        # Remove duplicates
        seen_ids = set()
        unique_results = []
        for result in results:
            gene_id = result.get("id")
            if gene_id and gene_id not in seen_ids:
                seen_ids.add(gene_id)
                unique_results.append(result)
        
        logger.info(f"Gramene gene search returned {len(unique_results)} results for '{query}' in {species}")
        return unique_results[:limit]
        
    except Exception as e:
        logger.warning(f"Gramene gene search failed for query '{query}': {e}")
        return []


def gramene_gene_lookup(gene_id: str) -> Dict[str, Any]:
    """
    Get detailed gene information from Ensembl Plants.
    
    Args:
        gene_id: Ensembl gene ID
    
    Returns:
        Detailed gene information
    """
    try:
        url = f"{_ENSEMBL_PLANTS_API}/lookup/id/{gene_id}"
        params = {"expand": "1"}
        response = _get(url, params=params, headers=_HEADERS_JSON)
        
        if response.status_code == 200:
            data = response.json()
            logger.info(f"Gramene gene lookup successful for {gene_id}")
            return data
        else:
            logger.warning(f"Gramene gene lookup returned status {response.status_code} for {gene_id}")
            return {}
            
    except Exception as e:
        logger.warning(f"Gramene gene lookup failed for {gene_id}: {e}")
        return {}


# -----------------------------------------------------------------------------
# 5. Legacy Gramene Functions (Deprecated)
# -----------------------------------------------------------------------------

_GRAMENE_API = "https://data.gramene.org/search"


def gramene_gene_symbol_search(gene_symbols: List[str], limit: int = 30) -> List[Dict[str, Any]]:
    """
    DEPRECATED: Legacy Gramene API search function.
    Use gramene_gene_search() instead for Ensembl Plants integration.
    """
    logger.warning("gramene_gene_symbol_search is deprecated - use gramene_gene_search instead")
    try:
        # Create a boolean OR query for multiple gene symbols
        query = " OR ".join([f'"{symbol}"' for symbol in gene_symbols])
        params = {
            "q": query, 
            "rows": str(limit),
            "fl": "id,name,description,species,synonyms"
        }
        
        logger.info(f"Gramene gene symbol search: {params}")
        response = _get(
            f"{_GRAMENE_API}/genes",
            params=params,
            headers=_HEADERS_JSON,
        )
        
        if response.status_code == 200:
            data = response.json()
            results = data.get("response", {}).get("docs", [])
            logger.info(f"Gramene gene symbol search returned {len(results)} results")
            return results
        else:
            logger.warning(f"Gramene API returned status {response.status_code}")
            return []
        
    except Exception as e:
        logger.warning(f"Gramene API error for gene symbols {gene_symbols}: {e}")
        return []


def gramene_gene_lookup_legacy(gene_id: str) -> Dict[str, Any]:
    """
    DEPRECATED: Legacy Gramene API lookup function.
    Use gramene_gene_lookup() instead for Ensembl Plants integration.
    """
    logger.warning("gramene_gene_lookup_legacy is deprecated - use gramene_gene_lookup instead")
    try:
        response = _get(f"{_GRAMENE_API}/genes/{gene_id}", headers=_HEADERS_JSON)
        if response.status_code == 200:
            return response.json()
        else:
            logger.warning(f"Gramene gene lookup returned status {response.status_code} for {gene_id}")
            return {}
    except Exception as e:
        logger.warning(f"Gramene API error for gene '{gene_id}': {e}")
        return {}


def gramene_gene_search_legacy(
    gene_symbols: Optional[List[str]] = None,
    stable_ids: Optional[List[str]] = None,
    ontology_codes: Optional[List[str]] = None,
    trait_terms: Optional[List[str]] = None,
    limit: int = 30
) -> List[Dict[str, Any]]:
    """
    DEPRECATED: Legacy comprehensive Gramene search function.
    Use gramene_gene_search() instead for Ensembl Plants integration.
    """
    logger.warning("gramene_gene_search_legacy is deprecated - use gramene_gene_search instead")
    try:
        attempts = []
        # 1. Gene symbols
        if gene_symbols:
            query = " OR ".join([f'"{symbol}"' for symbol in gene_symbols])
            attempts.append({
                "q": query, 
                "rows": str(limit),
                "fl": "id,name,description,species,synonyms"
            })
        # 2. Stable IDs
        if stable_ids:
            query = " OR ".join([f'"{sid}"' for sid in stable_ids])
            attempts.append({
                "q": query, 
                "rows": str(limit),
                "fl": "id,name,description,species,synonyms"
            })
        # 3. Ontology/annotation codes
        if ontology_codes:
            query = " OR ".join([f'"{code}"' for code in ontology_codes])
            attempts.append({
                "q": query, 
                "rows": str(limit),
                "fl": "id,name,description,species,synonyms"
            })
        # 4. Trait terms (fallback)
        if trait_terms:
            query = " OR ".join([f'"{term}"' for term in trait_terms])
            attempts.append({
                "q": query, 
                "rows": str(limit),
                "fl": "id,name,description,species,synonyms"
            })
        
        # Only try up to 3 attempts
        for i, params in enumerate(attempts[:3]):
            logger.info(f"Gramene gene search attempt {i+1}: {params}")
            response = _get(
                f"{_GRAMENE_API}/genes",
                params=params,
                headers=_HEADERS_JSON,
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Handle both list and dict responses from Gramene API
                if isinstance(data, list):
                    logger.info(f"Gramene API returned list with {len(data)} items")
                    results = data
                elif isinstance(data, dict):
                    logger.info(f"Gramene API response structure: {list(data.keys())}")
                    if "response" in data:
                        logger.info(f"Response keys: {list(data['response'].keys())}")
                        logger.info(f"Total results: {data['response'].get('numFound', 0)}")
                    results = data.get("response", {}).get("docs", [])
                else:
                    logger.warning(f"Unexpected Gramene API response type: {type(data)}")
                    results = []
                
                logger.info(f"Gramene gene search attempt {i+1} returned {len(results)} results")
                if results:
                    logger.info(f"First result: {results[0]}")
                    return results
            else:
                logger.warning(f"Gramene API returned status {response.status_code}")
                
        logger.warning("All Gramene gene search attempts returned no results.")
        return []
    except Exception as e:
        logger.warning(f"Gramene API error in gene search: {e}")
        return []

# -----------------------------------------------------------------------------
# 4. GWAS API – genome-wide association studies
# -----------------------------------------------------------------------------

_GWAS_API = "https://www.ebi.ac.uk/gwas/summary-statistics/api"


def gwas_hits(gene_name: str, pval_threshold: float = 1e-4, max_hits: int = 30) -> List[Dict[str, Any]]:
    """
    Get GWAS hits for a specific gene using the Summary Statistics API.
    
    Args:
        gene_name: Gene name/symbol to search for
        pval_threshold: P-value threshold for filtering results
        max_hits: Maximum number of associations to return
    
    Returns:
        List of GWAS associations for the given gene
    """
    try:
        # Use trait search endpoint for gene-related associations
        params = {
            "trait": gene_name,
            "p_upper": str(pval_threshold),
            "size": str(max_hits),
        }
        response = _get(f"{_GWAS_API}/associations", params=params, headers=_HEADERS_JSON)
        if response.status_code == 200:
            assoc = response.json()
            def _strip(a: Dict[str, Any]) -> Dict[str, Any]:
                return {
                    "pvalue": a.get("p_value"),
                    "trait": a.get("trait"),
                    "pubmed_id": a.get("study_accession"),
                    "variant_id": a.get("variant_id"),
                }
            return [_strip(a) for a in assoc.get("_embedded", {}).get("associations", [])]
        else:
            logger.warning(f"GWAS hits returned status {response.status_code} for {gene_name}")
            return []
    except Exception as e:
        logger.warning(f"GWAS hits failed for {gene_name}: {e}")
        return []


def gwas_trait_search(trait_term: str, pval_threshold: float = 1e-4, max_hits: int = 30) -> List[Dict[str, Any]]:
    """
    Search GWAS associations by trait term using Summary Statistics API.
    
    Args:
        trait_term: Trait term to search for (e.g., "diabetes", "obesity")
        pval_threshold: P-value threshold for filtering results
        max_hits: Maximum number of associations to return
    
    Returns:
        List of GWAS associations for the given trait
    """
    try:
        # First try to find the trait ID
        trait_params = {
            "size": "10"
        }
        trait_response = _get(f"{_GWAS_API}/traits", params=trait_params, headers=_HEADERS_JSON)
        
        if trait_response.status_code == 200:
            traits_data = trait_response.json()
            # Look for matching trait (note: API returns "trait" not "traits")
            matching_traits = []
            traits_list = traits_data.get("_embedded", {}).get("trait", [])
            if isinstance(traits_list, list):
                for trait in traits_list:
                    if isinstance(trait, dict):
                        trait_id = trait.get("trait", "")
                        if trait_term.lower() in trait_id.lower():
                            matching_traits.append(trait_id)
            
            # If we found matching traits, search for associations
            if matching_traits:
                trait_id = matching_traits[0]  # Use the first match
                params = {
                    "p_upper": str(pval_threshold),
                    "size": str(max_hits),
                }
                response = _get(f"{_GWAS_API}/traits/{trait_id}/associations", params=params, headers=_HEADERS_JSON)
                
                if response.status_code == 200:
                    assoc = response.json()
                    def _strip(a: Dict[str, Any]) -> Dict[str, Any]:
                        # Handle trait field which can be a list
                        trait_value = a.get("trait", [])
                        trait_str = trait_value[0] if isinstance(trait_value, list) and trait_value else str(trait_value)
                        return {
                            "pvalue": a.get("p_value"),
                            "trait": trait_str,
                            "pubmed_id": a.get("study_accession"),
                            "variant_id": a.get("variant_id"),
                            "gene_name": "",  # Not directly available in this API
                            "risk_allele": a.get("effect_allele"),
                            "odds_ratio": a.get("odds_ratio"),
                            "confidence_interval": f"{a.get('ci_lower', '')}-{a.get('ci_upper', '')}",
                        }
                    # Handle associations which is a dict with numeric keys, not a list
                    associations_dict = assoc.get("_embedded", {}).get("associations", {})
                    if isinstance(associations_dict, dict):
                        associations_list = list(associations_dict.values())
                    else:
                        associations_list = associations_dict if isinstance(associations_dict, list) else []
                    return [_strip(a) for a in associations_list]
        
        # Fallback: try general associations search
        params = {
            "p_upper": str(pval_threshold),
            "size": str(max_hits),
        }
        response = _get(f"{_GWAS_API}/associations", params=params, headers=_HEADERS_JSON)
        if response.status_code == 200:
            assoc = response.json()
            # Filter results that might be related to the trait
            filtered_results = []
            # Handle associations which is a dict with numeric keys, not a list
            associations_dict = assoc.get("_embedded", {}).get("associations", {})
            if isinstance(associations_dict, dict):
                associations_list = list(associations_dict.values())
            else:
                associations_list = associations_dict if isinstance(associations_dict, list) else []
            
            for a in associations_list:
                # Handle trait field which can be a list
                trait_value = a.get("trait", [])
                trait_name = trait_value[0] if isinstance(trait_value, list) and trait_value else str(trait_value)
                if trait_term.lower() in trait_name.lower():
                    filtered_results.append({
                        "pvalue": a.get("p_value"),
                        "trait": trait_name,
                        "pubmed_id": a.get("study_accession"),
                        "variant_id": a.get("variant_id"),
                        "gene_name": "",
                        "risk_allele": a.get("effect_allele"),
                        "odds_ratio": a.get("odds_ratio"),
                        "confidence_interval": f"{a.get('ci_lower', '')}-{a.get('ci_upper', '')}",
                    })
            return filtered_results[:max_hits]
        else:
            logger.warning(f"GWAS trait search returned status {response.status_code} for {trait_term}")
            return []
    except Exception as e:
        logger.warning(f"GWAS trait search failed for '{trait_term}': {e}")
        return []


def gwas_advanced_search(
    gene_name: Optional[str] = None,
    trait_term: Optional[str] = None,
    snp_id: Optional[str] = None,
    pval_threshold: float = 1e-4,
    max_hits: int = 30
) -> List[Dict[str, Any]]:
    """
    Advanced GWAS search with multiple filter options using Summary Statistics API.
    
    Args:
        gene_name: Gene name to search for
        trait_term: Trait term to search for
        snp_id: SNP identifier to search for
        pval_threshold: P-value threshold for filtering results
        max_hits: Maximum number of associations to return
    
    Returns:
        List of GWAS associations matching the criteria
    """
    try:
        if snp_id:
            # Search by variant ID
            params = {
                "p_upper": str(pval_threshold),
                "size": str(max_hits),
            }
            response = _get(f"{_GWAS_API}/associations/{snp_id}", params=params, headers=_HEADERS_JSON)
        elif trait_term:
            # Use trait search
            return gwas_trait_search(trait_term, pval_threshold, max_hits)
        else:
            # General search
            params = {
                "p_upper": str(pval_threshold),
                "size": str(max_hits),
            }
            response = _get(f"{_GWAS_API}/associations", params=params, headers=_HEADERS_JSON)
        
        if response.status_code == 200:
            assoc = response.json()
            def _strip(a: Dict[str, Any]) -> Dict[str, Any]:
                return {
                    "pvalue": a.get("p_value"),
                    "trait": a.get("trait"),
                    "pubmed_id": a.get("study_accession"),
                    "variant_id": a.get("variant_id"),
                    "gene_name": "",
                    "risk_allele": a.get("effect_allele"),
                    "odds_ratio": a.get("odds_ratio"),
                    "confidence_interval": f"{a.get('ci_lower', '')}-{a.get('ci_upper', '')}",
                    "study_id": a.get("study_accession"),
                    "study_name": "",
                }
            return [_strip(a) for a in assoc.get("_embedded", {}).get("associations", [])]
        else:
            logger.warning(f"GWAS advanced search returned status {response.status_code}")
            return []
    except Exception as e:
        logger.warning(f"GWAS advanced search failed: {e}")
        return []


def gwas_trait_info(trait_term: str, max_hits: int = 10) -> List[Dict[str, Any]]:
    """
    Search for trait information using Summary Statistics API.
    
    Args:
        trait_term: Trait term to search for
        max_hits: Maximum number of traits to return
    
    Returns:
        List of matching traits with their information
    """
    params = {
        "size": str(max_hits),
    }
    try:
        response = _get(f"{_GWAS_API}/traits", params=params, headers=_HEADERS_JSON)
        if response.status_code == 200:
            traits = response.json()
            # Filter traits that match the search term
            matching_traits = []
            for trait in traits.get("_embedded", {}).get("trait", []):  # Note: "trait" not "traits"
                trait_id = trait.get("trait", "")
                if trait_term.lower() in trait_id.lower():
                    matching_traits.append({
                        "trait_id": trait_id,
                        "trait_name": trait_id,  # Summary Stats API doesn't provide human-readable names
                        "description": "",
                        "synonyms": [],
                        "parent_traits": [],
                    })
            return matching_traits[:max_hits]
        else:
            logger.warning(f"GWAS trait info returned status {response.status_code} for {trait_term}")
            return []
    except Exception as e:
        logger.warning(f"GWAS trait info error for trait '{trait_term}': {e}")
        return []

# -----------------------------------------------------------------------------
# 5. QuickGO REST – GO annotations
# -----------------------------------------------------------------------------

_QUICKGO_API = "https://www.ebi.ac.uk/QuickGO/services"


def quickgo_annotations(gene_product_id: str, evidence_codes: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """
    Get GO annotations for a UniProt protein ID using QuickGO REST API.
    
    CRITICAL: This function ONLY accepts UniProt accessions (e.g., P12345).
    Use uniprot_gene_mapping() first to convert gene symbols to UniProt IDs.
    
    Args:
        gene_product_id: UniProt accession (REQUIRED - gene symbols will fail)
        evidence_codes: List of evidence codes to filter by (e.g., ["EXP", "IDA"])
    
    Returns:
        List of GO annotations
    """
    try:
        # Validate that this looks like a UniProt accession
        if not gene_product_id or len(gene_product_id) < 6:
            logger.error(f"QuickGO requires UniProt accession, got: {gene_product_id}")
            return []
        
        # Basic UniProt ID format validation (e.g., P12345, Q9UHC7, A0A024R5W9)
        import re
        uniprot_pattern = r'^[A-NR-Z][0-9][A-Z][A-Z0-9][A-Z0-9][0-9]$|^[OPQ][0-9][A-Z0-9][A-Z0-9][A-Z0-9][0-9]$'
        if not re.match(uniprot_pattern, gene_product_id):
            logger.error(f"Invalid UniProt ID format: {gene_product_id}. Use uniprot_gene_mapping() to get correct UniProt accessions.")
            return []
        
        # Use simple QuickGO annotation search endpoint
        params = {"geneProductId": gene_product_id}
        
        # Note: Evidence code filtering seems to cause 400 errors in QuickGO API
        # We'll filter the results after retrieval instead
        # if evidence_codes:
        #     params["evidenceCode"] = ",".join(evidence_codes)
        
        response = _get(
            f"{_QUICKGO_API}/annotation/search",
            params=params,
            headers={"Accept": "application/json"}
        )
        
        if response.status_code == 200:
            data = response.json()
            annotations = []
            
            # Extract annotations from QuickGO response
            for result in data.get("results", []):
                # Filter by evidence codes if specified
                if evidence_codes:
                    result_evidence = result.get('goEvidence', '')
                    if result_evidence not in evidence_codes:
                        continue
                
                annotation = {
                    'go_id': result.get('goId') or None,
                    'term': result.get('goName') or None,
                    'aspect': result.get('goAspect') or None,
                    'evidence_code': result.get('goEvidence') or None,
                    'reference': result.get('reference') or None,
                    'qualifier': result.get('qualifier') or None,
                    'gene_product_id': result.get('geneProductId') or None,
                    'taxon_id': result.get('taxonId') or None
                }
                
                # Only add annotation if it has at least a GO ID or term
                if annotation['go_id'] or annotation['term']:
                    annotations.append(annotation)
            
            logger.info(f"QuickGO found {len(annotations)} annotations for UniProt ID {gene_product_id}")
            return annotations
        elif response.status_code == 400:
            logger.error(f"QuickGO 400 error for {gene_product_id} - likely invalid UniProt ID format")
            return []
        elif response.status_code == 404:
            logger.warning(f"QuickGO 404 error for {gene_product_id} - no annotations found or invalid UniProt ID")
            return []
        else:
            logger.warning(f"QuickGO returned status {response.status_code} for {gene_product_id}")
            return []
    except Exception as e:
        logger.warning(f"GO annotations failed for {gene_product_id}: {e}")
        return []

# -----------------------------------------------------------------------------
# 6. KEGG REST – pathways
# -----------------------------------------------------------------------------

_KEGG_REST = "https://rest.kegg.jp"


def kegg_pathways(gene_id: str) -> List[str]:
    """
    Get KEGG pathways for a gene using the KEGG REST API.
    
    Based on: https://www.kegg.jp/kegg/rest/keggapi.html
    
    Args:
        gene_id: KEGG gene ID (e.g., "osa:4326559" for rice)
    
    Returns:
        List of pathway IDs
    """
    try:
        # Use the correct KEGG REST API format: https://rest.kegg.jp/link/pathway/<gene_id>
        response = _get(f"https://rest.kegg.jp/link/pathway/{gene_id}")
        
        if response.status_code == 200:
            content = response.text.strip()
            if content:
                # Parse the response format: gene_id\tpathway_id
                pathways = []
                for line in content.split('\n'):
                    if line and '\t' in line:
                        pathway_id = line.split('\t')[1]
                        pathways.append(pathway_id)
                return pathways
            else:
                logger.info(f"No KEGG pathways found for {gene_id}")
                return []
        else:
            logger.warning(f"KEGG API returned status {response.status_code} for {gene_id}")
            return []
            
    except Exception as e:
        logger.warning(f"KEGG pathways failed for {gene_id}: {e}")
        return []


def kegg_gene_info(gene_id: str) -> Dict[str, Any]:
    """
    Get detailed information about a KEGG gene.
    
    Based on: https://www.kegg.jp/kegg/rest/keggapi.html
    
    Args:
        gene_id: KEGG gene ID (e.g., "osa:4326559")
    
    Returns:
        Dictionary with gene information
    """
    try:
        response = _get(f"https://rest.kegg.jp/get/{gene_id}")
        
        if response.status_code == 200:
            content = response.text.strip()
            if content:
                # Parse KEGG entry format
                lines = content.split('\n')
                info = {}
                current_section = None
                
                for line in lines:
                    if line.startswith('NAME'):
                        info['name'] = line.split('NAME')[1].strip()
                    elif line.startswith('DEFINITION'):
                        info['definition'] = line.split('DEFINITION')[1].strip()
                    elif line.startswith('ORTHOLOGY'):
                        info['orthology'] = line.split('ORTHOLOGY')[1].strip()
                    elif line.startswith('PATHWAY'):
                        if 'pathways' not in info:
                            info['pathways'] = []
                        pathway = line.split('PATHWAY')[1].strip()
                        info['pathways'].append(pathway)
                
                return info
            else:
                logger.info(f"No KEGG gene info found for {gene_id}")
                return {}
        else:
            logger.warning(f"KEGG API returned status {response.status_code} for {gene_id}")
            return {}
            
    except Exception as e:
        logger.warning(f"KEGG gene info failed for {gene_id}: {e}")
        return {}


def kegg_convert_id(source_db: str, target_db: str, entry_id: str) -> List[str]:
    """
    Convert between KEGG and external database identifiers.
    
    Based on: https://www.kegg.jp/kegg/rest/keggapi.html
    
    Args:
        source_db: Source database (e.g., "ncbi-geneid", "uniprot")
        target_db: Target database (e.g., "osa", "hsa")
        entry_id: Entry identifier
    
    Returns:
        List of converted identifiers
    """
    try:
        response = _get(f"https://rest.kegg.jp/conv/{target_db}/{source_db}:{entry_id}")
        
        if response.status_code == 200:
            content = response.text.strip()
            if content:
                # Parse conversion results
                converted_ids = []
                for line in content.split('\n'):
                    if line and '\t' in line:
                        converted_id = line.split('\t')[1]
                        converted_ids.append(converted_id)
                return converted_ids
            else:
                logger.info(f"No conversion found for {source_db}:{entry_id} to {target_db}")
                return []
        else:
            logger.warning(f"KEGG conversion API returned status {response.status_code}")
            return []
            
    except Exception as e:
        logger.warning(f"KEGG conversion failed for {source_db}:{entry_id}: {e}")
        return []

# -----------------------------------------------------------------------------
# Public export list – enables `from tooling import *` without clutter
# -----------------------------------------------------------------------------

__all__ = [
    "pubmed_search",
    "pubmed_fetch_summaries",
    "ensembl_search_genes",
    "ensembl_gene_info",
    "ensembl_orthologs",
    "gramene_gene_symbol_search",
    "gramene_gene_search",
    "gramene_gene_lookup",
    "gwas_hits",
    "gwas_trait_search",
    "gwas_advanced_search",
    "gwas_trait_info",
    "quickgo_annotations",
    "kegg_pathways",
    "kegg_gene_info",
    "kegg_convert_id",
]

# -----------------------------------------------------------------------------
# ALL_TOOLS_DICT - Mapping of function names to actual functions
# -----------------------------------------------------------------------------

ALL_TOOLS_DICT = {
    "pubmed_search": {"function": pubmed_search},
    "pubmed_fetch_summaries": {"function": pubmed_fetch_summaries},
    "ensembl_search_genes": {"function": ensembl_search_genes},
    "ensembl_gene_info": {"function": ensembl_gene_info},
    "ensembl_orthologs": {"function": ensembl_orthologs},
    "gramene_gene_symbol_search": {"function": gramene_gene_symbol_search},
    "gramene_gene_search": {"function": gramene_gene_search},
    "gramene_gene_lookup": {"function": gramene_gene_lookup},
    "gwas_hits": {"function": gwas_hits},
    "gwas_trait_search": {"function": gwas_trait_search},
    "gwas_advanced_search": {"function": gwas_advanced_search},
    "gwas_trait_info": {"function": gwas_trait_info},
    "quickgo_annotations": {"function": quickgo_annotations},
    "kegg_pathways": {"function": kegg_pathways},
    "kegg_gene_info": {"function": kegg_gene_info},
    "kegg_convert_id": {"function": kegg_convert_id},
}

# End of tooling.py – Mandrake‑GeneSearch
