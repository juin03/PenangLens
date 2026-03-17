"""
Personalization services for onboarding-interest based recommendations.

This module provides:
- Interest-to-vector embedding
- Vector recommendations from the existing text index

Important: this implementation avoids creating new Azure Search indices so it can run
on low-tier services with strict index quotas.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional

import numpy as np
from dotenv import load_dotenv

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery

from google import genai
from google.genai import types as genai_types

from .logging_config import get_logger

load_dotenv()
logger = get_logger("penang_agent.personalization")


AZURE_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT", "").strip()
AZURE_KEY = os.getenv("AZURE_SEARCH_KEY", "").strip()
TEXT_INDEX_NAME = os.getenv("AZURE_TEXT_INDEX_NAME", "penang-text-index").strip()
USER_PROFILE_INDEX_NAME = os.getenv("AZURE_USER_PROFILE_INDEX_NAME", "penang-user-profile-index").strip()
PLACE_PROFILE_INDEX_NAME = os.getenv("AZURE_PLACE_PROFILE_INDEX_NAME", "penang-place-profile-index").strip()

EMBEDDING_PROVIDER = os.getenv("PERSONALIZATION_EMBEDDING_PROVIDER", "google").strip().lower()
EMBEDDING_DIM = int(os.getenv("PERSONALIZATION_EMBEDDING_DIM", "768"))

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "").strip()
GOOGLE_EMBED_MODEL = os.getenv("GOOGLE_EMBED_MODEL", "gemini-embedding-001").strip()

INTEREST_EXPANSIONS: dict[str, str] = {
    "street art": "Street Art: murals, creative public art, photo spots, graffiti culture, interactive wall art.",
    "history": "History: historical sites, colonial era stories, heritage narratives, museums, important events from the past.",
    "nature": "Nature: parks, gardens, hills, scenic viewpoints, wildlife, greenery, outdoor exploration.",
    "architecture": "Architecture: design styles, iconic buildings, structural details, religious and colonial architecture.",
    "local food": "Local Food: hawker culture, authentic Penang dishes, street food, local flavors, food heritage.",
    "museums": "Museums: curated exhibits, cultural institutions, historical collections, art and educational galleries.",
    "nightlife": "Nightlife: evening activities, lively streets, night markets, social venues, after-dark experiences.",
    "shopping": "Shopping: malls, local markets, souvenir spots, artisan products, retail streets.",
    "coffee shops": "Coffee Shops: cafes, specialty coffee, cozy hangout spaces, brunch spots, local cafe culture.",
    "live music": "Live Music: performances, local bands, cultural shows, acoustic sets, music venues.",
    "heritage": "Heritage: culturally and historically significant places that preserve traditions, architecture, and stories of Penang communities.",
    "religious": "Religious: temples, mosques, churches, sacred landmarks, spiritual and cultural significance.",
    "food": "Food: culinary attractions, local cuisine, street food experiences, popular eateries.",
    "art": "Art: creative spaces, galleries, installations, murals, cultural expression.",
    "historical": "Historical: landmarks tied to major past events, old districts, monuments, heritage narratives.",
}


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize(vec: list[float]) -> list[float]:
    arr = np.array(vec, dtype=np.float32)
    norm = np.linalg.norm(arr)
    if norm == 0:
        return vec
    return (arr / norm).tolist()


def _is_azure_ready() -> bool:
    return bool(AZURE_ENDPOINT and AZURE_KEY and "your-search-service" not in AZURE_ENDPOINT)


class _EmbeddingService:
    def __init__(self):
        self._google_client: Optional[genai.Client] = None

    def _get_google_client(self) -> genai.Client:
        if self._google_client is None:
            if not GOOGLE_API_KEY:
                raise RuntimeError("GOOGLE_API_KEY is missing for personalization embeddings")
            self._google_client = genai.Client(api_key=GOOGLE_API_KEY)
        return self._google_client

    def embed(self, text: str, task_type: str) -> list[float]:
        if EMBEDDING_PROVIDER != "google":
            raise RuntimeError(
                f"Unsupported PERSONALIZATION_EMBEDDING_PROVIDER='{EMBEDDING_PROVIDER}'. "
                "Currently supported: 'google'."
            )

        client = self._get_google_client()
        result = client.models.embed_content(
            model=GOOGLE_EMBED_MODEL,
            contents=text,
            config=genai_types.EmbedContentConfig(
                task_type=task_type,
                output_dimensionality=EMBEDDING_DIM,
            ),
        )
        vector = result.embeddings[0].values
        return _normalize(vector)


class PersonalizationService:
    def __init__(self):
        self.embedder = _EmbeddingService()

    def is_configured(self) -> bool:
        return _is_azure_ready()

    def _search_client(self, index_name: str) -> SearchClient:
        return SearchClient(AZURE_ENDPOINT, index_name, AzureKeyCredential(AZURE_KEY))

    def ensure_indices(self) -> None:
        # Intentionally a no-op to avoid index quota errors on low-tier Azure Search.
        return

    def _build_interest_text(self, interests: list[str]) -> str:
        cleaned = [i.strip() for i in interests if i and i.strip()]
        if not cleaned:
            return "Traveler interested in Penang attractions."

        expanded_chunks: list[str] = []
        for interest in cleaned:
            lower_interest = interest.lower()
            expanded = INTEREST_EXPANSIONS.get(lower_interest)
            if expanded:
                expanded_chunks.append(expanded)
            else:
                expanded_chunks.append(
                    f"{interest}: places and experiences related to {interest.lower()} in Penang."
                )

        return (
            f"Traveler interested in: {', '.join(cleaned)}. "
            "Recommend places in Penang that best match these preferences. "
            + " ".join(expanded_chunks)
        )

    def upsert_user_profile(self, user_id: str, interests: list[str], source: str = "onboarding") -> bool:
        if not self.is_configured() or not user_id:
            return False

        # No dedicated user-profile index in quota-constrained mode.
        logger.info(
            "Skipping user profile index upsert (quota-safe mode)",
            extra={"user_id": user_id, "source": source, "interest_count": len(interests or [])},
        )
        return True

    def get_user_profile(self, user_id: str) -> Optional[dict]:
        return None

    def backfill_place_profiles_from_text_index(self, limit: int = 500) -> dict:
        if not self.is_configured():
            return {"success": False, "reason": "azure_search_not_configured", "upserted": 0}

        # No backfill needed in quota-safe mode since recommendations run directly on text index.
        return {
            "success": True,
            "upserted": 0,
            "mode": "quota_safe_text_index_direct",
            "message": "Using existing text index directly; no place-profile index backfill required.",
            "checkedAt": _utc_iso(),
            "limit": limit,
        }

    def recommend_by_interests(self, interests: list[str], top_k: int = 8) -> list[dict]:
        if not self.is_configured() or not interests:
            return []

        interest_text = self._build_interest_text(interests)
        query_vec = self.embedder.embed(interest_text, "RETRIEVAL_QUERY")
        vector_query = VectorizedQuery(
            vector=query_vec,
            k_nearest_neighbors=max(20, top_k * 6),
            fields="vector_768",
        )

        client = self._search_client(TEXT_INDEX_NAME)
        results = client.search(
            search_text="*",
            vector_queries=[vector_query],
            select=["spotId", "spotType", "name", "content", "tags"],
            top=max(20, top_k * 6),
        )

        grouped: dict[str, dict] = {}
        for row in results:
            spot_id = row.get("spotId")
            if not spot_id:
                continue
            score = float(row.get("@search.score", 0))
            if spot_id not in grouped:
                grouped[spot_id] = {
                    "spot_id": spot_id,
                    "spot_type": row.get("spotType"),
                    "name": row.get("name"),
                    "description": row.get("content"),
                    "tags": row.get("tags") or [],
                    "score": score,
                }
            else:
                grouped[spot_id]["score"] = max(grouped[spot_id]["score"], score)

        ranked = sorted(grouped.values(), key=lambda x: x["score"], reverse=True)
        return ranked[: max(1, top_k)]


personalization_service = PersonalizationService()
