/**
 * Run: npx ts-node --project tsconfig.seed.json scripts/clear-vision-index.ts
 * Deletes ALL documents from Azure AI Search vision index + all blobs in the images container.
 */
import { BlobServiceClient } from '@azure/storage-blob';
import * as dotenv from 'dotenv';
import * as path from 'path';

dotenv.config({ path: path.resolve(__dirname, '../.env.local') });

const AZURE_ENDPOINT = process.env.AZURE_SEARCH_ENDPOINT!;
const AZURE_KEY      = process.env.AZURE_SEARCH_KEY!;
const BLOB_CONN_STR  = process.env.AZURE_STORAGE_CONNECTION_STRING!;
const BLOB_CONTAINER = process.env.AZURE_STORAGE_CONTAINER_NAME || 'images';
const INDEX_NAME     = 'penanglens-poc-index';

async function getAllDocIds(): Promise<string[]> {
  const url = `${AZURE_ENDPOINT}/indexes/${INDEX_NAME}/docs?api-version=2023-11-01&$select=id&$top=1000`;
  const res = await fetch(url, { headers: { 'api-key': AZURE_KEY } });
  if (!res.ok) throw new Error(`Search list failed: ${await res.text()}`);
  const data = await res.json() as any;
  return (data.value || []).map((d: any) => d.id);
}

async function deleteFromIndex(ids: string[]) {
  if (ids.length === 0) return;
  const docs = ids.map(id => ({ '@search.action': 'delete', id }));
  const url = `${AZURE_ENDPOINT}/indexes/${INDEX_NAME}/docs/index?api-version=2023-11-01`;
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'api-key': AZURE_KEY },
    body: JSON.stringify({ value: docs }),
  });
  if (!res.ok) throw new Error(`Search delete failed: ${await res.text()}`);
}

async function deleteAllBlobs() {
  const client = BlobServiceClient.fromConnectionString(BLOB_CONN_STR);
  const container = client.getContainerClient(BLOB_CONTAINER);
  let count = 0;
  for await (const blob of container.listBlobsFlat()) {
    await container.deleteBlob(blob.name);
    console.log(`  🗑️  Deleted blob: ${blob.name}`);
    count++;
  }
  return count;
}

async function main() {
  console.log('🔍 Fetching all vector index documents...');
  const ids = await getAllDocIds();
  console.log(`   Found ${ids.length} documents`);

  if (ids.length > 0) {
    await deleteFromIndex(ids);
    console.log(`✅ Deleted ${ids.length} vectors from Azure AI Search`);
  }

  console.log('\n🗂️  Deleting all blobs from Azure Blob Storage...');
  const blobCount = await deleteAllBlobs();
  console.log(`✅ Deleted ${blobCount} blobs`);

  console.log('\n✨ Done — vision index and blob storage are now empty.');
}

main().catch(e => { console.error(e); process.exit(1); });
