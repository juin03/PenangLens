from roboflow import Roboflow
import os

def download_project(api_key, workspace, project_id, version, attraction_name, root_folder="Dataset"):
    """
    Downloads a specific project version from Roboflow.
    """
    target_location = os.path.join(os.path.dirname(__file__), root_folder, attraction_name)
    
    print(f"\n🚀 Connecting to Roboflow for '{attraction_name}'...")
    print(f"📂 Target Folder: {target_location}")
    
    try:
        rf = Roboflow(api_key=api_key)
        project = rf.workspace(workspace).project(project_id)
        dataset = project.version(version).download("yolov11", location=target_location)
        print(f"✅ Download Success for {attraction_name}!")
        return True
    except Exception as e:
        print(f"❌ Error downloading {attraction_name}: {e}")
        return False
