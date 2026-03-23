from PIL import Image
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from ultralytics import YOLO
import os
import torch
import io
import base64
from pathlib import Path
from dotenv import load_dotenv

# ================= CONFIGURATION =================
load_dotenv()

# YOLO11 Fine-tuned model
FINETUNED_MODEL_PATH = "models/results/partial_finetuning/weights/best.pt"
DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'

# DINOv2 for coarse identification (lazy loaded)
DINO_PROCESSOR = None
DINO_MODEL = None

# Azure AI Search (for DINOv2 vector retrieval)
AZURE_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
AZURE_API_KEY = os.getenv("AZURE_SEARCH_KEY")
INDEX_NAME = "penanglens-poc-index"

# DINOv2 minimum confidence threshold — results below this are treated as "Unknown Landmark"
DINO_CONFIDENCE_THRESHOLD = float(os.getenv("DINO_CONFIDENCE_THRESHOLD", "0.6"))

# POI → class mapping (which YOLO classes are valid for each POI)
POI_CLASS_MAP = {
    "kekloksi": ["Chinese Octagonal Base", "Thai Middle Tier", "Burmese Spire", "pagoda", "temple"],
    "penanghill": ["funicular train", "railway track", "stone bridge", "forest canopy", "lamppost"],
    "fortcornwallis": ["cannon", "fortress wall", "watchtower", "flagpole"],
    "guanyintemple": ["statue", "buddha statue", "guanyin statue", "incense burner", "calligraphy"],
    "clanjettie": ["wooden jetty", "stilted house", "fishing boat", "temple"],
}

# Initialize App
app = FastAPI(title="PenangLens VisionML", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ================= LOAD YOLO11 MODEL =================
print(f"🚀 Loading Fine-Tuned YOLO11 Model from: {FINETUNED_MODEL_PATH}")

try:
    yolo_model = YOLO(FINETUNED_MODEL_PATH)
    yolo_model.to(DEVICE)
    CLASS_NAMES = yolo_model.names
    print(f"✅ YOLO11 Model loaded successfully!")
    print(f"   Classes: {list(CLASS_NAMES.values()) if isinstance(CLASS_NAMES, dict) else CLASS_NAMES}")
    print(f"   Device: {DEVICE}")
except Exception as e:
    print(f"❌ WARNING: Could not load fine-tuned model. Falling back to base yolo11s.pt")
    try:
        yolo_model = YOLO("yolo11s.pt")
        yolo_model.to(DEVICE)
        CLASS_NAMES = yolo_model.names
    except:
        print("❌ CRITICAL: Could not load any YOLO model.")
        yolo_model = None
        CLASS_NAMES = {}


# ================= DINOv2 LOADING (LAZY) =================
def get_dino_model():
    """Lazily loads the DINOv2 model to avoid startup delay."""
    global DINO_PROCESSOR, DINO_MODEL
    if DINO_MODEL is None:
        from transformers import AutoImageProcessor, AutoModel
        print(f"📦 Loading DINOv2 model on {DEVICE}...")
        DINO_PROCESSOR = AutoImageProcessor.from_pretrained("facebook/dinov2-base")
        DINO_MODEL = AutoModel.from_pretrained("facebook/dinov2-base").to(DEVICE)
        print("✅ DINOv2 loaded.")
    return DINO_PROCESSOR, DINO_MODEL


def get_dino_embedding(pil_image: Image.Image) -> list:
    """Generates a DINOv2 768-dim vector embedding from a PIL Image."""
    processor, model = get_dino_model()
    inputs = processor(images=pil_image, return_tensors="pt").to(DEVICE)
    with torch.no_grad():
        outputs = model(**inputs)
        embedding = outputs.last_hidden_state.mean(dim=1).cpu().numpy().flatten()
    return embedding.tolist()


def identify_poi(pil_image: Image.Image) -> dict | None:
    """Stage 1: DINOv2 vector search to identify the landmark."""
    if not AZURE_ENDPOINT or not AZURE_API_KEY:
        print("⚠️ Azure credentials not set — skipping DINOv2 identification")
        return None

    try:
        from azure.core.credentials import AzureKeyCredential
        from azure.search.documents import SearchClient
        from azure.search.documents.models import VectorizedQuery

        query_vector = get_dino_embedding(pil_image)
        search_client = SearchClient(AZURE_ENDPOINT, INDEX_NAME, AzureKeyCredential(AZURE_API_KEY))
        vector_query = VectorizedQuery(vector=query_vector, k_nearest_neighbors=1, fields="imageVector")
        results = search_client.search(search_text="", vector_queries=[vector_query])

        top_result = next(results)
        score = float(top_result["@search.score"])

        # Reject low-confidence matches to prevent false landmark identification
        if score < DINO_CONFIDENCE_THRESHOLD:
            print(f"⚠️ DINOv2 confidence too low ({score:.3f} < {DINO_CONFIDENCE_THRESHOLD}) — treating as Unknown Landmark")
            return None

        return {
            "poi_id": top_result["poi_id"],
            "score": score,
            "filename": top_result.get("filename", ""),
        }
    except Exception as e:
        print(f"⚠️ DINOv2 identification failed: {e}")
        return None


def run_yolo_detection(pil_image: Image.Image, poi_id: str | None = None) -> tuple:
    """Stage 2: Run YOLO11 and optionally filter by POI-specific classes."""
    if yolo_model is None:
        return [], None

    results = yolo_model.predict(
        source=pil_image, conf=0.25, iou=0.45,
        device=DEVICE, save=False, verbose=False
    )
    result = results[0]

    # Extract detections
    detections = []
    if result.boxes is not None:
        boxes = result.boxes.cpu()
        for box in boxes:
            cls_idx = int(box.cls.item())
            conf = float(box.conf.item())
            class_name = result.names[cls_idx]
            detections.append({"class": class_name, "confidence": conf})

    # Sequential validation: filter by POI-specific class list
    if poi_id and poi_id in POI_CLASS_MAP:
        valid_classes = [c.lower() for c in POI_CLASS_MAP[poi_id]]
        detections = [d for d in detections if d["class"].lower() in valid_classes]

    # Generate annotated image
    result_plot_np = result.plot()
    result_image = Image.fromarray(result_plot_np[..., ::-1])
    buffered = io.BytesIO()
    result_image.save(buffered, format="JPEG", quality=80)
    img_b64 = base64.b64encode(buffered.getvalue()).decode()

    return detections, f"data:image/jpeg;base64,{img_b64}"


# ================= API ROUTES =================

@app.get("/")
async def serve_index():
    return FileResponse("index.html")


@app.get("/health")
async def health():
    return {"status": "ok", "model": "YOLO11", "device": DEVICE, "dino_loaded": DINO_MODEL is not None}


@app.post("/embed")
async def embed_image(image: UploadFile = File(...)):
    """
    Returns a DINOv2 768-d embedding for an uploaded image.
    Used by the admin portal when indexing new POI reference images.
    """
    try:
        contents = await image.read()
        pil_image = Image.open(io.BytesIO(contents)).convert("RGB")
        vector = get_dino_embedding(pil_image)
        return JSONResponse({
            "success": True,
            "vector": vector,
            "dimensions": len(vector),
            "model": "dinov2-base",
        })
    except Exception as e:
        import traceback
        print(f"❌ Error in /embed: {e}\n{traceback.format_exc()}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.post("/detect")
async def detect(image: UploadFile = File(...)):
    """Legacy endpoint: YOLO11 detection only (no DINOv2 identification)."""
    if yolo_model is None:
        return JSONResponse({"success": False, "error": "Model not loaded"}, status_code=500)

    try:
        contents = await image.read()
        pil_image = Image.open(io.BytesIO(contents)).convert("RGB")
        detections, image_url = run_yolo_detection(pil_image)

        return JSONResponse({
            "success": True,
            "image_url": image_url,
            "count": len(detections),
            "detections": detections,
            "model": "YOLO11",
        })
    except Exception as e:
        import traceback
        print(f"❌ Error in /detect: {e}")
        print(traceback.format_exc())
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.post("/pipeline")
async def full_pipeline(image: UploadFile = File(...)):
    """
    Full Vision Pipeline:
    Stage 1 (DINOv2): Identify landmark via vector similarity search
    Stage 2 (YOLO11): Detect architectural details, filtered by POI context
    """
    import time
    if yolo_model is None:
        return JSONResponse({"success": False, "error": "YOLO model not loaded"}, status_code=500)

    try:
        t_start = time.time()

        contents = await image.read()
        pil_image = Image.open(io.BytesIO(contents)).convert("RGB")

        # Resize image for speed (max 640px on longest side)
        max_dim = 640
        w, h = pil_image.size
        if max(w, h) > max_dim:
            ratio = max_dim / max(w, h)
            pil_image = pil_image.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
            print(f"  📐 Resized image: {w}x{h} → {pil_image.size[0]}x{pil_image.size[1]}")

        t_read = time.time()
        print(f"  ⏱️ Image read+resize: {t_read - t_start:.2f}s")

        # Stage 1: DINOv2 Identification
        poi_result = identify_poi(pil_image)
        poi_id = poi_result["poi_id"] if poi_result else None
        poi_score = poi_result["score"] if poi_result else 0.0
        t_dino = time.time()
        print(f"  ⏱️ DINOv2 identify: {t_dino - t_read:.2f}s → POI={poi_id} ({poi_score:.3f})")

        # Stage 2: YOLO11 Detection (with POI-specific filtering)
        detections, image_url = run_yolo_detection(pil_image, poi_id)
        t_yolo = time.time()
        print(f"  ⏱️ YOLO11 detect: {t_yolo - t_dino:.2f}s → {len(detections)} detections")
        print(f"  ⏱️ TOTAL pipeline: {t_yolo - t_start:.2f}s")

        # Build human-readable POI name
        poi_name = poi_id.replace("_", " ").replace("-", " ").title() if poi_id else "Unknown Landmark"

        return JSONResponse({
            "success": True,
            "pipeline": True,
            "poi_id": poi_id,
            "poi_name": poi_name,
            "poi_confidence": poi_score,
            "image_url": image_url,
            "count": len(detections),
            "detections": detections,
            "model": "DINOv2 + YOLO11",
            "timing_ms": int((t_yolo - t_start) * 1000),
        })

    except Exception as e:
        import traceback
        print(f"❌ Error in /pipeline: {e}")
        print(traceback.format_exc())
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


if __name__ == "__main__":
    import uvicorn
    print("\n" + "=" * 60)
    print("🌟 PenangLens VisionML Server v2.0")
    print("   Full Pipeline: DINOv2 (Identify) → YOLO11 (Detect)")
    print("=" * 60)
    print(f"🌐 Server: http://127.0.0.1:8001")
    print(f"📡 Endpoints: /detect (legacy), /pipeline (full), /health")
    print("=" * 60 + "\n")

    uvicorn.run(app, host="127.0.0.1", port=8001)