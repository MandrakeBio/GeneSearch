# Trait‑Discovery API Documentation

A FastAPI web service that combines literature mining with automated gene‑trait validation through a three‑agent pipeline (research → hypothesis → validation). It replaces the legacy protein‑centric FoldSearch API.

---

## Table of Contents

* [System Architecture](#system-architecture)
* [Workflow](#workflow)
* [API Endpoints](#api-endpoints)
* [Response Models](#response-models)
* [Quick‑Start](#quick-start)
* [Client Examples](#client-examples)

---

## System Architecture

```
┌────────────────┐   ┌────────────────────┐   ┌───────────────────┐
│  FastAPI app   │→  │ Literature Agent    │→  │ Gene Pipeline      │
│  (main.py)     │   │ (WebResearchAgent) │   │ (3 internal agents │
│                │   │                    │   │  – research / hypo │
│ • REST layer   │   │ • PubMed / GEO     │   │   / validation)    │
│ • Swagger UI   │   │ • Up‑to‑date papers│   │ • Bioinformatics   │
└────────────────┘   └────────────────────┘   └───────────────────┘
```

*All heavy computation runs in a thread‑pool so the API remains responsive.*

---

## Workflow

1. **Web search** – harvests papers, expression studies, and GEO IDs.
2. **Hypothesis generation** – ranks genes/pathways linked to the trait.
3. **Validation** – unlimited tool calls (Ensembl, KEGG, GO, GWAS) to confirm or refute each hypothesis.
4. **Analysis** – GPT‑4o synthesises an executive markdown report.

---

## API Endpoints

| Method | Path           | Description                                      |
| ------ | -------------- | ------------------------------------------------ |
| POST   | `/web-search`  | Literature agent only. Fast (5‑15 s).            |
| POST   | `/gene-search` | Full gene pipeline (research → validation).      |
| POST   | `/search`      | Combined: literature + gene pipeline + analysis. |
| GET    | `/health`      | Liveness probe.                                  |
| GET    | `/`            | API metadata & docs link.                        |

### Example request (`/search`)

```json
{
  "query": "salt tolerance in rice",
  "include_web": true,
  "include_gene": true
}
```

---

## Bioinformatics Tooling

Below are the wrapper functions exposed in **`tooling.py`** and available to the Validation Agent. They are language‑agnostic HTTP/REST helpers, so you can replicate them in other clients if needed.

| Tool name              | Primary source    | Key arguments                           | Typical use                                     | Notes                                                     |
| ---------------------- | ----------------- | --------------------------------------- | ----------------------------------------------- | --------------------------------------------------------- |
| `ensembl_search_genes` | Ensembl REST      | `keyword:str`, `species:str \| None`    | Get initial gene IDs by free‑text               | 1‑1 mapping with Ensembl `/xrefs/symbol/:species/:symbol` |
| `gramene_trait_search` | Gramene API v1    | `trait_term:str`, `limit:int`           | Discover genes annotated with the queried trait | Returns full gene dicts, not just IDs                     |
| `ensembl_gene_info`    | Ensembl REST      | `ensembl_id:str`                        | Chromosome, coords, description                 | Used for each top candidate                               |
| `ensembl_orthologs`    | Ensembl REST      | `ensembl_id:str`, `species:str \| None` | Expand to cross‑species orthologs               | Filters high‑confidence orthologues only                  |
| `gramene_gene_lookup`  | Gramene API       | `gene_id:str`                           | Extra metadata (taxon, symbol)                  | Complements Ensembl fields                                |
| `kegg_pathways`        | KEGG REST         | `gene_id:str`                           | Pathway IDs (`map04075`, …)                     | Splitline‑safe wrapper fixes newline bug                  |
| `go_annotations`       | QuickGO           | `ensembl_id:str`                        | Molecular‑function & biological‑process terms   | Cached for 1 day in Redis                                 |
| `gwas_hits`            | GWAS Catalog REST | `ensembl_id:str`                        | Associated phenotypes, p‑values                 | Filtered for plants only                                  |

*All tools return raw JSON so downstream agents can merge evidence or expose it through `TraitAnalysis.evidence_map`.*

---

## Response Models

### `CombinedSearchResult`

```python
class CombinedSearchResult(BaseModel):
    query: str
    tool_results: Dict[str, Any]
    trait_analysis: TraitAnalysis | None
    search_type: Literal["web", "gene", "web+gene"]
    success: bool
    total_execution_time: float
```

### `TraitAnalysis`

Markdown summary **plus** evidence map for drill‑down.

```python
class TraitAnalysis(BaseModel):
    analysis_markdown: str          # executive summary
    top_hits: List[str]             # validated genes
    open_questions: List[str]       # inconclusive genes
    evidence_map: Dict[str, List[ExecutedCall]]
```

---

## Quick‑Start

```bash
pip install -r requirements.txt  # fastapi, uvicorn, openai, tiktoken, bleach, backoff
export OPENAI_API_KEY="sk‑…"
uvicorn main:app --reload        # localhost:8000/docs
```

### Smoke test

```bash
curl -X POST http://127.0.0.1:8000/search \
     -H "Content-Type: application/json" \
     -d '{"query":"salt tolerance in rice"}' | jq '.trait_analysis.top_hits'
```

---

## Client Examples

### Python

```python
import requests
resp = requests.post("http://localhost:8000/search", json={"query":"salt tolerance in rice"})
print(resp.json()["trait_analysis"]["analysis_markdown"])
```

### Typescript (fetch)

```ts
const res = await fetch("/search", {
  method: "POST",
  headers: {"Content-Type": "application/json"},
  body: JSON.stringify({query: "drought resistance maize"})
});
const data = await res.json();
console.log(data.trait_analysis.top_hits);
```

---

## Changelog

* **v2.0** – Switch from protein‑centric FoldSearch to gene‑centric trait discovery. Removes `/protein-search`, adds `/gene-search`, new response models, full evidence traceability.
