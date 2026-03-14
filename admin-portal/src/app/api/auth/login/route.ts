import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { verifyPassword, createToken } from '@/lib/auth';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { email, password } = body;

    if (!email || !password) {
      return NextResponse.json({ error: 'Email and password are required' }, { status: 400 });
    }

    const user = await prisma.user.findUnique({ where: { email } });
    if (!user || !user.hashedPassword) {
      return NextResponse.json({ error: 'Invalid email or password' }, { status: 401 });
    }

    if (!verifyPassword(password, user.hashedPassword)) {
      return NextResponse.json({ error: 'Invalid email or password' }, { status: 401 });
    }

    // Load user preferences (tags)
    const prefs = await prisma.userPreference.findMany({
      where: { userId: user.id },
      include: { tag: true },
    });
    const interests = prefs.map((p: { tag: { name: string } }) => p.tag.name);

    const token = createToken(user.id, user.email);

    return NextResponse.json({
      user: { id: user.id, email: user.email, name: user.name, role: user.role, interests },
      token,
    });
  } catch (error) {
    console.error('Login error:', error);
    return NextResponse.json({ error: 'Login failed' }, { status: 500 });
  }
}
