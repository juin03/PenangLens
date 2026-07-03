# YOLO Model Size Experiment Report

**Date:** 2026-04-05 10:46:12  
**GPU:** NVIDIA GeForce RTX 4050 Laptop GPU

## Configuration

| Parameter | Value |
|-----------|-------|
| Epochs | 50 |
| Batch Size | 16 |
| Image Size | 640 |
| Freeze Layers | 10 |
| Dropout | 0.15 |
| Weight Decay | 0.0005 |
| Patience | 5 |
| Augmentation | 5x (optimal) |

## Training Summary

| Model | Parameters | Epochs Completed | Best Epoch | Early Stop | Training Time |
|-------|------------|------------------|------------|------------|---------------|
| YOLO11-nano | 2.6M | 14/50 | 9 | Yes | 14.00 minutes (0.23 hours) |
| YOLO11-small | 9.4M | 16/50 | 11 | Yes | 16.00 minutes (0.27 hours) |
| YOLO11-medium | 20.1M | 21/50 | 16 | Yes | 21.00 minutes (0.35 hours) |
| YOLO11-large | 25.3M | 22/50 | 17 | Yes | 22.00 minutes (0.37 hours) |

## Results Summary

| Model | Precision | Recall | F1 Score | mAP50 | mAP50-95 | Train Loss | Val Loss |
|-------|-----------|--------|----------|-------|----------|------------|----------|
| YOLO11-nano | 0.8217 | 0.7871 | 0.8040 | 0.8703 | 0.5550 | 1.1833 | 1.5816 |
| YOLO11-small | 0.8813 | 0.8254 | 0.8525 | 0.9126 | 0.6040 | 0.9578 | 1.3766 |
| YOLO11-medium | 0.8903 | 0.8750 | 0.8826 | 0.9279 | 0.6520 | 0.8033 | 1.2813 |
| YOLO11-large | 0.8625 | 0.8418 | 0.8520 | 0.9127 | 0.6374 | 0.8462 | 1.2825 |

## Best Metrics (Per Model Size)

| Model | Best Epoch | Best mAP50 | Best mAP50-95 | Best Precision | Best Recall |
|-------|------------|------------|---------------|----------------|-------------|
| YOLO11-nano | 9 | 0.8464 | 0.5568 | 0.7243 | 0.8115 |
| YOLO11-small | 11 | 0.8977 | 0.6164 | 0.8265 | 0.8433 |
| YOLO11-medium | 16 | 0.9093 | 0.6527 | 0.8729 | 0.8476 |
| YOLO11-large | 17 | 0.8980 | 0.6405 | 0.7502 | 0.8212 |

## Conclusion

**Best Model:** YOLO11-medium

### Best Model Performance
- Parameters: 20.1M
- Best mAP50-95: **0.6527** (achieved at epoch 16)
- Best mAP50: 0.9093
- Best Precision: 0.8729
- Best Recall: 0.8476

### Final Model Performance
- Final Precision: 0.8903
- Final Recall: 0.8750
- Final F1 Score: 0.8826
- Final Validation Loss: 1.2813

### Training Details
- Epochs Completed: 21/50
- Early Stopping: Triggered

This model size provides the best balance between accuracy, speed, and resource usage.

## Model Weights

All trained models are saved in `C:\Users\User\Desktop\USM\Y4\FYP\runs\detect\model_size_experiments`:
- `yolo11nano/weights/best.pt` (best at epoch 9)
- `yolo11nano/weights/last.pt` (final at epoch 14)
- `yolo11small/weights/best.pt` (best at epoch 11)
- `yolo11small/weights/last.pt` (final at epoch 16)
- `yolo11medium/weights/best.pt` (best at epoch 16)
- `yolo11medium/weights/last.pt` (final at epoch 21)
- `yolo11large/weights/best.pt` (best at epoch 17)
- `yolo11large/weights/last.pt` (final at epoch 22)
