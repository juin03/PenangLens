import { PrismaClient } from '@prisma/client';
const prisma = new PrismaClient();

const LANDMARKS = [
  { name: 'Air Itam Dam', description: 'Scenic reservoir surrounded by hills, popular for morning walks.', location: '5.3950,100.2700', tags: ['Nature'] },
  { name: 'Poh Hock Seah Temple', description: 'Historic Chinese temple, one of the oldest in Penang.', location: '5.4000,100.2760', tags: ['Religious', 'Heritage'] },
  { name: 'Esplanade (Padang Kota Lama)', description: 'Large waterfront field next to Fort Cornwallis with sea views.', location: '5.4215,100.3445', tags: ['Heritage', 'Nature'] },
  { name: 'Penang City Hall', description: 'Grand colonial Edwardian Baroque building from 1903.', location: '5.4220,100.3420', tags: ['Heritage', 'Architecture'] },
  { name: 'Penang Town Hall', description: 'Elegant Palladian-style building from 1883.', location: '5.4218,100.3415', tags: ['Heritage', 'Architecture'] },
  { name: 'Goddess of Mercy Temple (Kuan Yin Teng)', description: 'One of the oldest Chinese temples in Penang, built in 1728.', location: '5.4160,100.3360', tags: ['Religious', 'Heritage'] },
  { name: 'Yap Kongsi Temple', description: 'Beautifully restored Hokkien clan temple.', location: '5.4148,100.3370', tags: ['Heritage', 'Culture'] },
  { name: 'Han Jiang Ancestral Temple', description: 'UNESCO-awarded Teochew clan temple.', location: '5.4155,100.3375', tags: ['Heritage', 'Culture', 'Architecture'] },
  { name: 'Street Art on Lebuh Cannon', description: 'Wire-frame art installations and murals.', location: '5.4158,100.3365', tags: ['Art'] },
  { name: 'The Mugshot Cafe', description: 'Popular heritage shophouse cafe.', location: '5.4162,100.3378', tags: ['Food', 'Art'] },
  { name: 'Narrow Marrow', description: 'Trendy narrow shophouse cafe with specialty coffee.', location: '5.4158,100.3382', tags: ['Food'] },
  { name: "Wheeler's Coffee", description: 'Specialty coffee roaster and cafe.', location: '5.4170,100.3360', tags: ['Food'] },
  { name: 'Tanjung Bungah Floating Mosque', description: 'Striking mosque built on stilts over the sea.', location: '5.4650,100.2800', tags: ['Religious', 'Architecture'] },
  { name: 'Tanjung Bungah Beach', description: 'Quieter beach alternative to Batu Ferringhi.', location: '5.4620,100.2830', tags: ['Nature'] },
  { name: 'Penang Toy Museum', description: 'Museum with over 100,000 toy collectibles.', location: '5.4640,100.2810', tags: ['Culture', 'Art'] },
  { name: 'Penang War Museum', description: 'WWII fortress with tunnels and bunkers.', location: '5.2870,100.2830', tags: ['Heritage'] },
  { name: 'Snake Temple', description: 'Unique Buddhist temple where pit vipers roam freely.', location: '5.3180,100.2870', tags: ['Religious', 'Heritage'] },
  { name: 'Made in Penang Interactive Museum', description: '3D interactive museum with trick art.', location: '5.4155,100.3350', tags: ['Art', 'Culture'] },
  { name: 'Setia SPICE Arena', description: "Penang's largest convention centre.", location: '5.3200,100.2780', tags: ['Architecture'] },
  { name: 'Kek Lok Si Botanical Garden', description: 'Peaceful botanical garden near Kek Lok Si.', location: '5.3980,100.2730', tags: ['Nature'] },
  { name: 'Penang Bridge Viewpoint', description: 'Popular spot to photograph the Penang Bridge.', location: '5.3540,100.3480', tags: ['Nature', 'Architecture'] },
  { name: 'Gurney Wharf', description: 'New waterfront promenade with parks and cycling paths.', location: '5.4380,100.3150', tags: ['Nature'] },
];

async function main() {
  let created = 0, skipped = 0;
  for (const lm of LANDMARKS) {
    const existing = await prisma.landmark.findFirst({ where: { name: lm.name } });
    if (existing) { skipped++; continue; }
    for (const t of lm.tags) await prisma.tag.upsert({ where: { name: t }, update: {}, create: { name: t } });
    await prisma.landmark.create({
      data: {
        name: lm.name, description: lm.description, location: lm.location, status: 'published',
        tags: { create: await Promise.all(lm.tags.map(async t => ({ tagId: (await prisma.tag.findUnique({ where: { name: t } }))!.id }))) },
      },
    });
    created++;
    console.log(`  ✓ ${lm.name}`);
  }
  console.log(`\n${created} created, ${skipped} skipped`);
}
main().catch(console.error).finally(() => prisma.$disconnect());
