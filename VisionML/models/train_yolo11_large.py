"""
Train YOLO11-Large with 5x augmentation.
Single model training to compare with nano/small/medium.
"""

import os
import sys
import yaml
import torch
import time
from datetime import datetime
from ultralytics import YOLO

# ==============================================================================
# CONFIGURATION
# ==============================================================================
DATASET_LOCATION = r"C:\Users\User\Desktop\USM\Y4\FYP\PenangLens\VisionML\data_prep\Dataset\all"
MODEL_WEIGHTS = "yolo11l.pt"
EPOCHS = 50
IMAGE_SIZE = 640
BATCH_SIZE = 16
FREEZE_LAYERS = 10

# ==============================================================================
# GPU CHECK
# ==============================================================================
def check_gpu():
    if torch.cuda.is_available():
        print(f"✅ GPU Detected: {torch.cuda.get_device_name(0)}")
        return 0
    else:
        print("❌ No GPU detected.")
        sys.exit(1)

# ==============================================================================
# VERIFY DATASET
# ==============================================================================
def verify_dataset(dataset_location):
    yaml_path = os.path.join(dataset_location, "data.yaml")
    with open(yaml_path, 'r') as f:
        data = yaml.safe_load(f)
    
    base_path = dataset_location.replace("\\", "/")
    data['path'] = base_path
    data['train'] = "train/images"
    data['val'] = "valid/images"
    data['test'] = "test/images"
    
    with open(yaml_path, 'w') as f:
        yaml.dump(data, f, sort_keys=False)
    
    return yaml_path

# ==============================================================================
# TRAIN YOLO11-LARGE
# ==============================================================================
def train_yolo11_large(yaml_file, device_id):
    print(f"\n{'='*60}")
    print(f"🎯 Training YOLO11-LARGE")
    print(f"{'='*60}")
    
    model = YOLO(MODEL_WEIGHTS)
    
    print(f"Model: YOLO11-Large (25.3M parameters)")
    print(f"Augmentation: 5x (optimal)")
    print(f"Freeze layers: {FREEZE_LAYERS}")
    print(f"Epochs: {EPOCHS}")
    print(f"Batch size: {BATCH_SIZE}")
    
    start_time = time.time()
    
    results = model.train(
        data=yaml_file,
        epochs=EPOCHS,
        imgsz=IMAGE_SIZE,
        batch=BATCH_SIZE,
        device=device_id,
        project="./model_size_experiments",
        name="yolo11l",
        freeze=FREEZE_LAYERS,
        exist_ok=True,
        verbose=True,
        workers=0,
        plots=True,
        patience=5,
        dropout=0.15,
        weight_decay=0.0005,
        # 5x augmentation (optimal)
        hsv_h=0.01,
        hsv_s=0.5,
        hsv_v=0.2,
        degrees=5.0,
        fliplr=0.5,
    )
    
    end_time = time.time()
    training_time = end_time - start_time
    
    print(f"\n{'='*60}")
    print(f"✅ Training Complete!")
    print(f"{'='*60}")
    print(f"Training time: {training_time/60:.2f} minutes ({training_time/3600:.2f} hours)")
    print(f"Model saved to: ./model_size_experiments/yolo11l/weights/best.pt")
    
    return training_time

if __name__ == "__main__":
    print("🚀 YOLO11-Large Training")
    print("="*60)
    
    device = check_gpu()
    yaml_path = verify_dataset(DATASET_LOCATION)
    
    training_time = train_yolo11_large(yaml_path, device)
    
    print(f"\n✅ Done! Now run extract_model_results.py to update the comparison report.")
