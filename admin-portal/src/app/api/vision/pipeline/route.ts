import { NextRequest, NextResponse } from 'next/server';

const VISION_ML_URL = process.env.VISION_ML_URL || 'http://127.0.0.1:8001';

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData();
    const response = await fetch(`${VISION_ML_URL}/pipeline`, {
      method: 'POST',
      body: formData,
    });
    const data = await response.text();
    return new NextResponse(data, {
      status: response.status,
      headers: { 'Content-Type': response.headers.get('Content-Type') || 'application/json' },
    });
  } catch (error) {
    return NextResponse.json({ error: 'Vision proxy error', message: String(error) }, { status: 500 });
  }
}
