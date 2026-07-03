# PenangLens YOLO11 Training Log

---

## Run 1: Initial Training (Before Fixes)
**Date:** 2026-03-29
**Script:** `yolo11_partial_training.py`
**Model:** YOLO11s (partial fine-tuning, freeze 10 layers)
**Dataset Versions:** st_george v2, mosque v3, queen_victoria v2, khoo_kongsi v2, fort_cornwallis v2, guan_yin v3, pagoda v9
**Config:** epochs=50, batch=8, dropout=0.1, patience=10, augment=10x
**Bug:** val/test pointed to train/images — early stopping never triggered, validated on training data

### Training
- Epochs completed: 50/50 (early stopping did NOT trigger)
- Training time: 0.874 hours
- Final train val mAP@50: 0.977 (fake — was testing on training data)
- Final train val mAP@50-95: 0.900 (fake)

### Test Evaluation (13 test images, 76 instances)
| Metric | Value |
|--------|-------|
| mAP@50 | 0.8491 |
| mAP@50-95 | 0.5508 |
| Val-Test Gap (mAP@50-95) | 0.349 (severe overfitting) |

### Per-Class Test Results
| Class | mAP@50 | mAP@50-95 |
|-------|--------|-----------|
| fort_cornwallis_chapel | 0.9950 | 0.2985 |
| fort_cornwallis_lighthouse | 0.9950 | 0.4975 |
| seri_rambai_cannon | 0.0000 | 0.0000 |
| statue_francis_light | 0.0000 | 0.0000 |
| dragon_pillar | 0.8839 | 0.3752 |
| guan_yin_statue | 0.9950 | 0.8012 |
| holy_vase | 0.3317 | 0.1658 |
| lotus_base | 0.9950 | 0.4975 |
| three_tiered_pavilion_roof | 0.9950 | 0.9330 |
| arched_arcade | 0.9125 | 0.3995 |
| arched_gateway | 0.1244 | 0.0498 |
| crescent_finial | 0.9950 | 0.1948 |
| guldastas | 0.9950 | 0.7040 |
| minaret | 0.9441 | 0.5723 |
| onion_dome | 0.9950 | 0.5827 |
| guardian_lion | 0.9950 | 0.8271 |
| main_ridge | 0.9950 | 0.3271 |
| swallowtail_roof | 0.9950 | 0.8955 |
| burmese_spire | 0.9950 | 0.4758 |
| chinese_base | 0.9950 | 0.7960 |
| thai_tier | 0.9950 | 0.8955 |
| balcony_tier | 0.5314 | 0.2126 |
| clock_face | 0.9950 | 0.8955 |
| golden_cupola | 0.9950 | 0.7960 |
| octagonal_base | 0.9950 | 0.7960 |
| pinang_sculpture | 0.9950 | 0.6965 |
| church_steeple | 0.9950 | 0.8955 |
| dome_pavilion | 0.9950 | 0.6965 |
| front_portico | 0.9950 | 0.6965 |

### Per-Landmark Test Results
| Landmark | mAP@50 | mAP@50-95 | Classes |
|----------|--------|-----------|---------|
| fort_cornwallis | 0.4975 | 0.1990 | 4 |
| guan_yin_teng | 0.8401 | 0.5545 | 5 |
| kapitan_keling_mosque | 0.8277 | 0.4172 | 6 |
| khoo_kongsi | 0.9950 | 0.6832 | 3 |
| pagoda_rama_vi | 0.9950 | 0.7224 | 3 |
| queen_victoria_memorial_clock | 0.9023 | 0.6793 | 5 |
| st_george_church | 0.9950 | 0.7628 | 3 |

### Issues Identified
- val/test pointed to train/images → no real validation → no early stopping
- 2 classes with 0.0 detection (seri_rambai_cannon, statue_francis_light)
- Severe overfitting (val-test gap of 0.349)
- Test set too small (13 images)

---

## Run 2: Fixed Validation + More Data (2026-03-29)
**Date:** 2026-03-29
**Script:** `yolo11_partial_training.py`
**Model:** YOLO11s (partial fine-tuning, freeze 10 layers)
**Dataset Versions:** st_george v2, mosque v4, queen_victoria v3, khoo_kongsi v3, fort_cornwallis v3, guan_yin v4, pagoda v10
**Config:** epochs=50, batch=16, dropout=0.15, patience=10, augment=10x
**Fixes Applied:**
1. val → valid/images (proper validation split)
2. test → test/images (proper test split)
3. Updated Roboflow dataset versions (~5 new images per landmark)
4. Batch size 8 → 16
5. Dropout 0.1 → 0.15

### Training
- Epochs completed: 29/50 (early stopping triggered at epoch 29, best at epoch 19)
- Training time: 0.394 hours
- Best val mAP@50: 0.899 (real validation on 29 images)
- Best val mAP@50-95: 0.657 (real)

### Training Progression (key epochs)
| Epoch | box_loss | cls_loss | dfl_loss | mAP@50 | mAP@50-95 |
|-------|----------|----------|----------|--------|-----------|
| 1 | 1.737 | 3.744 | 1.614 | 0.612 | 0.389 |
| 5 | 1.206 | 0.982 | 1.204 | 0.871 | 0.593 |
| 10 | 0.999 | 0.722 | 1.120 | 0.887 | 0.605 |
| 15 | 0.869 | 0.608 | 1.054 | 0.914 | 0.637 |
| 19* | 0.829 | 0.574 | 1.038 | 0.899 | 0.658 |
| 25 | 0.751 | 0.512 | 1.002 | 0.921 | 0.655 |
| 29 | 0.695 | 0.478 | 0.979 | 0.892 | 0.655 |

*Best model saved at epoch 19

### Validation Results (best.pt on 29 val images, 138 instances)
| Class | Images | Instances | P | R | mAP@50 | mAP@50-95 |
|-------|--------|-----------|---|---|--------|-----------|
| all | 29 | 138 | 0.835 | 0.813 | 0.899 | 0.657 |
| fort_cornwallis_chapel | 2 | 2 | 0.608 | 1.000 | 0.995 | 0.822 |
| fort_cornwallis_lighthouse | 3 | 3 | 1.000 | 0.839 | 0.995 | 0.497 |
| seri_rambai_cannon | 3 | 3 | 1.000 | 0.772 | 0.995 | 0.611 |
| statue_francis_light | 2 | 2 | 0.822 | 1.000 | 0.995 | 0.850 |
| dragon_pillar | 7 | 30 | 0.939 | 0.733 | 0.858 | 0.428 |
| guan_yin_statue | 4 | 4 | 0.848 | 1.000 | 0.995 | 0.842 |
| holy_vase | 4 | 4 | 0.402 | 0.201 | 0.345 | 0.088 |
| lotus_base | 3 | 3 | 0.911 | 0.667 | 0.913 | 0.733 |
| three_tiered_pavilion_roof | 2 | 2 | 0.875 | 1.000 | 0.995 | 0.852 |
| arched_arcade | 3 | 3 | 0.000 | 0.000 | 0.122 | 0.046 |
| arched_gateway | 2 | 2 | 0.686 | 0.500 | 0.745 | 0.700 |
| crescent_finial | 3 | 8 | 1.000 | 0.444 | 0.967 | 0.512 |
| guldastas | 3 | 5 | 0.920 | 1.000 | 0.995 | 0.749 |
| onion_dome | 3 | 12 | 0.908 | 0.820 | 0.976 | 0.734 |
| guardian_lion | 3 | 4 | 0.971 | 0.750 | 0.788 | 0.588 |
| main_ridge | 4 | 4 | 1.000 | 0.880 | 0.995 | 0.727 |
| swallowtail_roof | 4 | 13 | 1.000 | 0.612 | 0.760 | 0.439 |
| burmese_spire | 3 | 3 | 0.865 | 1.000 | 0.995 | 0.831 |
| chinese_base | 3 | 3 | 0.897 | 1.000 | 0.995 | 0.729 |
| thai_tier | 4 | 4 | 0.745 | 1.000 | 0.995 | 0.806 |
| balcony_tier | 3 | 3 | 0.916 | 1.000 | 0.995 | 0.931 |
| clock_face | 3 | 5 | 1.000 | 0.707 | 0.995 | 0.536 |
| golden_cupola | 3 | 3 | 0.911 | 1.000 | 0.995 | 0.814 |
| octagonal_base | 3 | 3 | 0.642 | 0.667 | 0.693 | 0.525 |
| pinang_sculpture | 2 | 2 | 0.858 | 1.000 | 0.995 | 0.778 |
| church_steeple | 2 | 2 | 0.849 | 1.000 | 0.995 | 0.701 |
| dome_pavilion | 2 | 2 | 0.838 | 1.000 | 0.995 | 0.895 |
| front_portico | 2 | 2 | 0.842 | 1.000 | 0.995 | 0.850 |
| tower_clock | 2 | 2 | 0.960 | 1.000 | 0.995 | 0.453 |

### Test Evaluation (22 test images, 110 instances)
| Metric | Value |
|--------|-------|
| mAP@50 | 0.9036 |
| mAP@50-95 | 0.6216 |
| Val-Test Gap (mAP@50-95) | 0.035 (healthy) |

### Per-Class Test Results
| Class | mAP@50 | mAP@50-95 |
|-------|--------|-----------|
| fort_cornwallis_chapel | 0.9950 | 0.8984 |
| fort_cornwallis_lighthouse | 0.9950 | 0.5994 |
| seri_rambai_cannon | 0.9950 | 0.5506 |
| statue_francis_light | 0.9950 | 0.6100 |
| dragon_pillar | 0.8842 | 0.3889 |
| guan_yin_statue | 0.9950 | 0.7243 |
| holy_vase | 0.0000 | 0.0000 |
| lotus_base | 0.9950 | 0.7033 |
| three_tiered_pavilion_roof | 0.9950 | 0.7960 |
| arched_arcade | 0.5596 | 0.2930 |
| arched_gateway | 0.8283 | 0.5506 |
| crescent_finial | 0.9950 | 0.3097 |
| guldastas | 0.7850 | 0.5282 |
| minaret | 0.8942 | 0.4786 |
| onion_dome | 0.9950 | 0.6898 |
| guardian_lion | 0.9950 | 0.8589 |
| main_ridge | 0.9950 | 0.4384 |
| swallowtail_roof | 0.9950 | 0.8687 |
| burmese_spire | 0.6810 | 0.2907 |
| chinese_base | 0.9950 | 0.7148 |
| thai_tier | 0.9950 | 0.8955 |
| balcony_tier | 0.6755 | 0.4105 |
| clock_face | 0.9950 | 0.6508 |
| golden_cupola | 0.9950 | 0.8955 |
| octagonal_base | 0.9950 | 0.9950 |
| pinang_sculpture | 0.9950 | 0.6965 |
| church_steeple | 0.9950 | 0.6965 |
| dome_pavilion | 0.9950 | 0.7960 |
| front_portico | 0.9950 | 0.6965 |

### Per-Landmark Test Results
| Landmark | mAP@50 | mAP@50-95 | Classes |
|----------|--------|-----------|---------|
| fort_cornwallis | 0.9950 | 0.6646 | 4 |
| guan_yin_teng | 0.7738 | 0.5225 | 5 |
| kapitan_keling_mosque | 0.8429 | 0.4750 | 6 |
| khoo_kongsi | 0.9950 | 0.7220 | 3 |
| pagoda_rama_vi | 0.8903 | 0.6337 | 3 |
| queen_victoria_memorial_clock | 0.9311 | 0.7297 | 5 |
| st_george_church | 0.9950 | 0.7297 | 3 |

### Comparison: Run 1 vs Run 2
| Metric | Run 1 | Run 2 | Change |
|--------|-------|-------|--------|
| Test mAP@50 | 0.849 | 0.904 | +5.5% ✅ |
| Test mAP@50-95 | 0.551 | 0.622 | +7.1% ✅ |
| Val-Test Gap | 0.349 | 0.035 | Fixed ✅ |
| Epochs | 50 | 29 | Early stop worked ✅ |
| Training Time | 0.874h | 0.394h | 55% faster ✅ |
| Zero-detection classes | 2 | 1 | Improved ✅ |

### Key Improvements (Run 1 → Run 2)
| Class | Run 1 | Run 2 | Change |
|-------|-------|-------|--------|
| seri_rambai_cannon | 0.000 | 0.551 | Fixed 🎉 |
| statue_francis_light | 0.000 | 0.610 | Fixed 🎉 |
| arched_gateway | 0.050 | 0.551 | +0.501 🎉 |
| fort_cornwallis_chapel | 0.299 | 0.898 | +0.599 🎉 |
| balcony_tier | 0.213 | 0.411 | +0.198 ✅ |

### Remaining Problem Classes (mAP@50-95 < 0.5 on test)
| Class | mAP@50 | mAP@50-95 | Issue |
|-------|--------|-----------|-------|
| holy_vase | 0.000 | 0.000 | Complete failure |
| burmese_spire | 0.681 | 0.291 | Poor detection |
| arched_arcade | 0.560 | 0.293 | Poor detection |
| crescent_finial | 0.995 | 0.310 | Bad localization |
| dragon_pillar | 0.884 | 0.389 | Moderate |
| balcony_tier | 0.676 | 0.411 | Moderate |
| main_ridge | 0.995 | 0.438 | Bad localization |
| tower_clock | — | 0.453 | Bad localization |
| minaret | 0.894 | 0.479 | Moderate |

---

## Debug Findings (Run 2)

### holy_vase — Complete Failure (0.0 mAP)
**Root Cause:** Objects are extremely tiny in test images
- Image 1: vase is 11% × 8.6% of image — very small
- Image 2: vase is 2.7% × 3.9% of image — nearly invisible
- Model detects other objects (guan_yin_statue, lotus_base) but misses the tiny vase
- When tested on index.html with the same image, model CAN detect it — but evaluation fails because box doesn't match ground truth at that scale
**Fix:** Add close-up training/test images where holy_vase is prominent in frame

### arched_arcade — Inter-Class Confusion (0.293 mAP@50-95)
**Root Cause:** Model confuses arched_arcade (class 9) with arched_gateway (class 10)
- Both classes have arch shapes — visually similar
- mosque_1 test image: ground truth says class 10 (arched_gateway), model predicts class 9 (arched_arcade)
- This counts as a miss for arched_gateway AND a false positive for arched_arcade — both classes penalized
- When uploaded to index.html, detection looks correct visually, but evaluation says 0 because predicted class doesn't match ground truth class
- Class ID mapping verified correct (Roboflow → merge is fine)
- Issue is either: (1) Roboflow labels have arcade/gateway swapped on some images, or (2) model can't distinguish them
**Fix:** 
1. Review Roboflow annotations — verify arcade vs gateway labels are correct
2. Add more distinct training examples of each (arcade = repeated arches in corridor, gateway = single entrance arch)

### burmese_spire — Poor Localization (0.291 mAP@50-95)
**Root Cause:** Model detects correctly (0.718-0.938 confidence) but bounding boxes don't align precisely with ground truth
- All 3 test images: burmese_spire detected successfully
- Low mAP@50-95 means boxes are roughly right but not tight enough
**Fix:** Check training label consistency — ensure all bounding boxes are drawn the same way

## Next Steps
- [ ] holy_vase: Add close-up images to Roboflow where vase is clearly visible and large in frame
- [ ] arched_arcade/gateway: Review and fix Roboflow annotations — verify correct class on each image
- [ ] burmese_spire: Check training label box consistency
- [ ] Add more training data for weak classes (< 0.5 mAP@50-95)
- [ ] Consider increasing test set size (currently 22 images) for more reliable evaluation
- [ ] Check label consistency for other bad localization classes (crescent_finial, main_ridge, tower_clock)
