import os
import sys
import yaml
import torch
import cv2
import glob
from ultralytics import YOLOWorld

# ==============================================================================
# 1. CONFIGURATION
# ==============================================================================
DATASET_LOCATION = r"C:\Users\User\Desktop\USM\Y4\FYP\PenangLens\VisionML\Dataset\all"

# Training Settings
MODEL_WEIGHTS = "yolov8s-world.pt"
EPOCHS = 50           
PATIENCE = 0  # Set to 0 to disable early stopping for speed training
IMAGE_SIZE = 640
BATCH_SIZE = 8

# Speed Training Mode (skip validation/test)
SPEED_TRAINING = True  # Set to False for full training with validation

# Test Folder
TEST_FOLDER_PATH = os.path.join(DATASET_LOCATION, "test", "images")

# ==============================================================================
# STEP 0: GPU CHECK
# ==============================================================================
def check_gpu():
    print("\n--- STEP 0: Checking Hardware ---")
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        print(f"✅ GPU Detected: {gpu_name}")
        return 0
    else:
        print("❌ ERROR: No NVIDIA GPU detected! Training will be too slow.")
        sys.exit(1)

# ==============================================================================
# STEP 1: VERIFY DATA FORMAT FOR YOLO-WORLD
# ==============================================================================
def verify_dataset_format(dataset_location, speed_mode=False):
    print("\n--- STEP 1: Verifying Dataset Format for YOLO-World ---")
    yaml_path = os.path.join(dataset_location, "data.yaml")
    
    if not os.path.exists(yaml_path):
        print(f"❌ CRITICAL ERROR: data.yaml not found at {yaml_path}")
        sys.exit(1)

    # Read YAML
    with open(yaml_path, 'r') as f:
        data = yaml.safe_load(f)

    # Verify required fields
    required_fields = ['path', 'train', 'nc', 'names']
    for field in required_fields:
        if field not in data:
            print(f"❌ Missing required field: {field}")
            sys.exit(1)

    # Fix paths to absolute with forward slashes
    base_path = dataset_location.replace("\\", "/")
    data['path'] = base_path
    data['train'] = os.path.join(base_path, "train", "images").replace("\\", "/")
    
    # Handle speed training mode
    if speed_mode:
        print("⚡ SPEED TRAINING MODE: Skipping validation/test sets")
        # Point val to train for compatibility, or set to empty string
        data['val'] = data['train']  # Use train set for validation too
        data['test'] = data['train']  # Use train set for testing too
    else:
        data['val'] = os.path.join(base_path, "valid", "images").replace("\\", "/")
        data['test'] = os.path.join(base_path, "test", "images").replace("\\", "/")
        
        # Verify directories exist
        for split in ['val', 'test']:
            img_path = data[split]
            if not os.path.exists(img_path):
                print(f"⚠️ Warning: {split} images not found at {img_path}")

    # Verify train directory exists
    if not os.path.exists(data['train']):
        print(f"❌ CRITICAL: Training images not found at {data['train']}")
        sys.exit(1)

    # Extract class names for YOLO-World
    class_names = data['names']
    if isinstance(class_names, dict):
        class_names = [class_names[i] for i in sorted(class_names.keys())]
    
    print(f"✅ Dataset verified: {data['nc']} classes")
    print(f"📋 Classes: {class_names}")

    # Save updated YAML
    with open(yaml_path, 'w') as f:
        yaml.dump(data, f, sort_keys=False)

    return class_names

# ==============================================================================
# STEP 2: TRAIN YOLO-WORLD MODEL
# ==============================================================================
def train_yolo_world(dataset_path, class_names, device_id, speed_mode=False):
    print(f"\n--- STEP 2: Fine-tuning YOLO-World (Epochs={EPOCHS}) ---")
    
    if speed_mode:
        print("⚡ Running in SPEED TRAINING mode (no validation)")
    
    # Initialize YOLO-World model
    model = YOLOWorld(MODEL_WEIGHTS)
    
    # Set classes for YOLO-World
    print(f"🏷️ Setting class prompts: {class_names}")
    model.set_classes(class_names)
    
    yaml_file = os.path.join(dataset_path, "data.yaml")

    # Save outputs to avoid Windows/OneDrive locks
    output_drive = "C:/" if os.path.exists("C:/") else os.getcwd()
    project_path = os.path.join(output_drive, "Temp", "PenangLens_YOLOWorld_Runs")
    os.makedirs(project_path, exist_ok=True)

    print(f"📂 Training results will be saved to: {project_path}")

    # Train with YOLO-World specific settings
    model.train(
        data=yaml_file,
        epochs=EPOCHS,
        imgsz=IMAGE_SIZE,
        batch=BATCH_SIZE,
        patience=PATIENCE,
        plots=True,
        device=device_id,
        project=project_path,
        name="yoloworld_finetuned", 
        exist_ok=True,
        verbose=True,
        workers=0,  # Windows fix
        val=not speed_mode,  # Disable validation in speed mode
        
        # Training augmentation
        degrees=15.0,
        fliplr=0.5,
        mosaic=1.0,
        scale=0.5,
        
        # YOLO-World specific settings
        close_mosaic=10,
    )
    
    print("✅ YOLO-World Fine-tuning Complete.")
    
    # Load best model
    best_model_path = os.path.join(project_path, "yoloworld_finetuned", "weights", "best.pt")
    if os.path.exists(best_model_path):
        print(f"📦 Loading best model from: {best_model_path}")
        best_model = YOLOWorld(best_model_path)
        best_model.set_classes(class_names)
        return best_model
    else:
        print("⚠️ Warning: best.pt not found, returning current model.")
        model.set_classes(class_names)
        return model

# ==============================================================================
# STEP 3: BATCH TESTING WITH YOLO-WORLD
# ==============================================================================
def test_yolo_world_folder(model, folder_path, device_id):
    print(f"\n--- STEP 3: Testing YOLO-World on Folder: {folder_path} ---")
    
    if not os.path.exists(folder_path):
        print(f"❌ Error: Folder not found: {folder_path}")
        return

    results_dir = os.path.join(folder_path, "..", "yoloworld_inference_results")
    os.makedirs(results_dir, exist_ok=True)
    print(f"📂 Results will be saved in: {results_dir}")

    # Find all images
    valid_extensions = ['*.jpg', '*.jpeg', '*.png', '*.webp', '*.JPG', '*.PNG']
    image_files = []
    for ext in valid_extensions:
        image_files.extend(glob.glob(os.path.join(folder_path, ext)))
    
    image_files = list(set(image_files))

    if not image_files:
        print("⚠️ No images found!")
        return

    print(f"🔍 Found {len(image_files)} images. Running YOLO-World inference...")

    for i, img_path in enumerate(image_files):
        filename = os.path.basename(img_path)
        try:
            results = model.predict(
                source=img_path,
                imgsz=IMAGE_SIZE,
                device=device_id,
                verbose=False,
                conf=0.15,
                iou=0.5,
                agnostic_nms=True
            )

            for result in results:
                result_plot = result.plot()
                save_path = os.path.join(results_dir, f"result_{filename}")
                cv2.imwrite(save_path, result_plot)
                
                if len(result.boxes) > 0:
                    print(f"  ✓ {filename}: {len(result.boxes)} detections")

        except Exception as e:
            print(f"❌ Failed: {filename} - {e}")

    print(f"\n🎉 DONE! View results at: {results_dir}")

# ==============================================================================
# MAIN
# ==============================================================================
if __name__ == "__main__":
    device_id = check_gpu()
    
    # Verify dataset and get class names
    class_names = verify_dataset_format(DATASET_LOCATION, speed_mode=SPEED_TRAINING)
    
    # Train YOLO-World model
    trained_model = train_yolo_world(DATASET_LOCATION, class_names, device_id, speed_mode=SPEED_TRAINING)
    
    # Test on training set (since test folder is empty)
    if SPEED_TRAINING:
        test_folder = os.path.join(DATASET_LOCATION, "train", "images")
        print(f"\n⚡ Testing on training set (speed mode)")
    else:
        test_folder = TEST_FOLDER_PATH
    
    test_yolo_world_folder(trained_model, test_folder, device_id)