import os
import shutil
import yaml

def merge_all_datasets(root_folder="Dataset"):
    """
    Merges all individual attraction datasets into a single 'all' folder.
    """
    # Target root is now inside the same data_prep folder as this script
    source_root = os.path.join(os.path.dirname(__file__), root_folder)
    dest_root = os.path.join(source_root, "all")

    print(f"\n🚀 Starting Merge Process...")
    print(f"📂 Source: {source_root}")
    print(f"📂 Destination: {dest_root}")

    # 1. Clean/Create Destination
    if os.path.exists(dest_root):
        shutil.rmtree(dest_root)
    
    for split in ['train', 'valid', 'test']:
        for dtype in ['images', 'labels']:
            os.makedirs(os.path.join(dest_root, split, dtype), exist_ok=True)

    # 2. Initialize Master Class List
    master_classes = []
    
    # 3. Iterate through every folder in 'Dataset'
    for project_folder in os.listdir(source_root):
        project_path = os.path.join(source_root, project_folder)
        
        if not os.path.isdir(project_path) or project_folder == "all" or project_folder.startswith("."):
            continue

        print(f"\n📦 Merging Landmark: {project_folder}...")

        yaml_path = os.path.join(project_path, "data.yaml")
        id_map = {}
        
        if os.path.exists(yaml_path):
            with open(yaml_path, 'r') as f:
                data = yaml.safe_load(f)
                local_names = data.get('names', [])
                
                if isinstance(local_names, dict):
                    local_names = [local_names[i] for i in sorted(local_names.keys())]

                for local_id, name in enumerate(local_names):
                    if name not in master_classes:
                        master_classes.append(name)
                    
                    master_id = master_classes.index(name)
                    id_map[local_id] = master_id
                    print(f"   - Class '{name}': {local_id} -> {master_id}")
        else:
            continue

        for split in ['train', 'valid', 'test']:
            src_img_dir = os.path.join(project_path, split, 'images')
            src_lbl_dir = os.path.join(project_path, split, 'labels')
            
            dest_img_dir = os.path.join(dest_root, split, 'images')
            dest_lbl_dir = os.path.join(dest_root, split, 'labels')

            if not os.path.exists(src_img_dir): continue

            images = [f for f in os.listdir(src_img_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.bmp'))]
            
            for img_file in images:
                file_root = os.path.splitext(img_file)[0]
                ext = os.path.splitext(img_file)[1]
                
                new_base_name = f"{project_folder}_{file_root}"
                new_img_name = new_base_name + ext
                new_txt_name = new_base_name + ".txt"

                shutil.copy2(os.path.join(src_img_dir, img_file), os.path.join(dest_img_dir, new_img_name))

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
                        if old_id in id_map:
                            new_id = id_map[old_id]
                            new_lines.append(f"{new_id} {' '.join(parts[1:])}\n")
                    
                    with open(new_txt_path, 'w') as f_out:
                        f_out.writelines(new_lines)

    # 4. Generate Final data.yaml
    # We use relative paths in the YAML so YOLO can find them regardless of where it's run from
    final_yaml_content = {
        'path': '../all', # Relative to where the train/val paths are usually relative to
        'train': 'train/images',
        'val': 'valid/images',
        'test': 'test/images',
        'nc': len(master_classes),
        'names': master_classes
    }
    
    # Note: Roboflow often expects absolute paths or specific relative paths. 
    # For our training scripts, we override 'path' anyway in verify_dataset().

    with open(os.path.join(dest_root, "data.yaml"), 'w') as f:
        yaml.dump(final_yaml_content, f, sort_keys=False)

    print(f"\n🎉 MERGE COMPLETE!")
    print(f"📍 Merged Dataset: {dest_root}")
    print(f"📚 Total Master Classes: {len(master_classes)}")

if __name__ == "__main__":
    merge_all_datasets()
