# PenangLens Vision Pipeline — Technical Overview

## 1. Two-Stage Pipeline Architecture

```
User scans image
       │
       ▼
┌──────────────────────────────────────┐
│  Stage 1: DINOv2 (Landmark ID)      │
│  "Which landmark am I looking at?"   │
│                                      │
│  • Generates 768-dim embedding       │
│  • Vector search in Azure AI Search  │
│  • Returns: landmark name + score    │
│  • Threshold: score ≥ 0.6            │
└──────────────┬───────────────────────┘
               │ landmark identified
               ▼
┌──────────────────────────────────────┐
│  Stage 2: YOLO11 (Detail Detection)  │
│  "What architectural features are    │
│   visible in this image?"            │
│                                      │
│  • Detects 29 architectural classes  │
│  • Filtered by landmark context      │
│  • Returns: bounding boxes + labels  │
└──────────────────────────────────────┘
```

### Why Two Stages?

| | DINOv2 | YOLO11 |
|--|--------|--------|
| Task | Coarse identification | Fine-grained detection |
| Output | "This is Fort Cornwallis" | "I see a cannon and a lighthouse" |
| Method | Vector similarity search | Object detection with bounding boxes |
| Training | Pre-trained (no fine-tuning) | Fine-tuned on our dataset |

DINOv2 answers **where**, YOLO answers **what**.

---

## 2. DINOv2 — Landmark Identification

- **Model**: `facebook/dinov2-base` (pre-trained, no fine-tuning needed)
- **Embedding**: 768-dimensional vector per image
- **Index**: Azure AI Search with HNSW vector search
- **Retrieval**: k=1 nearest neighbor, cosine similarity
- **Threshold**: Score ≥ 0.6 to accept match, below = "Unknown Landmark"

### How It Works
1. Admin uploads reference images per landmark via admin portal
2. Each image is embedded into a 768-dim vector and stored in Azure AI Search
3. At scan time, user's photo is embedded and compared against all stored vectors
4. The closest match determines which landmark the user is looking at

---

## 3. YOLO11 — Architectural Detail Detection

### 3.1 Dataset

**Source**: Roboflow (manually annotated bounding boxes)

| Landmark | Original Images | After 10x Augmentation |
|----------|---------------:|----------------------:|
| Fort Cornwallis | 28 | 308 |
| Guan Yin Temple | 17 | 187 |
| Kapitan Keling Mosque | 10 | 110 |
| Khoo Kongsi | 15 | 165 |
| Pagoda Rama VI | 14 | 154 |
| Queen Victoria Clock | 10 | 110 |
| St. George's Church | 5 | 55 |
| **Total** | **99** | **1,089** |

**Splits**: Train: 1,089 | Validation: 29 | Test: 22

### 3.2 Augmentation Techniques (10x per image)

Each training image generates 10 augmented copies using random combinations of:

| Technique | Probability | Parameters |
|-----------|:-----------:|------------|
| Horizontal flip | 50% | Mirror image, adjust bbox |
| Brightness/contrast | 50% | α: 0.7–1.3, β: -30 to +30 |
| Gaussian blur | 30% | Kernel: 3 or 5 |
| Color jitter (HSV) | 50% | Hue ±10, Saturation ±30 |
| Gaussian noise | 30% | σ = 10 |
| Small rotation | 30% | ±10 degrees |

Augmentation is applied **only to training set**. Validation and test sets are untouched.

### 3.3 Fine-Tuning Strategy

| Parameter | Value |
|-----------|-------|
| Base model | YOLO11s (small) |
| Strategy | Partial fine-tuning |
| Frozen layers | First 10 (backbone) |
| Trainable | Detection head only |
| Image size | 640 × 640 |
| Batch size | 16 |
| Optimizer | SGD (YOLO default) |
| Dropout | 0.15 |
| Weight decay | 0.0005 |
| Max epochs | 50 |
| Early stopping patience | 10 epochs |

**Why partial fine-tuning?**
- Backbone (frozen) retains general visual features learned from COCO
- Detection head (trainable) learns our 29 specific architectural classes
- Prevents overfitting on our small dataset (99 original images)

### 3.4 Early Stopping

Training stopped at **epoch 29** (best model saved at epoch 19).

| Epoch | box_loss | cls_loss | mAP@50 | mAP@50-95 |
|------:|---------:|---------:|-------:|----------:|
| 1 | 1.737 | 3.744 | 0.612 | 0.389 |
| 5 | 1.206 | 0.982 | 0.871 | 0.593 |
| 10 | 0.999 | 0.722 | 0.887 | 0.605 |
| 15 | 0.869 | 0.608 | 0.914 | 0.637 |
| **19** | **0.829** | **0.574** | **0.899** | **0.658** |
| 25 | 0.751 | 0.512 | 0.921 | 0.655 |
| 29 | 0.695 | 0.478 | 0.892 | 0.655 |

Best model at epoch 19: validation mAP@50-95 peaked at 0.658, then plateaued. Early stopping triggered at epoch 29 (10 epochs without improvement).

### 3.5 Overfitting Analysis

| Metric | Validation | Test | Gap |
|--------|:----------:|:----:|:---:|
| mAP@50 | 0.899 | 0.904 | **0.005** |
| mAP@50-95 | 0.657 | 0.622 | **0.035** |

**Val-Test gap of 0.035 confirms no overfitting.** A gap > 0.1 would indicate overfitting. Our model generalizes well to unseen test images.

Contributing factors:
- Partial fine-tuning (frozen backbone prevents memorization)
- Dropout 0.15
- Weight decay 0.0005
- Early stopping at epoch 19
- 10x augmentation increases training diversity

---

## 4. Results

### 4.1 Overall

| Metric | Value |
|--------|------:|
| Test mAP@50 | **0.904** |
| Test mAP@50-95 | **0.622** |
| Classes | 29 |
| Landmarks | 7 |
| Training time | 0.394 hours |

### 4.2 Per-Landmark Performance

| Landmark | Classes | mAP@50 | mAP@50-95 |
|----------|:-------:|:------:|:---------:|
| Fort Cornwallis | 4 | 0.995 | 0.665 |
| Khoo Kongsi | 3 | 0.995 | 0.722 |
| St. George's Church | 3 | 0.995 | 0.730 |
| Queen Victoria Clock | 5 | 0.931 | 0.730 |
| Pagoda Rama VI | 3 | 0.890 | 0.634 |
| Guan Yin Temple | 5 | 0.774 | 0.523 |
| Kapitan Keling Mosque | 6 | 0.843 | 0.475 |

### 4.3 All 29 Classes

| Class | Landmark | mAP@50 | mAP@50-95 |
|-------|----------|:------:|:---------:|
| fort_cornwallis_chapel | Fort Cornwallis | 0.995 | 0.898 |
| fort_cornwallis_lighthouse | Fort Cornwallis | 0.995 | 0.599 |
| seri_rambai_cannon | Fort Cornwallis | 0.995 | 0.551 |
| statue_francis_light | Fort Cornwallis | 0.995 | 0.610 |
| dragon_pillar | Guan Yin Temple | 0.884 | 0.389 |
| guan_yin_statue | Guan Yin Temple | 0.995 | 0.724 |
| holy_vase | Guan Yin Temple | 0.000 | 0.000 |
| lotus_base | Guan Yin Temple | 0.995 | 0.703 |
| three_tiered_pavilion_roof | Guan Yin Temple | 0.995 | 0.796 |
| arched_arcade | Kapitan Keling Mosque | 0.560 | 0.293 |
| arched_gateway | Kapitan Keling Mosque | 0.828 | 0.551 |
| crescent_finial | Kapitan Keling Mosque | 0.995 | 0.310 |
| guldastas | Kapitan Keling Mosque | 0.785 | 0.528 |
| minaret | Kapitan Keling Mosque | 0.894 | 0.479 |
| onion_dome | Kapitan Keling Mosque | 0.995 | 0.690 |
| guardian_lion | Khoo Kongsi | 0.995 | 0.859 |
| main_ridge | Khoo Kongsi | 0.995 | 0.438 |
| swallowtail_roof | Khoo Kongsi | 0.995 | 0.869 |
| burmese_spire | Pagoda Rama VI | 0.681 | 0.291 |
| chinese_base | Pagoda Rama VI | 0.995 | 0.715 |
| thai_tier | Pagoda Rama VI | 0.995 | 0.896 |
| balcony_tier | Queen Victoria Clock | 0.676 | 0.411 |
| clock_face | Queen Victoria Clock | 0.995 | 0.651 |
| golden_cupola | Queen Victoria Clock | 0.995 | 0.896 |
| octagonal_base | Queen Victoria Clock | 0.995 | 0.995 |
| pinang_sculpture | Queen Victoria Clock | 0.995 | 0.697 |
| church_steeple | St. George's Church | 0.995 | 0.697 |
| dome_pavilion | St. George's Church | 0.995 | 0.796 |
| front_portico | St. George's Church | 0.995 | 0.697 |

### 4.4 POI-Based Class Filtering

After DINOv2 identifies the landmark, YOLO detections are filtered to only allow classes belonging to that landmark. This prevents false positives like detecting `onion_dome` at Khoo Kongsi.

| Landmark | Allowed YOLO Classes |
|----------|---------------------|
| Fort Cornwallis | chapel, lighthouse, cannon, statue |
| Guan Yin Temple | dragon_pillar, guan_yin_statue, holy_vase, lotus_base, pavilion_roof |
| Kapitan Keling Mosque | arched_arcade, arched_gateway, crescent_finial, guldastas, minaret, onion_dome |
| Khoo Kongsi | guardian_lion, main_ridge, swallowtail_roof |
| Pagoda Rama VI | burmese_spire, chinese_base, thai_tier |
| Queen Victoria Clock | balcony_tier, clock_face, golden_cupola, octagonal_base, pinang_sculpture |
| St. George's Church | church_steeple, dome_pavilion, front_portico |

---

## 5. Inference Performance

| Stage | Time (CPU) |
|-------|:----------:|
| Image read + resize | ~0.1–0.3s |
| DINOv2 embedding + search | ~1.5–3.0s |
| YOLO11 detection | ~0.05–0.2s |
| **Total pipeline** | **~2–3s** |

No GPU required for inference. Model runs on CPU with acceptable latency for a mobile app demo.
