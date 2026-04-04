"""
PenangLens: DINOv2 Retrieval Accuracy Evaluation
--------------------------------------------------
Tests DINOv2 landmark identification accuracy against the test set.

Metrics reported:
  - Top-1 accuracy  (correct landmark is the #1 result)
  - Top-3 accuracy  (correct landmark is in top-3 results)
  - Mean similarity score per landmark
  - Confusion matrix

Usage:
    cd VisionML/models
    python evaluate_dino.py

Requirements:
  - Azure Search index must be populated (run admin portal reindex first)
  - .env must have AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_KEY
"""

import os
import sys
import torch
import time
from pathlib import Path
from PIL import Image
from dotenv import load_dotenv
from collections import defaultdict

# Load .env from VisionML root
load_dotenv(Path(__file__).parent.parent / ".env")

# ============================================================
# CONFIG
# ============================================================
TEST_IMAGES_DIR = Path(__file__).parent.parent / "data_prep" / "Dataset" / "all" / "test" / "images"
AZURE_ENDPOINT  = os.getenv("AZURE_SEARCH_ENDPOINT")
AZURE_API_KEY   = os.getenv("AZURE_SEARCH_KEY")
INDEX_NAME      = "penanglens-poc-index"
DINO_MODEL_NAME = "facebook/dinov2-base"
TOP_K           = 3   # retrieve top-k results for top-k accuracy
DEVICE          = "cuda" if torch.cuda.is_available() else "cpu"

# Map class prefixes -> landmark label (must match what's stored in Azure index)
CLASS_TO_LANDMARK = {
    "fort_cornwallis_chapel":       "fort_cornwallis",
    "fort_cornwallis_lighthouse":   "fort_cornwallis",
    "fort_cornwallis_cannon":       "fort_cornwallis",
    "seri_rambai_cannon":           "fort_cornwallis",
    "statue_francis_light":         "fort_cornwallis",
    "dragon_pillar":                "guan_yin_teng",
    "guan_yin_statue":              "guan_yin_teng",
    "holy_vase":                    "guan_yin_teng",
    "lotus_base":                   "guan_yin_teng",
    "three_tiered_pavilion_roof":   "guan_yin_teng",
    "arched_arcade":                "kapitan_keling_mosque",
    "arched_gateway":               "kapitan_keling_mosque",
    "crescent_finial":              "kapitan_keling_mosque",
    "guldastas":                    "kapitan_keling_mosque",
    "minaret":                      "kapitan_keling_mosque",
    "onion_dome":                   "kapitan_keling_mosque",
    "guardian_lion":                "khoo_kongsi",
    "main_ridge":                   "khoo_kongsi",
    "swallowtail_roof":             "khoo_kongsi",
    "burmese_spire":                "pagoda_rama_vi",
    "chinese_base":                 "pagoda_rama_vi",
    "thai_tier":                    "pagoda_rama_vi",
    "balcony_tier":                 "queen_victoria_memorial_clock",
    "clock_face":                   "queen_victoria_memorial_clock",
    "golden_cupola":                "queen_victoria_memorial_clock",
    "octagonal_base":               "queen_victoria_memorial_clock",
    "pinang_sculpture":             "queen_victoria_memorial_clock",
    "church_steeple":               "st_george_church",
    "dome_pavilion":                "st_george_church",
    "front_portico":                "st_george_church",
    "tower_clock":                  "st_george_church",
}

LANDMARKS = sorted(set(CLASS_TO_LANDMARK.values()))


def get_ground_truth_landmark(filename: str) -> str | None:
    """Extract landmark label from filename prefix."""
    stem = Path(filename).stem.lower()
    for cls_prefix, landmark in CLASS_TO_LANDMARK.items():
        if stem.startswith(cls_prefix):
            return landmark
    return None


def load_dino():
    from transformers import AutoImageProcessor, AutoModel
    print(f"Loading DINOv2 ({DINO_MODEL_NAME}) on {DEVICE}...")
    processor = AutoImageProcessor.from_pretrained(DINO_MODEL_NAME)
    model = AutoModel.from_pretrained(DINO_MODEL_NAME).to(DEVICE)
    model.eval()
    print("DINOv2 loaded.")
    return processor, model


def get_embedding(pil_image: Image.Image, processor, model) -> list:
    inputs = processor(images=pil_image, return_tensors="pt").to(DEVICE)
    with torch.no_grad():
        outputs = model(**inputs)
        embedding = outputs.last_hidden_state.mean(dim=1).cpu().numpy().flatten()
    return embedding.tolist()


def query_azure(vector: list, top_k: int) -> list:
    """Returns list of (poi_id, score, poi_name) tuples."""
    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents import SearchClient
    from azure.search.documents.models import VectorizedQuery

    client = SearchClient(AZURE_ENDPOINT, INDEX_NAME, AzureKeyCredential(AZURE_API_KEY))
    vq = VectorizedQuery(vector=vector, k_nearest_neighbors=top_k, fields="imageVector")
    results = client.search(search_text="", vector_queries=[vq], top=top_k)
    return [(r["poi_id"], float(r["@search.score"]), r.get("poi_name", "")) for r in results]


def landmark_from_poi_id(poi_id: str) -> str:
    """
    Derive landmark from poi_id.
    Assumes poi_id contains the landmark name as a prefix or substring.
    Adjust this if your Azure index stores landmark differently.
    """
    poi_lower = poi_id.lower().replace("-", "_").replace(" ", "_")
    for lm in LANDMARKS:
        if lm in poi_lower:
            return lm
    return poi_id  # fallback: return raw poi_id


def evaluate():
    if not AZURE_ENDPOINT or not AZURE_API_KEY:
        print("ERROR: AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_KEY must be set in .env")
        sys.exit(1)

    if not TEST_IMAGES_DIR.exists():
        print(f"ERROR: Test images dir not found: {TEST_IMAGES_DIR}")
        sys.exit(1)

    processor, model = load_dino()

    image_files = (
        list(TEST_IMAGES_DIR.glob("*.jpg")) +
        list(TEST_IMAGES_DIR.glob("*.jpeg")) +
        list(TEST_IMAGES_DIR.glob("*.png"))
    )

    print(f"\nFound {len(image_files)} test images\n")

    top1_correct = 0
    topk_correct = 0
    total = 0
    skipped = 0

    per_lm_total  = defaultdict(int)
    per_lm_top1   = defaultdict(int)
    per_lm_scores = defaultdict(list)
    confusion     = defaultdict(lambda: defaultdict(int))

    t_start = time.time()

    for img_path in image_files:
        gt_landmark = get_ground_truth_landmark(img_path.name)
        if gt_landmark is None:
            skipped += 1
            continue

        try:
            pil_image = Image.open(img_path).convert("RGB")
            vector = get_embedding(pil_image, processor, model)
            hits = query_azure(vector, TOP_K)
        except Exception as e:
            print(f"  WARN: {img_path.name} failed: {e}")
            skipped += 1
            continue

        if not hits:
            skipped += 1
            continue

        top1_poi_id, top1_score, _ = hits[0]
        predicted_landmark = landmark_from_poi_id(top1_poi_id)

        total += 1
        per_lm_total[gt_landmark] += 1
        per_lm_scores[gt_landmark].append(top1_score)
        confusion[gt_landmark][predicted_landmark] += 1

        if predicted_landmark == gt_landmark:
            top1_correct += 1
            per_lm_top1[gt_landmark] += 1

        topk_landmarks = [landmark_from_poi_id(h[0]) for h in hits]
        if gt_landmark in topk_landmarks:
            topk_correct += 1

    elapsed = time.time() - t_start

    # ============================================================
    # RESULTS
    # ============================================================
    print(f"\n{'='*60}")
    print(f"  DINOv2 RETRIEVAL ACCURACY RESULTS")
    print(f"{'='*60}")
    print(f"  Total evaluated : {total}")
    print(f"  Skipped         : {skipped}")
    print(f"  Elapsed         : {elapsed:.1f}s  ({elapsed/max(total,1):.2f}s/img)")
    print(f"\n  Top-1 Accuracy  : {top1_correct}/{total} = {top1_correct/max(total,1)*100:.1f}%")
    print(f"  Top-{TOP_K} Accuracy  : {topk_correct}/{total} = {topk_correct/max(total,1)*100:.1f}%")

    print(f"\n{'='*60}")
    print(f"  PER-LANDMARK BREAKDOWN")
    print(f"{'='*60}")
    print(f"  {'Landmark':<38} {'Top-1':>6} {'Count':>6} {'Avg Score':>10}")
    print(f"  {'-'*62}")
    for lm in LANDMARKS:
        n = per_lm_total[lm]
        if n == 0:
            print(f"  {lm:<38} {'N/A':>6} {'0':>6} {'N/A':>10}")
            continue
        acc = per_lm_top1[lm] / n * 100
        avg_score = sum(per_lm_scores[lm]) / len(per_lm_scores[lm])
        print(f"  {lm:<38} {acc:>5.1f}% {n:>6} {avg_score:>10.4f}")

    print(f"\n{'='*60}")
    print(f"  CONFUSION MATRIX (rows=true, cols=predicted)")
    print(f"{'='*60}")
    short = {lm: lm[:12] for lm in LANDMARKS}
    header = "  " + " " * 20 + "".join(f"{short[lm]:>14}" for lm in LANDMARKS)
    print(header)
    for true_lm in LANDMARKS:
        row = f"  {true_lm:<20}"
        for pred_lm in LANDMARKS:
            row += f"{confusion[true_lm][pred_lm]:>14}"
        print(row)

    print(f"\nDone.")


if __name__ == "__main__":
    evaluate()
