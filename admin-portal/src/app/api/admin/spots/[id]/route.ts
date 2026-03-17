import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

const AGENT_BASE_URL = process.env.AGENT_BASE_URL || 'http://127.0.0.1:8000';

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
  tags?: string[]; searchPrompts?: string[]; parentLandmarkName?: string;
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
      // Collect all images from child POIs so mobile can show a hero image
      const allImages = landmark.pois.flatMap(poi =>
        poi.images.map(img => ({ id: img.id, url: img.imageUrl, filename: img.caption || 'image.jpg' }))
      );
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
  const { name, description, location, status, content, type } = body;

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
        const searchPrompts = Array.isArray(updatedSpot.searchPrompts) ? updatedSpot.searchPrompts : [];
        await triggerIndex({
          id,
          name: updatedSpot.name,
          type: 'poi',
          description: updatedSpot.description,
          searchPrompts,
          parentLandmarkName: updatedSpot.landmark?.name,
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
      // Trigger RAG indexing when published
      if (status === 'published') {
        const tags = updatedSpot.tags?.map((t: any) => t.tag.name) ?? [];
        await triggerIndex({
          id,
          name: updatedSpot.name,
          type: 'landmark',
          description: updatedSpot.description,
          tags,
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
      return NextResponse.json({ success: true });
    }
    const poi = await prisma.pointOfInterest.findUnique({ where: { id } });
    if (poi) {
      await prisma.pointOfInterest.delete({ where: { id } });
      await triggerDeleteIndex(id);
      return NextResponse.json({ success: true });
    }
    return NextResponse.json({ error: 'Not found' }, { status: 404 });
  } catch (error) {
    console.error('Spot DELETE error:', error);
    return NextResponse.json({ error: 'Failed to delete spot' }, { status: 500 });
  }
}
