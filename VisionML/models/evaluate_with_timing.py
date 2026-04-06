"""
PenangLens: Model Evaluation with Inference Time
-------------------------------------------------
Evaluates trained YOLO models and measures inference speed.

Usage:
    python evaluate_with_timing.py
"""

import os
import sys
import yaml
import torch
import time
import numpy as np
from ultralytics import YOLO

# ==============================================================================
# CONFIGURATION
# ==============================================================================
DATASET_LOCATION = r"C:\Users\User\Desktop\USM\Y4\FYP\PenangLens\VisionML\data_prep\Dataset"

# Models to evaluate
MODELS = {
    'YOLO11n': r"C:\Users\User\Desktop\USM\Y4\FYP\runs\detect\model_size_experiments\yolo11n\weights\best.pt",
    'YOLO11s': r"C:\Users\User\Desktop\USM\Y4\FYP\runs\detect\model_size_experiments\yolo11s\weights\best.pt",
    'YOLO11m': r"C:\Users\User\Desktop\USM\Y4\FYP\runs\detect\model_size_experiments\yolo11m\weights\best.pt",
    'YOLO11l': r"C:\Users\User\Desktop\USM\Y4\FYP\runs\detect\model_size_experiments\yolo11l\weights\best.pt",
}

def check_gpu():
    if torch.cuda.is_available():
        print(f"✅ GPU: {torch.cuda.get_device_name(0)}")
        return 0
    print("⚠️ No GPU — using CPU")
    return "cpu"

def measure_inference_time(model, test_images, device='cuda', warmup=10, runs=50):
    """Measure inference time on test images."""
    print(f"\n  Measuring inference time ({runs} runs)...")
    
    # Warmup
    for _ in range(warmup):
        for img in test_images[:5]:  # Use first 5 images for warmup
            _ = model.predict(img, verbose=False, device=device)
    
    # Benchmark
    times = []
    for _ in range(runs):
        for img in test_images:
            start = time.time()
            _ = model.predict(img, verbose=False, device=device)
            end = time.time()
            times.append((end - start) * 1000)  # Convert to ms
    
    times = np.array(times)
    return {
        'avg_ms': np.mean(times),
        'median_ms': np.median(times),
        'std_ms': np.std(times),
        'min_ms': np.min(times),
        'max_ms': np.max(times),
        'fps': 1000 / np.mean(times)
    }

def evaluate_model(model_name, model_path, device):
    """Evaluate a single model."""
    print(f"\n{'='*70}")
    print(f"📊 EVALUATING: {model_name}")
    print(f"{'='*70}")
    
    if not os.path.exists(model_path):
        print(f"❌ Model not found: {model_path}")
        return None
    
    model = YOLO(model_path)
    all_yaml = os.path.join(DATASET_LOCATION, "all", "data.yaml")
    
    # Fix paths in data.yaml
    with open(all_yaml, 'r') as f:
        data = yaml.safe_load(f)
    data['path'] = os.path.join(DATASET_LOCATION, "all").replace("\\", "/")
    data['val'] = "valid/images"
    data['test'] = "test/images"
    with open(all_yaml, 'w') as f:
        yaml.dump(data, f, sort_keys=False)
    
    # Get test images
    test_dir = os.path.join(DATASET_LOCATION, "all", "test", "images")
    test_images = [os.path.join(test_dir, f) for f in os.listdir(test_dir) 
                   if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))][:10]
    
    print(f"Test images: {len(test_images)}")
    
    # Measure GPU inference time
    timing_gpu = measure_inference_time(model, test_images, device=device)
    
    print(f"\n  ⏱️  GPU Inference Time:")
    print(f"     Average: {timing_gpu['avg_ms']:.2f} ms ({timing_gpu['fps']:.1f} FPS)")
    print(f"     Median:  {timing_gpu['median_ms']:.2f} ms")
    print(f"     Min:     {timing_gpu['min_ms']:.2f} ms")
    print(f"     Max:     {timing_gpu['max_ms']:.2f} ms")
    
    # Measure CPU inference time
    timing_cpu = measure_inference_time(model, test_images, device='cpu')
    
    print(f"\n  ⏱️  CPU Inference Time:")
    print(f"     Average: {timing_cpu['avg_ms']:.2f} ms ({timing_cpu['fps']:.1f} FPS)")
    print(f"     Median:  {timing_cpu['median_ms']:.2f} ms")
    print(f"     Min:     {timing_cpu['min_ms']:.2f} ms")
    print(f"     Max:     {timing_cpu['max_ms']:.2f} ms")
    print(f"     Slowdown: {timing_cpu['avg_ms'] / timing_gpu['avg_ms']:.2f}x vs GPU")
    
    # Evaluate accuracy
    print(f"\n  📊 Evaluating accuracy on test set...")
    results = model.val(data=all_yaml, split="test", device=device, batch=4, workers=0, verbose=False)
    
    print(f"\n  📈 Accuracy Metrics:")
    print(f"     mAP@50:    {results.box.map50:.4f}")
    print(f"     mAP@50-95: {results.box.map:.4f}")
    print(f"     Precision: {results.box.mp:.4f}")
    print(f"     Recall:    {results.box.mr:.4f}")
    
    return {
        'model': model_name,
        'inference_gpu': timing_gpu,
        'inference_cpu': timing_cpu,
        'accuracy': {
            'mAP50': float(results.box.map50),
            'mAP50_95': float(results.box.map),
            'precision': float(results.box.mp),
            'recall': float(results.box.mr)
        }
    }

def main():
    print("🚀 YOLO Model Evaluation with Inference Timing")
    print("="*70)
    
    device = check_gpu()
    all_results = []
    
    for model_name, model_path in MODELS.items():
        result = evaluate_model(model_name, model_path, device)
        if result:
            all_results.append(result)
    
    # Print comparison table
    print(f"\n{'='*110}")
    print("📊 COMPARISON TABLE")
    print(f"{'='*110}")
    print(f"{'Model':<12} {'GPU (ms)':<12} {'GPU FPS':<10} {'CPU (ms)':<12} {'CPU FPS':<10} {'mAP50':<10} {'mAP50-95':<10} {'Precision':<10} {'Recall':<10}")
    print("-"*110)
    
    for r in all_results:
        print(f"{r['model']:<12} {r['inference_gpu']['avg_ms']:<12.2f} {r['inference_gpu']['fps']:<10.1f} "
              f"{r['inference_cpu']['avg_ms']:<12.2f} {r['inference_cpu']['fps']:<10.1f} "
              f"{r['accuracy']['mAP50']:<10.4f} {r['accuracy']['mAP50_95']:<10.4f} "
              f"{r['accuracy']['precision']:<10.4f} {r['accuracy']['recall']:<10.4f}")
    
    # Save results
    import json
    output_path = "./evaluation_with_timing_results.json"
    with open(output_path, 'w') as f:
        json.dump(all_results, f, indent=2)
    print(f"\n✅ Results saved to: {output_path}")
    
    # Find best
    if all_results:
        best_accuracy = max(all_results, key=lambda x: x['accuracy']['mAP50_95'])
        best_speed_gpu = min(all_results, key=lambda x: x['inference_gpu']['avg_ms'])
        best_speed_cpu = min(all_results, key=lambda x: x['inference_cpu']['avg_ms'])
        
        print(f"\n🏆 Best Accuracy: {best_accuracy['model']} (mAP50-95: {best_accuracy['accuracy']['mAP50_95']:.4f})")
        print(f"⚡ Fastest GPU: {best_speed_gpu['model']} ({best_speed_gpu['inference_gpu']['avg_ms']:.2f} ms, {best_speed_gpu['inference_gpu']['fps']:.1f} FPS)")
        print(f"⚡ Fastest CPU: {best_speed_cpu['model']} ({best_speed_cpu['inference_cpu']['avg_ms']:.2f} ms, {best_speed_cpu['inference_cpu']['fps']:.1f} FPS)")

if __name__ == "__main__":
    main()
