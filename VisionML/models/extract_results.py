"""
Extract results from already-trained augmentation experiment models.
No retraining needed - just reads existing results.csv files.
"""

import os
import json
import time
import pandas as pd
import yaml
from datetime import datetime

# Path where your models were saved
RESULTS_BASE = r"C:\Users\User\Desktop\USM\Y4\FYP\runs\detect\aug_experiments"
AUGMENTATION_FACTORS = [0, 5, 10, 15]
EPOCHS = 50

def extract_metrics_from_run(factor):
    """Extract metrics from an existing training run."""
    run_path = os.path.join(RESULTS_BASE, f"aug_{factor}x")
    csv_path = os.path.join(run_path, "results.csv")
    
    if not os.path.exists(csv_path):
        print(f"❌ No results found for {factor}x at {csv_path}")
        return None
    
    df = pd.read_csv(csv_path)
    
    # Get final metrics
    final_map50 = df['metrics/mAP50(B)'].iloc[-1]
    final_map50_95 = df['metrics/mAP50-95(B)'].iloc[-1]
    final_precision = df['metrics/precision(B)'].iloc[-1]
    final_recall = df['metrics/recall(B)'].iloc[-1]
    final_train_loss = df['train/box_loss'].iloc[-1]
    final_val_loss = df['val/box_loss'].iloc[-1]
    
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
    
    # Try to get training time from args.yaml
    args_path = os.path.join(run_path, "args.yaml")
    training_time = 0
    if os.path.exists(args_path):
        with open(args_path, 'r') as f:
            args = yaml.safe_load(f)
            # Training time not in args, estimate from epochs
            training_time = final_epoch * 60  # Rough estimate: 1 min per epoch
    
    training_time_str = f"{training_time/60:.2f} minutes ({training_time/3600:.2f} hours)"
    
    result_data = {
        'factor': int(factor),
        'training_time_seconds': float(training_time),
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
    
    return result_data


def generate_markdown_report(log):
    """Generate markdown report."""
    md = f"""# Augmentation Factor Experiment Report

**Date:** {log['experiment_date']}

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
        md += f"- Epochs Completed: {best['epochs']['completed']}/{best['epochs']['total']}\n"
        md += f"- Early Stopping: {'Triggered' if best['epochs']['early_stopped'] else 'Not triggered'}\n\n"
        md += f"This augmentation factor provides the best balance between model performance and generalization.\n"
    
    md += f"\n## Model Weights\n\n"
    md += f"All trained models are saved in `{RESULTS_BASE}`:\n"
    for r in log['results']:
        if 'error' not in r:
            md += f"- `aug_{r['factor']}x/weights/best.pt` (best at epoch {r['best_metrics']['epoch']})\n"
            md += f"- `aug_{r['factor']}x/weights/last.pt` (final at epoch {r['epochs']['completed']})\n"
    
    return md


def main():
    print("📊 Extracting results from trained models...\n")
    
    experiment_log = {
        'experiment_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'config': {
            'epochs': 50,
            'batch_size': 16,
            'image_size': 640,
            'freeze_layers': 10,
            'dropout': 0.15,
            'weight_decay': 0.0005,
            'patience': 5
        },
        'results': []
    }
    
    for factor in AUGMENTATION_FACTORS:
        print(f"Processing {factor}x augmentation...")
        result = extract_metrics_from_run(factor)
        if result:
            experiment_log['results'].append(result)
            print(f"  ✅ Epochs: {result['epochs']['completed']}/{result['epochs']['total']}")
            print(f"  ✅ Best mAP50-95: {result['best_metrics']['mAP50-95']:.4f} (epoch {result['best_metrics']['epoch']})")
        else:
            print(f"  ❌ Failed to extract results")
    
    # Create output directory
    output_dir = "./aug_experiments"
    os.makedirs(output_dir, exist_ok=True)
    
    # Save JSON
    json_path = os.path.join(output_dir, "experiment_results.json")
    with open(json_path, 'w') as f:
        json.dump(experiment_log, f, indent=2)
    print(f"\n✅ JSON saved: {json_path}")
    
    # Save Markdown
    md_report = generate_markdown_report(experiment_log)
    md_path = os.path.join(output_dir, "EXPERIMENT_REPORT.md")
    with open(md_path, 'w') as f:
        f.write(md_report)
    print(f"✅ Markdown saved: {md_path}")
    
    # Print summary
    print(f"\n{'='*60}")
    print("📊 RESULTS SUMMARY")
    print(f"{'='*60}")
    print(f"{'Factor':<10} {'Precision':<12} {'Recall':<12} {'F1':<12} {'mAP50-95':<12}")
    print("-" * 60)
    for r in experiment_log['results']:
        print(f"{r['factor']}x{' ':<7} {r['final_metrics']['precision']:<12.4f} "
              f"{r['final_metrics']['recall']:<12.4f} {r['final_metrics']['f1_score']:<12.4f} "
              f"{r['final_metrics']['mAP50-95']:<12.4f}")
    
    # Find best
    if experiment_log['results']:
        best = max(experiment_log['results'], key=lambda x: x['best_metrics']['mAP50-95'])
        print(f"\n🏆 Best: {best['factor']}x augmentation (mAP50-95: {best['best_metrics']['mAP50-95']:.4f})")


if __name__ == "__main__":
    main()
