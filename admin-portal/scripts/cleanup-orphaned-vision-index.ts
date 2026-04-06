/**
 * Cleanup script: Remove orphaned vision index entries
 * 
 * Finds all documents in the vision index (penanglens-poc-index) where the
 * poi_id no longer exists in the database, and deletes them.
 * 
 * Run: npx ts-node --project tsconfig.seed.json scripts/cleanup-orphaned-vision-index.ts
 */

import { PrismaClient } from '@prisma/client';
import * as dotenv from 'dotenv';

dotenv.config({ path: '.env.local' });

const prisma = new PrismaClient();

const AZURE_ENDPOINT = process.env.AZURE_SEARCH_ENDPOINT || '';
const AZURE_KEY = process.env.AZURE_SEARCH_KEY || '';
const VISION_INDEX = 'penanglens-poc-index';

async function main() {
  console.log('🔍 Scanning vision index for orphaned entries...\n');

  // 1. Get all valid spot IDs from database
  const landmarks = await prisma.landmark.findMany({ select: { id: true } });
  const pois = await prisma.pointOfInterest.findMany({ select: { id: true } });
  const validSpotIds = new Set([
    ...landmarks.map(l => l.id),
    ...pois.map(p => p.id),
  ]);

  console.log(`✅ Found ${validSpotIds.size} valid spots in database`);

  // 2. Get all documents from vision index
  const searchUrl = `${AZURE_ENDPOINT}/indexes/${VISION_INDEX}/docs?api-version=2023-11-01&$select=id,poi_id&$top=10000`;
  const searchRes = await fetch(searchUrl, {
    headers: { 'api-key': AZURE_KEY },
  });

  if (!searchRes.ok) {
    throw new Error(`Failed to search vision index: ${searchRes.statusText}`);
  }

  const searchData = await searchRes.json() as any;
  const allDocs = searchData.value || [];
  console.log(`✅ Found ${allDocs.length} documents in vision index\n`);

  // 3. Find orphaned documents
  const orphanedDocs = allDocs.filter((doc: any) => {
    const poiId = doc.poi_id;
    return poiId && !validSpotIds.has(poiId);
  });

  if (orphanedDocs.length === 0) {
    console.log('✨ No orphaned entries found. Vision index is clean!');
    return;
  }

  console.log(`⚠️  Found ${orphanedDocs.length} orphaned documents:`);
  
  // Group by poi_id for better reporting
  const orphanedBySpot = new Map<string, string[]>();
  for (const doc of orphanedDocs) {
    const poiId = doc.poi_id;
    if (!orphanedBySpot.has(poiId)) {
      orphanedBySpot.set(poiId, []);
    }
    orphanedBySpot.get(poiId)!.push(doc.id);
  }

  for (const [poiId, imageIds] of orphanedBySpot) {
    console.log(`   - Spot ${poiId}: ${imageIds.length} images`);
  }

  console.log('\n🗑️  Deleting orphaned entries...');

  // 4. Delete orphaned documents
  const deleteUrl = `${AZURE_ENDPOINT}/indexes/${VISION_INDEX}/docs/index?api-version=2023-11-01`;
  const deleteDocs = orphanedDocs.map((doc: any) => ({
    '@search.action': 'delete',
    id: doc.id,
  }));

  const deleteRes = await fetch(deleteUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'api-key': AZURE_KEY },
    body: JSON.stringify({ value: deleteDocs }),
  });

  if (!deleteRes.ok) {
    const errorText = await deleteRes.text();
    throw new Error(`Failed to delete documents: ${errorText}`);
  }

  console.log(`✅ Successfully deleted ${orphanedDocs.length} orphaned entries`);
  console.log('\n✨ Cleanup complete!');
}

main()
  .catch((error) => {
    console.error('❌ Error:', error);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
