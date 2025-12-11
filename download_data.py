from roboflow import Roboflow
import os

# ================= CONFIGURATION =================
# 1. Your Credentials
API_KEY = "xxx"
WORKSPACE = "penangheritage-4k2mm"
PROJECT_ID = "penang-heritage-details" 

# 2. Specific Attraction Settings (CHANGE THESE for every new attraction)
VERSION_NUM = 7                        # The version you generated on Roboflow
ATTRACTION_NAME = "pagoda_rama_vi"      # Folder name: 'pagoda_rama_vi', 'guanyin', etc.

# 3. Main Root Folder
ROOT_FOLDER = "Dataset"                 # The master folder for all your data
# =================================================

def download_and_organize():
    # Construct the exact path: Dataset/pagoda_rama_vi
    target_location = os.path.join(os.getcwd(), ROOT_FOLDER, ATTRACTION_NAME)
    
    print(f"\n🚀 Connecting to Roboflow...")
    print(f"📂 Target Folder: {target_location}")
    
    rf = Roboflow(api_key=API_KEY)
    project = rf.workspace(WORKSPACE).project(PROJECT_ID)
    
    # Download directly into the specific attraction folder
    # The 'location' parameter forces Roboflow to unzip exactly where we want
    dataset = project.version(VERSION_NUM).download("yolov8", location=target_location)
    
    print(f"\n✅ Download Success!")
    print(f"   Data is stored at: {target_location}")
    
    # --- VERIFICATION STEP ---
    print("\n🔍 Checking Folder Structure:")
    for split in ['train', 'valid', 'test']:
        split_path = os.path.join(target_location, split, 'images')
        
        if os.path.exists(split_path):
            count = len(os.listdir(split_path))
            print(f"   📂 {ATTRACTION_NAME}/{split}: {count} images")
        else:
            print(f"   ⚠️ {ATTRACTION_NAME}/{split}: Not found (Check Roboflow split settings)")

if __name__ == "__main__":
    download_and_organize()