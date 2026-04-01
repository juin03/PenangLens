"""
PenangLens: Local Augmentation for Training Set
------------------------------------------------
Augments ONLY the train split of each landmark dataset.
Valid and test sets are left untouched.

Usage:
    python augment.py              # augment all landmarks (10x)
    python augment.py --factor 5   # augment 5x instead
"""

import os
import sys
import cv2
import numpy as np
import shutil
import random
import argparse

DATASET_ROOT = os.path.join(os.path.dirname(__file__), "Dataset")
random.seed(42)
np.random.seed(42)


def augment_image_and_labels(img, bboxes, img_h, img_w):
    """Apply a random combination of augmentations to image and bounding boxes.
    bboxes: list of [class_id, cx, cy, w, h] in YOLO normalized format.
    Returns augmented image and adjusted bboxes.
    """
    aug_img = img.copy()
    aug_bboxes = [b[:] for b in bboxes]

    # 1. Horizontal flip (50%)
    if random.random() < 0.5:
        aug_img = cv2.flip(aug_img, 1)
        for b in aug_bboxes:
            b[1] = 1.0 - b[1]  # flip cx

    # 2. Brightness/contrast
    if random.random() < 0.5:
        alpha = random.uniform(0.7, 1.3)  # contrast
        beta = random.randint(-30, 30)     # brightness
        aug_img = cv2.convertScaleAbs(aug_img, alpha=alpha, beta=beta)

    # 3. Gaussian blur
    if random.random() < 0.3:
        ksize = random.choice([3, 5])
        aug_img = cv2.GaussianBlur(aug_img, (ksize, ksize), 0)

    # 4. Color jitter (HSV)
    if random.random() < 0.5:
        hsv = cv2.cvtColor(aug_img, cv2.COLOR_BGR2HSV).astype(np.int16)
        hsv[:, :, 0] = np.clip(hsv[:, :, 0] + random.randint(-10, 10), 0, 179)
        hsv[:, :, 1] = np.clip(hsv[:, :, 1] + random.randint(-30, 30), 0, 255)
        aug_img = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)

    # 5. Gaussian noise
    if random.random() < 0.3:
        noise = np.random.normal(0, 10, aug_img.shape).astype(np.int16)
        aug_img = np.clip(aug_img.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    # 6. Small rotation (±10 degrees) — skip bbox adjustment for small angles
    if random.random() < 0.3:
        angle = random.uniform(-10, 10)
        M = cv2.getRotationMatrix2D((img_w / 2, img_h / 2), angle, 1.0)
        aug_img = cv2.warpAffine(aug_img, M, (img_w, img_h), borderMode=cv2.BORDER_REFLECT_101)

    return aug_img, aug_bboxes


def parse_yolo_labels(label_path):
    """Read YOLO format label file."""
    bboxes = []
    if not os.path.exists(label_path):
        return bboxes
    with open(label_path, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 5:
                bboxes.append([int(parts[0])] + [float(x) for x in parts[1:5]])
    return bboxes


def write_yolo_labels(label_path, bboxes):
    """Write YOLO format label file."""
    with open(label_path, 'w') as f:
        for b in bboxes:
            f.write(f"{b[0]} {b[1]:.6f} {b[2]:.6f} {b[3]:.6f} {b[4]:.6f}\n")


def augment_landmark(landmark_path, factor=10):
    """Augment the train split of a single landmark."""
    train_img_dir = os.path.join(landmark_path, "train", "images")
    train_lbl_dir = os.path.join(landmark_path, "train", "labels")

    if not os.path.exists(train_img_dir):
        return 0

    images = [f for f in os.listdir(train_img_dir)
              if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))]

    count = 0
    for img_file in images:
        img_path = os.path.join(train_img_dir, img_file)
        label_file = os.path.splitext(img_file)[0] + ".txt"
        label_path = os.path.join(train_lbl_dir, label_file)

        img = cv2.imread(img_path)
        if img is None:
            continue
        img_h, img_w = img.shape[:2]
        bboxes = parse_yolo_labels(label_path)

        for i in range(factor):
            aug_img, aug_bboxes = augment_image_and_labels(img, bboxes, img_h, img_w)

            # Save augmented image
            base = os.path.splitext(img_file)[0]
            ext = os.path.splitext(img_file)[1]
            new_img_name = f"{base}_aug{i}{ext}"
            new_lbl_name = f"{base}_aug{i}.txt"

            cv2.imwrite(os.path.join(train_img_dir, new_img_name), aug_img)
            write_yolo_labels(os.path.join(train_lbl_dir, new_lbl_name), aug_bboxes)
            count += 1

    return count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--factor", type=int, default=10, help="Augmentation multiplier")
    args = parser.parse_args()

    print(f"🔄 Augmenting train sets ({args.factor}x per image)...\n")

    total = 0
    for folder in sorted(os.listdir(DATASET_ROOT)):
        folder_path = os.path.join(DATASET_ROOT, folder)
        if not os.path.isdir(folder_path) or folder == "all":
            continue

        count = augment_landmark(folder_path, args.factor)
        total += count
        train_dir = os.path.join(folder_path, "train", "images")
        final_count = len([f for f in os.listdir(train_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]) if os.path.exists(train_dir) else 0
        print(f"  📍 {folder}: +{count} augmented → {final_count} total train images")

    print(f"\n✅ Augmentation complete! {total} new images created.")
    print("🚀 Now run: python prepare.py  (with SKIP_DOWNLOAD=True to just re-merge)")


if __name__ == "__main__":
    main()
