import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { hashPassword, createToken } from '@/lib/auth';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { email, password, name, interests } = body;

    if (!email || !password) {
      return NextResponse.json({ error: 'Email and password are required' }, { status: 400 });
    }

    // Check if user already exists
    const existing = await prisma.user.findUnique({ where: { email } });
    if (existing) {
      return NextResponse.json({ error: 'Email already registered' }, { status: 409 });
    }

    // Create user
    const user = await prisma.user.create({
      data: {
        email,
        name: name || email.split('@')[0],
        hashedPassword: hashPassword(password),
      },
    });

    // Save user preferences (interests) if provided
    if (interests && Array.isArray(interests) && interests.length > 0) {
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

    // Generate JWT
    const token = createToken(user.id, user.email);

    return NextResponse.json({
      user: { id: user.id, email: user.email, name: user.name },
      token,
    }, { status: 201 });
  } catch (error) {
    console.error('Register error:', error);
    return NextResponse.json({ error: 'Registration failed' }, { status: 500 });
  }
}
