"""Extract results from augmentation experiment (from YOLO's output path)."""
import pandas as pd
import json

RESULTS_DIR = "/mnt/c/Users/User/Desktop/USM/Y4/FYP/runs/detect/aug_experiments"

results = []
for factor in [0, 5, 10, 15]:
    path = f"{RESULTS_DIR}/aug_{factor}x/results.csv"
    df = pd.read_csv(path)
    df.columns = df.columns.str.strip()
    
    # Best epoch by mAP50-95
    best_idx = df['metrics/mAP50-95(B)'].idxmax()
    best = df.iloc[best_idx]
    final = df.iloc[-1]
    
    # Training time
    total_time_s = df['time'].iloc[-1]
    total_epochs = len(df)
    best_epoch = int(best['epoch'])
    
    p = float(best['metrics/precision(B)'])
    r = float(best['metrics/recall(B)'])
    f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0
    
    entry = {
        'factor': f"{factor}x",
        'epochs': total_epochs,
        'best_epoch': best_epoch,
        'training_time_min': round(total_time_s / 60, 1),
        'precision': round(p, 4),
        'recall': round(r, 4),
        'f1': round(f1, 4),
        'mAP50': round(float(best['metrics/mAP50(B)']), 4),
        'mAP50-95': round(float(best['metrics/mAP50-95(B)']), 4),
    }
    results.append(entry)
    
print(f"\n{'Factor':<8} {'Epochs':<8} {'Best':<6} {'Time':<8} {'Precision':<10} {'Recall':<10} {'F1':<10} {'mAP50':<10} {'mAP50-95':<10}")
print("-" * 80)
for r in results:
    print(f"{r['factor']:<8} {r['epochs']:<8} {r['best_epoch']:<6} {r['training_time_min']:<8} {r['precision']:<10} {r['recall']:<10} {r['f1']:<10} {r['mAP50']:<10} {r['mAP50-95']:<10}")

best = max(results, key=lambda x: x['mAP50-95'])
print(f"\n🏆 Best: {best['factor']} augmentation (mAP50-95: {best['mAP50-95']})")

with open('./aug_experiments/new_experiment_results.json', 'w') as f:
    json.dump(results, f, indent=2)
print("\nSaved to ./aug_experiments/new_experiment_results.json")
