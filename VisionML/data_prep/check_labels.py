import os

DATASET_ROOT = os.path.join(os.path.dirname(__file__), "Dataset")

for folder in sorted(os.listdir(DATASET_ROOT)):
    folder_path = os.path.join(DATASET_ROOT, folder)
    if not os.path.isdir(folder_path) or folder == "all":
        continue

    bbox = 0
    poly = 0
    for split in ['train', 'valid', 'test']:
        lbl_dir = os.path.join(folder_path, split, 'labels')
        if not os.path.exists(lbl_dir):
            continue
        for f in os.listdir(lbl_dir):
            if not f.endswith('.txt'):
                continue
            with open(os.path.join(lbl_dir, f)) as fh:
                for line in fh:
                    fields = len(line.strip().split())
                    if fields == 5:
                        bbox += 1
                    elif fields > 5:
                        poly += 1

    status = "✅ All bounding boxes" if poly == 0 else f"❌ {poly} polygon labels found!"
    print(f"📍 {folder}: {bbox} bbox, {poly} polygon → {status}")
