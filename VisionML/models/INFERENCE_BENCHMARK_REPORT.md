# YOLO11 Inference Time Benchmark Report

**Date:** 2026-04-05 11:00:30

## Test Configuration

- Warmup runs: 10
- Benchmark runs: 50
- Test images: 10 per run
- Total inferences per model: 500

## Results

### CPU Performance

| Model | Avg (ms) | Median (ms) | Min (ms) | Max (ms) | FPS | Speedup |
|-------|----------|-------------|----------|----------|-----|----------|
| nano | 85.69 | 84.39 | 71.70 | 162.42 | 11.7 | 1.00x |
| small | 171.10 | 164.69 | 123.97 | 516.25 | 5.8 | 0.50x |
| medium | 421.69 | 419.68 | 389.55 | 542.27 | 2.4 | 0.20x |
| large | 509.61 | 508.01 | 393.38 | 742.53 | 2.0 | 0.17x |

### CUDA Performance

| Model | Avg (ms) | Median (ms) | Min (ms) | Max (ms) | FPS | Speedup |
|-------|----------|-------------|----------|----------|-----|----------|
| nano | 37.80 | 37.52 | 24.42 | 54.23 | 26.5 | 1.00x |
| small | 36.35 | 36.40 | 23.05 | 57.16 | 27.5 | 1.04x |
| medium | 38.19 | 38.31 | 24.82 | 57.64 | 26.2 | 0.99x |
| large | 44.06 | 43.01 | 33.67 | 91.77 | 22.7 | 0.86x |

## Conclusion

**Fastest Model (GPU):** small
- Average inference time: 36.35 ms
- FPS: 27.5

## Accuracy vs Speed Tradeoff

| Model | mAP50-95 | Inference (ms) | Parameters | Recommendation |
|-------|----------|----------------|------------|----------------|
| nano | 0.5568 | fastest | 2.6M | Best for real-time |
| small | 0.6164 | fast | 9.4M | Balanced |
| medium | 0.6527 | moderate | 20.1M | Best accuracy |
