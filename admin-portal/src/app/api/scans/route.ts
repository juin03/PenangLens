import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { getUserFromRequest } from '@/lib/auth';

export async function GET(request: NextRequest) {
  const user = await getUserFromRequest(request);
  if (!user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

  const scans = await prisma.recognitionHistory.findMany({
    where: { userId: user.id },
    orderBy: { createdAt: 'desc' },
    take: 50,
  });

  return NextResponse.json({ scans });
}

export async function POST(request: NextRequest) {
  const user = await getUserFromRequest(request);
  if (!user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

  try {
    const body = await request.json();
    const { userImageUrl, annotatedImageBase64, userLatitude, userLongitude, aiDetails, poiId } = body;

    // Upload annotated image (with bounding boxes) to Blob Storage
    let annotatedImageUrl: string | undefined;
    if (annotatedImageBase64) {
      try {
        const { BlobServiceClient } = await import('@azure/storage-blob');
        const connStr = process.env.AZURE_STORAGE_CONNECTION_STRING;
        if (connStr) {
          const blobService = BlobServiceClient.fromConnectionString(connStr);
          const container = blobService.getContainerClient(process.env.AZURE_STORAGE_CONTAINER_NAME || 'images');
          const blobName = `scans/${user.id}_${Date.now()}.jpg`;
          const blockBlob = container.getBlockBlobClient(blobName);

          const base64Data = annotatedImageBase64.replace(/^data:image\/\w+;base64,/, '');
          const buffer = Buffer.from(base64Data, 'base64');
          await blockBlob.uploadData(buffer, { blobHTTPHeaders: { blobContentType: 'image/jpeg' } });
          annotatedImageUrl = blockBlob.url;
        }
      } catch (e) {
        console.warn('Failed to upload annotated image:', e);
      }
    }

    const scan = await prisma.recognitionHistory.create({
      data: {
        userImageUrl: annotatedImageUrl || userImageUrl,
        userLatitude,
        userLongitude,
        aiDetails,
        poiId: poiId || null,
        userId: user.id,
      },
    });

    return NextResponse.json({ scan }, { status: 201 });
  } catch (error) {
    console.error('Save scan error:', error);
    return NextResponse.json({ error: 'Failed to save scan' }, { status: 500 });
  }
}
