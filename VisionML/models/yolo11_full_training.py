import os
import sys
import yaml
import torch
import cv2
import glob
from ultralytics import YOLO

# ==============================================================================
# CONFIGURATION
# ==============================================================================
DATASET_LOCATION = r"C:\Users\User\Desktop\USM\Y4\FYP\PenangLens\VisionML\data_prep\Dataset\all"
MODEL_WEIGHTS = "yolo11s.pt"  # Using YOLO11 Small
EPOCHS = 50
IMAGE_SIZE = 640
BATCH_SIZE = 8
SPEED_TRAINING = False  # Set to True only for quick debugging

# ==============================================================================
# GPU CHECK
# ==============================================================================
def check_gpu():
    if torch.cuda.is_available():
        print(f"✅ GPU Detected: {torch.cuda.get_device_name(0)}")
        return 0
    else:
        print("❌ No GPU detected. Training will be extremely slow.")
        sys.exit(1)

# ==============================================================================
# VERIFY DATASET
# ==============================================================================
def verify_dataset(dataset_location):
    yaml_path = os.path.join(dataset_location, "data.yaml")
    if not os.path.exists(yaml_path):
        print(f"❌ Error: data.yaml not found at {yaml_path}")
        sys.exit(1)

    with open(yaml_path, 'r') as f:
        data = yaml.safe_load(f)
    
    # Handle empty valid/test folders by pointing to train
    base_path = dataset_location.replace("\\", "/")
    data['path'] = base_path
    train_path = "train/images"
    data['train'] = train_path
    data['val'] = "valid/images"
    data['test'] = "test/images"
    
    with open(yaml_path, 'w') as f:
        yaml.dump(data, f, sort_keys=False)
    
    print(f"✅ Dataset verified: {data['nc']} classes")
    return yaml_path

# ==============================================================================
# TRAIN YOLO11 (FULL FINE-TUNING)
# ==============================================================================
def train_full(yaml_file, device_id):
    print(f"\n{'='*60}")
    print(f"🎯 Starting YOLO11 FULL Fine-Tuning")
    print(f"{'='*60}")
    
    model = YOLO(MODEL_WEIGHTS)
    
    # Save models locally in the results subfolder (VisionML/models/results/)
    project_path = "./results"
    run_name = "full_finetuning"
    
    model.train(
        data=yaml_file,
        epochs=EPOCHS,
        imgsz=IMAGE_SIZE,
        batch=BATCH_SIZE,
        device=device_id,
        project=project_path,
        name=run_name,
        exist_ok=True,
        verbose=True,
        workers=0,
        plots=True,
        # Early stopping - stop if no improvement for 10 epochs
        patience=10,
        # Regularization - reduce overfitting
        dropout=0.1,
        weight_decay=0.0005,
    )
    
    best_path = os.path.join(project_path, run_name, "weights", "best.pt")
    print(f"\n✅ Training Complete. Best model: {best_path}")
    return best_path

if __name__ == "__main__":
    device = check_gpu()
    yaml_p = verify_dataset(DATASET_LOCATION)
    train_full(yaml_p, device)
