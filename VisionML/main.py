from PIL import Image
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from ultralytics import YOLO
import os
import torch
import io
import base64
from pathlib import Path

# ================= CONFIGURATION =================
# Path to your YOLO11 training result (now saved locally)
# FINETUNED_MODEL_PATH = r"models\results\full_finetuning\weights\best.pt"
# Alternative: Use partial model instead
FINETUNED_MODEL_PATH = r"models\results\partial_finetuning\weights\best.pt"

# Device
DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'

# Initialize App
app = FastAPI()

# ================= LOAD MODEL =================
print(f"🚀 Loading Fine-Tuned YOLO11 Model from: {FINETUNED_MODEL_PATH}")

try:
    model = YOLO(FINETUNED_MODEL_PATH) 
    model.to(DEVICE)
    
    # Get class names directly from the model
    CLASS_NAMES = model.names
    print(f"✅ Model loaded successfully!")
    print(f"   Number of classes: {len(CLASS_NAMES)}")
    print(f"   Classes: {list(CLASS_NAMES.values()) if isinstance(CLASS_NAMES, dict) else CLASS_NAMES}")
    print(f"   Device: {DEVICE}")

except Exception as e:
    print(f"❌ WARNING: Could not load model from {FINETUNED_MODEL_PATH}.")
    print(f"   Defaulting to base weights yolo11s.pt for initial testing.")
    try:
        model = YOLO("yolo11s.pt")
        model.to(DEVICE)
    except:
        print("❌ CRITICAL ERROR: Could not load base model either.")
        model = None

# ================= ROUTES =================

@app.get("/")
async def serve_index():
    return FileResponse("index.html")

@app.post("/detect")
async def detect(image: UploadFile = File(...)):
    if model is None:
        return JSONResponse({"success": False, "error": "Model not loaded properly"}, status_code=500)

    try:
        # Read image into memory
        contents = await image.read()
        pil_image = Image.open(io.BytesIO(contents)).convert("RGB")
        
        # Run inference using the PIL image directly
        results = model.predict(
            source=pil_image,
            conf=0.25,
            iou=0.45,
            device=DEVICE,
            save=False,
            verbose=False
        )
        
        result = results[0]
        
        # Plot result to memory
        result_plot_np = result.plot()
        # Convert BGR (OpenCV/Ultralytics) to RGB for PIL
        result_image = Image.fromarray(result_plot_np[..., ::-1])
        
        # Convert to Base64 string
        buffered = io.BytesIO()
        result_image.save(buffered, format="JPEG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        
        # Extract metadata
        detections = []
        if result.boxes is not None:
            boxes = result.boxes.cpu()
            for box in boxes:
                cls_idx = int(box.cls.item())
                conf = float(box.conf.item())
                class_name = result.names[cls_idx]
                detections.append({
                    "class": class_name,
                    "confidence": conf
                })
        
        return JSONResponse({
            "success": True,
            "image_url": f"data:image/jpeg;base64,{img_str}",
            "count": len(detections),
            "detections": detections,
            "model": "YOLO11"
        })
    
    except Exception as e:
        import traceback
        print(f"❌ Error in /detect: {e}")
        print(traceback.format_exc())
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*60)
    print("🌟 PenangLens YOLO11 Server Starting...")
    print("="*60)
    print(f"🌐 Server: http://127.0.0.1:8000")
    print("="*60 + "\n")
    
    uvicorn.run(app, host="127.0.0.1", port=8000)