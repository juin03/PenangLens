"""
RAG Indexer for PenangLens Agent.

Handles:
- Embedding landmark/POI content using gemini-embedding-001
- Upserting text chunks into Azure AI Search (penang-text-index)
- Hybrid search (vector + BM25) for RAG context retrieval
- Deleting spots from the index on unpublish/delete
"""

import os
import logging
import numpy as np
from typing import Optional
from dotenv import load_dotenv

from google import genai
from google.genai import types as genai_types
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex, SimpleField, SearchField, SearchableField,
    SearchFieldDataType, VectorSearch, HnswAlgorithmConfiguration,
    VectorSearchProfile, SemanticConfiguration, SemanticSearch,
    SemanticPrioritizedFields, SemanticField,
)
from azure.search.documents.models import VectorizedQuery, QueryType

load_dotenv()
logger = logging.getLogger("penang_agent.indexer")

# ── Config ────────────────────────────────────────────────────────────────────
AZURE_ENDPOINT  = os.getenv("AZURE_SEARCH_ENDPOINT", "")
AZURE_KEY       = os.getenv("AZURE_SEARCH_KEY", "")
TEXT_INDEX_NAME = os.getenv("AZURE_TEXT_INDEX_NAME", "penang-text-index")
GEMINI_API_KEY  = os.getenv("GOOGLE_API_KEY", "")
EMBED_MODEL     = "gemini-embedding-001"
DIM_768         = 768
DIM_256         = 256

# ── Gemini client (lazy singleton) ────────────────────────────────────────────
_gemini_client: Optional[genai.Client] = None

def _get_gemini():
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    return _gemini_client


def _normalize(vec: list[float]) -> list[float]:
    """L2-normalize a vector. Required for sub-3072-d MRL embeddings."""
    arr = np.array(vec, dtype=np.float32)
    norm = np.linalg.norm(arr)
    if norm == 0:
        return vec
    return (arr / norm).tolist()


def _embed(text: str, task_type: str, dim: int) -> list[float]:
    """
    Generate a single normalized embedding using gemini-embedding-001.

    Args:
        text: The text to embed.
        task_type: 'RETRIEVAL_DOCUMENT' (indexing) or 'RETRIEVAL_QUERY' (search).
        dim: Output dimension — 768 or 256.
    """
    client = _get_gemini()
    result = client.models.embed_content(
        model=EMBED_MODEL,
        contents=text,
        config=genai_types.EmbedContentConfig(
            task_type=task_type,
            output_dimensionality=dim,
        ),
    )
    vector = result.embeddings[0].values
    return _normalize(vector)  # must normalize for dim < 3072


# ── Azure Search helpers ──────────────────────────────────────────────────────
def _get_index_client() -> SearchIndexClient:
    return SearchIndexClient(AZURE_ENDPOINT, AzureKeyCredential(AZURE_KEY))


def _get_search_client() -> SearchClient:
    return SearchClient(AZURE_ENDPOINT, TEXT_INDEX_NAME, AzureKeyCredential(AZURE_KEY))


def ensure_text_index_exists():
    """
    Create the penang-text-index if it doesn't already exist.
    Schema: id, spotId, spotType, name, section, content, tags, vector_768, vector_256.
    Uses HNSW for vector fields and BM25+semantic for keyword fields.
    """
    idx_client = _get_index_client()

    try:
        idx_client.get_index(TEXT_INDEX_NAME)
        logger.info(f"Index '{TEXT_INDEX_NAME}' already exists.")
        return
    except Exception:
        pass  # Doesn't exist yet — create it

    logger.info(f"Creating index '{TEXT_INDEX_NAME}'...")

    fields = [
        SimpleField(name="id",       type=SearchFieldDataType.String, key=True, filterable=True),
        SimpleField(name="spotId",   type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="spotType", type=SearchFieldDataType.String, filterable=True),
        SearchableField(name="name",    type=SearchFieldDataType.String, analyzer_name="en.microsoft"),
        SimpleField( name="section", type=SearchFieldDataType.String, filterable=True),
        SearchableField(name="content", type=SearchFieldDataType.String, analyzer_name="en.microsoft"),
        SearchField(
            name="tags",
            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
            searchable=True, filterable=True,
        ),
        SearchField(
            name="vector_768",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=DIM_768,
            vector_search_profile_name="hnsw-768",
        ),
        SearchField(
            name="vector_256",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=DIM_256,
            vector_search_profile_name="hnsw-256",
        ),
    ]

    vector_search = VectorSearch(
        algorithms=[
            HnswAlgorithmConfiguration(name="hnsw-algo"),
        ],
        profiles=[
            VectorSearchProfile(name="hnsw-768", algorithm_configuration_name="hnsw-algo"),
            VectorSearchProfile(name="hnsw-256", algorithm_configuration_name="hnsw-algo"),
        ],
    )

    semantic = SemanticSearch(configurations=[
        SemanticConfiguration(
            name="default",
            prioritized_fields=SemanticPrioritizedFields(
                title_field=SemanticField(field_name="name"),
                content_fields=[SemanticField(field_name="content")],
                keywords_fields=[SemanticField(field_name="tags")],
            ),
        )
    ])

    index = SearchIndex(
        name=TEXT_INDEX_NAME,
        fields=fields,
        vector_search=vector_search,
        semantic_search=semantic,
    )
    idx_client.create_index(index)
    logger.info(f"Index '{TEXT_INDEX_NAME}' created successfully.")


# ── Content chunking ──────────────────────────────────────────────────────────
def _build_chunks(spot: dict) -> list[dict]:
    """
    Build indexable text chunks from a spot dict.
    Each chunk becomes one document in Azure AI Search.

    spot dict keys: id, name, type, description, tags (list[str]),
                    searchPrompts (list[str], POI only), parentLandmarkName (POI only)
    """
    spot_id   = spot.get("id", "")
    spot_type = spot.get("type", "")          # 'landmark' | 'poi'
    name      = spot.get("name", "")
    desc      = spot.get("description", "")
    tags      = spot.get("tags", [])
    prompts   = spot.get("searchPrompts", [])
    parent    = spot.get("parentLandmarkName", "")

    chunks = []

    # Chunk 1 — Overview (rich content, best for general questions)
    overview_parts = [f"{name} is a {'landmark' if spot_type == 'landmark' else 'point of interest'} in Penang, Malaysia."]
    if desc:
        overview_parts.append(desc)
    if parent:
        overview_parts.append(f"It belongs to {parent}.")

    chunks.append({
        "id":       f"{spot_id}_overview",
        "spotId":   spot_id,
        "spotType": spot_type,
        "name":     name,
        "section":  "overview",
        "content":  " ".join(overview_parts),
        "tags":     tags,
    })

    # Chunk 2 — Tags & categories (helps filter-style queries)
    if tags or prompts:
        tag_text_parts = []
        if tags:
            tag_text_parts.append(f"{name} is categorized as: {', '.join(tags)}.")
        if prompts:
            tag_text_parts.append(f"Visual features include: {', '.join(prompts)}.")
        chunks.append({
            "id":       f"{spot_id}_tags",
            "spotId":   spot_id,
            "spotType": spot_type,
            "name":     name,
            "section":  "tags",
            "content":  " ".join(tag_text_parts),
            "tags":     tags,
        })

    return chunks


# ── Public API ────────────────────────────────────────────────────────────────

def index_spot(spot: dict) -> bool:
    """
    Embed & upsert all text chunks for a spot into Azure AI Search.
    Called by the Agent /index endpoint when admin publishes a spot.

    Returns True on success, False on failure.
    """
    if not AZURE_ENDPOINT or "your-search-service" in AZURE_ENDPOINT:
        logger.warning("Azure Search not configured — skipping indexing.")
        return False

    try:
        ensure_text_index_exists()
        chunks = _build_chunks(spot)
        client = _get_search_client()

        docs = []
        for chunk in chunks:
            text = chunk["content"]
            v768 = _embed(text, "RETRIEVAL_DOCUMENT", DIM_768)
            v256 = _embed(text, "RETRIEVAL_DOCUMENT", DIM_256)
            docs.append({**chunk, "vector_768": v768, "vector_256": v256})

        client.upload_documents(docs)
        logger.info(f"Indexed {len(docs)} chunks for spot '{spot.get('name')}' (id={spot.get('id')})")
        return True

    except Exception as e:
        logger.error(f"Failed to index spot {spot.get('id')}: {e}")
        return False


def delete_spot(spot_id: str) -> bool:
    """
    Remove all indexed chunks for a spot from Azure AI Search.
    Called when a spot is deleted or unpublished.
    """
    if not AZURE_ENDPOINT or "your-search-service" in AZURE_ENDPOINT:
        return False

    try:
        client = _get_search_client()
        # Fetch all chunk IDs for this spot
        results = client.search(
            search_text="",
            filter=f"spotId eq '{spot_id}'",
            select=["id"],
            top=100,
        )
        ids_to_delete = [{"id": r["id"]} for r in results]
        if ids_to_delete:
            client.delete_documents(ids_to_delete)
            logger.info(f"Deleted {len(ids_to_delete)} chunks for spot_id={spot_id}")
        return True

    except Exception as e:
        logger.error(f"Failed to delete spot {spot_id}: {e}")
        return False


def search_context(query: str, top_k: int = 3, spot_type: Optional[str] = None) -> list[dict]:
    """
    Hybrid search (HNSW vector + BM25 keyword) for RAG context retrieval.

    Args:
        query:     The user's natural language question.
        top_k:     Number of chunks to return.
        spot_type: Optional filter — 'landmark' or 'poi'.

    Returns:
        List of dicts with keys: name, section, content, tags, score.
    """
    if not AZURE_ENDPOINT or "your-search-service" in AZURE_ENDPOINT:
        return []

    try:
        client = _get_search_client()
        query_vec = _embed(query, "RETRIEVAL_QUERY", DIM_768)

        vector_query = VectorizedQuery(
            vector=query_vec,
            k_nearest_neighbors=top_k,
            fields="vector_768",
        )

        filter_expr = f"spotType eq '{spot_type}'" if spot_type else None

        results = client.search(
            search_text=query,
            vector_queries=[vector_query],
            filter=filter_expr,
            query_type=QueryType.SIMPLE,
            select=["name", "section", "content", "tags", "spotType"],
            top=top_k,
        )

        context = []
        for r in results:
            context.append({
                "name":     r.get("name", ""),
                "section":  r.get("section", ""),
                "content":  r.get("content", ""),
                "tags":     r.get("tags", []),
                "spotType": r.get("spotType", ""),
                "score":    float(r.get("@search.score", 0)),
            })

        logger.debug(f"RAG search for '{query[:50]}' → {len(context)} chunks")
        return context

    except Exception as e:
        logger.error(f"search_context failed: {e}")
        return []
