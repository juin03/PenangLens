# PenangLens Pipeline Diagrams (Mermaid)

## Pipeline 1: Itinerary Generation (with ReAct)

```mermaid
flowchart TD
    A[User Request<br/>interests, location, time, mode] --> B[1. Parse Description<br/>GPT-4o-mini]
    B --> C[2. Fetch Recommendations<br/>Gemini Embed + Azure AI Search<br/>RAG]
    C --> D[3. Plan Node<br/>GPT-5.4-mini<br/>Picks stops + ordering]
    D --> E[4. Enrich Node<br/>Google Find Place + Details<br/>Validate, get coords/photos/hours]
    E --> F[5. Travel Time Node<br/>Google Distance Matrix<br/>Real drive/walk times]
    F --> G[6. Validate Node<br/>Deterministic<br/>Drop closed/over-time stops]
    G --> H[7. Refine Node<br/>GPT-4o-mini ReAct]

    subgraph ReAct Loop
        H --> I{LLM Reasons}
        I -->|Need food?| J[Tool: find_nearby_food]
        I -->|Verify time?| K[Tool: get_travel_time]
        I -->|Check place?| L[Tool: check_place]
        J --> I
        K --> I
        L --> I
        I -->|All good| M[Tool: done<br/>Write time-aware descriptions]
    end

    M --> N[7.5 Recalculate Travel Times]
    N --> O[8. Format Node<br/>Build final ItineraryData]
    O --> P[9. Post-Check + Fill Gaps<br/>Safety net]
    P --> Q[Final Itinerary<br/>Streamed to mobile]

    style H fill:#f59e0b,color:#000
    style I fill:#f59e0b,color:#000
    style C fill:#8b5cf6,color:#fff
    style D fill:#2563eb,color:#fff
```

## Pipeline 2: Itinerary Modification

```mermaid
flowchart TD
    A[User Message<br/>'swap stop 2 with Hameediyah'] --> B[Classify Intent<br/>GPT-4o-mini]
    B -->|MODIFY| C[Parse Operation<br/>GPT-4o-mini]
    B -->|QUESTION| Q[General Chat<br/>Answer question]
    C --> D{Operation Type}
    D -->|add/swap| E[LLM Suggests Place<br/>+ 2 alternatives]
    D -->|remove| F[Remove stop by index]
    D -->|rearrange| G[Move stop position]
    E --> H[Google Find Place<br/>Validate exists]
    H --> I{Open at<br/>planned time?}
    I -->|Yes| J[Add/Swap into itinerary]
    I -->|No| K[Try next alternative]
    K --> H
    F --> L[Recalculate Travel Times<br/>Google Distance Matrix]
    G --> L
    J --> L
    L --> M[Rebuild All Times<br/>arrival → duration → departure → travel]
    M --> N[Updated Itinerary<br/>Returned to mobile]

    style B fill:#2563eb,color:#fff
    style C fill:#2563eb,color:#fff
```

## Pipeline 3: Discover Chat (RAG)

```mermaid
flowchart TD
    A[User Question<br/>'What food is near Kek Lok Si?'] --> B[Classify Intent<br/>GPT-4o-mini]
    B -->|GREETING| C[Skip RAG<br/>Direct LLM response]
    B -->|QUESTION| D[Embed Question<br/>Gemini Embedding 001]
    D --> E[Vector Search<br/>Azure AI Search<br/>penang-text-index]
    E --> F[Top 3 Chunks<br/>Air Itam Laksa, Hokkien Mee,<br/>Koay Chiap]
    F --> G[Augment Prompt<br/>Question + RAG chunks]
    G --> H[LLM Response<br/>GPT-4o-mini<br/>Grounded in curated content]
    H --> I[Streamed to Mobile]

    style D fill:#8b5cf6,color:#fff
    style E fill:#8b5cf6,color:#fff
    style H fill:#2563eb,color:#fff
```

## Pipeline 4: Landmark & Scan Chat

```mermaid
flowchart TD
    A[User on Landmark Page] --> B{Source?}
    B -->|Landmark Detail| C[spot_content from DB<br/>overview, history,<br/>culture, funFacts]
    B -->|Scan Result| D[detected_classes from YOLO<br/>+ all_classes from DB]

    C --> E[Direct Context Injection<br/>No RAG needed]
    D --> F[Build Detection Context<br/>Detected: chapel, cannon<br/>Missed: statue of Francis Light]
    F --> E

    E --> G[User Question<br/>'What else should I see?']
    G --> H[LLM Response<br/>GPT-4o-mini<br/>Grounded in curated content<br/>+ detection awareness]
    H --> I[Streamed to Mobile]

    style E fill:#10b981,color:#fff
    style H fill:#2563eb,color:#fff
```

## Pipeline 5: Vision Recognition

```mermaid
flowchart TD
    A[User Takes Photo] --> B[YOLO11 Object Detection<br/>VisionML Service - GPU]
    B --> C[Detected Classes<br/>chapel 92%, cannon 88%,<br/>lighthouse 85%]
    B --> D[DINOv2 Image Embedding<br/>768-dim vector]
    D --> E[Vector Search<br/>Azure AI Search<br/>penanglens-poc-index]
    E --> F[Match Reference Images<br/>Identify Landmark + POI]
    C --> G[Annotated Image<br/>Bounding boxes + labels]
    F --> G
    G --> H[Recognition Result<br/>Fort Cornwallis, 3 features detected]

    style B fill:#ef4444,color:#fff
    style D fill:#ef4444,color:#fff
    style E fill:#8b5cf6,color:#fff
```

## System Overview — All 5 Pipelines

```mermaid
flowchart LR
    subgraph Mobile App
        DIS[Discover Tab]
        SCAN[Scan Tab]
        TRIP[Trips Tab]
        LAND[Landmark Page]
    end

    subgraph AI Agent Backend
        P1[Pipeline 1<br/>Itinerary Generation<br/>⚡ ReAct]
        P2[Pipeline 2<br/>Itinerary Modification]
        P3[Pipeline 3<br/>Discover Chat<br/>RAG]
        P4[Pipeline 4<br/>Landmark & Scan Chat]
        P5[Pipeline 5<br/>Vision Recognition]
    end

    subgraph External Services
        AZ[Azure AI Search<br/>Text + Image Indexes]
        GEM[Gemini Embedding<br/>768-dim vectors]
        GPT[Azure OpenAI<br/>GPT-5.4-mini / 4o-mini]
        GOOG[Google Maps APIs<br/>Places, Distance Matrix]
        VML[VisionML Service<br/>YOLO11 + DINOv2]
    end

    TRIP -->|Plan Trip| P1
    TRIP -->|Modify Chat| P2
    DIS -->|Ask AI| P3
    LAND -->|Chat| P4
    SCAN -->|Take Photo| P5
    SCAN -->|Chat on Result| P4

    P1 --> GPT
    P1 --> GEM
    P1 --> AZ
    P1 --> GOOG
    P2 --> GPT
    P2 --> GOOG
    P3 --> GPT
    P3 --> GEM
    P3 --> AZ
    P4 --> GPT
    P5 --> VML
    P5 --> AZ

    style P1 fill:#f59e0b,color:#000
    style P3 fill:#8b5cf6,color:#fff
    style P5 fill:#ef4444,color:#fff
```
