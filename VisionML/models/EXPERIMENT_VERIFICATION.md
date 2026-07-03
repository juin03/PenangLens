# Augmentation Experiment Verification

## Parameter Comparison: Original vs Experiment

### ✅ IDENTICAL PARAMETERS (Controlled Variables)

| Parameter | Original (yolo11_partial_training.py) | Experiment (augmentation_experiment.py) | Status |
|-----------|--------------------------------------|----------------------------------------|--------|
| EPOCHS | 50 | 50 | ✅ SAME |
| IMAGE_SIZE | 640 | 640 | ✅ SAME |
| BATCH_SIZE | 16 | 16 | ✅ SAME |
| FREEZE_LAYERS | 10 | 10 | ✅ SAME |
| MODEL_WEIGHTS | yolo11s.pt | yolo11s.pt | ✅ SAME |
| patience | 10 | 10 | ✅ SAME |
| dropout | 0.15 | 0.15 | ✅ SAME |
| weight_decay | 0.0005 | 0.0005 | ✅ SAME |
| workers | 0 | 0 | ✅ SAME |
| plots | True | True | ✅ SAME |
| verbose | True | True | ✅ SAME |
| exist_ok | True | True | ✅ SAME |

### 🔄 VARIABLE PARAMETERS (Independent Variable)

| Augmentation Factor | hsv_h | hsv_s | hsv_v | degrees | fliplr | translate | scale |
|---------------------|-------|-------|-------|---------|--------|-----------|-------|
| 0x (No Aug) | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 5x (Light) | 0.01 | 0.5 | 0.2 | 5.0 | 0.5 | - | - |
| 10x (Moderate) | 0.015 | 0.7 | 0.4 | 10.0 | 0.5 | - | - |
| 15x (Heavy) | 0.02 | 0.9 | 0.5 | 15.0 | 0.5 | 0.1 | 0.2 |

### 📁 Output Locations

- **Original Training**: `./results/partial_finetuning/weights/best.pt` (UNTOUCHED)
- **Experiment Results**: `./aug_experiments/aug_Nx/weights/best.pt` (NEW)

## Conclusion

✅ **100% IDENTICAL** except for augmentation parameters  
✅ Valid ablation study - only one variable changes  
✅ Original best.pt is safe and won't be overwritten
