import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { getUserFromRequest } from '@/lib/auth';

export async function GET(request: NextRequest) {
  const user = await getUserFromRequest(request);
  if (!user) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const prefs = await prisma.userPreference.findMany({
    where: { userId: user.id },
    include: { tag: true },
  });

  return NextResponse.json({
    user: {
      id: user.id,
      email: user.email,
      name: user.name,
      role: user.role,
      interests: prefs.map((p: { tag: { name: string } }) => p.tag.name),
    },
  });
}

export async function PATCH(request: NextRequest) {
  const user = await getUserFromRequest(request);
  if (!user) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const body = await request.json();
  const { name, interests } = body;

  // Update profile fields
  if (name) {
    await prisma.user.update({ where: { id: user.id }, data: { name } });
  }

  // Update interests: clear old preferences, insert new ones
  if (interests && Array.isArray(interests)) {
    await prisma.userPreference.deleteMany({ where: { userId: user.id } });
    for (const tagName of interests) {
      const tag = await prisma.tag.upsert({
        where: { name: tagName },
        update: {},
        create: { name: tagName },
      });
      await prisma.userPreference.create({
        data: { userId: user.id, tagId: tag.id },
      });
    }
  }

  return NextResponse.json({ success: true });
}
