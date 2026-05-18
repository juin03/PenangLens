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

# ── Test Dataset (aligned with indexed knowledge base) ────────────────────────

TEST_QUESTIONS = [
    {
        "question": "What is Khoo Kongsi?",
        "ground_truth": "Khoo Kongsi is one of the most magnificent Chinese clan temples in the world, located in George Town, Penang. It is a testament to Hokkien heritage with intricate carvings and architecture.",
    },
    {
        "question": "Tell me about the Blue Mansion in Penang",
        "ground_truth": "Cheong Fatt Tze - The Blue Mansion is an iconic indigo-blue Chinese courtyard mansion in George Town, Penang. It is a stunning heritage building known for its distinctive blue colour and Chinese architecture.",
    },
    {
        "question": "What is Fort Cornwallis?",
        "ground_truth": "Fort Cornwallis is the largest standing fort in Malaysia, built by the British East India Company. It is a heritage and historical landmark in George Town, Penang.",
    },
    {
        "question": "Tell me about Kek Lok Si Temple",
        "ground_truth": "Kek Lok Si Temple is the largest Buddhist temple in Malaysia, featuring the striking Pagoda of Rama VI. It is a religious, heritage, and architectural landmark in Penang.",
    },
    {
        "question": "What are the Clan Jetties of Penang?",
        "ground_truth": "The Clan Jetties of Penang are Chinese clan settlements built on stilts over the water. They are a heritage and cultural landmark representing the living heritage of Penang's Chinese immigrant communities.",
    },
    {
        "question": "Tell me about Kapitan Keling Mosque",
        "ground_truth": "Kapitan Keling Mosque is a majestic 19th-century mosque featuring Mughal-style golden domes. It is a religious, heritage, and architectural landmark in George Town, Penang.",
    },
    {
        "question": "What can I do at Penang Hill?",
        "ground_truth": "Penang Hill is a hill resort rising 833 metres above sea level. It is accessible by the Penang Hill Funicular Train, one of the oldest funicular railway systems in the region. It offers nature and scenic views.",
    },
    {
        "question": "What is Sister Curry Mee famous for?",
        "ground_truth": "Sister Curry Mee is a legendary curry mee stall in Air Itam, Penang, known for its rich coconut-based curry broth. It is a popular food landmark.",
    },
    {
        "question": "What food is available at Gurney Drive?",
        "ground_truth": "Gurney Drive Hawker Centre is one of the most famous hawker food streets in Asia, offering a wide variety of local Penang dishes. It also has a Char Kway Teow stall serving the iconic wok-fried flat rice noodle dish.",
    },
    {
        "question": "What is Batu Ferringhi known for?",
        "ground_truth": "Batu Ferringhi Beach is the most popular tourist beach in Penang, known for its water sports and beach activities. It is a nature and beach destination.",
    },
    {
        "question": "Where can I try char koay teow in Penang?",
        "ground_truth": "Famous char koay teow spots in Penang include Siam Road Char Koay Teow and Lorong Selamat Char Koay Teow. Air Itam also has its own char koay teow stall.",
    },
    {
        "question": "What is the Snake Temple in Penang?",
        "ground_truth": "The Snake Temple is a unique Buddhist temple in Penang where pit vipers roam freely. It is a heritage and religious landmark.",
    },
    {
        "question": "Tell me about Penang Botanic Gardens",
        "ground_truth": "Penang Botanic Gardens is a nature attraction in Penang, Malaysia. It is a green space for nature walks and outdoor activities.",
    },
    {
        "question": "What is the Penang Hill Funicular Train?",
        "ground_truth": "The Penang Hill Funicular Train is one of the oldest funicular railway systems in the region, providing access to Penang Hill which rises 833 metres above sea level.",
    },
    {
        "question": "Where can I eat nasi kandar in Penang?",
        "ground_truth": "Popular nasi kandar spots in Penang include Nasi Kandar Beratur and Deen Maju Nasi Kandar. Line Clear Nasi Kandar is also a well-known option.",
    },
    {
        "question": "What street art can I see in George Town?",
        "ground_truth": "George Town has street art including the Ernest Zacharevic murals and iron caricature art on Lebuh Cannon. Armenian Street is also known for its street art.",
    },
    {
        "question": "Is there a floating mosque in Penang?",
        "ground_truth": "Yes, the Tanjung Bungah Floating Mosque is a religious landmark in Penang built over the sea.",
    },
    {
        "question": "What is the Pinang Peranakan Mansion?",
        "ground_truth": "Pinang Peranakan Mansion is a heritage and culture landmark in Penang showcasing Peranakan (Baba-Nyonya) culture and architecture.",
    },
    {
        "question": "What can I see at Fort Cornwallis Lighthouse?",
        "ground_truth": "The Fort Cornwallis Lighthouse is a distinctive steel framework lighthouse erected within Fort Cornwallis, the largest standing fort in Malaysia.",
    },
    {
        "question": "What is the Penang War Museum?",
        "ground_truth": "The Penang War Museum is a heritage and historical landmark in Penang. It is located near Penang Hill.",
    },
]


# ── Run Pipeline ──────────────────────────────────────────────────────────────

def run_pipeline(question: str) -> dict:
    """Run question through RAG pipeline, return contexts + answer."""
    from src.indexer import search_context
    from langchain_openai import AzureChatOpenAI
    from langchain_core.messages import HumanMessage, SystemMessage

    # Step 1: Retrieve
    chunks = search_context(question, top_k=6)
    # Deduplicate by name+section to keep rich content but remove exact duplicates
    seen = set()
    unique = []
    for c in chunks:
        key = f"{c['name']}|{c.get('section','')}"
        if key not in seen:
            seen.add(key)
            unique.append(c)
    chunks = unique[:5]  # keep up to 5 diverse chunks
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
            import time
            time.sleep(1)  # avoid Gemini embedding rate limit
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
    try:
        from google import genai as google_genai
        from google.genai import types as genai_types
        from ragas.embeddings import BaseRagasEmbeddings

        class GeminiEmbeddings(BaseRagasEmbeddings):
            def __init__(self):
                self.client = google_genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
            def _embed(self, text):
                r = self.client.models.embed_content(
                    model="gemini-embedding-001",
                    contents=text,
                    config=genai_types.EmbedContentConfig(task_type="RETRIEVAL_QUERY", output_dimensionality=768),
                )
                return r.embeddings[0].values
            def embed_query(self, text): return self._embed(text)
            def embed_documents(self, texts): return [self._embed(t) for t in texts]
            async def aembed_query(self, text): return self._embed(text)
            async def aembed_documents(self, texts): return [self._embed(t) for t in texts]

        eval_embeddings = GeminiEmbeddings()
        print("✅ Using Gemini embeddings for Answer Relevance")
    except Exception as e:
        print(f"⚠️ Gemini embeddings unavailable ({e}) — skipping Answer Relevance")

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
    if eval_embeddings:
        metrics.append(ResponseRelevancy(llm=eval_llm, embeddings=eval_embeddings))

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
