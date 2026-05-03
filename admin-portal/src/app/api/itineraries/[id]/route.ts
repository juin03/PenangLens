import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { getUserFromRequest } from '@/lib/auth';

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const user = await getUserFromRequest(request);
  if (!user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

  const { id } = await params;
  const itinerary = await prisma.itinerary.findFirst({
    where: { id, userId: user.id },
    include: {
      stops: { orderBy: { stopOrder: 'asc' } },
      chatHistory: { orderBy: { createdAt: 'asc' } },
    },
  });

  if (!itinerary) return NextResponse.json({ error: 'Not found' }, { status: 404 });
  return NextResponse.json({ itinerary });
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const user = await getUserFromRequest(request);
  if (!user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

  const { id } = await params;
  const itinerary = await prisma.itinerary.findFirst({ where: { id, userId: user.id } });
  if (!itinerary) return NextResponse.json({ error: 'Not found' }, { status: 404 });

  const body = await request.json();
  const updated = await prisma.itinerary.update({
    where: { id },
    data: {
      ...(body.generatedNarrative !== undefined && { generatedNarrative: body.generatedNarrative }),
      ...(body.name !== undefined && { name: body.name }),
      ...(body.totalDuration !== undefined && { totalDuration: body.totalDuration }),
    },
  });
  return NextResponse.json({ itinerary: updated });
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const user = await getUserFromRequest(request);
  if (!user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

  const { id } = await params;
  const itinerary = await prisma.itinerary.findFirst({ where: { id, userId: user.id } });
  if (!itinerary) return NextResponse.json({ error: 'Not found' }, { status: 404 });

  await prisma.itinerary.delete({ where: { id } });
  return NextResponse.json({ success: true });
}
