"""
Debug: Compare ground truth vs model predictions for problem classes
"""
import os
from ultralytics import YOLO

MODEL_PATH = r"C:\Users\User\Desktop\USM\Y4\FYP\runs\detect\results\partial_finetuning\weights\best.pt"
TEST_DIR = r"C:\Users\User\Desktop\USM\Y4\FYP\PenangLens\VisionML\data_prep\Dataset\all\test"

# Problem classes to check
CHECK_CLASSES = {6: "holy_vase", 10: "arched_arcade", 18: "burmese_spire"}

model = YOLO(MODEL_PATH)
labels_dir = os.path.join(TEST_DIR, "labels")

for label_file in sorted(os.listdir(labels_dir)):
    if not label_file.endswith('.txt'):
        continue
    with open(os.path.join(labels_dir, label_file), 'r') as f:
        lines = f.readlines()

    for line in lines:
        cls_id = int(line.strip().split()[0])
        if cls_id not in CHECK_CLASSES:
            continue

        image_file = label_file.replace('.txt', '.jpg')
        image_path = os.path.join(TEST_DIR, "images", image_file)
        if not os.path.exists(image_path):
            continue

        print(f"\n{'='*60}")
        print(f"Image: {image_file}")
        print(f"Ground truth: class={cls_id} ({CHECK_CLASSES[cls_id]}) → {line.strip()}")
        print(f"{'='*60}")

        results = model.predict(image_path, conf=0.25, verbose=False)
        for r in results:
            for box in r.boxes:
                c = int(box.cls[0])
                conf = float(box.conf[0])
                xyxy = box.xyxy[0].tolist()
                name = model.names[c]
                print(f"  Detected: class={c} ({name}) conf={conf:.3f} box={xyxy}")
        break  # Only check first occurrence per file
