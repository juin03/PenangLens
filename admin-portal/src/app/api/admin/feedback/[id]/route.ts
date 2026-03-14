import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const { status, adminNotes } = await request.json();
  const feedback = await prisma.recognitionFeedback.update({
    where: { id },
    data: { status, adminNotes },
  });
  return NextResponse.json({ feedback });
}
