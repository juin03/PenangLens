# ==============================================================================
# PENANGLENS: FULL AI PIPELINE PROOF OF CONCEPT (Updated for New Test Case)
# ==============================================================================
# ... (Setup Comments remain the same) ...

import os
import torch
from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv

# --- Model & Library Imports ---
from ultralytics import YOLOWorld
from transformers import AutoImageProcessor, AutoModel
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex, SimpleField, SearchField, SearchFieldDataType,
    VectorSearch, HnswAlgorithmConfiguration, VectorSearchProfile
)

# --- Configuration ---
load_dotenv()
AZURE_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
AZURE_API_KEY = os.getenv("AZURE_SEARCH_KEY")
INDEX_NAME = "penanglens-poc-index"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

if not AZURE_ENDPOINT or not AZURE_API_KEY:
    raise ValueError("Azure credentials not found in .env file.")

# ==============================================================================
# STAGE 1: COARSE IDENTIFICATION (DINOv2 + Vector Search)
# ==============================================================================

# --- DINOv2 Model Loading (Cached) ---
DINO_PROCESSOR = None
DINO_MODEL = None

def get_dino_model():
    """Lazily loads the DINOv2 model to avoid reloading."""
    global DINO_PROCESSOR, DINO_MODEL
    if DINO_MODEL is None:
        print(f"Loading DINOv2 model on {DEVICE}...")
        DINO_PROCESSOR = AutoImageProcessor.from_pretrained("facebook/dinov2-base")
        DINO_MODEL = AutoModel.from_pretrained("facebook/dinov2-base").to(DEVICE)
    return DINO_PROCESSOR, DINO_MODEL

def get_dino_embedding(image_path: str) -> list:
    """Generates a DINOv2 vector embedding for a given image path."""
    processor, model = get_dino_model()
    image = Image.open(image_path).convert("RGB")
    inputs = processor(images=image, return_tensors="pt").to(DEVICE)
    with torch.no_grad():
        outputs = model(**inputs)
        embedding = outputs.last_hidden_state.mean(dim=1).cpu().numpy().flatten()
    return embedding.tolist()

def setup_azure_search_index():
    """Deletes and recreates the Azure Search Index for a clean run."""
    print("Setting up Azure Search Index...")
    index_client = SearchIndexClient(AZURE_ENDPOINT, AzureKeyCredential(AZURE_API_KEY))
    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SimpleField(name="poi_id", type=SearchFieldDataType.String, filterable=True, sortable=True),
        SimpleField(name="filename", type=SearchFieldDataType.String),
        SearchField(
            name="imageVector", type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True, vector_search_dimensions=768, vector_search_profile_name="my-vector-profile"
        ),
    ]
    vector_search = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name="my-hnsw")],
        profiles=[VectorSearchProfile(name="my-vector-profile", algorithm_configuration_name="my-hnsw")]
    )
    index = SearchIndex(name=INDEX_NAME, fields=fields, vector_search=vector_search)
    try:
        index_client.delete_index(INDEX_NAME)
    except Exception:
        pass # Index doesn't exist, which is fine
    index_client.create_index(index)
    print(f"Index '{INDEX_NAME}' is ready.")

def upload_reference_images(folder_path: str = "./images"):
    """Embeds and uploads all images from a folder to Azure AI Search."""
    print(f"Uploading reference images from '{folder_path}'...")
    search_client = SearchClient(AZURE_ENDPOINT, INDEX_NAME, AzureKeyCredential(AZURE_API_KEY))
    docs = []
    for idx, fname in enumerate(os.listdir(folder_path)):
        path = os.path.join(folder_path, fname)
        if os.path.isfile(path) and fname.lower().endswith((".jpg", ".jpeg", ".png")):
            try:
                embedding = get_dino_embedding(path)
                # *** FIX APPLIED HERE: Robustly extract POI ID ***
                base_name = fname.split('_')[0]
                poi_id = os.path.splitext(base_name)[0]
                
                docs.append({
                    "id": str(idx),
                    "poi_id": poi_id, 
                    "filename": fname,
                    "imageVector": embedding
                })
            except Exception as e:
                print(f"⚠️ Could not process {fname}: {e}")
    if docs:
        search_client.upload_documents(docs)
        print(f"Uploaded {len(docs)} image vectors to Azure.")

def identify_poi_from_image(query_image_path: str) -> str | None:
    """Performs vector search to find the most similar POI."""
    print(f"\n--- STAGE 1: Identifying POI for '{query_image_path}' ---")
    search_client = SearchClient(AZURE_ENDPOINT, INDEX_NAME, AzureKeyCredential(AZURE_API_KEY))
    query_vector = get_dino_embedding(query_image_path)
    vector_query = VectorizedQuery(vector=query_vector, k_nearest_neighbors=1, fields="imageVector")
    
    results = search_client.search(search_text="", vector_queries=[vector_query])
    
    try:
        top_result = next(results)
        print(f"  -> Best Match: '{top_result['filename']}' (Score: {top_result['@search.score']:.4f})")
        identified_poi = top_result['poi_id']
        print(f"  -> Identified Landmark as: '{identified_poi}'")
        return identified_poi
    except StopIteration:
        print("  -> No matching images found in the index.")
        return None

# ==============================================================================
# STAGE 2: FINE-GRAINED DETAIL DETECTION (YOLO-World)
# ==============================================================================

def find_and_draw_details(image_path: str, prompts: list, output_filename: str = "result_with_boxes_statue.jpg"):
    """Uses YOLO-World to find and draw bounding boxes for given text prompts."""
    print(f"\n--- STAGE 2: Finding details in '{image_path}' ---")
    
    # 1. Load YOLO-World model (will be downloaded on first run)
    print("  -> Loading YOLO-World model...")
    model = YOLOWorld('yolov8s-world.pt')
    
    # 2. Set the text prompts as the detection classes
    print(f"  -> Setting search prompts: {prompts}")
    model.set_classes(prompts)
    
    # 3. Run prediction on the image
    print("  -> Running model prediction...")
    results = model.predict(image_path, conf=0.05) # Lowered confidence for testing detailed features
    
    # 4. Use the built-in plot function to draw results on the image
    print("  -> Drawing bounding boxes...")
    result_with_boxes_np = results[0].plot()
    
    # 5. Convert from NumPy array (BGR) to PIL Image (RGB) and save
    output_image = Image.fromarray(result_with_boxes_np[..., ::-1])
    output_image.save(output_filename)
    print(f"\n✅ Success! Pipeline complete. Output saved to '{output_filename}'")

# ==============================================================================
# MAIN EXECUTION SCRIPT
# ==============================================================================

# ==============================================================================
# MAIN EXECUTION SCRIPT
# ==============================================================================

if __name__ == "__main__":
    # --- 1. SETUP ---
    # This assumes you have at least one reference image of Penang Hill in your './images' folder.
    # For example, an image named 'penanghill_1.jpg' would create the 'penanghill' POI ID.
    setup_azure_search_index()
    upload_reference_images("./images")

    # --- 2. DEFINE THE QUERY ---
    # Change this to your new image file.
    query_image_path = "./penanghilltrain.jpg" 
    
    if not os.path.exists(query_image_path):
        print(f"FATAL: Query image not found at '{query_image_path}'. Please add it to the same directory as your script.")
    else:
        # --- 3. RUN THE PIPELINE ---
        
        # STAGE 1: Identify the main landmark from the user's photo
        identified_poi_id = identify_poi_from_image(query_image_path)
        
        # STAGE 2: Run detail detection based on the identified POI
        if identified_poi_id == "guanyintemple2":
            # This is the original logic for the Guan Yin Temple
            statue_platform_prompts = [
                'large carved statue', 'mandala ceiling detail', 
                'stone pillar with calligraphy', 'inscription plaque',
                'buddha statue', 'guanyin statue', 'statue'
            ]
            find_and_draw_details(query_image_path, statue_platform_prompts, "result_statue_boxes.jpg")

        elif identified_poi_id == "penanghilltrain": # <-- NEW LOGIC FOR PENANG HILL
            # Using new descriptive prompts for the Penang Hill Funicular Train
            penang_hill_prompts = [
                'funicular train car',
                'railway track',
                'stone bridge arch',
                'green forest canopy',
                'vintage lamppost'
            ]
            find_and_draw_details(query_image_path, penang_hill_prompts, "result_penanghill_boxes.jpg")
            
        else:
            # Fallback for any other identified POI
            print(f"\nPOI ID '{identified_poi_id}' not recognized for Stage 2 prompts.")
            print("Detail detection (Stage 2) will not run.")