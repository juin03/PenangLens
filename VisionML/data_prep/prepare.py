"""
PenangLens: Dataset Preparation Orchestrator
-------------------------------------------
This script automates the full flow:
1. Downloads all specified landmark projects from Roboflow.
2. Augments the training set locally.
3. Merges them into a single dataset for YOLO11 training.
"""

from download import download_project
from merge import merge_all_datasets
from augment import main as run_augmentation
import os
import sys

# ==============================================================================
# CONFIGURATION
# ==============================================================================
API_KEY = "4Qgk60gHyCJlx8RO1CXN"
WORKSPACE = "penangheritage-4k2mm"

LANDMARK_PROJECTS = [
    {"project_id": "st_george_church",              "version": 2, "name": "st_george_church"},
    {"project_id": "kapitan_keling_mosque",         "version": 4, "name": "kapitan_keling_mosque"},
    {"project_id": "queen_victoria_memorial_clock", "version": 3, "name": "queen_victoria_memorial_clock"},
    {"project_id": "khoo_kongsi",                   "version": 3, "name": "khoo_kongsi"},
    {"project_id": "fort_cornwallis",               "version": 3, "name": "fort_cornwallis"},
    {"project_id": "guan_yin_teng",                 "version": 4, "name": "guan_yin_teng"},
    {"project_id": "pagoda_rama_vi",                "version": 10, "name": "pagoda_rama_vi"},
]

SKIP_DOWNLOAD = False    # Set True if datasets already downloaded
SKIP_AUGMENT = False     # Set True if already augmented
AUGMENT_FACTOR = 10      # How many augmented copies per train image

# ==============================================================================
# EXECUTION
# ==============================================================================

def prepare_pipeline():
    print("="*60)
    print("🏛️  PENANGLENS DATASET PREPARATION SYSTEM")
    print("="*60)

    # 1. Download
    if not SKIP_DOWNLOAD:
        print(f"\n📡 Phase 1: Downloading {len(LANDMARK_PROJECTS)} Landmarks...")
        for project in LANDMARK_PROJECTS:
            success = download_project(
                api_key=API_KEY,
                workspace=WORKSPACE,
                project_id=project["project_id"],
                version=project["version"],
                attraction_name=project["name"]
            )
            if not success:
                print(f"⚠️ Failed to download {project['name']}. Skipping...")
    else:
        print("\n⏭️ Skipping Download Phase")

    # 2. Augment
    if not SKIP_AUGMENT:
        print(f"\n🎨 Phase 2: Augmenting train sets ({AUGMENT_FACTOR}x)...")
        sys.argv = ["augment.py", "--factor", str(AUGMENT_FACTOR)]
        run_augmentation()
    else:
        print("\n⏭️ Skipping Augmentation Phase")

    # 3. Merge
    print(f"\n🔄 Phase 3: Merging all landmarks into master dataset...")
    merge_all_datasets()

    print("\n" + "="*60)
    print("✅ DATASET PREPARATION COMPLETE!")
    print("🚀 Now run training from VisionML/models/:")
    print("   python yolo11_full_training.py")
    print("="*60)

if __name__ == "__main__":
    prepare_pipeline()
