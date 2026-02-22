import os
import sys
import yaml
import torch
from ultralytics import YOLO

# ==============================================================================
# CONFIGURATION
# ==============================================================================
DATASET_LOCATION = r"C:\Users\User\Desktop\USM\Y4\FYP\PenangLens\VisionML\data_prep\Dataset\all"
MODEL_WEIGHTS = "yolo11s.pt" 
EPOCHS = 50
IMAGE_SIZE = 640
BATCH_SIZE = 8

# Partial Fine-tuning: Freeze the backbone
# For YOLO11s, freezing 10-12 layers usually covers the backbone.
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
    data['val'] = "train/images"
    data['test'] = "train/images"
    
    with open(yaml_path, 'w') as f:
        yaml.dump(data, f, sort_keys=False)
    
    return yaml_path

# ==============================================================================
# TRAIN YOLO11 (PARTIAL FINE-TUNING)
# ==============================================================================
def train_partial(yaml_file, device_id):
    print(f"\n{'='*60}")
    print(f"🎯 Starting YOLO11 PARTIAL Fine-Tuning (Frozen Backbone)")
    print(f"🔒 Freezing first {FREEZE_LAYERS} layers")
    print(f"{'='*60}")
    
    model = YOLO(MODEL_WEIGHTS)
    
    # Save models locally in the results subfolder (VisionML/models/results/)
    project_path = "./results"
    run_name = "partial_finetuning"
    
    model.train(
        data=yaml_file,
        epochs=EPOCHS,
        imgsz=IMAGE_SIZE,
        batch=BATCH_SIZE,
        device=device_id,
        project=project_path,
        name=run_name,
        freeze=FREEZE_LAYERS,
        exist_ok=True,
        verbose=True,
        workers=0,
        plots=True
    )
    
    best_path = os.path.join(project_path, run_name, "weights", "best.pt")
    print(f"\n✅ Partial Training Complete. Best model: {best_path}")
    return best_path

if __name__ == "__main__":
    device = check_gpu()
    yaml_p = verify_dataset(DATASET_LOCATION)
    train_partial(yaml_p, device)
