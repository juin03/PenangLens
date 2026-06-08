import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const { status } = await request.json();
  const feedback = await (prisma as any).chatFeedback.update({
    where: { id },
    data: { status },
  });
  return NextResponse.json({ feedback });
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  await (prisma as any).chatFeedback.delete({ where: { id } });
  return NextResponse.json({ success: true });
}
