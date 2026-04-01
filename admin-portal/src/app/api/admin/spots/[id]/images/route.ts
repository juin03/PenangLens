import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { BlobServiceClient } from '@azure/storage-blob';

const VISION_ML_URL = process.env.VISION_ML_URL || 'http://127.0.0.1:8001';
const AZURE_ENDPOINT = process.env.AZURE_SEARCH_ENDPOINT || '';
const AZURE_KEY      = process.env.AZURE_SEARCH_KEY      || '';
const VISION_INDEX   = 'penanglens-poc-index';

// Azure Blob config
const BLOB_CONN_STR = process.env.AZURE_STORAGE_CONNECTION_STRING || '';
const BLOB_CONTAINER = process.env.AZURE_STORAGE_CONTAINER_NAME || 'images';

/** Upsert a DINOv2 vector into the Azure AI Search vision index */
async function upsertToVisionIndex(spotId: string, spotName: string, imageId: string, vector: number[]) {
  const doc = {
    id:          imageId,
    poi_id:      spotId,
    poi_name:    spotName,
    filename:    `${imageId}.jpg`,
    imageVector: vector,
  };
  const url = `${AZURE_ENDPOINT}/indexes/${VISION_INDEX}/docs/index?api-version=2023-11-01`;
  const res = await fetch(url, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json', 'api-key': AZURE_KEY },
    body:    JSON.stringify({ value: [{ '@search.action': 'mergeOrUpload', ...doc }] }),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Azure AI Search upsert failed: ${err}`);
  }
}

async function deleteFromVisionIndex(imageIds: string[]) {
  if (imageIds.length === 0) return;
  const docs = imageIds.map(id => ({ '@search.action': 'delete', id }));
  const url = `${AZURE_ENDPOINT}/indexes/${VISION_INDEX}/docs/index?api-version=2023-11-01`;
  const res = await fetch(url, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json', 'api-key': AZURE_KEY },
    body:    JSON.stringify({ value: docs }),
  });
  if (!res.ok) {
    const err = await res.text();
    console.error(`Azure AI Search delete failed: ${err}`);
  }
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id: spotId } = await params;
  try {
    // Read multipart image file
    const formData = await request.formData();
    const file = formData.get('image') as File | null;
    if (!file) {
      return NextResponse.json({ error: 'No image provided' }, { status: 400 });
    }

    // Get spot name first (needed for Azure Search index)
    // For POIs, include parent landmark name: "Fort Cornwallis - Seri Rambai Cannon"
    const poi = await prisma.pointOfInterest.findUnique({ 
      where: { id: spotId }, 
      select: { name: true, landmark: { select: { name: true } } } 
    });
    const landmark = poi ? null : await prisma.landmark.findUnique({ where: { id: spotId }, select: { name: true } });
    
    let spotName: string;
    if (poi) {
      // POI: "Landmark Name - POI Name"
      spotName = poi.landmark?.name ? `${poi.landmark.name} - ${poi.name}` : poi.name;
    } else if (landmark) {
      spotName = landmark.name;
    } else {
      spotName = 'Unknown';
    }

    // Forward image to VisionML /embed for DINOv2 embedding
    const vmlForm = new FormData();
    const blob    = new Blob([await file.arrayBuffer()], { type: file.type });
    vmlForm.append('image', blob, file.name);

    const embedRes = await fetch(`${VISION_ML_URL}/embed`, { method: 'POST', body: vmlForm });
    if (!embedRes.ok) {
      const err = await embedRes.text();
      return NextResponse.json({ error: `VisionML /embed failed: ${err}` }, { status: 502 });
    }
    const { vector, dimensions } = await embedRes.json() as { vector: number[]; dimensions: number };

    // Upsert into Azure AI Search vision index (penanglens-poc-index)
    const imageId = `${spotId}_${Date.now()}`;
    await upsertToVisionIndex(spotId, spotName, imageId, vector);

    // Upload the actual file to Azure Blob Storage
    if (!BLOB_CONN_STR) {
      throw new Error("AZURE_STORAGE_CONNECTION_STRING is missing");
    }
    const blobServiceClient = BlobServiceClient.fromConnectionString(BLOB_CONN_STR);
    const containerClient = blobServiceClient.getContainerClient(BLOB_CONTAINER);
    const blobName = `${imageId}.jpg`;
    const blockBlobClient = containerClient.getBlockBlobClient(blobName);
    
    // Convert arrayBuffer to Node Buffer for upload
    const buffer = Buffer.from(await file.arrayBuffer());
    await blockBlobClient.uploadData(buffer, {
      blobHTTPHeaders: { blobContentType: 'image/jpeg' }
    });

    const publicUrl = blockBlobClient.url;

    // Save image record to DB - check if POI or Landmark
    if (poi) {
      await prisma.poiImage.create({
        data: { poiId: spotId, imageUrl: publicUrl, caption: file.name, isForEmbedding: true },
      });
    } else if (landmark) {
      await prisma.poiImage.create({
        data: { landmarkId: spotId, imageUrl: publicUrl, caption: file.name, isForEmbedding: true },
      });
    }

    return NextResponse.json({
      success:    true,
      imageId,
      spotId,
      dimensions,
      message:    `Image embedded (${dimensions}-d) and indexed for scan recognition.`,
    });

  } catch (error: any) {
    console.error('Image upload/embed error:', error);
    return NextResponse.json({ error: error.message || 'Failed to process image' }, { status: 500 });
  }
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id: spotId } = await params;
  try {
    // Try POI first, then Landmark
    let images: any[] = [];
    let isPoi = false;
    let isLandmark = false;
    
    const poi = await prisma.pointOfInterest.findUnique({ where: { id: spotId }, include: { images: true }});
    if (poi) {
      images = poi.images || [];
      isPoi = true;
    } else {
      // Check if it's a Landmark - get direct images
      const landmark = await prisma.landmark.findUnique({ 
        where: { id: spotId }, 
        include: { images: true }
      });
      if (!landmark) {
        return NextResponse.json({ error: 'Spot not found' }, { status: 404 });
      }
      images = landmark.images || [];
      isLandmark = true;
    }

    if (images.length === 0) {
      return NextResponse.json({ success: true, message: 'No images to delete' });
    }

    // 1. Delete from Azure Search using original imageId (extracted from url or filename)
    const imageIds = images.map((img: any) => {
      const url = img.imageUrl || img.url;
      // Match Azure Blob URL: https://...blob.core.windows.net/images/{imageId}.jpg
      const blobMatch = url?.match(/\/images\/([^\/]+)\.jpg$/);
      if (blobMatch) return blobMatch[1];
      // Match old local URL: /uploads/images/{imageId}.jpg
      const localMatch = url?.match(/\/uploads\/images\/(.+)\.jpg$/);
      if (localMatch) return localMatch[1];
      // Skip if we can't extract a valid ID (don't use full URL as key)
      return null;
    }).filter(Boolean);

    await deleteFromVisionIndex(imageIds);

    // 2. Delete local files
    const { unlink } = require('fs/promises');
    for (const img of images) {
      const url = img.imageUrl || img.url;
      if (url && url.startsWith('/')) {
        try {
          await unlink(join(process.cwd(), 'public', url));
        } catch (e) {}
      }
    }

    // 3. Delete from DB
    if (isPoi) {
      await prisma.poiImage.deleteMany({ where: { poiId: spotId }});
    } else if (isLandmark) {
      await prisma.poiImage.deleteMany({ where: { landmarkId: spotId }});
    }

    return NextResponse.json({ success: true, message: `Deleted ${images.length} images` });
  } catch (error: any) {
    console.error('Delete images error:', error);
    return NextResponse.json({ error: 'Failed to delete images' }, { status: 500 });
  }
}
