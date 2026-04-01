import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { BlobServiceClient } from '@azure/storage-blob';

const AZURE_ENDPOINT = process.env.AZURE_SEARCH_ENDPOINT || '';
const AZURE_KEY      = process.env.AZURE_SEARCH_KEY      || '';
const BLOB_CONN_STR  = process.env.AZURE_STORAGE_CONNECTION_STRING || '';
const BLOB_CONTAINER = process.env.AZURE_STORAGE_CONTAINER_NAME || 'images';
const VISION_INDEX   = 'penanglens-poc-index';

async function deleteFromVisionIndex(imageId: string) {
  const url = `${AZURE_ENDPOINT}/indexes/${VISION_INDEX}/docs/index?api-version=2023-11-01`;
  await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'api-key': AZURE_KEY },
    body: JSON.stringify({ value: [{ '@search.action': 'delete', id: imageId }] }),
  });
}

/** DELETE /api/admin/spots/[id]/images/[imageId] */
export async function DELETE(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string; imageId: string }> }
) {
  const { id: spotId, imageId } = await params;
  try {
    // 1. Delete from Azure AI Search
    await deleteFromVisionIndex(imageId);

    // 2. Delete blob
    if (BLOB_CONN_STR) {
      const blobClient = BlobServiceClient.fromConnectionString(BLOB_CONN_STR)
        .getContainerClient(BLOB_CONTAINER)
        .getBlockBlobClient(`${imageId}.jpg`);
      await blobClient.deleteIfExists();
    }

    // 3. Delete from DB (best-effort)
    try {
      await prisma.poiImage.deleteMany({
        where: { poiId: spotId, imageUrl: { contains: imageId } },
      });
    } catch {}

    return NextResponse.json({ success: true });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
