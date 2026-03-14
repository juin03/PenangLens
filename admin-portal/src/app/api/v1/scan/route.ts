import { NextRequest, NextResponse } from 'next/server';

const VISION_BASE_URL = process.env.VISION_ML_URL || 'http://127.0.0.1:8001';

export async function POST(request: NextRequest) {
  try {
    // Forward the multipart form data directly to VisionML
    const formData = await request.formData();

    const response = await fetch(`${VISION_BASE_URL}/pipeline`, {
      method: 'POST',
      body: formData,
    });

    const data = await response.json();

    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error('BFF Scan Proxy Error:', error);
    return NextResponse.json(
      { success: false, error: 'BFF scan proxy error', message: String(error) },
      { status: 500 }
    );
  }
}
