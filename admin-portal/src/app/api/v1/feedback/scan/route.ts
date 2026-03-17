import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { verifyToken } from '@/lib/auth';

export async function POST(request: NextRequest) {
  const body = await request.json();
  const { recognitionId, verdict, comment } = body;

  if (!recognitionId || !verdict) {
    return NextResponse.json({ error: 'recognitionId and verdict required' }, { status: 400 });
  }

  const isCorrect = String(verdict).toLowerCase() === 'good';

  let userId: string | undefined;
  try {
    const auth = request.headers.get('authorization');
    if (auth?.startsWith('Bearer ')) {
      const payload = verifyToken(auth.slice(7));
      userId = payload?.sub;
    }
  } catch { /* guest */ }

  try {
    const recognition = await prisma.recognitionHistory.findUnique({
      where: { id: String(recognitionId) },
      select: { userId: true },
    });

    if (!recognition) {
      return NextResponse.json({ error: 'Recognition record not found' }, { status: 404 });
    }

    const feedback = await prisma.recognitionFeedback.create({
      data: {
        recognitionId: String(recognitionId),
        isCorrect,
        userId: userId || recognition.userId,
        status: 'pending',
        adminNotes: comment ? `[User note] ${String(comment)}` : undefined,
      },
    });

    return NextResponse.json({ success: true, feedbackId: feedback.id });
  } catch (error) {
    console.error('Scan feedback error:', error);
    return NextResponse.json({ error: 'Failed to save scan feedback' }, { status: 500 });
  }
}
