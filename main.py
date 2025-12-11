import os
import shutil
import cv2
import torch
from PIL import Image
from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from ultralytics import YOLOWorld

# ================= CONFIGURATION =================
# Point this to your YOLO-World trained model
MODEL_PATH = r"C:\Temp\PenangLens_YOLOWorld_Runs\yoloworld_finetuned\weights\best.pt"
UPLOAD_FOLDER = 'uploads'
RESULTS_FOLDER = 'results'

# Class names (must match your training)
CLASS_NAMES = ['burmese_spire', 'chinese_base', 'thai_tier']

# Supported image formats
SUPPORTED_FORMATS = {'.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tiff', '.tif'}

# Device
DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'

# Initialize App
app = FastAPI()

# Ensure folders exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULTS_FOLDER, exist_ok=True)

# Mount the 'results' folder so the browser can access images via URL
app.mount("/results", StaticFiles(directory=RESULTS_FOLDER), name="results")

# Load YOLO-World Model
print("🚀 Loading YOLO-World Model...")
if os.path.exists(MODEL_PATH):
    model = YOLOWorld(MODEL_PATH)
    model.to(DEVICE)  # Ensure model is on correct device
    model.set_classes(CLASS_NAMES)
    print(f"✅ YOLO-World Model Loaded Successfully on {DEVICE}!")
    print(f"📋 Active Classes: {CLASS_NAMES}")
else:
    print(f"❌ ERROR: Model not found at {MODEL_PATH}")
    model = None

# Helper function to convert unsupported formats
def convert_to_supported_format(file_path: str) -> str:
    """Convert unsupported image formats to PNG."""
    file_ext = os.path.splitext(file_path)[1].lower()
    
    if file_ext not in SUPPORTED_FORMATS:
        print(f"⚠️ Converting {file_ext} to PNG...")
        try:
            # Open with PIL and convert
            img = Image.open(file_path)
            # Convert RGBA to RGB if needed
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            
            # Save as PNG
            new_path = os.path.splitext(file_path)[0] + '.png'
            img.save(new_path, 'PNG')
            
            # Delete original unsupported file
            os.remove(file_path)
            
            print(f"✅ Converted to: {new_path}")
            return new_path
        except Exception as e:
            print(f"❌ Conversion failed: {e}")
            raise
    
    return file_path

# 1. Root Route - Serves the HTML UI
@app.get("/")
def read_root():
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    return {"error": "index.html not found. Please create it in the same folder."}

# 1b. Zero-Shot Testing Page
@app.get("/test-zeroshot")
def test_page():
    if os.path.exists("test_zeroshot.html"):
        return FileResponse("test_zeroshot.html")
    return {"error": "test_zeroshot.html not found."}

# 2. Detection Endpoint (Fine-tuned classes)
@app.post("/detect")
def detect_objects(image: UploadFile = File(...)):
    if model is None:
        return JSONResponse(content={"error": "Model not loaded"}, status_code=500)

    # A. Save uploaded file to disk
    file_location = os.path.join(UPLOAD_FOLDER, image.filename)
    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(image.file, buffer)

    # Convert if needed
    try:
        file_location = convert_to_supported_format(file_location)
    except Exception as e:
        return JSONResponse(content={"error": f"Image conversion failed: {str(e)}"}, status_code=400)

    # B. Ensure model is using fine-tuned classes
    model.set_classes(CLASS_NAMES)

    # C. Run YOLO-World Inference
    results = model.predict(
        source=file_location,
        imgsz=640,
        conf=0.15,
        iou=0.5,
        device=DEVICE,
        agnostic_nms=True
    )

    # D. Save the Result Image
    result_filename = f"result_{os.path.basename(file_location)}"
    result_path = os.path.join(RESULTS_FOLDER, result_filename)

    for r in results:
        im_array = r.plot()
        cv2.imwrite(result_path, im_array)

    # E. Extract detection info
    detections = []
    for r in results:
        for box in r.boxes:
            detections.append({
                "class": CLASS_NAMES[int(box.cls[0])],
                "confidence": float(box.conf[0]),
                "bbox": box.xyxy[0].tolist()
            })

    # F. Return results
    return {
        "message": "Success",
        "image_url": f"/results/{result_filename}",
        "detections": detections,
        "count": len(detections)
    }

# 3. Zero-Shot Detection Endpoint (Custom prompts)
@app.post("/detect-custom")
def detect_custom_objects(
    image: UploadFile = File(...),
    prompts: str = Form(...)
):
    if model is None:
        return JSONResponse(content={"error": "Model not loaded"}, status_code=500)

    # Parse prompts (comma-separated)
    custom_classes = [p.strip() for p in prompts.split(',') if p.strip()]
    
    if not custom_classes:
        return JSONResponse(content={"error": "No valid prompts provided"}, status_code=400)

    print(f"🔍 Testing zero-shot with prompts: {custom_classes}")

    # A. Save uploaded file
    file_location = os.path.join(UPLOAD_FOLDER, f"custom_{image.filename}")
    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(image.file, buffer)

    # Convert if needed
    try:
        file_location = convert_to_supported_format(file_location)
    except Exception as e:
        return JSONResponse(content={"error": f"Image conversion failed: {str(e)}"}, status_code=400)

    try:
        # B. Set custom classes for zero-shot detection
        with torch.cuda.device(DEVICE if DEVICE == 'cuda' else 'cpu'):
            model.set_classes(custom_classes)

        # C. Run inference
        results = model.predict(
            source=file_location,
            imgsz=640,
            conf=0.10,  # Lower confidence for zero-shot
            iou=0.5,
            device=DEVICE,
            agnostic_nms=True
        )

        # D. Save result
        result_filename = f"custom_{os.path.basename(file_location)}"
        result_path = os.path.join(RESULTS_FOLDER, result_filename)

        for r in results:
            im_array = r.plot()
            cv2.imwrite(result_path, im_array)

        # E. Extract detections
        detections = []
        for r in results:
            for box in r.boxes:
                cls_id = int(box.cls[0])
                if cls_id < len(custom_classes):
                    detections.append({
                        "class": custom_classes[cls_id],
                        "confidence": float(box.conf[0]),
                        "bbox": box.xyxy[0].tolist()
                    })

        response = {
            "message": "Success",
            "image_url": f"/results/{result_filename}",
            "prompts_used": custom_classes,
            "detections": detections,
            "count": len(detections)
        }

    except Exception as e:
        print(f"❌ Error during zero-shot detection: {e}")
        response = {
            "error": f"Detection failed: {str(e)}",
            "prompts_used": custom_classes,
            "detections": [],
            "count": 0
        }
    finally:
        # F. Reset to fine-tuned classes (with proper device context)
        try:
            with torch.cuda.device(DEVICE if DEVICE == 'cuda' else 'cpu'):
                model.set_classes(CLASS_NAMES)
        except Exception as reset_error:
            print(f"⚠️ Warning: Could not reset classes - {reset_error}")

    return response

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)