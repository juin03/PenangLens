import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

const VISION_ML_URL = process.env.VISION_ML_URL || 'http://127.0.0.1:8001';
const AZURE_ENDPOINT = process.env.AZURE_SEARCH_ENDPOINT || '';
const AZURE_KEY      = process.env.AZURE_SEARCH_KEY      || '';
const VISION_INDEX   = 'penanglens-poc-index';

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

    // Also save image record in DB (for POI images relation)
    // Try POI first, then landmark — both can hold images
    try {
      const poi = await prisma.pointOfInterest.findUnique({ where: { id: spotId } });
      if (poi) {
        await (prisma as any).poiImage?.create?.({
          data: { poiId: spotId, url: imageId, filename: file.name },
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
