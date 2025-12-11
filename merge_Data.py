import os
import shutil
import yaml

# ================= CONFIGURATION =================
# 1. The folder where all your individual attractions live
#    Example: Dataset/pagoda_rama_vi, Dataset/guanyin
SOURCE_ROOT = os.path.join(os.getcwd(), "Dataset")

# 2. The folder where you want the combined result
DEST_ROOT = os.path.join(SOURCE_ROOT, "all")

# =================================================

def merge_datasets():
    print(f"🚀 Starting Merge Process...")
    print(f"📂 Source: {SOURCE_ROOT}")
    print(f"📂 Destination: {DEST_ROOT}")

    # 1. Clean/Create Destination
    if os.path.exists(DEST_ROOT):
        shutil.rmtree(DEST_ROOT) # CAREFUL: Clears previous 'all' folder
    
    for split in ['train', 'valid', 'test']:
        for dtype in ['images', 'labels']:
            os.makedirs(os.path.join(DEST_ROOT, split, dtype), exist_ok=True)

    # 2. Initialize Master Class List
    master_classes = []
    
    # 3. Iterate through every folder in 'Dataset'
    for project_folder in os.listdir(SOURCE_ROOT):
        project_path = os.path.join(SOURCE_ROOT, project_folder)
        
        # Skip files, the destination folder itself, and hidden folders
        if not os.path.isdir(project_path) or project_folder == "all" or project_folder.startswith("."):
            continue

        print(f"\n📦 Processing Attraction: {project_folder}...")

        # --- STEP A: Map Local Classes to Master Classes ---
        yaml_path = os.path.join(project_path, "data.yaml")
        id_map = {} # Maps {local_id: master_id}
        
        if os.path.exists(yaml_path):
            with open(yaml_path, 'r') as f:
                data = yaml.safe_load(f)
                local_names = data.get('names', [])
                
                # Handle dictionary format {0: 'name'} if present
                if isinstance(local_names, dict):
                    local_names = [local_names[i] for i in sorted(local_names.keys())]

                # Update Master List
                for local_id, name in enumerate(local_names):
                    if name not in master_classes:
                        master_classes.append(name)
                    
                    master_id = master_classes.index(name)
                    id_map[local_id] = master_id
                    print(f"   - Class '{name}': ID {local_id} -> {master_id}")
        else:
            print(f"   ⚠️ Warning: No data.yaml found in {project_folder}. Skipping class mapping.")
            continue

        # --- STEP B: Move Files & Update Labels ---
        for split in ['train', 'valid', 'test']:
            src_img_dir = os.path.join(project_path, split, 'images')
            src_lbl_dir = os.path.join(project_path, split, 'labels')
            
            dest_img_dir = os.path.join(DEST_ROOT, split, 'images')
            dest_lbl_dir = os.path.join(DEST_ROOT, split, 'labels')

            if not os.path.exists(src_img_dir): continue

            # Get list of images
            images = [f for f in os.listdir(src_img_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.bmp'))]
            
            for img_file in images:
                # 1. Rename file to avoid conflicts (e.g., pagoda_001.jpg)
                file_root = os.path.splitext(img_file)[0]
                ext = os.path.splitext(img_file)[1]
                
                new_base_name = f"{project_folder}_{file_root}"
                new_img_name = new_base_name + ext
                new_txt_name = new_base_name + ".txt"

                # 2. Copy Image
                shutil.copy2(
                    os.path.join(src_img_dir, img_file),
                    os.path.join(dest_img_dir, new_img_name)
                )

                # 3. Process Label (Change IDs)
                old_txt_path = os.path.join(src_lbl_dir, file_root + ".txt")
                new_txt_path = os.path.join(dest_lbl_dir, new_txt_name)

                if os.path.exists(old_txt_path):
                    with open(old_txt_path, 'r') as f_in:
                        lines = f_in.readlines()
                    
                    new_lines = []
                    for line in lines:
                        parts = line.strip().split()
                        if not parts: continue
                        
                        old_id = int(parts[0])
                        # Map to new ID
                        if old_id in id_map:
                            new_id = id_map[old_id]
                            # Reconstruct line
                            new_lines.append(f"{new_id} {' '.join(parts[1:])}\n")
                    
                    with open(new_txt_path, 'w') as f_out:
                        f_out.writelines(new_lines)

    # 4. Generate Final data.yaml
    final_yaml_content = {
        'path': DEST_ROOT,
        'train': 'train/images',
        'val': 'valid/images',
        'test': 'test/images',
        'nc': len(master_classes),
        'names': master_classes
    }

    with open(os.path.join(DEST_ROOT, "data.yaml"), 'w') as f:
        yaml.dump(final_yaml_content, f, sort_keys=False)

    print(f"\n🎉 MERGE COMPLETE!")
    print(f"📍 Location: {DEST_ROOT}")
    print(f"📚 Total Classes: {len(master_classes)}")
    print(f"📋 Class List: {master_classes}")

if __name__ == "__main__":
    merge_datasets()