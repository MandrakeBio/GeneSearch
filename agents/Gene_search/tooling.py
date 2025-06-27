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
    params = {
        "db": "pubmed",
        "term": query,
        "retmode": "json",
        "retmax": str(max_hits),
    }
    resp = _get(f"{_PUBMED_BASE}/esearch.fcgi", params=params)
    return resp.json().get("esearchresult", {}).get("idlist", [])


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
# 1.1. BioC PMC API (Enhanced PubMed Central Access)
# -----------------------------------------------------------------------------

_BIOC_PMC_BASE = "https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/pmcoa.cgi"


def bioc_pmc_fetch_article(article_id: str, format_type: str = "json", encoding: str = "unicode") -> Dict[str, Any]:
    """
    Fetch a full-text article from PMC in BioC format.
    
    Args:
        article_id: PubMed ID (e.g., "17299597") or PMC ID (e.g., "PMC1790863")
        format_type: "xml" or "json" (default: "json")
        encoding: "unicode" or "ascii" (default: "unicode")
    
    Returns:
        Full article content in BioC format
    """
    url = f"{_BIOC_PMC_BASE}/BioC_{format_type}/{article_id}/{encoding}"
    resp = _get(url, headers=_HEADERS_JSON)
    data = resp.json()
    
    # BioC API returns a list with one document, so extract the first item
    if isinstance(data, list) and len(data) > 0:
        return data[0]
    elif isinstance(data, dict):
        return data
    else:
        raise ValueError(f"Unexpected response format from BioC API: {type(data)}")


def bioc_pmc_extract_text_content(bioc_article: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract text content from a BioC article.
    
    Args:
        bioc_article: BioC article dictionary
    
    Returns:
        Dictionary with title, abstract, and full text
    """
    try:
        documents = bioc_article.get("documents", [])
        if not documents:
            return {"error": "No documents found in BioC article"}
        
        doc = documents[0]
        passages = doc.get("passages", [])
        
        title = ""
        abstract = ""
        full_text = []
        
        for passage in passages:
            passage_type = passage.get("infons", {}).get("type", "").lower()
            text = passage.get("text", "")
            
            if passage_type == "title":
                title = text
            elif passage_type == "abstract":
                abstract = text
            elif passage_type in ["body", "text"]:
                full_text.append(text)
        
        return {
            "title": title,
            "abstract": abstract,
            "full_text": "\n\n".join(full_text),
            "total_passages": len(passages),
            "has_full_text": len(full_text) > 0
        }
    except Exception as e:
        logger.error(f"Error extracting text from BioC article: {e}")
        return {"error": f"Failed to extract text: {str(e)}"}


def bioc_pmc_search_and_fetch(query: str, max_hits: int = 5) -> List[Dict[str, Any]]:
    """
    Search BioC PMC and fetch full articles.
    
    Args:
        query: Search query
        max_hits: Maximum number of articles to fetch
    
    Returns:
        List of article dictionaries with extracted content
    """
    try:
        # Search for articles
        search_params = {
            "query": query,
            "format": "json",
            "max_results": str(max_hits)
        }
        
        search_response = _get(
            "https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/pmcoa.cgi/BioC_json",
            params=search_params,
            headers=_HEADERS_JSON
        )
        
        if search_response.status_code != 200:
            logger.warning(f"BioC PMC search failed with status {search_response.status_code}")
            return []
        
        # Try to parse the search results
        try:
            search_data = search_response.json()
            articles = search_data.get("articles", [])
        except Exception as e:
            logger.warning(f"Failed to parse BioC PMC search results: {e}")
            return []
        
        results = []
        for article in articles[:max_hits]:
            try:
                pmid = article.get("pmid")
                if pmid:
                    # Fetch full article
                    article_data = bioc_pmc_fetch_article(pmid)
                    if article_data and "error" not in article_data:
                        # Extract text content
                        content = bioc_pmc_extract_text_content(article_data)
                        results.append({
                            "pmid": pmid,
                            "success": True,
                            "content": content
                        })
                    else:
                        results.append({
                            "pmid": pmid,
                            "success": False,
                            "error": article_data.get("error", "Failed to fetch article")
                        })
            except Exception as e:
                logger.warning(f"Could not fetch BioC content for PMID {pmid}: {e}")
                results.append({
                    "pmid": pmid if 'pmid' in locals() else "unknown",
                    "success": False,
                    "error": str(e)
                })
        
        return results
        
    except Exception as e:
        logger.error(f"BioC PMC search and fetch failed: {e}")
        return []

# -----------------------------------------------------------------------------
# 2. Ensembl Plants REST
# -----------------------------------------------------------------------------

_ENSEMBL_REST = "https://rest.ensembl.org"


def ensembl_search_genes(keyword: str, species: str, limit: int = 20) -> List[Dict[str, Any]]:
    species_code = species.replace(" ", "_").lower()
    url = f"{_ENSEMBL_REST}/xrefs/symbol/{species_code}/{keyword}"
    params = {"content-type": "application/json", "limit": str(limit)}
    return _get(url, params=params, headers=_HEADERS_JSON).json()


def ensembl_gene_info(gene_id: str) -> Dict[str, Any]:
    url = f"{_ENSEMBL_REST}/lookup/id/{gene_id}"
    params = {"expand": "1"}
    return _get(url, params=params, headers=_HEADERS_JSON).json()


def ensembl_orthologs(gene_id: str, target_species: Optional[List[str]] = None) -> Dict[str, Any]:
    url = f"{_ENSEMBL_REST}/homology/id/{gene_id}"
    params = {"type": "ortholog", "content-type": "application/json"}
    data = _get(url, params=params, headers=_HEADERS_JSON).json()
    if target_species:
        tslc = {s.lower() for s in target_species}
        hits = []
        for hom in data.get("data", []):
            for h in hom.get("homologies", []):
                if h.get("target", {}).get("species", "").lower() in tslc:
                    hits.append(h)
        return {"gene_id": gene_id, "orthologs": hits}
    return data

# -----------------------------------------------------------------------------
# 3. Gramene Swagger
# -----------------------------------------------------------------------------

_GRAMENE_API = "https://data.gramene.org/v69"


def gramene_trait_search(trait_term: str, limit: int = 30) -> List[Dict[str, Any]]:
    """
    Search Gramene for genes annotated with a given trait term.

    Returns the *full* gene objects (id, symbol, description, species, etc.)
    so the downstream mapper can populate `GeneHit` without guessing.
    """
    try:
        # Try multiple search strategies based on Gramene API documentation
        search_strategies = [
            # 1. Direct trait term search
            {"q": trait_term, "rows": str(limit)},
            # 2. Quoted phrase search
            {"q": f'"{trait_term}"', "rows": str(limit)},
            # 3. Wildcard search for trait-related terms
            {"q": f"*{trait_term.replace(' ', '*')}*", "rows": str(limit)},
            # 4. Boolean search with AND
            {"q": trait_term.replace(" ", " AND "), "rows": str(limit)},
            # 5. Search in description field
            {"q": f'description:"{trait_term}"', "rows": str(limit)},
            # 6. Try individual keywords
            {"q": trait_term.split()[0], "rows": str(limit)},  # First word
            # 7. Search for known salt tolerance genes if trait contains "salt"
            {"q": "HKT1 OR NHX1 OR SOS1 OR SKC1", "rows": str(limit)} if "salt" in trait_term.lower() else None,
        ]
        
        # Filter out None strategies
        search_strategies = [s for s in search_strategies if s is not None]
        
        for i, params in enumerate(search_strategies):
            logger.info(f"Gramene search attempt {i+1}: {params}")
            data = _get(
                f"{_GRAMENE_API}/genes",
                params=params,
                headers=_HEADERS_JSON,
            ).json()
            
            # Log the full response structure for debugging
            logger.info(f"Gramene API response structure: {list(data.keys())}")
            if "response" in data:
                logger.info(f"Response keys: {list(data['response'].keys())}")
                logger.info(f"Total results: {data['response'].get('numFound', 0)}")
            
            results = data.get("response", {}).get("docs", [])
            logger.info(f"Gramene search attempt {i+1} returned {len(results)} results")
            
            if results:
                logger.info(f"First result: {results[0]}")
                return results
        
        # If all strategies fail, return empty list
        logger.warning(f"All Gramene search strategies failed for trait '{trait_term}'")
        return []
        
    except Exception as e:
        logger.warning(f"Gramene API error for trait '{trait_term}': {e}")
        return []  # Return empty list instead of crashing


def gramene_gene_symbol_search(gene_symbols: List[str], limit: int = 30) -> List[Dict[str, Any]]:
    """
    Search Gramene for specific gene symbols that are known to be associated with traits.
    
    This is more reliable than trait-based searches as it uses exact gene symbols.
    """
    try:
        # Create a boolean OR query for multiple gene symbols
        query = " OR ".join(gene_symbols)
        params = {"q": query, "rows": str(limit)}
        
        logger.info(f"Gramene gene symbol search: {params}")
        data = _get(
            f"{_GRAMENE_API}/genes",
            params=params,
            headers=_HEADERS_JSON,
        ).json()
        
        results = data.get("response", {}).get("docs", [])
        logger.info(f"Gramene gene symbol search returned {len(results)} results")
        return results
        
    except Exception as e:
        logger.warning(f"Gramene API error for gene symbols {gene_symbols}: {e}")
        return []


def gramene_gene_lookup(gene_id: str) -> Dict[str, Any]:
    try:
        return _get(f"{_GRAMENE_API}/genes/{gene_id}", headers=_HEADERS_JSON).json()
    except Exception as e:
        logger.warning(f"Gramene API error for gene '{gene_id}': {e}")
        return {}  # Return empty dict instead of crashing


def gramene_prioritized_search(
    gene_symbols: Optional[List[str]] = None,
    stable_ids: Optional[List[str]] = None,
    ontology_codes: Optional[List[str]] = None,
    trait_terms: Optional[List[str]] = None,
    limit: int = 30
) -> List[Dict[str, Any]]:
    """
    Prioritized Gramene search: gene symbols → stable IDs → ontology/annotation codes → trait terms.
    Tries up to 3 searches, combining queries where possible, and returns the first non-empty result.
    """
    try:
        attempts = []
        # 1. Gene symbols
        if gene_symbols:
            attempts.append({"q": " OR ".join(gene_symbols), "rows": str(limit)})
        # 2. Stable IDs
        if stable_ids:
            attempts.append({"q": " OR ".join(stable_ids), "rows": str(limit)})
        # 3. Ontology/annotation codes
        if ontology_codes:
            attempts.append({"q": " OR ".join(ontology_codes), "rows": str(limit)})
        # 4. Trait terms (fallback)
        if trait_terms:
            attempts.append({"q": " OR ".join(trait_terms), "rows": str(limit)})
        
        # Only try up to 3 attempts
        for i, params in enumerate(attempts[:3]):
            logger.info(f"Gramene prioritized search attempt {i+1}: {params}")
            response = _get(
                f"{_GRAMENE_API}/genes",
                params=params,
                headers=_HEADERS_JSON,
            )
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
            
            logger.info(f"Gramene prioritized search attempt {i+1} returned {len(results)} results")
            if results:
                logger.info(f"First result: {results[0]}")
                return results
        logger.warning("All prioritized Gramene search attempts returned no results.")
        return []
    except Exception as e:
        logger.warning(f"Gramene API error in prioritized search: {e}")
        return []

# -----------------------------------------------------------------------------
# 4. GWAS Catalog REST
# -----------------------------------------------------------------------------

_GWAS_API = "https://www.ebi.ac.uk/gwas/rest/api"


def gwas_hits(gene_name: str, pval_threshold: float = 1e-4, max_hits: int = 30) -> List[Dict[str, Any]]:
    params = {
        "gene_name": gene_name,
        "pvalue": str(pval_threshold),
        "size": str(max_hits),
        "sort": "pvalue",
    }
    assoc = _get(f"{_GWAS_API}/associations", params=params, headers=_HEADERS_JSON).json()
    def _strip(a: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "pvalue": a.get("pvalue"),
            "trait": a.get("trait"),
            "pubmed_id": a.get("pubmedId"),
            "variant_id": a.get("variantId"),
        }
    return [_strip(a) for a in assoc.get("_embedded", {}).get("associations", [])]


def gwas_trait_search(trait_term: str, pval_threshold: float = 1e-4, max_hits: int = 30) -> List[Dict[str, Any]]:
    """
    Search GWAS associations by trait term using EFO (Experimental Factor Ontology).
    
    Args:
        trait_term: Trait term to search for (e.g., "diabetes", "obesity")
        pval_threshold: P-value threshold for filtering results
        max_hits: Maximum number of associations to return
    
    Returns:
        List of GWAS associations for the given trait
    """
    try:
        params = {
            "efo_trait": trait_term,
            "pvalue": str(pval_threshold),
            "size": str(max_hits),
            "sort": "pvalue",
        }
        assoc = _get(f"{_GWAS_API}/associations", params=params, headers=_HEADERS_JSON).json()
        def _strip(a: Dict[str, Any]) -> Dict[str, Any]:
            return {
                "pvalue": a.get("pvalue"),
                "trait": a.get("trait"),
                "pubmed_id": a.get("pubmedId"),
                "variant_id": a.get("variantId"),
                "gene_name": a.get("gene_name"),
                "risk_allele": a.get("riskAllele"),
                "odds_ratio": a.get("oddsRatio"),
                "confidence_interval": a.get("confidenceInterval"),
            }
        return [_strip(a) for a in assoc.get("_embedded", {}).get("associations", [])]
    except Exception as e:
        logger.warning(f"GWAS trait search failed for '{trait_term}': {e}")
        return []


def gwas_snp_search(snp_id: str, max_hits: int = 30) -> List[Dict[str, Any]]:
    """
    Search GWAS associations by SNP ID (e.g., rs123456).
    
    Args:
        snp_id: SNP identifier (e.g., "rs123456")
        max_hits: Maximum number of associations to return
    
    Returns:
        List of GWAS associations for the given SNP
    """
    params = {
        "variant_id": snp_id,
        "size": str(max_hits),
        "sort": "pvalue",
    }
    assoc = _get(f"{_GWAS_API}/associations", params=params, headers=_HEADERS_JSON).json()
    def _strip(a: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "pvalue": a.get("pvalue"),
            "trait": a.get("trait"),
            "pubmed_id": a.get("pubmedId"),
            "variant_id": a.get("variantId"),
            "gene_name": a.get("gene_name"),
            "risk_allele": a.get("riskAllele"),
            "odds_ratio": a.get("oddsRatio"),
            "confidence_interval": a.get("confidenceInterval"),
        }
    return [_strip(a) for a in assoc.get("_embedded", {}).get("associations", [])]


def gwas_advanced_search(
    gene_name: Optional[str] = None,
    trait_term: Optional[str] = None,
    snp_id: Optional[str] = None,
    pval_threshold: float = 1e-4,
    max_hits: int = 30
) -> List[Dict[str, Any]]:
    """
    Advanced GWAS search with multiple filter options.
    
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
        params = {
            "size": str(max_hits),
            "sort": "pvalue",
        }
        
        if gene_name:
            params["gene_name"] = gene_name
        if trait_term:
            params["efo_trait"] = trait_term
        if snp_id:
            params["variant_id"] = snp_id
        if pval_threshold:
            params["pvalue"] = str(pval_threshold)
        
        assoc = _get(f"{_GWAS_API}/associations", params=params, headers=_HEADERS_JSON).json()
        def _strip(a: Dict[str, Any]) -> Dict[str, Any]:
            return {
                "pvalue": a.get("pvalue"),
                "trait": a.get("trait"),
                "pubmed_id": a.get("pubmedId"),
                "variant_id": a.get("variantId"),
                "gene_name": a.get("gene_name"),
                "risk_allele": a.get("riskAllele"),
                "odds_ratio": a.get("oddsRatio"),
                "confidence_interval": a.get("confidenceInterval"),
                "study_id": a.get("study", {}).get("accessionId"),
                "study_name": a.get("study", {}).get("publicationInfo", {}).get("title"),
            }
        return [_strip(a) for a in assoc.get("_embedded", {}).get("associations", [])]
    except Exception as e:
        logger.warning(f"GWAS advanced search failed: {e}")
        return []


def gwas_study_info(study_id: str) -> Dict[str, Any]:
    """
    Get detailed information about a GWAS study.
    
    Args:
        study_id: GWAS study accession ID
    
    Returns:
        Detailed study information
    """
    try:
        study = _get(f"{_GWAS_API}/studies/{study_id}", headers=_HEADERS_JSON).json()
        return {
            "study_id": study.get("accessionId"),
            "title": study.get("publicationInfo", {}).get("title"),
            "authors": study.get("publicationInfo", {}).get("authors"),
            "journal": study.get("publicationInfo", {}).get("journal"),
            "pubmed_id": study.get("publicationInfo", {}).get("pubmedId"),
            "doi": study.get("publicationInfo", {}).get("doi"),
            "publication_date": study.get("publicationInfo", {}).get("publicationDate"),
            "trait": study.get("diseaseTrait", {}).get("trait"),
            "sample_size": study.get("initialSampleSize"),
            "replication_sample_size": study.get("replicateSampleSize"),
            "platform": study.get("genotypingTechnology"),
        }
    except Exception as e:
        logger.warning(f"GWAS study info error for study '{study_id}': {e}")
        return {}


def gwas_trait_info(trait_term: str, max_hits: int = 10) -> List[Dict[str, Any]]:
    """
    Search for trait information in the EFO (Experimental Factor Ontology).
    
    Args:
        trait_term: Trait term to search for
        max_hits: Maximum number of traits to return
    
    Returns:
        List of matching traits with their EFO information
    """
    params = {
        "size": str(max_hits),
        "search": trait_term,
    }
    try:
        traits = _get(f"{_GWAS_API}/efoTraits", params=params, headers=_HEADERS_JSON).json()
        return [{
            "trait_id": trait.get("shortForm"),
            "trait_name": trait.get("trait"),
            "description": trait.get("description"),
            "synonyms": trait.get("synonyms", []),
            "parent_traits": [p.get("trait") for p in trait.get("parentTraits", [])],
        } for trait in traits.get("_embedded", {}).get("efoTraits", [])]
    except Exception as e:
        logger.warning(f"GWAS trait info error for trait '{trait_term}': {e}")
        return []

# -----------------------------------------------------------------------------
# 5. QuickGO REST – GO annotations
# -----------------------------------------------------------------------------

_QUICKGO_API = "https://www.ebi.ac.uk/QuickGO/services"


def quickgo_annotations(gene_product_id: str, evidence_codes: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """
    Get GO annotations for a gene product using EBI Proteins API.
    
    Since QuickGO REST API is not publicly accessible, we use the EBI Proteins API
    which provides GO annotations from UniProt and other sources.
    
    Args:
        gene_product_id: UniProt protein ID (e.g., "P12345")
        evidence_codes: List of evidence codes to filter by (e.g., ["EXP", "IDA"]) - not used in this implementation
    
    Returns:
        List of GO annotations
    """
    try:
        # Use EBI Proteins API which provides GO annotations
        response = _get(
            f"https://www.ebi.ac.uk/proteins/api/proteins/{gene_product_id}",
            headers=_HEADERS_JSON
        )
        
        if response.status_code == 200:
            data = response.json()
            annotations = []
            
            # Extract GO annotations from dbReferences
            if 'dbReferences' in data:
                for ref in data['dbReferences']:
                    if ref.get('type') == 'GO':
                        annotation = {
                            'go_id': ref.get('id', ''),
                            'term': ref.get('properties', {}).get('term', ''),
                            'aspect': ref.get('properties', {}).get('term', '')[:1] if ref.get('properties', {}).get('term') else '',
                            'evidence_code': ref.get('properties', {}).get('source', '').split(':')[0] if ref.get('properties', {}).get('source') else '',
                            'reference': ref.get('properties', {}).get('source', ''),
                            'qualifier': ref.get('properties', {}).get('qualifier', '')
                        }
                        annotations.append(annotation)
            
            logger.info(f"Found {len(annotations)} GO annotations for {gene_product_id}")
            return annotations
        else:
            logger.warning(f"EBI Proteins API returned status {response.status_code} for {gene_product_id}")
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
    "bioc_pmc_fetch_article",
    "bioc_pmc_search_and_fetch",
    "bioc_pmc_extract_text_content",
    "ensembl_search_genes",
    "ensembl_gene_info",
    "ensembl_orthologs",
    "gramene_trait_search",
    "gramene_gene_symbol_search",
    "gramene_prioritized_search",
    "gramene_gene_lookup",
    "gwas_hits",
    "gwas_trait_search",
    "gwas_snp_search",
    "gwas_advanced_search",
    "gwas_study_info",
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
    "bioc_pmc_fetch_article": {"function": bioc_pmc_fetch_article},
    "bioc_pmc_search_and_fetch": {"function": bioc_pmc_search_and_fetch},
    "bioc_pmc_extract_text_content": {"function": bioc_pmc_extract_text_content},
    "ensembl_search_genes": {"function": ensembl_search_genes},
    "ensembl_gene_info": {"function": ensembl_gene_info},
    "ensembl_orthologs": {"function": ensembl_orthologs},
    "gramene_trait_search": {"function": gramene_trait_search},
    "gramene_gene_symbol_search": {"function": gramene_gene_symbol_search},
    "gramene_prioritized_search": {"function": gramene_prioritized_search},
    "gramene_gene_lookup": {"function": gramene_gene_lookup},
    "gwas_hits": {"function": gwas_hits},
    "gwas_trait_search": {"function": gwas_trait_search},
    "gwas_snp_search": {"function": gwas_snp_search},
    "gwas_advanced_search": {"function": gwas_advanced_search},
    "gwas_study_info": {"function": gwas_study_info},
    "gwas_trait_info": {"function": gwas_trait_info},
    "quickgo_annotations": {"function": quickgo_annotations},
    "kegg_pathways": {"function": kegg_pathways},
    "kegg_gene_info": {"function": kegg_gene_info},
    "kegg_convert_id": {"function": kegg_convert_id},
}

# End of tooling.py – Mandrake‑GeneSearch
