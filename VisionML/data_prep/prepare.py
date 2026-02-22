"""
PenangLens: Dataset Preparation Orchestrator
-------------------------------------------
This script automates the full flow:
1. Downloads all specified landmark projects from Roboflow.
2. Merges them into a single dataset for YOLO11 training.
"""

from download import download_project
from merge import merge_all_datasets
import os

# ==============================================================================
# CONFIGURATION
# ==============================================================================
# Your Roboflow API Key
API_KEY = "4Qgk60gHyCJlx8RO1CXN"
WORKSPACE = "penangheritage-4k2mm"

# List of all landmark projects you want to include in your model
LANDMARK_PROJECTS = [
    {
        "project_id": "guan_yin_teng",
        "version": 1,
        "name": "guan_yin_teng"
    },
    # Add more landmarks here as you label them:
    # {
    #     "project_id": "kek_lok_si",
    #     "version": 2,
    #     "name": "kek_lok_si"
    # },
]

SKIP_DOWNLOAD = False  # Set to True if you only want to re-merge existing data

# ==============================================================================
# EXECUTION
# ==============================================================================

def prepare_pipeline():
    print("="*60)
    print("🏛️  PENANGLENS DATASET PREPARATION SYSTEM")
    print("="*60)

    # 1. Download Step
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
        print("\n⏭️ Skipping Download Phase (SKIP_DOWNLOAD=True)")

    # 2. Merge Step
    print(f"\n🔄 Phase 2: Merging all landmarks into master dataset...")
    merge_all_datasets()

    print("\n" + "="*60)
    print("✅ DATASET PREPARATION COMPLETE!")
    print("🚀 You can now run 'python yolo11_full_training.py' to start training.")
    print("="*60)

if __name__ == "__main__":
    prepare_pipeline()
