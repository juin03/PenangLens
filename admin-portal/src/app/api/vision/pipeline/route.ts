import { NextRequest, NextResponse } from 'next/server';

const VISION_URL = process.env.VISION_URL || 'http://127.0.0.1:8001';

export async function POST(req: NextRequest) {
  const formData = await req.formData();
  const res = await fetch(`${VISION_URL}/pipeline`, {
    method: 'POST',
    body: formData,
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
