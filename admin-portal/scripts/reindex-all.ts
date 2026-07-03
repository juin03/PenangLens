/**
 * Re-index all published landmarks and POIs into Azure AI Search via the Agent.
 * Run with: npx ts-node --project tsconfig.seed.json scripts/reindex-all.ts
 */
import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();
const AGENT_BASE_URL = process.env.AGENT_BASE_URL || 'http://127.0.0.1:8000';

async function indexSpot(spot: object) {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (process.env.AGENT_INTERNAL_KEY) headers['X-Internal-Key'] = process.env.AGENT_INTERNAL_KEY;
  const res = await fetch(`${AGENT_BASE_URL}/index`, {
    method: 'POST',
    headers,
    body: JSON.stringify(spot),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
}

async function main() {
  // Index landmarks
  const landmarks = await prisma.landmark.findMany({
    where: { status: 'published' },
    include: { tags: { include: { tag: true } } },
  });

  console.log(`📚 Indexing ${landmarks.length} landmarks...`);
  for (const lm of landmarks) {
    try {
      await indexSpot({
        id: lm.id,
        name: lm.name,
        type: 'landmark',
        description: lm.description,
        tags: lm.tags.map((t: any) => t.tag.name),
      });
      console.log(`  ✅ ${lm.name}`);
    } catch (e) {
      console.log(`  ❌ ${lm.name}: ${e}`);
    }
  }

  // Index POIs
  const pois = await prisma.pointOfInterest.findMany({
    where: { status: 'published' },
    include: { landmark: true },
  });

  console.log(`📍 Indexing ${pois.length} POIs...`);
  for (const poi of pois) {
    try {
      await indexSpot({
        id: poi.id,
        name: poi.name,
        type: 'poi',
        description: poi.description,
        searchPrompts: poi.searchPrompts,
        parentLandmarkName: poi.landmark?.name,
      });
      console.log(`  ✅ ${poi.name}`);
    } catch (e) {
      console.log(`  ❌ ${poi.name}: ${e}`);
    }
  }

  console.log('🎉 Re-index complete!');
}

main()
  .catch(console.error)
  .finally(() => prisma.$disconnect());
