"""
Extract ACTUAL training times from results.csv files.
"""

import pandas as pd
import os

# Paths
MODEL_EXPERIMENTS = r"C:\Users\User\Desktop\USM\Y4\FYP\runs\detect\model_size_experiments"
AUG_EXPERIMENTS = r"C:\Users\User\Desktop\USM\Y4\FYP\runs\detect\aug_experiments"

def get_actual_training_time(csv_path):
    """Get actual training time from results.csv."""
    try:
        df = pd.read_csv(csv_path)
        if 'time' in df.columns:
            # Time column is cumulative - last value is total training time
            total_time_seconds = df['time'].iloc[-1]
            total_time_minutes = total_time_seconds / 60
            total_time_hours = total_time_seconds / 3600
            return {
                'seconds': total_time_seconds,
                'minutes': total_time_minutes,
                'hours': total_time_hours,
                'formatted': f"{total_time_minutes:.2f} min ({total_time_hours:.2f} hrs)"
            }
        return None
    except Exception as e:
        print(f"Error reading {csv_path}: {e}")
        return None

print("📊 ACTUAL TRAINING TIMES\n")
print("="*80)

# Model size experiments
print("\nMODEL SIZE EXPERIMENTS (5x augmentation):")
print("-"*80)
print(f"{'Model':<15} {'Epochs':<10} {'Actual Training Time':<30}")
print("-"*80)

models = [
    ('YOLO11n', 'yolo11n'),
    ('YOLO11s', 'yolo11s'),
    ('YOLO11m', 'yolo11m'),
    ('YOLO11l', 'yolo11l'),
]

model_times = {}
for model_name, folder in models:
    csv_path = os.path.join(MODEL_EXPERIMENTS, folder, "results.csv")
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path)
        epochs = len(df)
        time_info = get_actual_training_time(csv_path)
        if time_info:
            model_times[model_name] = time_info
            print(f"{model_name:<15} {epochs:<10} {time_info['formatted']}")
        else:
            print(f"{model_name:<15} {epochs:<10} No time data")
    else:
        print(f"{model_name:<15} {'N/A':<10} File not found")

# Augmentation experiments
print("\n\nAUGMENTATION EXPERIMENTS (YOLO11s):")
print("-"*80)
print(f"{'Augmentation':<15} {'Epochs':<10} {'Actual Training Time':<30}")
print("-"*80)

aug_factors = [
    ('0x', 'aug_0x'),
    ('5x', 'aug_5x'),
    ('10x', 'aug_10x'),
    ('15x', 'aug_15x'),
]

aug_times = {}
for aug_name, folder in aug_factors:
    csv_path = os.path.join(AUG_EXPERIMENTS, folder, "results.csv")
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path)
        epochs = len(df)
        time_info = get_actual_training_time(csv_path)
        if time_info:
            aug_times[aug_name] = time_info
            print(f"{aug_name:<15} {epochs:<10} {time_info['formatted']}")
        else:
            print(f"{aug_name:<15} {epochs:<10} No time data")
    else:
        print(f"{aug_name:<15} {'N/A':<10} File not found")

# Summary comparison
if model_times:
    print("\n\n" + "="*80)
    print("MODEL SIZE TRAINING TIME COMPARISON")
    print("="*80)
    
    if 'YOLO11n' in model_times:
        baseline = model_times['YOLO11n']['seconds']
        print(f"{'Model':<15} {'Time (min)':<15} {'Time (hrs)':<15} {'vs Nano':<15}")
        print("-"*80)
        for model_name in ['YOLO11n', 'YOLO11s', 'YOLO11m', 'YOLO11l']:
            if model_name in model_times:
                t = model_times[model_name]
                ratio = t['seconds'] / baseline
                print(f"{model_name:<15} {t['minutes']:<15.2f} {t['hours']:<15.2f} {ratio:<15.2f}x")

print("\n✅ Done!")
