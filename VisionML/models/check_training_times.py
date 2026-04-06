"""
Extract actual training times from YOLO training runs.
Checks multiple sources: args.yaml, results.csv timestamps, and training logs.
"""

import os
import yaml
import pandas as pd
from datetime import datetime

# Paths to check
AUG_EXPERIMENTS = r"C:\Users\User\Desktop\USM\Y4\FYP\runs\detect\aug_experiments"
MODEL_EXPERIMENTS = r"C:\Users\User\Desktop\USM\Y4\FYP\runs\detect\model_size_experiments"

def get_training_time_from_csv(csv_path):
    """Calculate training time from results.csv timestamps if available."""
    try:
        df = pd.read_csv(csv_path)
        # Some YOLO versions include timestamp columns
        if 'timestamp' in df.columns or 'time' in df.columns:
            return "Found timestamp column - needs parsing"
        
        # Otherwise, we can't get exact time from CSV
        return None
    except Exception as e:
        return None

def get_training_time_from_args(args_path):
    """Check args.yaml for training time info."""
    try:
        with open(args_path, 'r') as f:
            args = yaml.safe_load(f)
            # Check common fields where time might be stored
            if 'time' in args:
                return args['time']
            if 'training_time' in args:
                return args['training_time']
            if 'duration' in args:
                return args['duration']
        return None
    except Exception as e:
        return None

def check_run_folder(run_path, run_name):
    """Check a single run folder for training time."""
    print(f"\n{'='*60}")
    print(f"Checking: {run_name}")
    print(f"{'='*60}")
    
    # Check args.yaml
    args_path = os.path.join(run_path, "args.yaml")
    if os.path.exists(args_path):
        print(f"✅ Found args.yaml")
        time_info = get_training_time_from_args(args_path)
        if time_info:
            print(f"   Training time in args.yaml: {time_info}")
        else:
            print(f"   ❌ No training time field in args.yaml")
            # Print all keys to see what's available
            with open(args_path, 'r') as f:
                args = yaml.safe_load(f)
                print(f"   Available fields: {list(args.keys())[:10]}...")
    else:
        print(f"❌ No args.yaml found")
    
    # Check results.csv
    csv_path = os.path.join(run_path, "results.csv")
    if os.path.exists(csv_path):
        print(f"✅ Found results.csv")
        df = pd.read_csv(csv_path)
        print(f"   Columns: {list(df.columns)[:10]}...")
        
        # Check for time-related columns
        time_cols = [col for col in df.columns if 'time' in col.lower()]
        if time_cols:
            print(f"   Time-related columns: {time_cols}")
        else:
            print(f"   ❌ No time columns in results.csv")
    else:
        print(f"❌ No results.csv found")
    
    # Check for training log files
    log_files = [f for f in os.listdir(run_path) if f.endswith('.log') or f.endswith('.txt')]
    if log_files:
        print(f"✅ Found log files: {log_files}")
    else:
        print(f"❌ No log files found")
    
    # Check file timestamps as last resort
    if os.path.exists(csv_path):
        csv_modified = os.path.getmtime(csv_path)
        csv_created = os.path.getctime(csv_path)
        time_diff = csv_modified - csv_created
        print(f"   File timestamp difference: {time_diff/60:.2f} minutes")
        print(f"   (This is approximate - file creation to last modification)")

def main():
    print("🔍 Searching for training time information...\n")
    
    # Check augmentation experiments
    print("\n" + "="*60)
    print("AUGMENTATION EXPERIMENTS")
    print("="*60)
    
    aug_runs = ['aug_0x', 'aug_5x', 'aug_10x', 'aug_15x']
    for run in aug_runs:
        run_path = os.path.join(AUG_EXPERIMENTS, run)
        if os.path.exists(run_path):
            check_run_folder(run_path, run)
        else:
            print(f"\n❌ {run} folder not found at {run_path}")
    
    # Check model size experiments
    print("\n" + "="*60)
    print("MODEL SIZE EXPERIMENTS")
    print("="*60)
    
    model_runs = ['yolo11n', 'yolo11s', 'yolo11m']
    for run in model_runs:
        run_path = os.path.join(MODEL_EXPERIMENTS, run)
        if os.path.exists(run_path):
            check_run_folder(run_path, run)
        else:
            print(f"\n❌ {run} folder not found at {run_path}")
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print("If no training time was found in args.yaml or results.csv,")
    print("you'll need to either:")
    print("1. Use file timestamp approximations (shown above)")
    print("2. Re-run training with explicit time tracking")
    print("3. Check console output logs if you saved them")

if __name__ == "__main__":
    main()
