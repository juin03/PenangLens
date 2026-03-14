import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

export async function GET(request: NextRequest) {
  try {
    // Get all landmarks with their POI counts and child POIs
    const landmarks = await prisma.landmark.findMany({
      include: {
        pois: { orderBy: { createdAt: 'asc' } },
        tags: { include: { tag: true } },
      },
      orderBy: { updatedAt: 'desc' },
    });

    const spots = landmarks.map(l => ({
      id: l.id,
      name: l.name,
      type: 'landmark' as const,
      status: l.status,
      poiCount: l.pois.length,
      updatedAt: l.updatedAt.toISOString(),
      location: l.location,
      description: l.description,
      tags: l.tags.map(t => t.tag.name),
      pois: l.pois.map(p => ({
        id: p.id,
        name: p.name,
        type: 'poi' as const,
        status: p.status,
        updatedAt: p.updatedAt.toISOString(),
        location: p.location,
        landmarkId: p.landmarkId,
      })),
    }));

    return NextResponse.json({ spots });
  } catch (error) {
    console.error('Spots GET error:', error);
    return NextResponse.json({ error: 'Failed to fetch spots' }, { status: 500 });
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { name, type, description, location, landmarkId, tags, searchPrompts, status } = body;

    if (!name) return NextResponse.json({ error: 'Name is required' }, { status: 400 });

    if (type === 'poi') {
      const poi = await prisma.pointOfInterest.create({
        data: {
          name, description, location,
          landmarkId: landmarkId || null,
          searchPrompts: Array.isArray(searchPrompts) ? searchPrompts : [],
          status: status || 'draft',
        },
      });
      return NextResponse.json({ spot: poi }, { status: 201 });
    } else {
      // Create landmark
      const landmark = await prisma.landmark.create({
        data: { name, description, location, sourceUrls: [], status: status || 'draft' },
      });

      // Save tags: find or create each tag, then link via LandmarkTag
      if (Array.isArray(tags) && tags.length > 0) {
        for (const tagName of tags) {
          let tag = await prisma.tag.findFirst({ where: { name: tagName } });
          if (!tag) tag = await prisma.tag.create({ data: { name: tagName } });
          // Only create if not already linked
          const exists = await prisma.landmarkTag.findFirst({ where: { landmarkId: landmark.id, tagId: tag.id } });
          if (!exists) {
            await prisma.landmarkTag.create({ data: { landmarkId: landmark.id, tagId: tag.id } });
          }
        }
      }

      return NextResponse.json({ spot: landmark }, { status: 201 });
    }
  } catch (error) {
    console.error('Spots POST error:', error);
    return NextResponse.json({ error: 'Failed to create spot' }, { status: 500 });
  }
}
