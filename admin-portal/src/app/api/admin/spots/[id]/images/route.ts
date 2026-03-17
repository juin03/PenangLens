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
async function upsertToVisionIndex(spotId: string, imageId: string, vector: number[]) {
  const doc = {
    id:          imageId,
    poi_id:      spotId,
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
    await upsertToVisionIndex(spotId, imageId, vector);

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

    // Try POI first, then landmark — both can hold images
    try {
      const poi = await prisma.pointOfInterest.findUnique({ where: { id: spotId } });
      if (poi) {
        await prisma.poiImage.create({
          data: { poiId: spotId, imageUrl: publicUrl, caption: file.name, isForEmbedding: true },
        });
      }
    } catch {
      // poiImage table may not exist yet — vision index is the source of truth
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
    const poi = await prisma.pointOfInterest.findUnique({ where: { id: spotId }, include: { images: true }});
    if (!poi) return NextResponse.json({ error: 'POI not found' }, { status: 404 });

    const images = (poi as any).images || [];
    if (images.length === 0) {
      return NextResponse.json({ success: true, message: 'No images to delete' });
    }

    // 1. Delete from Azure Search using original imageId (extracted from url or filename)
    const imageIds = images.map((img: any) => {
      const url = img.imageUrl || img.url;
      const match = url?.match(/\/uploads\/images\/(.+)\.jpg$/);
      return match ? match[1] : url; // Fallback for old ones where url was just the id
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
    await prisma.poiImage.deleteMany({ where: { poiId: spotId }});

    return NextResponse.json({ success: true, message: `Deleted ${images.length} images` });
  } catch (error: any) {
    console.error('Delete images error:', error);
    return NextResponse.json({ error: 'Failed to delete images' }, { status: 500 });
  }
}
