import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { getUserFromRequest } from '@/lib/auth';

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const user = await getUserFromRequest(request);
  if (!user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

  const { id } = await params;
  const itinerary = await prisma.itinerary.findFirst({ where: { id, userId: user.id } });
  if (!itinerary) return NextResponse.json({ error: 'Not found' }, { status: 404 });

  const body = await request.json();
  const { messages } = body; // [{role, content}]

  if (!Array.isArray(messages) || messages.length === 0) {
    return NextResponse.json({ error: 'Messages required' }, { status: 400 });
  }

  const created = await prisma.itineraryChatHistory.createMany({
    data: messages.map((m: { role: string; content: string }) => ({
      role: m.role,
      content: m.content,
      itineraryId: id,
    })),
  });

  return NextResponse.json({ saved: created.count });
}
