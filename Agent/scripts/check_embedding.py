"""
Test Script for Personalization Engine using Gemini Embeddings
"""

import os
import math
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Color codes for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
BLUE = '\033[94m'
YELLOW = '\033[93m'
RESET = '\033[0m'

def cosine_similarity(v1, v2):
    """Calculate cosine similarity between two vectors."""
    dot_product = sum(a * b for a, b in zip(v1, v2))
    magnitude1 = math.sqrt(sum(a * a for a in v1))
    magnitude2 = math.sqrt(sum(b * b for b in v2))
    if magnitude1 == 0 or magnitude2 == 0:
        return 0
    return dot_product / (magnitude1 * magnitude2)

def test_personalization():
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}{'Testing Personalization Engine (Gemini Embeddings)'.center(60)}{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")

    api_key = os.getenv("GOOGLE_API_KEY")


    if not api_key:
        print(f"{RED}❌ Error: API Key not provided.{RESET}")
        return

    client = genai.Client(api_key=api_key)
    model_name = "gemini-embedding-001"
    dimensions = 2048

    # 1. Define User Profile (Selected Tags from Onboarding)
    # Simulating user selecting chips/tags in the UI
    user_tags = ["History", "Temples", "Street Art", "Local Food"]
    
    # For the embedding model, we can simply join them with commas.
    # This creates a semantic representation of the combined concepts.
    user_profile_text = ", ".join(user_tags)
    
    print(f"{YELLOW}👤 User Selected Tags:{RESET}")
    print(f"   {user_tags}")
    print(f"{YELLOW}🔤 Input to Model:{RESET}")
    print(f"   \"{user_profile_text}\"\n")

    # 2. Define Penang Locations
    locations = [
        {
            "name": "Kek Lok Si Temple",
            "description": "The largest Buddhist temple in Malaysia, featuring a seven-tiered pagoda, beautiful gardens, and a giant bronze statue of Kuan Yin. A major cultural and religious landmark."
        },
        {
            "name": "George Town Street Art",
            "description": "A collection of famous murals and wire sculptures scattered throughout the UNESCO World Heritage zone. Perfect for a cultural walking tour to see the 'Children on Bicycle' and other heritage scenes."
        },
        {
            "name": "Gurney Drive Hawker Centre",
            "description": "A famous seafront food court offering the best of Penang's street food. A paradise for foodies to try Char Koay Teow, Asam Laksa, and Rojak."
        },
        {
            "name": "The Habitat Penang Hill",
            "description": "A world-class rainforest discovery centre sitting on the fringes of a 130-million-year-old virgin rainforest. Features a canopy walk and nature trails for hiking enthusiasts."
        },
        {
            "name": "Escape Theme Park",
            "description": "An outdoor adventure theme park with water slides, obstacle courses, and zip lines. Designed for thrill-seekers and extreme sports lovers."
        }
    ]

    try:
        # 3. Embed User Profile
        print(f"{BLUE}ℹ️  Embedding User Profile...{RESET}")
        user_result = client.models.embed_content(
            model=model_name,
            contents=user_profile_text,
            config=types.EmbedContentConfig(
                output_dimensionality=dimensions,
                task_type="RETRIEVAL_QUERY" # Treat user interest as the query
            )
        )
        user_vector = user_result.embeddings[0].values

        # 4. Embed Locations and Calculate Similarity
        print(f"{BLUE}ℹ️  Embedding {len(locations)} Locations and Calculating Similarity...{RESET}\n")
        
        scored_locations = []

        for loc in locations:
            loc_result = client.models.embed_content(
                model=model_name,
                contents=loc["description"],
                config=types.EmbedContentConfig(
                    output_dimensionality=dimensions,
                    task_type="RETRIEVAL_DOCUMENT" # Treat locations as documents to be retrieved
                )
            )
            loc_vector = loc_result.embeddings[0].values
            
            # Calculate Similarity
            score = cosine_similarity(user_vector, loc_vector)
            scored_locations.append({
                "name": loc["name"],
                "score": score,
                "description": loc["description"]
            })

        # 5. Sort and Display Results
        scored_locations.sort(key=lambda x: x["score"], reverse=True)

        print(f"{GREEN}🎯 Personalization Results (Ranked by Similarity):{RESET}")
        print(f"{'-'*60}")
        print(f"{'LOCATION':<30} | {'SCORE':<10} | {'MATCH REASON'}")
        print(f"{'-'*60}")

        for item in scored_locations:
            # Simple logic to guess match reason for display
            reason = "Unknown"
            if item["score"] > 0.75: reason = "Strong Match"
            elif item["score"] > 0.60: reason = "Good Match" # Adjusted threshold
            else: reason = "Low Relevance"
            
            print(f"{item['name']:<30} | {item['score']:.4f}     | {reason}")

        # ---------------------------------------------------------
        # DEBUG: Why did Kek Lok Si score lower?
        # ---------------------------------------------------------
        print(f"\n{YELLOW}🔍 Debug Analysis: Why the score dropped?{RESET}")
        print("The user profile combines 4 distinct concepts: History, Temples, Street Art, Food.")
        print("This creates a 'diluted' vector that tries to be everything at once.")
        
        print(f"\n{BLUE}ℹ️  Testing single tag 'Temples' against Kek Lok Si...{RESET}")
        
        # Embed just "Temples"
        single_tag_result = client.models.embed_content(
            model=model_name,
            contents="Temples",
            config=types.EmbedContentConfig(output_dimensionality=dimensions, task_type="RETRIEVAL_QUERY")
        )
        single_tag_vector = single_tag_result.embeddings[0].values
        
        # Find Kek Lok Si vector again (it's in the loop, let's just grab the one we need)
        # For efficiency in a real app, you'd cache these. 
        # Here I'll just re-embed or find it if I stored it. 
        # Let's just re-embed for clarity of code.
        kek_lok_si_desc = locations[0]["description"] # Kek Lok Si is index 0
        
        kls_result = client.models.embed_content(
            model=model_name,
            contents=kek_lok_si_desc,
            config=types.EmbedContentConfig(output_dimensionality=dimensions, task_type="RETRIEVAL_DOCUMENT")
        )
        kls_vector = kls_result.embeddings[0].values
        
        single_score = cosine_similarity(single_tag_vector, kls_vector)
        
        print(f"User Input: 'Temples'")
        print(f"Location:   'Kek Lok Si...'")
        print(f"Score:      {GREEN}{single_score:.4f}{RESET} (Much higher!)")
        
        print(f"\n{BLUE}ℹ️  Conclusion:{RESET}")
        print("When you add 'Street Art' and 'Food' to the user profile, Kek Lok Si becomes")
        print("less perfect of a match because it doesn't have street art or food.")

    except Exception as e:
        print(f"{RED}❌ Error: {str(e)}{RESET}")

if __name__ == "__main__":
    test_personalization()
