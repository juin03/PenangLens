import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { verifyToken } from '@/lib/auth';

export async function POST(request: NextRequest) {
  const body = await request.json();
  const { rating, aiMessage, userMessage, context, comment } = body;

  if (!rating || !aiMessage) {
    return NextResponse.json({ error: 'rating and aiMessage required' }, { status: 400 });
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
    const contextWithComment = comment
      ? `${context || 'General Chat'} | User note: ${String(comment)}`
      : context;

    await (prisma as any).chatFeedback.create({
      data: { rating: Number(rating), aiMessage, userMessage, context: contextWithComment, threadId: body.threadId ?? null, userId },
    });
    return NextResponse.json({ success: true });
  } catch (error) {
    console.error('Chat feedback error:', error);
    return NextResponse.json({ error: 'Failed to save feedback' }, { status: 500 });
  }
}
