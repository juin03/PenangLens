import { PrismaClient } from '@prisma/client';
const prisma = new PrismaClient();

const MORE_LANDMARKS = [
  // Ayer Itam food
  { name: 'Air Itam Laksa', description: 'Famous roadside laksa stall near Kek Lok Si. One of the best assam laksa in Penang.', location: '5.3990,100.2750', status: 'published', tags: ['Food'] },
  { name: 'Air Itam Char Koay Teow', description: 'Popular char kuey teow stall in Air Itam market area.', location: '5.4010,100.2770', status: 'published', tags: ['Food'] },
  { name: 'Koay Chiap Air Itam', description: 'Famous duck rice and koay chiap stall in Air Itam.', location: '5.4005,100.2775', status: 'published', tags: ['Food'] },
  { name: 'Fook Kin Kopitiam Air Itam', description: 'Traditional kopitiam serving classic Penang coffee and toast.', location: '5.4015,100.2785', status: 'published', tags: ['Food'] },
  { name: 'Hokkien Mee Air Itam', description: 'Prawn noodle soup stall known for rich prawn broth.', location: '5.4008,100.2768', status: 'published', tags: ['Food'] },
  // George Town food
  { name: 'Siam Road Char Koay Teow', description: 'Widely considered the best char kuey teow in Penang.', location: '5.4225,100.3250', status: 'published', tags: ['Food'] },
  { name: 'Lorong Selamat Char Koay Teow', description: 'Legendary char kuey teow fried with duck eggs.', location: '5.4200,100.3270', status: 'published', tags: ['Food'] },
  { name: 'Nasi Kandar Beratur', description: 'Famous nasi kandar with long queues on Jalan Transfer.', location: '5.4160,100.3320', status: 'published', tags: ['Food'] },
  { name: 'Deen Maju Nasi Kandar', description: 'Popular 24-hour nasi kandar on Jalan Gurdwara.', location: '5.4185,100.3315', status: 'published', tags: ['Food'] },
  { name: 'Sup Hameed', description: 'Late-night Indian Muslim soup stall famous for sup tulang.', location: '5.4190,100.3345', status: 'published', tags: ['Food'] },
  { name: 'Woodlands Vegetarian Restaurant', description: 'South Indian vegetarian restaurant serving thali and dosai.', location: '5.4175,100.3350', status: 'published', tags: ['Food'] },
  { name: 'Kebaya Dining Room', description: 'Fine dining Peranakan restaurant with award-winning nyonya cuisine.', location: '5.4195,100.3385', status: 'published', tags: ['Food'] },
  // Balik Pulau
  { name: 'Balik Pulau Laksa', description: 'Authentic Penang laksa in rural Balik Pulau.', location: '5.3540,100.2230', status: 'published', tags: ['Food'] },
  { name: 'Tropical Fruit Farm Balik Pulau', description: 'Fruit farm with tours and tastings of tropical fruits.', location: '5.3450,100.2100', status: 'published', tags: ['Nature', 'Food'] },
  // Tanjung Bungah / Gurney
  { name: 'Hai Boey Seafood', description: 'Popular seafood restaurant in Tanjung Bungah.', location: '5.4580,100.2850', status: 'published', tags: ['Food'] },
  { name: 'Suffolk House', description: 'Restored Georgian mansion from 1809, oldest intact building in Penang.', location: '5.4320,100.3050', status: 'published', tags: ['Heritage', 'Food'] },
  // Heritage/culture
  { name: 'Armenian Street (Lebuh Armenian)', description: 'Most famous street for street art and heritage shophouses.', location: '5.4150,100.3380', status: 'published', tags: ['Heritage', 'Art'] },
  { name: 'Acheen Street Malay Mosque', description: 'One of the oldest mosques in Penang, built in 1808.', location: '5.4155,100.3390', status: 'published', tags: ['Religious', 'Heritage'] },
  { name: 'Hainan Temple', description: 'Ornate Chinese temple dedicated to Mazu, the sea goddess.', location: '5.4160,100.3375', status: 'published', tags: ['Religious', 'Heritage'] },
  { name: 'Penang House of Music', description: 'Interactive museum celebrating Penang musical heritage.', location: '5.4180,100.3400', status: 'published', tags: ['Art', 'Culture'] },
];

async function main() {
  let created = 0, skipped = 0;
  for (const lm of MORE_LANDMARKS) {
    const existing = await prisma.landmark.findFirst({ where: { name: lm.name } });
    if (existing) { skipped++; continue; }
    for (const t of lm.tags) await prisma.tag.upsert({ where: { name: t }, update: {}, create: { name: t } });
    await prisma.landmark.create({
      data: {
        name: lm.name, description: lm.description, location: lm.location, status: lm.status,
        tags: { create: await Promise.all(lm.tags.map(async t => ({ tagId: (await prisma.tag.findUnique({ where: { name: t } }))!.id }))) },
      },
    });
    created++;
    console.log(`  ✓ ${lm.name}`);
  }
  console.log(`\n${created} created, ${skipped} skipped`);
}
main().catch(console.error).finally(() => prisma.$disconnect());
