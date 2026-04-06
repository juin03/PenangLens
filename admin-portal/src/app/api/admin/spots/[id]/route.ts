import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

const AGENT_BASE_URL = process.env.AGENT_BASE_URL || 'http://127.0.0.1:8000';
const AZURE_ENDPOINT = process.env.AZURE_SEARCH_ENDPOINT || '';
const AZURE_KEY = process.env.AZURE_SEARCH_KEY || '';
const VISION_INDEX = 'penanglens-poc-index';

function isValidLatLng(location: string): boolean {
  const parts = String(location || '').replace(/[°NSEW\s]/g, '').split(',');
  if (parts.length !== 2) return false;
  const lat = Number(parts[0]);
  const lng = Number(parts[1]);
  return !Number.isNaN(lat) && !Number.isNaN(lng) && lat >= -90 && lat <= 90 && lng >= -180 && lng <= 180;
}

/** Fire-and-forget: index spot into Azure AI Search via Agent microservice */
async function triggerIndex(spot: {
  id: string; name: string; type: string; description?: string | null;
  tags?: string[]; parentLandmarkName?: string;
  location?: string | null; content?: any;
}) {
  try {
    await fetch(`${AGENT_BASE_URL}/index`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(spot),
    });
  } catch {
    console.warn(`[RAG] Failed to index spot ${spot.id} — Agent may be offline.`);
  }
}

/** Fire-and-forget: remove spot from Azure AI Search */
async function triggerDeleteIndex(spotId: string) {
  try {
    await fetch(`${AGENT_BASE_URL}/index/${spotId}`, { method: 'DELETE' });
  } catch {
    console.warn(`[RAG] Failed to delete index for spot ${spotId} — Agent may be offline.`);
  }
}

/** Delete all vision index entries for a spot (by poi_id filter) */
async function deleteFromVisionIndex(spotId: string) {
  try {
    // First, search for all documents with this poi_id
    const searchUrl = `${AZURE_ENDPOINT}/indexes/${VISION_INDEX}/docs?api-version=2023-11-01&$filter=poi_id eq '${spotId}'&$select=id&$top=1000`;
    const searchRes = await fetch(searchUrl, {
      headers: { 'api-key': AZURE_KEY },
    });

    if (!searchRes.ok) {
      console.warn(`[Vision] Failed to search vision index for spot ${spotId}`);
      return;
    }

    const searchData = await searchRes.json() as any;
    const imageIds = (searchData.value || []).map((doc: any) => doc.id);

    if (imageIds.length === 0) {
      console.log(`[Vision] No images found in vision index for spot ${spotId}`);
      return;
    }

    // Delete all found documents
    const deleteUrl = `${AZURE_ENDPOINT}/indexes/${VISION_INDEX}/docs/index?api-version=2023-11-01`;
    const deleteDocs = imageIds.map((id: string) => ({ '@search.action': 'delete', id }));
    
    const deleteRes = await fetch(deleteUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'api-key': AZURE_KEY },
      body: JSON.stringify({ value: deleteDocs }),
    });

    if (deleteRes.ok) {
      console.log(`[Vision] Deleted ${imageIds.length} images from vision index for spot ${spotId}`);
    } else {
      console.warn(`[Vision] Failed to delete from vision index for spot ${spotId}`);
    }
  } catch (error) {
    console.warn(`[Vision] Error deleting from vision index for spot ${spotId}:`, error);
  }
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  try {
    const landmark = await prisma.landmark.findUnique({
      where: { id },
          include: { 
            pois: { 
              include: { images: { take: 10, orderBy: { createdAt: 'asc' } } },
              orderBy: { createdAt: 'asc' },
            }, 
            tags: { include: { tag: true } }, 
            creator: true 
          },
    });
    if (landmark) {
      // Collect images from child POIs
      const poiImages = landmark.pois.flatMap(poi =>
        poi.images.map(img => ({ id: img.id, imageId: img.id, url: img.imageUrl, filename: img.caption || 'image.jpg' }))
      );
      // Also fetch indexed images from Azure AI Search for this landmark
      let searchImages: { id: string; imageId: string; url: string; filename: string }[] = [];
      try {
        const AZURE_ENDPOINT = process.env.AZURE_SEARCH_ENDPOINT || '';
        const AZURE_KEY = process.env.AZURE_SEARCH_KEY || '';
        const searchUrl = `${AZURE_ENDPOINT}/indexes/penanglens-poc-index/docs?api-version=2023-11-01&$filter=poi_id eq '${id}'&$select=id,filename&$top=100`;
        const searchRes = await fetch(searchUrl, { headers: { 'api-key': AZURE_KEY } });
        if (searchRes.ok) {
          const searchData = await searchRes.json() as any;
          const BLOB_BASE = `https://penanglensstorage.blob.core.windows.net/images`;
          searchImages = (searchData.value || []).map((doc: any) => ({
            id: doc.id,
            imageId: doc.id,
            url: `${BLOB_BASE}/${doc.id}.jpg`,
            filename: doc.filename || `${doc.id}.jpg`,
          }));
        }
      } catch {}
      const allImages = [...poiImages, ...searchImages];
      return NextResponse.json({
        spot: {
          ...landmark,
          type: 'landmark',
          tags: landmark.tags.map(t => t.tag.name),
          images: allImages,
        },
      });
    }

    const poi = await prisma.pointOfInterest.findUnique({
      where: { id },
          include: { images: true, landmark: true, creator: true },
    });
    if (poi) {
      const mappedImages = poi.images.map(img => ({
        id: img.id,
        url: img.imageUrl,
        filename: img.caption || 'image.jpg'
      }));
      return NextResponse.json({ spot: { ...poi, images: mappedImages, type: 'poi' } });
    }

    return NextResponse.json({ error: 'Not found' }, { status: 404 });
  } catch (error) {
    console.error('Spot GET error:', error);
    return NextResponse.json({ error: 'Failed to fetch spot' }, { status: 500 });
  }
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const body = await request.json();
  const { name, description, location, status, content, type, tags } = body;

  if (location && !isValidLatLng(location)) {
    return NextResponse.json({ error: 'Location must be valid GPS coordinates in lat,lng format' }, { status: 400 });
  }

  try {
    let updatedSpot: any;

    if (type === 'poi') {
      updatedSpot = await prisma.pointOfInterest.update({
        where: { id },
        data: { name, description, location, status, content },
        include: { landmark: { select: { name: true } } },
      });
      // Trigger RAG indexing when published
      if (status === 'published') {
        await triggerIndex({
          id,
          name: updatedSpot.name,
          type: 'poi',
          description: updatedSpot.description,
          content: updatedSpot.content,
          parentLandmarkName: updatedSpot.landmark?.name,
          location: updatedSpot.location,
        });
      } else if (status === 'draft') {
        // Unpublished — remove from index
        await triggerDeleteIndex(id);
      }
      return NextResponse.json({ spot: { ...updatedSpot, type: 'poi' } });

    } else {
      updatedSpot = await prisma.landmark.update({
        where: { id },
        data: { name, description, location, status, content },
        include: { tags: { include: { tag: true } } },
      });
      // Update tags if provided
      if (Array.isArray(tags)) {
        await prisma.landmarkTag.deleteMany({ where: { landmarkId: id } });
        for (const tagName of tags) {
          const tag = await prisma.tag.upsert({ where: { name: tagName }, update: {}, create: { name: tagName } });
          await prisma.landmarkTag.create({ data: { landmarkId: id, tagId: tag.id } });
        }
        updatedSpot = await prisma.landmark.findUnique({ where: { id }, include: { tags: { include: { tag: true } } } });
      }
      // Trigger RAG indexing when published
      if (status === 'published') {
        const tags = updatedSpot.tags?.map((t: any) => t.tag.name) ?? [];
        await triggerIndex({
          id,
          name: updatedSpot.name,
          type: 'landmark',
          description: updatedSpot.description,
          content: updatedSpot.content,
          tags,
          location: updatedSpot.location,
        });
      } else if (status === 'draft') {
        await triggerDeleteIndex(id);
      }
      return NextResponse.json({
        spot: { ...updatedSpot, type: 'landmark', tags: updatedSpot.tags?.map((t: any) => t.tag.name) ?? [] },
      });
    }
  } catch (error) {
    console.error('Spot PATCH error:', error);
    return NextResponse.json({ error: 'Failed to update spot' }, { status: 500 });
  }
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  try {
    const landmark = await prisma.landmark.findUnique({ where: { id } });
    if (landmark) {
      await prisma.landmark.delete({ where: { id } });
      await triggerDeleteIndex(id);
      await deleteFromVisionIndex(id);
      return NextResponse.json({ success: true });
    }
    const poi = await prisma.pointOfInterest.findUnique({ where: { id } });
    if (poi) {
      await prisma.pointOfInterest.delete({ where: { id } });
      await triggerDeleteIndex(id);
      await deleteFromVisionIndex(id);
      return NextResponse.json({ success: true });
    }
    return NextResponse.json({ error: 'Not found' }, { status: 404 });
  } catch (error) {
    console.error('Spot DELETE error:', error);
    return NextResponse.json({ error: 'Failed to delete spot' }, { status: 500 });
  }
}
