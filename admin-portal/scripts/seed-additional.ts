import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

/**
 * Additional seed data — run AFTER seed-mock-data.ts
 * Only adds NEW landmarks/POIs, won't duplicate existing ones.
 */

const ADDITIONAL_LANDMARKS = [
  // ==========================================
  // FOOD — George Town
  // ==========================================
  {
    name: 'Tek Sen Restaurant',
    description: 'A legendary Chinese restaurant in George Town known for its double-roasted pork and claypot dishes. Always packed — arrive early.',
    location: '5.4155,100.3345',
    status: 'published',
    tags: ['Food'],
    content: {
      overview: 'Tek Sen is one of the most celebrated restaurants in Penang, famous for its Hokkien-style Chinese cooking. Located on Lebuh Carnarvon, it has been serving locals and tourists for decades.',
      funFacts: 'The queue often stretches down the street. Their signature double-roasted pork belly is considered one of the best dishes in Penang.'
    }
  },
  {
    name: 'Hameediyah Restaurant',
    description: 'The oldest nasi kandar restaurant in Penang, established in 1907. Famous for its murtabak and biryani.',
    location: '5.4178,100.3340',
    status: 'published',
    tags: ['Food'],
    content: {
      overview: 'Hameediyah is a Penang institution, serving nasi kandar since 1907 on Lebuh Campbell. It is widely regarded as the birthplace of nasi kandar in Penang.',
      funFacts: 'Their murtabak recipe has remained unchanged for over a century. The restaurant has been visited by multiple Malaysian prime ministers.'
    }
  },
  {
    name: 'Joo Hooi Cafe',
    description: 'A no-frills hawker stall famous for its Penang Assam Laksa, consistently rated among the best in the city.',
    location: '5.4170,100.3310',
    status: 'published',
    tags: ['Food'],
    content: {
      overview: 'Joo Hooi Cafe on Lebuh Keng Kwee is a must-visit for Penang Assam Laksa lovers. The tangy, fish-based broth with thick rice noodles is a Penang signature dish.',
    }
  },
  {
    name: 'Toh Soon Cafe',
    description: 'A charming back-alley cafe famous for its charcoal-toasted bread with kaya and soft-boiled eggs.',
    location: '5.4165,100.3355',
    status: 'published',
    tags: ['Food'],
    content: {
      overview: 'Hidden in a back alley off Lebuh Campbell, Toh Soon Cafe is a beloved breakfast spot. The charcoal-toasted bread with homemade kaya and butter is a Penang morning ritual.',
    }
  },
  {
    name: 'New Lane Hawker Centre',
    description: 'One of Penang\'s most popular street food destinations, operating as an evening hawker strip along Lorong Baru.',
    location: '5.4145,100.3280',
    status: 'published',
    tags: ['Food'],
    content: {
      overview: 'New Lane (Lorong Baru) transforms into a bustling hawker paradise every evening. Famous for char kuey teow, fried oyster omelette, and lok-lok.',
    }
  },
  {
    name: 'Sister Curry Mee',
    description: 'A legendary curry mee stall in Air Itam, known for its rich coconut-based curry broth with prawns and cockles.',
    location: '5.4020,100.2780',
    status: 'published',
    tags: ['Food'],
    content: {
      overview: 'Air Itam Sister Curry Mee is a Penang institution. The stall has been serving its signature curry mee for decades, drawing long queues every morning.',
    }
  },
  {
    name: 'Red Garden Food Paradise',
    description: 'A large open-air food court in George Town with live entertainment and dozens of hawker stalls.',
    location: '5.4185,100.3350',
    status: 'published',
    tags: ['Food'],
    content: {
      overview: 'Red Garden is one of the largest food courts in George Town, offering a wide variety of local and international dishes under one roof with nightly live music.',
    }
  },
  // ==========================================
  // FOOD — Batu Ferringhi / North
  // ==========================================
  {
    name: 'Long Beach Food Court Batu Ferringhi',
    description: 'A popular beachside food court in Batu Ferringhi with seafood BBQ and local dishes.',
    location: '5.4735,100.2465',
    status: 'published',
    tags: ['Food'],
    content: {
      overview: 'Long Beach is the go-to food court for visitors staying in Batu Ferringhi. Fresh seafood BBQ, satay, and local favourites are served nightly along the beach.',
    }
  },
  {
    name: 'Ferringhi Garden Restaurant',
    description: 'A highly-rated garden restaurant in Batu Ferringhi serving Western and Asian fusion cuisine.',
    location: '5.4720,100.2490',
    status: 'published',
    tags: ['Food'],
    content: {
      overview: 'Set in a lush tropical garden, Ferringhi Garden is one of the best dining experiences in the Batu Ferringhi area, known for its steaks and seafood.',
    }
  },
  {
    name: 'BoraBora by Sunset Bar',
    description: 'A beachfront bar and restaurant in Batu Ferringhi, perfect for sunset drinks and casual dining.',
    location: '5.4740,100.2450',
    status: 'published',
    tags: ['Food'],
    content: {
      overview: 'BoraBora is a laid-back beach bar right on the sand at Batu Ferringhi. Great for sunset cocktails, grilled seafood, and a relaxed evening atmosphere.',
    }
  },
  // ==========================================
  // FOOD — Gurney / Pulau Tikus
  // ==========================================
  {
    name: 'Pulau Tikus Market',
    description: 'A morning wet market and hawker centre in the Pulau Tikus neighbourhood, popular with locals for breakfast.',
    location: '5.4350,100.3100',
    status: 'published',
    tags: ['Food', 'Culture'],
    content: {
      overview: 'Pulau Tikus Market is where locals go for authentic Penang breakfast — popiah, kuih, curry mee, and fresh produce. A genuine local experience away from tourist crowds.',
    }
  },
  {
    name: 'Northam Beach Cafe',
    description: 'A waterfront cafe along Northam Road with views of the Penang Strait.',
    location: '5.4280,100.3200',
    status: 'published',
    tags: ['Food'],
    content: {
      overview: 'Northam Beach Cafe offers casual dining with a sea view. Popular for evening meals and weekend brunches.',
    }
  },
  // ==========================================
  // HERITAGE — George Town
  // ==========================================
  {
    name: 'Cheong Fatt Tze - The Blue Mansion',
    description: 'A stunning indigo-blue Chinese courtyard mansion, now a boutique hotel and museum. UNESCO World Heritage Site.',
    location: '5.4210,100.3380',
    status: 'published',
    tags: ['Heritage', 'Architecture'],
    content: {
      overview: 'The Blue Mansion is one of the most iconic buildings in George Town. Built in the 1880s by Chinese merchant Cheong Fatt Tze, it showcases exquisite Chinese architecture with Art Nouveau influences.',
      history: 'Cheong Fatt Tze was a Hakka merchant who became one of the wealthiest men in Southeast Asia. The mansion took 7 years to build and features 38 rooms, 5 courtyards, and 7 staircases.',
    }
  },
  {
    name: 'Pinang Peranakan Mansion',
    description: 'A beautifully restored Peranakan mansion showcasing the opulent lifestyle of the Straits Chinese community.',
    location: '5.4195,100.3370',
    status: 'published',
    tags: ['Heritage', 'Culture'],
    content: {
      overview: 'The Pinang Peranakan Mansion is a museum dedicated to the Peranakan (Straits Chinese) culture of Penang. The mansion is filled with antiques, furniture, and artefacts from the 19th century.',
    }
  },
  {
    name: 'Clan Jetties of Penang',
    description: 'A collection of Chinese clan settlements built on stilts over the water, dating back to the 19th century.',
    location: '5.4120,100.3420',
    status: 'published',
    tags: ['Heritage', 'Culture'],
    content: {
      overview: 'The Clan Jetties are waterfront settlements where Chinese immigrant clans built their homes on stilts over the sea. Chew Jetty is the largest and most visited, with temples, shops, and homes still in use.',
    }
  },
  {
    name: 'Sun Yat Sen Museum',
    description: 'A museum dedicated to Dr. Sun Yat Sen\'s revolutionary activities in Penang during the early 20th century.',
    location: '5.4200,100.3395',
    status: 'published',
    tags: ['Heritage'],
    content: {
      overview: 'This museum occupies the house where Dr. Sun Yat Sen planned the 1911 Chinese Revolution. It documents his time in Penang and the role of overseas Chinese in the revolution.',
    }
  },
  // ==========================================
  // ART & CULTURE
  // ==========================================
  {
    name: 'The Camera Museum',
    description: 'A quirky museum on Lebuh Muntri showcasing vintage cameras and the history of photography.',
    location: '5.4175,100.3365',
    status: 'published',
    tags: ['Art', 'Culture'],
    content: {
      overview: 'The Camera Museum houses a collection of over 1,000 vintage cameras spanning 100 years of photography history. Interactive exhibits let visitors try old camera techniques.',
    }
  },
  {
    name: 'Penang State Museum and Art Gallery',
    description: 'The main state museum covering Penang\'s history, culture, and art from prehistoric times to the present.',
    location: '5.4215,100.3410',
    status: 'published',
    tags: ['Heritage', 'Art', 'Culture'],
    content: {
      overview: 'Located near Fort Cornwallis, the Penang State Museum covers the island\'s rich multicultural history through exhibits on Malay, Chinese, Indian, and colonial heritage.',
    }
  },
  {
    name: 'ChinaHouse',
    description: 'A sprawling art space, cafe, and bar complex spanning three heritage buildings on Lebuh Pantai.',
    location: '5.4165,100.3395',
    status: 'published',
    tags: ['Art', 'Food'],
    content: {
      overview: 'ChinaHouse is one of the longest buildings in George Town, combining art galleries, a cafe, a restaurant, and a live music bar. Famous for its cakes and creative atmosphere.',
    }
  },
  // ==========================================
  // NATURE — Various areas
  // ==========================================
  {
    name: 'Tropical Spice Garden',
    description: 'An award-winning spice garden in Batu Ferringhi with guided tours, cooking classes, and nature trails.',
    location: '5.4680,100.2350',
    status: 'published',
    tags: ['Nature'],
    content: {
      overview: 'The Tropical Spice Garden spans 8 acres of hillside in Batu Ferringhi, showcasing over 500 species of tropical plants and spices. Guided tours and cooking classes are available.',
    }
  },
  {
    name: 'Escape Theme Park Penang',
    description: 'An outdoor adventure theme park with zip lines, water slides, and obstacle courses set in a forest.',
    location: '5.4550,100.2250',
    status: 'published',
    tags: ['Nature', 'Culture'],
    content: {
      overview: 'ESCAPE Penang is a unique outdoor theme park focused on nature-based adventures. Activities include the world\'s longest water slide, zip lines, and treetop obstacle courses.',
    }
  },
  {
    name: 'Batu Ferringhi Beach',
    description: 'The most popular tourist beach in Penang, known for its water sports, night market, and beachfront hotels.',
    location: '5.4734,100.2461',
    status: 'published',
    tags: ['Nature'],
    content: {
      overview: 'Batu Ferringhi is Penang\'s main beach destination. The 2km stretch of sand offers parasailing, jet skiing, banana boat rides, and a famous night market.',
    }
  },
  // ==========================================
  // SHOPPING
  // ==========================================
  {
    name: 'Gurney Plaza',
    description: 'A major shopping mall on Gurney Drive with international brands, a food court, and a cinema.',
    location: '5.4370,100.3130',
    status: 'published',
    tags: ['Shopping'],
    content: {
      overview: 'Gurney Plaza is one of Penang\'s premier shopping destinations, located along the Gurney Drive waterfront. It houses international fashion brands, electronics stores, and a large food court.',
    }
  },
  {
    name: 'Komtar',
    description: 'Penang\'s tallest building and a major commercial hub with shopping, The Top attraction, and transport links.',
    location: '5.4140,100.3290',
    status: 'published',
    tags: ['Shopping', 'Architecture'],
    content: {
      overview: 'KOMTAR (Kompleks Tun Abdul Razak) is the 65-storey landmark tower of Penang. It houses shopping floors, The Top observation deck, and is the main bus terminal hub.',
    }
  },
  {
    name: 'Little India Penang',
    description: 'A vibrant Indian quarter in George Town with textile shops, spice stores, flower garlands, and Indian restaurants.',
    location: '5.4175,100.3340',
    status: 'published',
    tags: ['Shopping', 'Culture', 'Food'],
    content: {
      overview: 'Little India on Lebuh Pasar and surrounding streets is a colourful enclave of Indian culture in George Town. Browse saris, sample banana leaf rice, and soak in the atmosphere.',
    }
  },
];

async function main() {
  console.log('Seeding additional landmarks...');
  let created = 0, skipped = 0;

  for (const lm of ADDITIONAL_LANDMARKS) {
    // Check if already exists
    const existing = await prisma.landmark.findFirst({ where: { name: lm.name } });
    if (existing) {
      skipped++;
      continue;
    }

    // Ensure tags exist
    for (const tagName of lm.tags) {
      await prisma.tag.upsert({ where: { name: tagName }, update: {}, create: { name: tagName } });
    }

    await prisma.landmark.create({
      data: {
        name: lm.name,
        description: lm.description,
        location: lm.location,
        status: lm.status,
        content: lm.content as any,
        tags: {
          create: await Promise.all(
            lm.tags.map(async (t) => {
              const tag = await prisma.tag.findUnique({ where: { name: t } });
              return { tagId: tag!.id };
            })
          ),
        },
      },
    });
    created++;
    console.log(`  ✓ ${lm.name}`);
  }

  console.log(`\nDone: ${created} created, ${skipped} skipped (already exist)`);
}

main()
  .catch(console.error)
  .finally(() => prisma.$disconnect());
