"""
Benchmark inference time for different YOLO11 model sizes.
Tests on CPU and GPU with multiple images.
"""

import os
import time
import torch
import numpy as np
from ultralytics import YOLO

# Model paths
MODEL_PATHS = {
    'nano': r"C:\Users\User\Desktop\USM\Y4\FYP\runs\detect\model_size_experiments\yolo11n\weights\best.pt",
    'small': r"C:\Users\User\Desktop\USM\Y4\FYP\runs\detect\model_size_experiments\yolo11s\weights\best.pt",
    'medium': r"C:\Users\User\Desktop\USM\Y4\FYP\runs\detect\model_size_experiments\yolo11m\weights\best.pt",
    'large': r"C:\Users\User\Desktop\USM\Y4\FYP\runs\detect\model_size_experiments\yolo11l\weights\best.pt",
}

# Test images directory
TEST_IMAGES_DIR = r"C:\Users\User\Desktop\USM\Y4\FYP\PenangLens\VisionML\data_prep\Dataset\all\test\images"

def benchmark_model(model_path, model_name, device='cuda', num_runs=50, warmup=10):
    """Benchmark inference time for a model."""
    print(f"\n{'='*60}")
    print(f"Benchmarking {model_name.upper()} on {device.upper()}")
    print(f"{'='*60}")
    
    # Load model
    model = YOLO(model_path)
    model.to(device)
    
    # Get test images
    test_images = [os.path.join(TEST_IMAGES_DIR, f) for f in os.listdir(TEST_IMAGES_DIR) 
                   if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))][:10]
    
    if not test_images:
        print(f"❌ No test images found in {TEST_IMAGES_DIR}")
        return None
    
    print(f"Using {len(test_images)} test images")
    
    # Warmup runs
    print(f"Warming up ({warmup} runs)...")
    for _ in range(warmup):
        for img in test_images:
            _ = model.predict(img, verbose=False, device=device)
    
    # Benchmark runs
    print(f"Benchmarking ({num_runs} runs)...")
    times = []
    
    for i in range(num_runs):
        for img in test_images:
            start = time.time()
            _ = model.predict(img, verbose=False, device=device)
            end = time.time()
            times.append((end - start) * 1000)  # Convert to ms
    
    # Calculate statistics
    times = np.array(times)
    avg_time = np.mean(times)
    std_time = np.std(times)
    min_time = np.min(times)
    max_time = np.max(times)
    median_time = np.median(times)
    
    # Calculate FPS
    fps = 1000 / avg_time
    
    results = {
        'model': model_name,
        'device': device,
        'avg_ms': avg_time,
        'std_ms': std_time,
        'min_ms': min_time,
        'max_ms': max_time,
        'median_ms': median_time,
        'fps': fps,
        'total_runs': num_runs * len(test_images)
    }
    
    print(f"\n✅ Results:")
    print(f"   Average: {avg_time:.2f} ms ({fps:.1f} FPS)")
    print(f"   Median:  {median_time:.2f} ms")
    print(f"   Min:     {min_time:.2f} ms")
    print(f"   Max:     {max_time:.2f} ms")
    print(f"   Std Dev: {std_time:.2f} ms")
    
    return results

def main():
    print("🚀 YOLO11 Inference Time Benchmark")
    print("="*60)
    
    # Check GPU availability
    if torch.cuda.is_available():
        print(f"✅ GPU: {torch.cuda.get_device_name(0)}")
        devices = ['cuda', 'cpu']
    else:
        print("⚠️  No GPU detected, testing CPU only")
        devices = ['cpu']
    
    all_results = []
    
    for device in devices:
        for model_name, model_path in MODEL_PATHS.items():
            if os.path.exists(model_path):
                result = benchmark_model(model_path, model_name, device=device)
                if result:
                    all_results.append(result)
            else:
                print(f"\n❌ Model not found: {model_path}")
    
    # Print comparison table
    print(f"\n{'='*80}")
    print("📊 INFERENCE TIME COMPARISON")
    print(f"{'='*80}")
    
    for device in devices:
        device_results = [r for r in all_results if r['device'] == device]
        if device_results:
            print(f"\n{device.upper()} Performance:")
            print(f"{'Model':<15} {'Avg (ms)':<12} {'Median (ms)':<12} {'FPS':<10} {'Speedup':<10}")
            print("-" * 80)
            
            baseline = device_results[0]['avg_ms']
            for r in device_results:
                speedup = baseline / r['avg_ms']
                print(f"{r['model']:<15} {r['avg_ms']:<12.2f} {r['median_ms']:<12.2f} "
                      f"{r['fps']:<10.1f} {speedup:<10.2f}x")
    
    # Save results
    import json
    output_path = "./inference_benchmark_results.json"
    with open(output_path, 'w') as f:
        json.dump(all_results, f, indent=2)
    print(f"\n✅ Results saved to: {output_path}")
    
    # Generate markdown report
    md = generate_markdown_report(all_results)
    md_path = "./INFERENCE_BENCHMARK_REPORT.md"
    with open(md_path, 'w') as f:
        f.write(md)
    print(f"✅ Report saved to: {md_path}")

def generate_markdown_report(results):
    """Generate markdown report for inference benchmarks."""
    md = f"""# YOLO11 Inference Time Benchmark Report

**Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}

## Test Configuration

- Warmup runs: 10
- Benchmark runs: 50
- Test images: 10 per run
- Total inferences per model: 500

## Results

"""
    
    devices = list(set(r['device'] for r in results))
    
    for device in devices:
        device_results = [r for r in results if r['device'] == device]
        md += f"### {device.upper()} Performance\n\n"
        md += "| Model | Avg (ms) | Median (ms) | Min (ms) | Max (ms) | FPS | Speedup |\n"
        md += "|-------|----------|-------------|----------|----------|-----|----------|\n"
        
        baseline = device_results[0]['avg_ms']
        for r in device_results:
            speedup = baseline / r['avg_ms']
            md += f"| {r['model']} | {r['avg_ms']:.2f} | {r['median_ms']:.2f} | "
            md += f"{r['min_ms']:.2f} | {r['max_ms']:.2f} | {r['fps']:.1f} | {speedup:.2f}x |\n"
        
        md += "\n"
    
    # Find fastest
    gpu_results = [r for r in results if r['device'] == 'cuda']
    if gpu_results:
        fastest = min(gpu_results, key=lambda x: x['avg_ms'])
        md += f"## Conclusion\n\n"
        md += f"**Fastest Model (GPU):** {fastest['model']}\n"
        md += f"- Average inference time: {fastest['avg_ms']:.2f} ms\n"
        md += f"- FPS: {fastest['fps']:.1f}\n\n"
        
        # Accuracy vs Speed tradeoff
        md += "## Accuracy vs Speed Tradeoff\n\n"
        md += "| Model | mAP50-95 | Inference (ms) | Parameters | Recommendation |\n"
        md += "|-------|----------|----------------|------------|----------------|\n"
        md += "| nano | 0.5568 | fastest | 2.6M | Best for real-time |\n"
        md += "| small | 0.6164 | fast | 9.4M | Balanced |\n"
        md += "| medium | 0.6527 | moderate | 20.1M | Best accuracy |\n"
    
    return md

if __name__ == "__main__":
    main()
