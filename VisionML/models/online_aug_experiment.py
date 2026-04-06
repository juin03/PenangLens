"""
Online Augmentation Experiment
-------------------------------
Base: 5x offline augmentation (594 images) - winner from previous experiment.
Tests different YOLO online augmentation levels: none, light, moderate, heavy.
"""

import os
import sys
import yaml
import torch
import time
import json
import glob
import cv2
import numpy as np
import random
from datetime import datetime
from ultralytics import YOLO

# Paths
DATASET_ALL = r"C:\Users\User\Desktop\USM\Y4\FYP\PenangLens\VisionML\data_prep\Dataset\all"
TRAIN_IMG_DIR = os.path.join(DATASET_ALL, "train", "images")
TRAIN_LBL_DIR = os.path.join(DATASET_ALL, "train", "labels")
RESULTS_BASE = r"C:\Users\User\Desktop\USM\Y4\FYP\runs\detect\online_aug_experiments"

MODEL_WEIGHTS = "yolo11s.pt"
EPOCHS = 50
IMAGE_SIZE = 640
BATCH_SIZE = 16
FREEZE_LAYERS = 10

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'data_prep'))
from augment import augment_image_and_labels, parse_yolo_labels, write_yolo_labels

ONLINE_AUG_LEVELS = {
    'none': {
        'hsv_h': 0.0, 'hsv_s': 0.0, 'hsv_v': 0.0,
        'degrees': 0.0, 'translate': 0.0, 'scale': 0.0,
        'flipud': 0.0, 'fliplr': 0.0, 'mosaic': 0.0, 'mixup': 0.0,
    },
    'light': {
        'hsv_h': 0.01, 'hsv_s': 0.5, 'hsv_v': 0.2,
        'degrees': 5.0, 'fliplr': 0.5,
    },
    'moderate': {
        'hsv_h': 0.015, 'hsv_s': 0.7, 'hsv_v': 0.4,
        'degrees': 10.0, 'fliplr': 0.5, 'mosaic': 1.0,
    },
    'heavy': {
        'hsv_h': 0.02, 'hsv_s': 0.9, 'hsv_v': 0.5,
        'degrees': 15.0, 'translate': 0.1, 'scale': 0.2,
        'fliplr': 0.5, 'mosaic': 1.0, 'mixup': 0.1,
    },
}


def clean_augmented_images():
    for f in glob.glob(os.path.join(TRAIN_IMG_DIR, "*_aug*")):
        os.remove(f)
    for f in glob.glob(os.path.join(TRAIN_LBL_DIR, "*_aug*")):
        os.remove(f)


def augment_training_set(factor):
    if factor == 0:
        return 0
    images = [f for f in os.listdir(TRAIN_IMG_DIR)
              if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')) and '_aug' not in f]
    count = 0
    for img_file in images:
        img_path = os.path.join(TRAIN_IMG_DIR, img_file)
        label_file = os.path.splitext(img_file)[0] + ".txt"
        label_path = os.path.join(TRAIN_LBL_DIR, label_file)
        img = cv2.imread(img_path)
        if img is None:
            continue
        img_h, img_w = img.shape[:2]
        bboxes = parse_yolo_labels(label_path)
        for i in range(factor):
            aug_img, aug_bboxes = augment_image_and_labels(img, bboxes, img_h, img_w)
            base = os.path.splitext(img_file)[0]
            ext = os.path.splitext(img_file)[1]
            cv2.imwrite(os.path.join(TRAIN_IMG_DIR, f"{base}_aug{i}{ext}"), aug_img)
            write_yolo_labels(os.path.join(TRAIN_LBL_DIR, f"{base}_aug{i}.txt"), aug_bboxes)
            count += 1
    return count


def verify_dataset():
    yaml_path = os.path.join(DATASET_ALL, "data.yaml")
    with open(yaml_path, 'r') as f:
        data = yaml.safe_load(f)
    base_path = DATASET_ALL.replace("\\", "/")
    data['path'] = base_path
    data['train'] = "train/images"
    data['val'] = "valid/images"
    data['test'] = "test/images"
    with open(yaml_path, 'w') as f:
        yaml.dump(data, f, sort_keys=False)
    return yaml_path


def count_training_images():
    return len([f for f in os.listdir(TRAIN_IMG_DIR)
                if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))])


def main():
    if not torch.cuda.is_available():
        print("❌ No GPU detected.")
        sys.exit(1)

    print(f"✅ GPU: {torch.cuda.get_device_name(0)}")
    yaml_path = verify_dataset()

    # Step 1: Prepare 5x offline augmented dataset
    print("\n🧹 Cleaning augmented images...")
    clean_augmented_images()
    random.seed(42)
    np.random.seed(42)
    print("📸 Applying 5x offline augmentation...")
    aug_count = augment_training_set(5)
    total_images = count_training_images()
    print(f"✅ Dataset ready: {total_images} images (99 original + {aug_count} augmented)")

    results = []
    experiment_log = {
        'experiment_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'gpu': torch.cuda.get_device_name(0),
        'config': {
            'model': MODEL_WEIGHTS,
            'offline_augmentation': '5x (594 images)',
            'epochs': EPOCHS,
            'batch_size': BATCH_SIZE,
            'image_size': IMAGE_SIZE,
            'freeze_layers': FREEZE_LAYERS,
            'dropout': 0.15,
            'weight_decay': 0.0005,
            'patience': 10,
        },
        'results': []
    }

    # Step 2: Train with different online augmentation levels
    for level_name, aug_params in ONLINE_AUG_LEVELS.items():
        try:
            print(f"\n{'='*60}")
            print(f"🧪 Testing online augmentation: {level_name.upper()}")
            print(f"{'='*60}")

            model = YOLO(MODEL_WEIGHTS)
            start_time = time.time()
            model.train(
                data=yaml_path,
                epochs=EPOCHS,
                imgsz=IMAGE_SIZE,
                batch=BATCH_SIZE,
                device=0,
                project=RESULTS_BASE,
                name=f"online_{level_name}",
                freeze=FREEZE_LAYERS,
                exist_ok=True,
                verbose=True,
                workers=0,
                plots=True,
                patience=10,
                dropout=0.15,
                weight_decay=0.0005,
                **aug_params,
            )
            training_time = time.time() - start_time

            # Extract results
            import pandas as pd
            csv_path = os.path.join(RESULTS_BASE, f"online_{level_name}", "results.csv")
            df = pd.read_csv(csv_path)
            df.columns = df.columns.str.strip()

            best_idx = df['metrics/mAP50-95(B)'].idxmax()
            best = df.iloc[best_idx]
            p = float(best['metrics/precision(B)'])
            r = float(best['metrics/recall(B)'])
            f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0

            result = {
                'level': level_name,
                'training_time_seconds': round(training_time, 1),
                'training_time_min': round(training_time / 60, 1),
                'epochs_completed': len(df),
                'best_epoch': int(best['epoch']),
                'precision': round(p, 4),
                'recall': round(r, 4),
                'f1': round(f1, 4),
                'mAP50': round(float(best['metrics/mAP50(B)']), 4),
                'mAP50_95': round(float(best['metrics/mAP50-95(B)']), 4),
            }
            results.append(result)
            experiment_log['results'].append(result)

            print(f"\n✅ {level_name} Complete: mAP50-95={result['mAP50_95']}, F1={result['f1']}")

        except Exception as e:
            print(f"❌ Failed for {level_name}: {e}")
            import traceback
            traceback.print_exc()
            experiment_log['results'].append({'level': level_name, 'error': str(e)})

    # Print summary
    print(f"\n{'='*90}")
    print("📊 ONLINE AUGMENTATION EXPERIMENT (Base: 5x Offline Aug, 594 images)")
    print(f"{'='*90}")
    print(f"{'Level':<12} {'Epochs':<8} {'Best':<6} {'Time':<8} {'Prec':<8} {'Recall':<8} {'F1':<8} {'mAP50':<8} {'mAP50-95':<10}")
    print("-" * 90)
    for r in results:
        print(f"{r['level']:<12} {r['epochs_completed']:<8} {r['best_epoch']:<6} "
              f"{r['training_time_min']:<8} {r['precision']:<8} {r['recall']:<8} {r['f1']:<8} "
              f"{r['mAP50']:<8} {r['mAP50_95']:<10}")

    if results:
        best = max(results, key=lambda x: x['mAP50_95'])
        print(f"\n🏆 Best: {best['level']} online augmentation (mAP50-95: {best['mAP50_95']})")

    # Save
    save_dir = os.path.join(os.path.dirname(__file__), "online_aug_experiments")
    os.makedirs(save_dir, exist_ok=True)
    with open(os.path.join(save_dir, "experiment_results.json"), 'w') as f:
        json.dump(experiment_log, f, indent=2)
    print(f"\n📄 Results saved to online_aug_experiments/experiment_results.json")


if __name__ == "__main__":
    main()
