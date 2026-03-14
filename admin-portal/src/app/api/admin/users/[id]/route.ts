import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const { role } = await request.json();
  const user = await prisma.user.update({ where: { id }, data: { role } });
  return NextResponse.json({ user });
}
