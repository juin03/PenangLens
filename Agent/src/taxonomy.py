"""
Centralized taxonomy for interest categories.
Loaded from shared/taxonomy.json to ensure consistency across services.
"""

import json
from pathlib import Path
from typing import Dict, List

# Load taxonomy from shared file
TAXONOMY_PATH = Path(__file__).parent.parent.parent / "shared" / "taxonomy.json"

try:
    with open(TAXONOMY_PATH, 'r', encoding='utf-8') as f:
        TAXONOMY = json.load(f)
except FileNotFoundError:
    # Fallback if file doesn't exist
    TAXONOMY = {"version": "1.0", "categories": []}

CANONICAL_TAGS = TAXONOMY.get("categories", [])

# Build interest expansions from taxonomy
INTEREST_EXPANSIONS: Dict[str, str] = {
    cat["id"]: cat["description"]
    for cat in CANONICAL_TAGS
}

# Also support label-based lookup
for cat in CANONICAL_TAGS:
    INTEREST_EXPANSIONS[cat["label"].lower()] = cat["description"]
    for alias in cat.get("aliases", []):
        INTEREST_EXPANSIONS[alias.lower()] = cat["description"]


def normalize_interest(interest: str) -> str:
    """Normalize legacy interest tags to canonical labels."""
    interest_lower = interest.lower().strip()
    
    for cat in CANONICAL_TAGS:
        if cat["label"].lower() == interest_lower:
            return cat["label"]
        if interest_lower in [a.lower() for a in cat.get("aliases", [])]:
            return cat["label"]
    
    return interest


def get_search_keywords(interest: str) -> List[str]:
    """Get search keywords for an interest category."""
    interest_lower = interest.lower().strip()
    
    for cat in CANONICAL_TAGS:
        if cat["label"].lower() == interest_lower or interest_lower in [a.lower() for a in cat.get("aliases", [])]:
            return cat.get("searchKeywords", [])
    
    return []
