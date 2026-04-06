/**
 * Check script: Find orphaned vision index entries (READ-ONLY)
 * 
 * Scans the vision index (penanglens-poc-index) and reports all documents
 * where the poi_id no longer exists in the database.
 * 
 * This script does NOT delete anything - it only reports what would be cleaned up.
 * 
 * Run: npx ts-node --project tsconfig.seed.json scripts/check-orphaned-vision-index.ts
 */

import { PrismaClient } from '@prisma/client';
import * as dotenv from 'dotenv';

dotenv.config({ path: '.env.local' });

const prisma = new PrismaClient();

const AZURE_ENDPOINT = process.env.AZURE_SEARCH_ENDPOINT || '';
const AZURE_KEY = process.env.AZURE_SEARCH_KEY || '';
const VISION_INDEX = 'penanglens-poc-index';

async function main() {
  console.log('🔍 Scanning vision index for orphaned entries (READ-ONLY)...\n');

  // 1. Get all valid spot IDs from database
  const landmarks = await prisma.landmark.findMany({ select: { id: true, name: true } });
  const pois = await prisma.pointOfInterest.findMany({ select: { id: true, name: true } });
  
  const validSpotIds = new Set([
    ...landmarks.map(l => l.id),
    ...pois.map(p => p.id),
  ]);

  const spotNames = new Map([
    ...landmarks.map(l => [l.id, l.name] as [string, string]),
    ...pois.map(p => [p.id, p.name] as [string, string]),
  ]);

  console.log(`✅ Found ${validSpotIds.size} valid spots in database:`);
  console.log(`   - ${landmarks.length} landmarks`);
  console.log(`   - ${pois.length} POIs\n`);

  // 2. Get all documents from vision index
  const searchUrl = `${AZURE_ENDPOINT}/indexes/${VISION_INDEX}/docs?api-version=2023-11-01&$select=id,poi_id,poi_name,filename&$top=10000`;
  const searchRes = await fetch(searchUrl, {
    headers: { 'api-key': AZURE_KEY },
  });

  if (!searchRes.ok) {
    throw new Error(`Failed to search vision index: ${searchRes.statusText}`);
  }

  const searchData = await searchRes.json() as any;
  const allDocs = searchData.value || [];
  console.log(`✅ Found ${allDocs.length} documents in vision index\n`);

  // 3. Categorize documents
  const validDocs = allDocs.filter((doc: any) => {
    const poiId = doc.poi_id;
    return poiId && validSpotIds.has(poiId);
  });

  const orphanedDocs = allDocs.filter((doc: any) => {
    const poiId = doc.poi_id;
    return poiId && !validSpotIds.has(poiId);
  });

  const unknownDocs = allDocs.filter((doc: any) => !doc.poi_id);

  console.log('📊 Vision Index Summary:');
  console.log(`   ✅ Valid entries: ${validDocs.length}`);
  console.log(`   ⚠️  Orphaned entries: ${orphanedDocs.length}`);
  console.log(`   ❓ Unknown entries (no poi_id): ${unknownDocs.length}\n`);

  // 4. Report valid entries by spot
  if (validDocs.length > 0) {
    console.log('✅ Valid Entries (by spot):');
    const validBySpot = new Map<string, any[]>();
    for (const doc of validDocs) {
      const poiId = doc.poi_id;
      if (!validBySpot.has(poiId)) {
        validBySpot.set(poiId, []);
      }
      validBySpot.get(poiId)!.push(doc);
    }

    for (const [poiId, docs] of validBySpot) {
      const spotName = spotNames.get(poiId) || 'Unknown';
      console.log(`   - ${spotName} (${poiId}): ${docs.length} images`);
    }
    console.log('');
  }

  // 5. Report orphaned entries
  if (orphanedDocs.length === 0) {
    console.log('✨ No orphaned entries found. Vision index is clean!');
  } else {
    console.log(`⚠️  Orphaned Entries (${orphanedDocs.length} total):`);
    console.log('   These images belong to deleted spots:\n');
    
    // Group by poi_id for better reporting
    const orphanedBySpot = new Map<string, any[]>();
    for (const doc of orphanedDocs) {
      const poiId = doc.poi_id;
      if (!orphanedBySpot.has(poiId)) {
        orphanedBySpot.set(poiId, []);
      }
      orphanedBySpot.get(poiId)!.push(doc);
    }

    for (const [poiId, docs] of orphanedBySpot) {
      const poiName = docs[0].poi_name || 'Unknown';
      console.log(`   📍 Spot: ${poiName}`);
      console.log(`      ID: ${poiId}`);
      console.log(`      Images: ${docs.length}`);
      
      // Show first 3 image IDs as examples
      const exampleIds = docs.slice(0, 3).map(d => d.id);
      console.log(`      Example IDs: ${exampleIds.join(', ')}${docs.length > 3 ? '...' : ''}`);
      console.log('');
    }

    console.log(`\n💡 To clean up these ${orphanedDocs.length} orphaned entries, run:`);
    console.log('   npx ts-node --project tsconfig.seed.json scripts/cleanup-orphaned-vision-index.ts');
  }

  // 6. Report unknown entries
  if (unknownDocs.length > 0) {
    console.log(`\n❓ Unknown Entries (${unknownDocs.length} total):`);
    console.log('   These documents have no poi_id field:\n');
    
    for (const doc of unknownDocs.slice(0, 5)) {
      console.log(`   - ID: ${doc.id}`);
      console.log(`     Filename: ${doc.filename || 'N/A'}`);
    }
    
    if (unknownDocs.length > 5) {
      console.log(`   ... and ${unknownDocs.length - 5} more`);
    }
  }

  console.log('\n✨ Check complete!');
}

main()
  .catch((error) => {
    console.error('❌ Error:', error);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
