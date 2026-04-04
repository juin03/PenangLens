"""
Test RAG vector search scores for specific interests.
Usage: python scripts/test_rag_scores.py
"""
import sys
sys.path.insert(0, ".")

from src.indexer import search_context, _embed, DIM_768
from src.personalization import INTEREST_EXPANSIONS

def build_query(interests: list[str]) -> str:
    """Build expanded query from interests (same as PersonalizationService)."""
    expanded = []
    for i in interests:
        exp = INTEREST_EXPANSIONS.get(i.lower())
        if exp:
            expanded.append(exp)
        else:
            expanded.append(f"{i}: places related to {i.lower()} in Penang.")
    
    return (
        f"Traveler interested in: {', '.join(interests)}. "
        "Recommend places in Penang that best match these preferences. "
        + " ".join(expanded)
    )

def test_interests(interests: list[str], top_k: int = 10):
    print(f"\n{'='*60}")
    print(f"Interests: {interests}")
    print(f"{'='*60}")
    
    query = build_query(interests)
    print(f"\nExpanded Query:\n{query}\n")
    
    results = search_context(query, top_k=top_k * 2, vector_only=True)
    
    # Deduplicate by name, keep highest score
    seen = {}
    for r in results:
        name = r['name']
        if name not in seen or r['score'] > seen[name]['score']:
            seen[name] = r
    unique = sorted(seen.values(), key=lambda x: x['score'], reverse=True)[:top_k]
    
    print(f"{'Rank':<5} {'Place':<40} {'Score':<10} {'Tags'}")
    print("-" * 80)
    for i, r in enumerate(unique, 1):
        tags = ", ".join(r.get("tags", []))[:30]
        print(f"{i:<5} {r['name'][:38]:<40} {r['score']:.4f}    [{tags}]")

if __name__ == "__main__":
    # Test: Heritage + Culture
    test_interests(["Heritage", "Culture"])
    
    # Test: Architecture + Culture  
    test_interests(["Architecture", "Culture"])
    
    # Test: Food
    test_interests(["Food"])
    
    # Test: Nature
    test_interests(["Nature"])
