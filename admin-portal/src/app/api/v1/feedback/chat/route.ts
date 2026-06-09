import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { verifyToken } from '@/lib/auth';

export async function POST(request: NextRequest) {
  const body = await request.json();
  const { rating, comment, context, threadId, messageCount, conversation } = body;

  // Per-session rating: 1–5 stars
  const stars = Number(rating);
  if (!stars || stars < 1 || stars > 5) {
    return NextResponse.json({ error: 'rating (1–5) is required' }, { status: 400 });
  }

  // Extract user ID from JWT if present (optional — works for guests too)
  let userId: string | undefined;
  try {
    const auth = request.headers.get('authorization');
    if (auth?.startsWith('Bearer ')) {
      const payload = verifyToken(auth.slice(7));
      userId = payload?.sub;
    }
  } catch { /* guest—no user id */ }

  try {
    await (prisma as any).chatFeedback.create({
      data: {
        rating: stars,
        comment: comment ? String(comment) : null,
        context: context ? String(context) : null,
        threadId: threadId ?? null,
        messageCount: messageCount != null ? Number(messageCount) : null,
        conversation: Array.isArray(conversation) ? conversation : undefined,
        status: 'pending',
        userId,
      },
    });
    return NextResponse.json({ success: true });
  } catch (error) {
    console.error('Chat feedback error:', error);
    return NextResponse.json({ error: 'Failed to save feedback' }, { status: 500 });
  }
}
