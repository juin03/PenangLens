"""
PenangLens: Model Evaluation
-----------------------------
Evaluates the trained YOLO model and reports:
- Overall mAP@50, mAP@50-95, precision, recall
- Per-landmark breakdown

Usage:
    cd VisionML/models
    python evaluate.py
"""

import os
import sys
import yaml
import torch
from ultralytics import YOLO

# ==============================================================================
# CONFIGURATION
# ==============================================================================
DATASET_LOCATION = r"C:\Users\User\Desktop\USM\Y4\FYP\PenangLens\VisionML\data_prep\Dataset"
MODEL_PATH = r"C:\Users\User\Desktop\USM\Y4\FYP\runs\detect\results\partial_finetuning\weights\best.pt"

# Map each class to its landmark
LANDMARK_CLASS_MAP = {
    "fort_cornwallis": ["fort_cornwallis_chapel", "fort_cornwallis_lighthouse", "seri_rambai_cannon", "statue_francis_light"],
    "guan_yin_teng": ["0", "dragon_pillar", "guan_yin_statue", "holy_vase", "lotus_base", "three_tiered_pavilion_roof"],
    "kapitan_keling_mosque": ["arched_arcade", "arched_gateway", "crescent_finial", "guldastas", "minaret", "onion_dome"],
    "khoo_kongsi": ["guardian_lion", "main_ridge", "swallowtail_roof"],
    "pagoda_rama_vi": ["burmese_spire", "chinese_base", "thai_tier"],
    "queen_victoria_memorial_clock": ["balcony_tier", "clock_face", "golden_cupola", "octagonal_base", "pinang_sculpture"],
    "st_george_church": ["church_steeple", "dome_pavilion", "front_portico", "tower_clock"],
}


def check_gpu():
    if torch.cuda.is_available():
        print(f"✅ GPU: {torch.cuda.get_device_name(0)}")
        return 0
    print("⚠️ No GPU — using CPU")
    return "cpu"


def evaluate():
    device = check_gpu()

    # Load model
    if not os.path.exists(MODEL_PATH):
        print(f"❌ Model not found: {MODEL_PATH}")
        sys.exit(1)

    model = YOLO(MODEL_PATH)
    all_yaml = os.path.join(DATASET_LOCATION, "all", "data.yaml")

    # Fix paths in data.yaml for evaluation
    with open(all_yaml, 'r') as f:
        data = yaml.safe_load(f)
    data['path'] = os.path.join(DATASET_LOCATION, "all").replace("\\", "/")
    data['val'] = "valid/images"
    # Use test_all if it exists (all splits combined), otherwise normal test
    test_all_dir = os.path.join(DATASET_LOCATION, "all", "test_all", "images")
    data['test'] = "test_all/images" if os.path.exists(test_all_dir) else "test/images"
    with open(all_yaml, 'w') as f:
        yaml.dump(data, f, sort_keys=False)

    class_names = data['names']

    # Delete old cache to force re-scan
    for cache in [os.path.join(DATASET_LOCATION, "all", "test", "labels.cache"),
                  os.path.join(DATASET_LOCATION, "all", "test_all", "labels.cache")]:
        if os.path.exists(cache):
            os.remove(cache)

    # ==================== OVERALL EVALUATION ====================
    print(f"\n{'='*60}")
    print(f"📊 OVERALL EVALUATION (on {data['test']})")
    print(f"{'='*60}")

    results = model.val(data=all_yaml, split="test", device=device, batch=4, workers=0, verbose=False)

    print(f"\n  mAP@50:    {results.box.map50:.4f}")
    print(f"  mAP@50-95: {results.box.map:.4f}")

    # Per-class results
    per_class_ap50 = results.box.ap50
    per_class_ap = results.box.ap

    print(f"\n{'='*60}")
    print("📊 PER-CLASS RESULTS")
    print(f"{'='*60}")
    print(f"  {'Class':<35} {'mAP@50':>8} {'mAP@50-95':>10}")
    print(f"  {'-'*55}")

    for i, name in enumerate(class_names):
        if i < len(per_class_ap50):
            print(f"  {name:<35} {per_class_ap50[i]:>8.4f} {per_class_ap[i]:>10.4f}")

    # ==================== PER-LANDMARK BREAKDOWN ====================
    print(f"\n{'='*60}")
    print("📊 PER-LANDMARK BREAKDOWN")
    print(f"{'='*60}")
    print(f"  {'Landmark':<35} {'mAP@50':>8} {'mAP@50-95':>10} {'Classes':>8}")
    print(f"  {'-'*63}")

    for landmark, classes in LANDMARK_CLASS_MAP.items():
        landmark_ap50 = []
        landmark_ap = []
        for cls_name in classes:
            if cls_name in class_names:
                idx = class_names.index(cls_name)
                if idx < len(per_class_ap50):
                    landmark_ap50.append(per_class_ap50[idx])
                    landmark_ap.append(per_class_ap[idx])

        if landmark_ap50:
            avg_ap50 = sum(landmark_ap50) / len(landmark_ap50)
            avg_ap = sum(landmark_ap) / len(landmark_ap)
            print(f"  {landmark:<35} {avg_ap50:>8.4f} {avg_ap:>10.4f} {len(landmark_ap50):>8}")
        else:
            print(f"  {landmark:<35} {'N/A':>8} {'N/A':>10} {'0':>8}")

    print(f"\n✅ Evaluation complete!")


if __name__ == "__main__":
    evaluate()
