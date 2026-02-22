from roboflow import Roboflow
import os

def download_project(api_key, workspace, project_id, version, attraction_name, root_folder="Dataset"):
    """
    Downloads a specific project version from Roboflow.
    """
    # Target location is now inside the same data_prep folder as this script
    target_location = os.path.join(os.path.dirname(__file__), root_folder, attraction_name)
    
    print(f"\n🚀 Connecting to Roboflow for '{attraction_name}'...")
    print(f"📂 Target Folder: {target_location}")
    
    try:
        rf = Roboflow(api_key=api_key)
        project = rf.workspace(workspace).project(project_id)
        
        # Download directly into the specific attraction folder
        dataset = project.version(version).download("yolov8", location=target_location)
        
        print(f"✅ Download Success for {attraction_name}!")
        return True
    except Exception as e:
        print(f"❌ Error downloading {attraction_name}: {e}")
        return False

if __name__ == "__main__":
    # This allows the script to still be run standalone for a single project
    API_KEY = "4Qgk60gHyCJlx8RO1CXN"
    WORKSPACE = "penangheritage-4k2mm"
    PROJECT_ID = "guan_yin_teng" 
    VERSION_NUM = 1
    ATTRACTION_NAME = "guan_yin_teng"
    
    download_project(API_KEY, WORKSPACE, PROJECT_ID, VERSION_NUM, ATTRACTION_NAME)
