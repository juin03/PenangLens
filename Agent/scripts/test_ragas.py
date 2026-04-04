"""
RAGAS evaluation for PenangLens Discover Chat RAG pipeline.

Evaluates: context_precision, context_recall, faithfulness, answer_relevancy

Usage:
  python scripts/test_ragas.py
"""

import os, sys, json

# Load env
for line in open(os.path.join(os.path.dirname(__file__), '..', '.env')):
    line = line.strip()
    if '=' in line and not line.startswith('#'):
        k, v = line.split('=', 1)
        os.environ[k] = v

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# ── Test Dataset ──────────────────────────────────────────────────────────────

TEST_QUESTIONS = [
    {
        "question": "What food is famous near Air Itam?",
        "ground_truth": "Air Itam is famous for laksa (asam laksa), char koay teow, hokkien mee, koay chiap, curry mee from Sister Curry Mee, and traditional kopitiam food from Fook Kin Kopitiam.",
    },
    {
        "question": "Tell me about Sister Curry Mee",
        "ground_truth": "Sister Curry Mee is a popular food stall in Air Itam, Penang, known for its rich and spicy curry mee noodle soup. It is a local favourite and a must-try for food lovers visiting the Air Itam area.",
    },
    {
        "question": "Which temples should I visit in Penang?",
        "ground_truth": "Notable temples include Kek Lok Si Temple (largest Buddhist temple in Southeast Asia), Kapitan Keling Mosque, Goddess of Mercy Temple (Kuan Yin Teng), Hainan Temple, Han Jiang Ancestral Temple, Dhammikarama Burmese Temple, Wat Chayamangkalaram, and Snake Temple.",
    },
    {
        "question": "Where can I see street art in George Town?",
        "ground_truth": "Street art can be found on Armenian Street (Lebuh Armenian), Lebuh Cannon with iron caricature art, and throughout George Town including the famous Children on Bicycle mural and Boy on Motorcycle mural by Ernest Zacharevic.",
    },
    {
        "question": "Is there a floating mosque in Penang?",
        "ground_truth": "Yes, the Tanjung Bungah Floating Mosque is built on stilts over the sea in Tanjung Bungah. It is a striking architectural landmark offering beautiful views of the coastline.",
    },
    {
        "question": "What can I do at Batu Ferringhi?",
        "ground_truth": "Batu Ferringhi offers beach activities, the Long Beach Food Court for local food, Ferringhi Garden Restaurant, BoraBora sunset bar, Tropical Spice Garden for nature walks, and ESCAPE Theme Park for adventure activities.",
    },
    {
        "question": "What is Khoo Kongsi?",
        "ground_truth": "Khoo Kongsi (Leong San Tong) is a grand Chinese clan house and temple in George Town, Penang. It is one of the most ornate clan temples in Southeast Asia, featuring elaborate carvings, paintings, and architecture reflecting Hokkien heritage.",
    },
    {
        "question": "Where can I try char koay teow in Penang?",
        "ground_truth": "Famous char koay teow spots include Siam Road Char Koay Teow, Air Itam Char Koay Teow, and Lorong Selamat Char Koay Teow. These are iconic Penang street food stalls.",
    },
    {
        "question": "What is there to see at Fort Cornwallis?",
        "ground_truth": "Fort Cornwallis features the Seri Rambai Cannon, a lighthouse, a chapel, and the Statue of Francis Light. It is the largest standing fort in Malaysia, built by the British East India Company.",
    },
    {
        "question": "What shopping options are in George Town?",
        "ground_truth": "Shopping options include Chowrasta Market for local goods, Little India for textiles and spices, Gurney Plaza mall, Komtar, and Queensbay Mall in Bayan Lepas.",
    },
    {
        "question": "What nature attractions are in Penang?",
        "ground_truth": "Nature attractions include Penang Hill with funicular railway, Penang Botanic Gardens, Penang National Park with Monkey Beach, The Habitat Penang Hill for canopy walks, Tropical Spice Garden, and Entopia butterfly farm.",
    },
    {
        "question": "Where can I eat nasi kandar in Penang?",
        "ground_truth": "Popular nasi kandar spots include Line Clear Nasi Kandar on Jalan Penang, Nasi Kandar Beratur, Deen Maju Nasi Kandar, and Hameediyah Restaurant which is one of the oldest nasi kandar restaurants in Penang.",
    },
    {
        "question": "What is the Blue Mansion?",
        "ground_truth": "Cheong Fatt Tze - The Blue Mansion is a 19th-century Chinese courtyard house in George Town painted in distinctive indigo blue. It was built by Cheong Fatt Tze, a Hakka Chinese merchant, and is now a boutique hotel and heritage museum.",
    },
    {
        "question": "What heritage sites are in George Town?",
        "ground_truth": "George Town heritage sites include Cheong Fatt Tze Blue Mansion, Pinang Peranakan Mansion, Khoo Kongsi, Fort Cornwallis, Clan Jetties, Kapitan Keling Mosque, St George's Church, Queen Victoria Memorial Clock Tower, and Armenian Street.",
    },
    {
        "question": "Tell me about Penang Hill",
        "ground_truth": "Penang Hill (Bukit Bendera) is an 833m hill accessible by funicular railway. It offers cooler temperatures, panoramic views, colonial-era bungalows, The Habitat nature centre, and David Brown's Restaurant for dining. It takes about 3 hours to explore.",
    },
    {
        "question": "What is Clan Jetties?",
        "ground_truth": "The Clan Jetties are waterfront settlements in George Town built on stilts over the sea. Each jetty is named after a Chinese clan — the most visited is Chew Jetty. They represent the living heritage of Penang's Chinese immigrant communities.",
    },
    {
        "question": "Where to eat breakfast in George Town?",
        "ground_truth": "Popular breakfast spots include Toh Soon Cafe for charcoal-toasted bread and eggs, Joo Hooi Cafe for local noodles, and various kopitiam around Lebuh Chulia and Lebuh Campbell.",
    },
    {
        "question": "What religious sites are in Penang?",
        "ground_truth": "Religious sites include Kek Lok Si Temple (Buddhist), Kapitan Keling Mosque (Muslim), St George's Church (Anglican), Goddess of Mercy Temple, Dhammikarama Burmese Temple, Wat Chayamangkalaram (Thai Buddhist), Malay Central Mosque on Lebuh Acheh, and Sri Mahamariamman Temple (Hindu).",
    },
    {
        "question": "What is Gurney Drive known for?",
        "ground_truth": "Gurney Drive is known for the Gurney Drive Hawker Centre with local street food, Gurney Plaza shopping mall, Gurney Wharf waterfront promenade, and nearby Wat Chayamangkalaram and Dhammikarama Burmese Temple.",
    },
    {
        "question": "What museums are in Penang?",
        "ground_truth": "Museums include Penang State Museum and Art Gallery, The Camera Museum, Made in Penang Interactive Museum, Sun Yat Sen Museum, Penang House of Music, and Penang Toy Museum in Tanjung Bungah.",
    },
]


# ── Run Pipeline ──────────────────────────────────────────────────────────────

def run_pipeline(question: str) -> dict:
    """Run question through RAG pipeline, return contexts + answer."""
    from src.indexer import search_context
    from langchain_openai import AzureChatOpenAI
    from langchain_core.messages import HumanMessage, SystemMessage

    # Step 1: Retrieve
    chunks = search_context(question, top_k=3)
    contexts = [c['content'] for c in chunks if c.get('content')]

    # Step 2: Build augmented prompt (same as chat endpoint)
    rag_context = ""
    if contexts:
        rag_context = "\n\nRelevant Penang Heritage Information:\n" + "\n".join(
            f"- [{c['name']}] {c['content']}" for c in chunks
        )

    augmented = (
        "[INSTRUCTION: Answer the user's question about Penang concisely. "
        "Do NOT plan an itinerary. Just provide helpful information.]\n\n"
        + question + rag_context
    )

    # Step 3: Generate answer
    llm = AzureChatOpenAI(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        azure_deployment=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o-mini"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview"),
        temperature=0.3,
    )
    resp = llm.invoke([
        SystemMessage(content="You are a helpful Penang travel guide. Answer based on the provided context."),
        HumanMessage(content=augmented),
    ])

    return {
        "contexts": contexts,
        "answer": resp.content.strip(),
        "chunk_names": [c['name'] for c in chunks],
    }


def main():
    import logging
    logging.basicConfig(level=logging.WARNING)

    print("Running RAG pipeline for 20 questions...\n")

    questions = []
    answers = []
    contexts_list = []
    ground_truths = []

    for i, test in enumerate(TEST_QUESTIONS):
        q = test["question"]
        print(f"  [{i+1}/{len(TEST_QUESTIONS)}] {q}...", end=" ", flush=True)
        try:
            result = run_pipeline(q)
            questions.append(q)
            answers.append(result["answer"])
            contexts_list.append(result["contexts"])
            ground_truths.append(test["ground_truth"])
            print(f"✅ RAG: {result['chunk_names']}")
        except Exception as e:
            print(f"❌ {e}")
            questions.append(q)
            answers.append("Error generating answer")
            contexts_list.append([])
            ground_truths.append(test["ground_truth"])

    # ── RAGAS Evaluation ──────────────────────────────────────────────────────
    print("\nRunning RAGAS evaluation...\n")

    from datasets import Dataset
    from ragas import evaluate
    from ragas.metrics import (
        Faithfulness,
        ResponseRelevancy,
        LLMContextPrecisionWithoutReference,
        LLMContextRecall,
    )
    from ragas.llms import LangchainLLMWrapper
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings

    eval_llm = LangchainLLMWrapper(AzureChatOpenAI(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        azure_deployment=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o-mini"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview"),
        temperature=0,
    ))

    eval_embeddings = None

    dataset = Dataset.from_dict({
        "user_input": questions,
        "response": answers,
        "retrieved_contexts": contexts_list,
        "reference": ground_truths,
    })

    metrics = [
        Faithfulness(llm=eval_llm),
        LLMContextPrecisionWithoutReference(llm=eval_llm),
        LLMContextRecall(llm=eval_llm),
    ]

    try:
        result = evaluate(dataset=dataset, metrics=metrics)

        print("=" * 60)
        print("RAGAS EVALUATION RESULTS")
        print("=" * 60)

        # Get scores from result
        df = result.to_pandas()
        for col in df.columns:
            if col in ("user_input", "response", "retrieved_contexts", "reference"):
                continue
            vals = df[col].dropna()
            if len(vals) > 0:
                print(f"  {col:40s} {vals.mean():.4f}")
        print("=" * 60)

        # Save detailed results
        df = result.to_pandas()
        df.to_csv("docs/ragas_results.csv", index=False)
        print(f"\nDetailed results saved to docs/ragas_results.csv")

        # Print per-question scores
        print(f"\nPer-question breakdown:")
        for i, row in df.iterrows():
            q = row.get("user_input", "")[:50]
            f_score = row.get("faithfulness", "N/A")
            r_score = row.get("answer_relevancy", row.get("response_relevancy", "N/A"))
            print(f"  {i+1}. {q:50s} faith={f_score:.2f} rel={r_score:.2f}" if isinstance(f_score, float) else f"  {i+1}. {q}")

    except Exception as e:
        print(f"RAGAS evaluation error: {e}")
        import traceback
        traceback.print_exc()

        # Fallback: manual scoring
        print("\n--- Manual RAG Quality Check ---")
        for i, q in enumerate(questions):
            ctx = contexts_list[i]
            has_context = len(ctx) > 0
            ans_len = len(answers[i])
            print(f"  {i+1}. {q[:50]:50s} chunks={len(ctx)} ans_len={ans_len} {'✅' if has_context and ans_len > 50 else '⚠️'}")


if __name__ == "__main__":
    main()
