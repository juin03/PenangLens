FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY models/*.pt ./models/

# Set model path for container (copy your best.pt to models/ before building)
ENV YOLO_MODEL_PATH="/app/models/best.pt"
ENV CUDA_VISIBLE_DEVICES=""

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
