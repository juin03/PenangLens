/**
 * Add missing tags (Historical, Adventure) and update landmark tags to 10-category system.
 * 
 * Run: npx ts-node --compiler-options '{"module":"commonjs"}' scripts/fix-tags.ts
 * Or:  npx tsx scripts/fix-tags.ts
 */
import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

// Landmarks that need Historical tag added
const ADD_HISTORICAL = [
  'Fort Cornwallis',
  'Queen Victoria Memorial Clock Tower',
  'Penang War Museum',
  'City Hall & Town Hall Esplanade',
  "St. George's Church",
  'Suffolk House',
  'Sun Yat Sen Museum',
];

// Landmarks that need Adventure tag added
const ADD_ADVENTURE = [
  'Escape Theme Park Penang',
  'Penang National Park',
  'Penang Hill',
  'Entopia by Penang Butterfly Farm',
  'Batu Ferringhi Beach',
  'Tanjung Bungah Beach',
  'Tropical Fruit Farm Balik Pulau',
];

async function main() {
  // Step 1: Ensure Historical and Adventure tags exist
  for (const tagName of ['Historical', 'Adventure']) {
    const tag = await prisma.tag.upsert({
      where: { name: tagName },
      update: {},
      create: { name: tagName },
    });
    console.log(`✅ Tag '${tagName}' ready (id=${tag.id})`);
  }

  // Step 2: Add Historical tag to landmarks
  const historicalTag = await prisma.tag.findUnique({ where: { name: 'Historical' } });
  for (const name of ADD_HISTORICAL) {
    const lm = await prisma.landmark.findFirst({ where: { name: { contains: name } } });
    if (!lm) { console.log(`⚠️  '${name}' not found, skipping`); continue; }
    
    const exists = await prisma.landmarkTag.findFirst({
      where: { landmarkId: lm.id, tagId: historicalTag!.id },
    });
    if (exists) { console.log(`⏭️  '${name}' already has Historical`); continue; }
    
    await prisma.landmarkTag.create({
      data: { landmarkId: lm.id, tagId: historicalTag!.id },
    });
    console.log(`✅ Added Historical → '${name}'`);
  }

  // Step 3: Add Adventure tag to landmarks
  const adventureTag = await prisma.tag.findUnique({ where: { name: 'Adventure' } });
  for (const name of ADD_ADVENTURE) {
    const lm = await prisma.landmark.findFirst({ where: { name: { contains: name } } });
    if (!lm) { console.log(`⚠️  '${name}' not found, skipping`); continue; }
    
    const exists = await prisma.landmarkTag.findFirst({
      where: { landmarkId: lm.id, tagId: adventureTag!.id },
    });
    if (exists) { console.log(`⏭️  '${name}' already has Adventure`); continue; }
    
    await prisma.landmarkTag.create({
      data: { landmarkId: lm.id, tagId: adventureTag!.id },
    });
    console.log(`✅ Added Adventure → '${name}'`);
  }

  console.log('\n🎉 Done! All tags updated.');
}

main()
  .catch(e => { console.error(e); process.exit(1); })
  .finally(() => prisma.$disconnect());
