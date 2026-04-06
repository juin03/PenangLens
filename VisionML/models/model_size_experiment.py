"""
YOLO Model Size Experiment
---------------------------
Tests different YOLO11 model sizes (nano, small, medium, large, xlarge).
Uses 5x augmentation (optimal from previous experiment).
Logs training time and metrics for report.
"""

import os
import sys
import yaml
import torch
import time
import json
from datetime import datetime
from ultralytics import YOLO

# ==============================================================================
# CONFIGURATION
# ==============================================================================
DATASET_LOCATION = r"C:\Users\User\Desktop\USM\Y4\FYP\PenangLens\VisionML\data_prep\Dataset\all"
EPOCHS = 50
IMAGE_SIZE = 640
BATCH_SIZE = 16
FREEZE_LAYERS = 10

# Model sizes to test
MODEL_CONFIGS = [
    {'name': 'nano', 'weights': 'yolo11n.pt'},
    {'name': 'small', 'weights': 'yolo11s.pt'},
    {'name': 'medium', 'weights': 'yolo11m.pt'},
]

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
# TRAIN YOLO11 WITH SPECIFIC MODEL SIZE
# ==============================================================================
def train_model_size(yaml_file, model_config, device_id):
    print(f"\n{'='*60}")
    print(f"🧪 Training YOLO11-{model_config['name'].upper()}")
    print(f"{'='*60}")
    
    model = YOLO(model_config['weights'])
    
    # Base parameters - SAME AS AUGMENTATION EXPERIMENT
    base_params = {
        'data': yaml_file,
        'epochs': EPOCHS,
        'imgsz': IMAGE_SIZE,
        'batch': BATCH_SIZE,
        'device': device_id,
        'project': r"C:\Users\User\Desktop\USM\Y4\FYP\runs\detect\model_size_experiments",
        'name': f"yolo11{model_config['name'][0]}",  # yolo11n, yolo11s, etc.
        'freeze': FREEZE_LAYERS,
        'exist_ok': True,
        'verbose': True,
        'workers': 0,
        'plots': True,
        'patience': 10,
        'dropout': 0.15,
        'weight_decay': 0.0005,
        # Light online augmentation (winner from online aug experiment)
        'hsv_h': 0.01, 'hsv_s': 0.5, 'hsv_v': 0.2,
        'degrees': 5.0, 'fliplr': 0.5,
    }
    
    results = model.train(**base_params)
    return results

# ==============================================================================
# MAIN EXPERIMENT
# ==============================================================================
def main():
    device = check_gpu()
    yaml_path = verify_dataset(DATASET_LOCATION)
    
    results_summary = []
    experiment_log = {
        'experiment_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'gpu': torch.cuda.get_device_name(0),
        'config': {
            'epochs': EPOCHS,
            'batch_size': BATCH_SIZE,
            'image_size': IMAGE_SIZE,
            'freeze_layers': FREEZE_LAYERS,
            'dropout': 0.15,
            'weight_decay': 0.0005,
            'patience': 10,
            'augmentation': '5x offline + light online'
        },
        'results': []
    }
    
    for model_config in MODEL_CONFIGS:
        try:
            print(f"\n{'='*60}")
            print(f"Starting YOLO11-{model_config['name'].upper()} training...")
            print(f"{'='*60}")
            
            start_time = time.time()
            results = train_model_size(yaml_path, model_config, device)
            end_time = time.time()
            
            training_time = end_time - start_time
            training_time_str = f"{training_time/60:.2f} minutes ({training_time/3600:.2f} hours)"
            
            # Extract metrics from results.csv
            metrics_file = rf"C:\Users\User\Desktop\USM\Y4\FYP\runs\detect\model_size_experiments\yolo11{model_config['name'][0]}\results.csv"
            if os.path.exists(metrics_file):
                import pandas as pd
                df = pd.read_csv(metrics_file)
                
                # Get final metrics
                final_map50 = float(df['metrics/mAP50(B)'].iloc[-1])
                final_map50_95 = float(df['metrics/mAP50-95(B)'].iloc[-1])
                final_precision = float(df['metrics/precision(B)'].iloc[-1])
                final_recall = float(df['metrics/recall(B)'].iloc[-1])
                final_train_loss = float(df['train/box_loss'].iloc[-1])
                final_val_loss = float(df['val/box_loss'].iloc[-1])
                
                # Get epoch info
                total_epochs = len(df)
                final_epoch = int(df['epoch'].iloc[-1]) if 'epoch' in df.columns else int(total_epochs)
                
                # Calculate F1 score
                if final_precision + final_recall > 0:
                    final_f1 = 2 * (final_precision * final_recall) / (final_precision + final_recall)
                else:
                    final_f1 = 0.0
                
                # Get best metrics and their epochs
                best_map50_idx = df['metrics/mAP50-95(B)'].idxmax()
                best_map50 = float(df['metrics/mAP50(B)'].iloc[best_map50_idx])
                best_map50_95 = float(df['metrics/mAP50-95(B)'].iloc[best_map50_idx])
                best_precision = float(df['metrics/precision(B)'].iloc[best_map50_idx])
                best_recall = float(df['metrics/recall(B)'].iloc[best_map50_idx])
                best_epoch = int(df['epoch'].iloc[best_map50_idx]) if 'epoch' in df.columns else int(best_map50_idx + 1)
                
                # Check if early stopping triggered
                early_stopped = final_epoch < EPOCHS
                
                # Get model parameters count (approximate)
                model_params = {
                    'nano': '2.6M',
                    'small': '9.4M',
                    'medium': '20.1M',
                    'large': '25.3M',
                    'xlarge': '56.9M'
                }
                
                result_data = {
                    'model': f"YOLO11{model_config['name'][0]}",
                    'parameters': model_params[model_config['name']],
                    'training_time_seconds': float(training_time),
                    'training_time_hrs': round(training_time / 3600, 2),
                    'epochs': {
                        'completed': int(final_epoch),
                        'total': EPOCHS,
                        'best_epoch': int(best_epoch),
                        'early_stopped': early_stopped
                    },
                    'best_metrics': {
                        'mAP50': float(best_map50),
                        'mAP50-95': float(best_map50_95),
                        'precision': float(best_precision),
                        'recall': float(best_recall),
                        'epoch': int(best_epoch)
                    }
                }
                
                # Calculate F1 from best metrics
                bp = float(best_precision)
                br = float(best_recall)
                result_data['best_metrics']['f1'] = round(2 * bp * br / (bp + br), 4) if (bp + br) > 0 else 0
                
                results_summary.append(result_data)
                experiment_log['results'].append(result_data)
                
                print(f"\n✅ YOLO11-{model_config['name']} Complete:")
                print(f"   Training Time: {training_time_str}")
                print(f"   Epochs: {final_epoch}/{EPOCHS} (best at epoch {best_epoch})")
                print(f"   mAP50-95: {best_map50_95:.4f}, Precision: {best_precision:.4f}, Recall: {best_recall:.4f}")
        
        except Exception as e:
            print(f"❌ Failed for YOLO11-{model_config['name']}: {e}")
            experiment_log['results'].append({
                'model': f"YOLO11-{model_config['name']}",
                'error': str(e)
            })
    
    # =========================================================================
    # INFERENCE BENCHMARKING
    # =========================================================================
    print(f"\n{'='*80}")
    print("⏱️  INFERENCE BENCHMARKING")
    print(f"{'='*80}")

    import numpy as np
    RESULTS_BASE = r"C:\Users\User\Desktop\USM\Y4\FYP\runs\detect\model_size_experiments"
    test_img_dir = os.path.join(DATASET_LOCATION, "test", "images")
    test_images = [os.path.join(test_img_dir, f) for f in os.listdir(test_img_dir)
                   if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    dummy_img = test_images[0] if test_images else None

    for r in results_summary:
        model_short = r['model'].lower()  # e.g. yolo11n
        best_pt = os.path.join(RESULTS_BASE, model_short, "weights", "best.pt")
        if not os.path.exists(best_pt):
            r['inference_gpu'] = -1
            r['inference_cpu'] = -1
            continue

        # GPU inference
        model = YOLO(best_pt)
        for _ in range(5):  # warmup
            model.predict(dummy_img, device=0, verbose=False)
        gpu_times = []
        for _ in range(50):
            t0 = time.time()
            model.predict(dummy_img, device=0, verbose=False)
            gpu_times.append((time.time() - t0) * 1000)
        r['inference_gpu'] = round(float(np.median(gpu_times)), 2)

        # CPU inference
        model_cpu = YOLO(best_pt)
        for _ in range(3):  # warmup
            model_cpu.predict(dummy_img, device='cpu', verbose=False)
        cpu_times = []
        for _ in range(20):
            t0 = time.time()
            model_cpu.predict(dummy_img, device='cpu', verbose=False)
            cpu_times.append((time.time() - t0) * 1000)
        r['inference_cpu'] = round(float(np.median(cpu_times)), 2)

        print(f"   {r['model']}: GPU={r['inference_gpu']}ms, CPU={r['inference_cpu']}ms")

    # =========================================================================
    # FINAL TABLE
    # =========================================================================
    print(f"\n{'='*120}")
    print("📊 FINAL RESULTS")
    print(f"{'='*120}")
    header = f"{'Model':<10} {'Params':<10} {'Epochs':<8} {'Train Time':<12} {'Precision':<10} {'Recall':<8} {'F1':<8} {'mAP50':<8} {'mAP50-95':<10} {'GPU(ms)':<9} {'CPU(ms)':<9}"
    print(header)
    print("-" * 120)
    for r in results_summary:
        m = r['best_metrics']
        print(f"{r['model']:<10} {r['parameters']:<10} {r['epochs']['completed']:<8} "
              f"{r['training_time_hrs']:<12} {m['precision']:<10.4f} {m['recall']:<8.4f} "
              f"{m['f1']:<8.4f} {m['mAP50']:<8.4f} {m['mAP50-95']:<10.4f} "
              f"{r.get('inference_gpu', -1):<9} {r.get('inference_cpu', -1):<9}")

    if results_summary:
        best = max(results_summary, key=lambda x: x['best_metrics']['mAP50-95'])
        print(f"\n🏆 Best: {best['model']} (mAP50-95: {best['best_metrics']['mAP50-95']:.4f})")

    # Save JSON
    save_dir = os.path.join(os.path.dirname(__file__), "model_size_experiments")
    os.makedirs(save_dir, exist_ok=True)
    json_path = os.path.join(save_dir, "experiment_results.json")
    with open(json_path, 'w') as f:
        json.dump(experiment_log, f, indent=2)
    print(f"\n📄 Results saved to {json_path}")



if __name__ == "__main__":
    main()
