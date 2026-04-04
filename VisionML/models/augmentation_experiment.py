"""
Augmentation Factor Experiment
-------------------------------
Tests different augmentation multipliers to find optimal value.
Trains YOLO11 with 0x, 5x, 10x, 15x augmentation.
Logs training time and metrics for report.
"""

import os
import sys
import yaml
import torch
import shutil
import time
import json
from datetime import datetime
from ultralytics import YOLO

DATASET_LOCATION = r"C:\Users\User\Desktop\USM\Y4\FYP\PenangLens\VisionML\data_prep\Dataset\all"
MODEL_WEIGHTS = "yolo11s.pt"
EPOCHS = 50  # Same as original training
IMAGE_SIZE = 640
BATCH_SIZE = 16
FREEZE_LAYERS = 10

AUGMENTATION_FACTORS = [0, 5, 10, 15]


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


def train_with_factor(yaml_file, factor, device_id):
    print(f"\n{'='*60}")
    print(f"🧪 Training with {factor}x augmentation")
    print(f"{'='*60}")
    
    model = YOLO(MODEL_WEIGHTS)
    
    # Base parameters - SAME AS ORIGINAL
    base_params = {
        'data': yaml_file,
        'epochs': EPOCHS,
        'imgsz': IMAGE_SIZE,
        'batch': BATCH_SIZE,
        'device': device_id,
        'project': "./aug_experiments",
        'freeze': FREEZE_LAYERS,
        'exist_ok': True,
        'verbose': True,
        'workers': 0,
        'plots': True,
        'patience': 5,
        'dropout': 0.15,
        'weight_decay': 0.0005,
    }
    
    # ONLY augmentation changes based on factor
    if factor == 0:
        # No augmentation
        aug_params = {
            'hsv_h': 0.0,
            'hsv_s': 0.0,
            'hsv_v': 0.0,
            'degrees': 0.0,
            'translate': 0.0,
            'scale': 0.0,
            'flipud': 0.0,
            'fliplr': 0.0,
            'mosaic': 0.0,
            'mixup': 0.0,
        }
    elif factor == 5:
        # Light augmentation
        aug_params = {
            'hsv_h': 0.01,
            'hsv_s': 0.5,
            'hsv_v': 0.2,
            'degrees': 5.0,
            'fliplr': 0.5,
        }
    elif factor == 10:
        # Moderate augmentation
        aug_params = {
            'hsv_h': 0.015,
            'hsv_s': 0.7,
            'hsv_v': 0.4,
            'degrees': 10.0,
            'fliplr': 0.5,
        }
    else:  # 15x
        # Heavy augmentation
        aug_params = {
            'hsv_h': 0.02,
            'hsv_s': 0.9,
            'hsv_v': 0.5,
            'degrees': 15.0,
            'translate': 0.1,
            'scale': 0.2,
            'fliplr': 0.5,
        }
    
    # Merge parameters
    base_params['name'] = f"aug_{factor}x"
    base_params.update(aug_params)
    
    results = model.train(**base_params)
    return results


def main():
    if not torch.cuda.is_available():
        print("❌ No GPU detected.")
        sys.exit(1)
    
    print(f"✅ GPU: {torch.cuda.get_device_name(0)}")
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
            'patience': 5
        },
        'results': []
    }
    
    for factor in AUGMENTATION_FACTORS:
        try:
            print(f"\n{'='*60}")
            print(f"Starting {factor}x augmentation training...")
            print(f"{'='*60}")
            
            start_time = time.time()
            results = train_with_factor(yaml_path, factor, 0)
            end_time = time.time()
            
            training_time = end_time - start_time
            training_time_str = f"{training_time/60:.2f} minutes ({training_time/3600:.2f} hours)"
            
            # Extract metrics from results.csv
            metrics_file = f"./aug_experiments/aug_{factor}x/results.csv"
            if os.path.exists(metrics_file):
                import pandas as pd
                df = pd.read_csv(metrics_file)
                
                # Get final metrics
                final_map50 = df['metrics/mAP50(B)'].iloc[-1]
                final_map50_95 = df['metrics/mAP50-95(B)'].iloc[-1]
                final_precision = df['metrics/precision(B)'].iloc[-1]
                final_recall = df['metrics/recall(B)'].iloc[-1]
                final_train_loss = df['train/box_loss'].iloc[-1]
                final_val_loss = df['val/box_loss'].iloc[-1]
                
                # Get epoch info
                total_epochs = len(df)
                final_epoch = df['epoch'].iloc[-1] if 'epoch' in df.columns else total_epochs
                
                # Calculate F1 score
                if final_precision + final_recall > 0:
                    final_f1 = 2 * (final_precision * final_recall) / (final_precision + final_recall)
                else:
                    final_f1 = 0.0
                
                # Get best metrics and their epochs
                best_map50_idx = df['metrics/mAP50-95(B)'].idxmax()
                best_map50 = df['metrics/mAP50(B)'].iloc[best_map50_idx]
                best_map50_95 = df['metrics/mAP50-95(B)'].iloc[best_map50_idx]
                best_precision = df['metrics/precision(B)'].iloc[best_map50_idx]
                best_recall = df['metrics/recall(B)'].iloc[best_map50_idx]
                best_epoch = df['epoch'].iloc[best_map50_idx] if 'epoch' in df.columns else best_map50_idx + 1
                
                # Check if early stopping triggered
                early_stopped = final_epoch < EPOCHS
                
                result_data = {
                    'factor': factor,
                    'training_time_seconds': training_time,
                    'training_time_formatted': training_time_str,
                    'epochs': {
                        'completed': int(final_epoch),
                        'total': EPOCHS,
                        'best_epoch': int(best_epoch),
                        'early_stopped': early_stopped
                    },
                    'final_metrics': {
                        'mAP50': float(final_map50),
                        'mAP50-95': float(final_map50_95),
                        'precision': float(final_precision),
                        'recall': float(final_recall),
                        'f1_score': float(final_f1),
                        'train_box_loss': float(final_train_loss),
                        'val_box_loss': float(final_val_loss)
                    },
                    'best_metrics': {
                        'mAP50': float(best_map50),
                        'mAP50-95': float(best_map50_95),
                        'precision': float(best_precision),
                        'recall': float(best_recall),
                        'epoch': int(best_epoch)
                    }
                }
                
                results_summary.append(result_data)
                experiment_log['results'].append(result_data)
                
                print(f"\n✅ {factor}x Complete:")
                print(f"   Training Time: {training_time_str}")
                print(f"   Epochs: {final_epoch}/{EPOCHS} (best at epoch {best_epoch})")
                print(f"   Early Stopped: {'Yes' if early_stopped else 'No'}")
                print(f"   Final mAP50: {final_map50:.4f}")
                print(f"   Final mAP50-95: {final_map50_95:.4f}")
                print(f"   Precision: {final_precision:.4f}")
                print(f"   Recall: {final_recall:.4f}")
                print(f"   F1 Score: {final_f1:.4f}")
                print(f"   Best mAP50-95: {best_map50_95:.4f} (epoch {best_epoch})")
        
        except Exception as e:
            print(f"❌ Failed for {factor}x: {e}")
            experiment_log['results'].append({
                'factor': factor,
                'error': str(e)
            })
    
    # Save JSON log
    json_path = "./aug_experiments/experiment_results.json"
    with open(json_path, 'w') as f:
        json.dump(experiment_log, f, indent=2)
    
    # Create markdown report
    md_report = generate_markdown_report(experiment_log)
    md_path = "./aug_experiments/EXPERIMENT_REPORT.md"
    with open(md_path, 'w') as f:
        f.write(md_report)
    
    # Print comparison
    print(f"\n{'='*60}")
    print("📊 RESULTS SUMMARY")
    print(f"{'='*60}")
    print(f"{'Factor':<10} {'Time':<20} {'Precision':<12} {'Recall':<12} {'F1':<12} {'mAP50-95':<12}")
    print("-" * 80)
    for r in results_summary:
        print(f"{r['factor']}x{' ':<7} {r['training_time_formatted']:<20} "
              f"{r['final_metrics']['precision']:<12.4f} {r['final_metrics']['recall']:<12.4f} "
              f"{r['final_metrics']['f1_score']:<12.4f} {r['final_metrics']['mAP50-95']:<12.4f}")
    
    # Find best
    if results_summary:
        best = max(results_summary, key=lambda x: x['best_metrics']['mAP50-95'])
        print(f"\n🏆 Best: {best['factor']}x augmentation (mAP50-95: {best['best_metrics']['mAP50-95']:.4f})")
    
    print(f"\n📄 Reports saved:")
    print(f"   - JSON: {json_path}")
    print(f"   - Markdown: {md_path}")


def generate_markdown_report(log):
    """Generate a markdown report for the experiment."""
    md = f"""# Augmentation Factor Experiment Report

**Date:** {log['experiment_date']}  
**GPU:** {log['gpu']}

## Configuration

| Parameter | Value |
|-----------|-------|
| Epochs | {log['config']['epochs']} |
| Batch Size | {log['config']['batch_size']} |
| Image Size | {log['config']['image_size']} |
| Freeze Layers | {log['config']['freeze_layers']} |
| Dropout | {log['config']['dropout']} |
| Weight Decay | {log['config']['weight_decay']} |
| Patience | {log['config']['patience']} |

## Training Summary

| Aug Factor | Epochs Completed | Best Epoch | Early Stop | Training Time |
|------------|------------------|------------|------------|---------------|
"""
    
    for r in log['results']:
        if 'error' not in r:
            md += f"| {r['factor']}x | {r['epochs']['completed']}/{r['epochs']['total']} | "
            md += f"{r['epochs']['best_epoch']} | "
            md += f"{'Yes' if r['epochs']['early_stopped'] else 'No'} | "
            md += f"{r['training_time_formatted']} |\n"
        else:
            md += f"| {r['factor']}x | ERROR | - | - | - |\n"
    
    md += "\n## Results Summary\n\n"
    md += "| Aug Factor | Precision | Recall | F1 Score | mAP50 | mAP50-95 | Train Loss | Val Loss |\n"
    md += "|------------|-----------|--------|----------|-------|----------|------------|----------|\n"
    
    for r in log['results']:
        if 'error' not in r:
            md += f"| {r['factor']}x | "
            md += f"{r['final_metrics']['precision']:.4f} | "
            md += f"{r['final_metrics']['recall']:.4f} | "
            md += f"{r['final_metrics']['f1_score']:.4f} | "
            md += f"{r['final_metrics']['mAP50']:.4f} | "
            md += f"{r['final_metrics']['mAP50-95']:.4f} | "
            md += f"{r['final_metrics']['train_box_loss']:.4f} | "
            md += f"{r['final_metrics']['val_box_loss']:.4f} |\n"
        else:
            md += f"| {r['factor']}x | - | - | - | - | - | - | - |\n"
    
    md += "\n## Best Metrics (Per Augmentation Factor)\n\n"
    md += "| Aug Factor | Best Epoch | Best mAP50 | Best mAP50-95 | Best Precision | Best Recall |\n"
    md += "|------------|------------|------------|---------------|----------------|-------------|\n"
    
    for r in log['results']:
        if 'error' not in r:
            md += f"| {r['factor']}x | {r['best_metrics']['epoch']} | "
            md += f"{r['best_metrics']['mAP50']:.4f} | "
            md += f"{r['best_metrics']['mAP50-95']:.4f} | "
            md += f"{r['best_metrics']['precision']:.4f} | "
            md += f"{r['best_metrics']['recall']:.4f} |\n"
    
    # Find best
    valid_results = [r for r in log['results'] if 'error' not in r]
    if valid_results:
        best = max(valid_results, key=lambda x: x['best_metrics']['mAP50-95'])
        md += f"\n## Conclusion\n\n"
        md += f"**Best Augmentation Factor:** {best['factor']}x\n\n"
        md += f"### Best Model Performance\n"
        md += f"- Best mAP50-95: **{best['best_metrics']['mAP50-95']:.4f}** (achieved at epoch {best['best_metrics']['epoch']})\n"
        md += f"- Best mAP50: {best['best_metrics']['mAP50']:.4f}\n"
        md += f"- Best Precision: {best['best_metrics']['precision']:.4f}\n"
        md += f"- Best Recall: {best['best_metrics']['recall']:.4f}\n\n"
        md += f"### Final Model Performance\n"
        md += f"- Final Precision: {best['final_metrics']['precision']:.4f}\n"
        md += f"- Final Recall: {best['final_metrics']['recall']:.4f}\n"
        md += f"- Final F1 Score: {best['final_metrics']['f1_score']:.4f}\n"
        md += f"- Final Validation Loss: {best['final_metrics']['val_box_loss']:.4f}\n\n"
        md += f"### Training Details\n"
        md += f"- Training Time: {best['training_time_formatted']}\n"
        md += f"- Epochs Completed: {best['epochs']['completed']}/{best['epochs']['total']}\n"
        md += f"- Early Stopping: {'Triggered' if best['epochs']['early_stopped'] else 'Not triggered'}\n\n"
        md += f"This augmentation factor provides the best balance between model performance and generalization.\n"
    
    md += f"\n## Model Weights\n\n"
    md += f"All trained models are saved in:\n"
    for r in log['results']:
        if 'error' not in r:
            md += f"- `./aug_experiments/aug_{r['factor']}x/weights/best.pt` (best at epoch {r['best_metrics']['epoch']})\n"
            md += f"- `./aug_experiments/aug_{r['factor']}x/weights/last.pt` (final at epoch {r['epochs']['completed']})\n"
    
    return md


if __name__ == "__main__":
    main()
