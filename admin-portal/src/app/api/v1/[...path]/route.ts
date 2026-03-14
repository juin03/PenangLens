import { NextRequest, NextResponse } from 'next/server';

const AGENT_BASE_URL = process.env.AGENT_URL || 'http://127.0.0.1:8000';

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return handleProxy(request, await params);
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return handleProxy(request, await params);
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return handleProxy(request, await params);
}

async function handleProxy(request: NextRequest, params: { path: string[] }) {
  try {
    const pathString = params.path.join('/');
    const targetUrl = new URL(`/api/v1/${pathString}`, AGENT_BASE_URL);

    // Forward query parameters
    request.nextUrl.searchParams.forEach((value, key) => {
      targetUrl.searchParams.append(key, value);
    });

    const headers = new Headers();
    headers.set('Content-Type', 'application/json');
    // Basic API Key auth can be added here, e.g., headers.set('Authorization', ...)

    let body = undefined;
    if (request.method !== 'GET' && request.method !== 'HEAD') {
      body = await request.text();
    }

    const response = await fetch(targetUrl.toString(), {
      method: request.method,
      headers,
      body,
    });

    // Handle streaming response (e.g. for /api/v1/chat/stream)
    if (response.headers.get('content-type')?.includes('text/event-stream')) {
      return new NextResponse(response.body, {
        status: response.status,
        headers: {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache',
          'Connection': 'keep-alive',
        },
      });
    }

    const responseData = await response.text();
    
    return new NextResponse(responseData, {
      status: response.status,
      headers: {
        'Content-Type': 'application/json',
      },
    });
  } catch (error) {
    console.error('BFF Proxy Error:', error);
    return NextResponse.json(
      { error: 'BFF proxy error', message: String(error) },
      { status: 500 }
    );
  }
}
