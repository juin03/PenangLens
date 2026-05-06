import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

export async function GET(request: NextRequest) {
  const days = parseInt(request.nextUrl.searchParams.get('days') || '30');
  const since = new Date(Date.now() - days * 24 * 60 * 60 * 1000);

  try {
    // ── Core scan stats ──────────────────────────────────────────────
    const [totalRecognitions, feedbackCount, correctCount] = await Promise.all([
      prisma.recognitionHistory.count({ where: { createdAt: { gte: since } } }),
      prisma.recognitionFeedback.count({ where: { createdAt: { gte: since } } }),
      prisma.recognitionFeedback.count({ where: { createdAt: { gte: since }, isCorrect: true } }),
    ]);

    // ── Catalog stats ────────────────────────────────────────────────
    const [totalUsers, totalPois, publishedPois, poisWithContent, pendingFeedback] = await Promise.all([
      prisma.user.count(),
      prisma.pointOfInterest.count(),
      prisma.pointOfInterest.count({ where: { status: 'published' } }),
      prisma.pointOfInterest.count({ where: { content: { not: undefined } } }),
      prisma.recognitionFeedback.count({ where: { status: 'pending' } }),
    ]);

    const contentCoverage = totalPois > 0 ? Math.round((poisWithContent / totalPois) * 100) : 0;

    // ── Scan Trend: daily counts for the range ───────────────────────
    const allScans = await prisma.recognitionHistory.findMany({
      where: { createdAt: { gte: since } },
      select: { createdAt: true },
      orderBy: { createdAt: 'asc' },
    });
    const trendMap: Record<string, number> = {};
    allScans.forEach(r => {
      const d = r.createdAt.toISOString().slice(0, 10);
      trendMap[d] = (trendMap[d] ?? 0) + 1;
    });
    // Fill missing days
    const scanTrend: { date: string; count: number }[] = [];
    for (let i = days - 1; i >= 0; i--) {
      const d = new Date(Date.now() - i * 86400000).toISOString().slice(0, 10);
      scanTrend.push({ date: d, count: trendMap[d] ?? 0 });
    }

    // ── Top 5 Scanned Spots ──────────────────────────────────────────
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const topSpotsRaw = await (prisma.recognitionHistory as any).groupBy({
      by: ['poiId'],
      where: { createdAt: { gte: since }, poiId: { not: null } },
      _count: { poiId: true },
      orderBy: { _count: { poiId: 'desc' } },
      take: 5,
    }) as { poiId: string | null; _count: { poiId: number } }[];
    
    const topPoiIds = topSpotsRaw.map(r => r.poiId).filter(Boolean) as string[];
    const topPois = await prisma.pointOfInterest.findMany({
      where: { id: { in: topPoiIds } },
      select: { id: true, name: true },
    });
    const poiNameMap = Object.fromEntries(topPois.map(p => [p.id, p.name]));
    const topSpots = topSpotsRaw.map(r => ({
      name: poiNameMap[r.poiId!] ?? 'Unknown',
      scanCount: r._count.poiId,
    }));

    // ── Chat Feedback Stats ──────────────────────────────────────────
    let totalChatFeedback = 0, chatPositiveCount = 0;
    try {
      totalChatFeedback = await (prisma as any).chatFeedback.count({ where: { createdAt: { gte: since } } });
      chatPositiveCount = await (prisma as any).chatFeedback.count({ where: { createdAt: { gte: since }, rating: 1 } });
    } catch { /* table may not exist yet */ }

    // ── Itinerary Feedback Stats ─────────────────────────────────────
    let totalItineraryFeedback = 0, avgItineraryRating = 0;
    try {
      const iResult = await (prisma as any).itineraryFeedback.aggregate({
        where: { createdAt: { gte: since } },
        _count: { id: true },
        _avg: { rating: true },
      });
      totalItineraryFeedback = iResult._count.id ?? 0;
      avgItineraryRating = Math.round((iResult._avg.rating ?? 0) * 10) / 10;
    } catch { /* table may not exist yet */ }

    // ── Recent Scan Feedback ─────────────────────────────────────────
    const recentScanFeedback = await prisma.recognitionFeedback.findMany({
      where: { createdAt: { gte: since } },
      orderBy: { createdAt: 'desc' },
      take: 15,
      include: {
        user: { select: { email: true } },
        recognition: { include: { poi: { select: { name: true } } } },
      },
    });

    // ── Recent Chat Feedback ─────────────────────────────────────────
    let recentChatFeedback: any[] = [];
    try {
      recentChatFeedback = await (prisma as any).chatFeedback.findMany({
        where: { createdAt: { gte: since } },
        orderBy: { createdAt: 'desc' },
        take: 10,
        include: { user: { select: { email: true } } },
      });
    } catch { /* table may not exist yet */ }

    // ── Recent Itinerary Feedback ─────────────────────────────────────
    let recentItineraryFeedback: any[] = [];
    try {
      recentItineraryFeedback = await (prisma as any).itineraryFeedback.findMany({
        where: { createdAt: { gte: since } },
        orderBy: { createdAt: 'desc' },
        take: 10,
        include: {
          user: { select: { email: true } },
          itinerary: {
            select: {
              name: true,
              originalPrompt: true,
              generatedNarrative: true,
              stops: {
                select: {
                  stopOrder: true,
                  poi: { select: { name: true } },
                },
                orderBy: { stopOrder: 'asc' },
              },
              chatHistory: {
                select: {
                  role: true,
                  content: true,
                  createdAt: true,
                },
                orderBy: { createdAt: 'asc' },
              },
            },
          },
        },
      });
    } catch { /* table may not exist yet */ }

    return NextResponse.json({
      totalRecognitions, feedbackCount, correctCount,
      totalUsers, totalPois, publishedPois, contentCoverage, pendingFeedback,
      scanTrend, topSpots,
      totalChatFeedback, chatPositiveCount,
      totalItineraryFeedback, avgItineraryRating,
      recentFeedback: recentScanFeedback,
      recentChatFeedback,
      recentItineraryFeedback,
    });
  } catch (error) {
    console.error('Analytics error:', error);
    return NextResponse.json({ error: 'Failed to fetch analytics' }, { status: 500 });
  }
}
