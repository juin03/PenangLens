import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { AGENT_BASE_URL, agentHeaders } from '@/lib/agent';

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const body = await request.json();

  try {
    // Fetch spot name from landmark or POI
    const spot = await prisma.landmark.findUnique({ where: { id } }) ||
                 await prisma.pointOfInterest.findUnique({ where: { id } });

    if (!spot) return NextResponse.json({ error: 'Spot not found' }, { status: 404 });

    // Call Agent to curate content
    const instructionBlock = body.instructions 
      ? `\n\nUSER SPECIFIC INSTRUCTIONS/CONTEXT:\n${body.instructions}\n\nPlease prioritize the above context or instructions in your generation.`
      : '';

    const agentRes = await fetch(
      `${AGENT_BASE_URL}/api/v1/chat`,
      {
        method: 'POST',
        headers: agentHeaders(),
        body: JSON.stringify({
          message: `You are a heritage tourism writer for Penang, Malaysia. Write detailed content about "${spot.name}".${instructionBlock}\n\nReturn ONLY a JSON object with these keys: overview (2-3 sentences), history (3-4 sentences about origin/history), culture (2-3 sentences about cultural significance), funFacts (2-3 interesting facts as a single paragraph). Be accurate and informative.`,
          thread_id: `admin_curate_${id}`,
        }),
      }
    );

    if (!agentRes.ok) throw new Error('Agent unavailable');
    const agentData = await agentRes.json();

    // Try to parse JSON from response
    let content: Record<string, string> = {};
    try {
      const jsonMatch = (agentData.response || '').match(/\{[\s\S]*\}/);
      if (jsonMatch) content = JSON.parse(jsonMatch[0]);
    } catch {
      content = { overview: agentData.response || '' };
    }

    return NextResponse.json({ content });
  } catch (error) {
    console.error('Curate error:', error);
    return NextResponse.json({ error: 'AI curation failed' }, { status: 500 });
  }
}
