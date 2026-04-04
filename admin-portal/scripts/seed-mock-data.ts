import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

const CATEGORIES = ['Heritage', 'Food', 'Nature', 'Art', 'Culture', 'Religious', 'Shopping', 'Historical', 'Architecture'];

const MOCK_DATA = [
  // ==========================================
  // HERITAGE / RELIGIOUS
  // ==========================================
  {
    name: 'Kek Lok Si Temple',
    description: 'The largest Buddhist temple in Malaysia, featuring the striking Pagoda of Rama VI and a towering Guan Yin statue.',
    location: '5.3995,100.2743',
    status: 'published',
    tags: ['Religious', 'Heritage', 'Architecture'],
    content: {
      overview: 'Kek Lok Si is a magnificent Buddhist temple situated in Air Itam, Penang. Facing the sea and commanding an impressive view of the surrounding hills and the Straits of Malacca, it is one of the best known temples on the island and a major pilgrimage destination for Buddhists across Southeast Asia. The temple complex sprawls across several terraced hillside levels, each tier revealing increasingly elaborate shrines, pavilions, and statues. Visitors ascend through a covered bazaar lined with souvenir stalls before reaching the main temple halls, pagoda, and the iconic Guan Yin statue at the summit.',
      history: 'Construction of Kek Lok Si began in 1890 under the guidance of Beow Lean, the chief monk of the Goddess of Mercy Temple on Pitt Street. The project was supported by donations from devotees across Southeast Asia and even from the Qing Emperor Guangxu, who granted an imperial edict and a collection of Buddhist scriptures. The main temple halls were completed by 1904, but the broader complex continued to expand for decades. The iconic Pagoda of Rama VI was completed in 1930, and the towering bronze Guan Yin statue was added in the late 20th century, replacing an earlier plaster version destroyed by fire.',
      culture: 'Kek Lok Si serves as a major pilgrimage center for Buddhists from Malaysia, Singapore, Hong Kong, Thailand, and beyond. The temple blends three distinct Buddhist traditions — Chinese, Thai, and Burmese — reflecting the multicultural heritage of Penang itself. During Chinese New Year, the entire complex is illuminated with tens of thousands of lanterns and colored lights, drawing enormous crowds for the nightly light-up ceremony. The temple also hosts regular prayer sessions, vegetarian food fairs, and cultural performances that keep it vibrant throughout the year.',
      funFacts: 'The name "Kek Lok Si" translates to "Temple of Supreme Bliss" in Hokkien. The Pagoda of Rama VI is sometimes called the "Pagoda of Ten Thousand Buddhas" because its interior walls are lined with thousands of small Buddha images. The temple complex is so large that it has its own internal funicular lift to carry visitors up to the Guan Yin statue level. During the annual Chinese New Year light-up, over 10,000 lanterns and 300,000 light bulbs are used to illuminate the entire hillside.'
    },
    pois: [
      {
        name: 'Pagoda of Rama VI',
        description: 'The iconic seven-storey Pagoda of Ten Thousand Buddhas, blending Chinese, Thai, and Burmese architectural styles into a single towering structure.',
        location: '5.3997,100.2739',
        searchPrompts: ['burmese_spire', 'chinese_base', 'thai_tier', 'pagoda', 'seven_storey'],
        content: {
          overview: 'The Pagoda of Rama VI, also known as the Pagoda of Ten Thousand Buddhas, is the defining centerpiece of Kek Lok Si Temple. Rising seven storeys above the hillside, it is one of the most architecturally distinctive pagodas in Southeast Asia. The structure is a deliberate fusion of three Buddhist architectural traditions: a Chinese octagonal base, a Thai middle tier, and a Burmese crown topped with a gilded spire. The interior walls of each level are lined with hundreds of small Buddha images, giving the pagoda its popular name.',
          history: 'Construction of the pagoda began in 1915 and was completed in 1930. It was named in honor of King Rama VI of Thailand, who made a donation toward its construction during a royal visit. The pagoda was built to house sacred Buddhist relics and scriptures, and its syncretic design was a deliberate statement of pan-Buddhist unity across the three major traditions represented in Penang.',
          culture: 'The pagoda is the spiritual heart of Kek Lok Si and the focal point of all major religious ceremonies at the temple. Devotees circumambulate the pagoda clockwise while chanting prayers, a practice common across all three Buddhist traditions represented in its architecture. The pagoda is particularly significant during Wesak Day, when it is illuminated and monks lead processions around its base.',
          funFacts: 'The pagoda contains over 10,000 individual Buddha images on its interior walls. The gilded Burmese spire at the top is said to have been cast from a single mold. On clear days, the view from the upper levels of the pagoda extends across the Straits of Malacca to the mainland of Peninsular Malaysia.'
        }
      },
      {
        name: 'Guan Yin Statue Pavilion',
        description: 'A massive 30.2-metre bronze statue of Guan Yin, the Goddess of Mercy, housed in an ornate open-air pavilion at the summit of the temple complex.',
        location: '5.4003,100.2745',
        searchPrompts: ['dragon_pillar', 'guan_yin_statue', 'holy_vase', 'lotus_base', 'three_tiered_pavilion_roof', 'bronze_statue'],
        content: {
          overview: 'Standing 30.2 metres tall on a lotus-shaped base, the bronze statue of Guan Yin at Kek Lok Si is one of the tallest statues of the Goddess of Mercy in the world. The statue depicts Guan Yin in her classic form — robed, serene, and holding a holy vase — and is visible from much of the surrounding hillside. The pavilion surrounding the statue features ornate dragon-wrapped pillars, a three-tiered roof with upswept eaves, and intricate carvings throughout.',
          history: 'The original Guan Yin statue at this location was made of plaster and was significantly smaller. It was destroyed in a fire in the mid-20th century. The current bronze statue was commissioned as a replacement and was unveiled in 2002 after years of fundraising from devotees across Southeast Asia. The pavilion was constructed simultaneously to shelter the statue from the elements.',
          culture: 'Guan Yin, the Bodhisattva of Compassion, is one of the most widely venerated figures in Chinese Buddhism. Devotees visit the statue to pray for mercy, healing, and protection. The statue is the final destination of the pilgrimage route through Kek Lok Si, and many visitors make the journey on foot as an act of devotion. Offerings of flowers, incense, and fruit are placed at the base of the statue daily.',
          funFacts: 'The bronze used to cast the statue was sourced from multiple countries as a symbol of pan-Asian Buddhist solidarity. The statue weighs several tonnes and required specialized engineering to anchor it safely to the hillside. On clear nights, the statue is illuminated and can be seen from boats in the Straits of Malacca.'
        }
      },
      {
        name: 'Ban Po Thar (Ten Thousand Buddhas Pagoda Base)',
        description: 'The ornate entrance gateway and lower courtyard of Kek Lok Si, featuring elaborate carvings, turtle ponds, and the start of the covered bazaar.',
        location: '5.3993,100.2741',
        searchPrompts: ['temple_gate', 'turtle_pond', 'covered_bazaar', 'entrance_arch'],
        content: {
          overview: 'The lower courtyard of Kek Lok Si is the first area visitors encounter after ascending from the car park. It features a large turtle liberation pond — a common feature of Chinese Buddhist temples where devotees release turtles as an act of merit-making — as well as the ornate main gateway arch, souvenir stalls, and the beginning of the covered walkway that leads up through the complex.',
          history: 'The lower courtyard was among the first sections of Kek Lok Si to be completed, established in the early 1900s as the formal entrance to the temple. The turtle pond has been a feature since the earliest days of the temple, reflecting the Buddhist principle of releasing living creatures to accumulate merit.',
          culture: 'Releasing turtles at Buddhist temples is a widespread practice in Chinese Buddhism known as "fang sheng" (releasing life). Devotees purchase turtles from vendors near the pond and release them as an act of compassion and merit-making. The lower courtyard is also where many visitors purchase incense, offerings, and religious items before ascending to the main halls.',
          funFacts: 'The turtle pond at Kek Lok Si contains hundreds of turtles of various species, some of which have lived there for decades. The covered bazaar leading up through the complex is lined with stalls selling everything from religious items to local snacks, and the walk through it is considered part of the temple experience.'
        }
      }
    ]
  },
  {
    name: 'Fort Cornwallis',
    description: 'The largest standing fort in Malaysia, built by the British East India Company in the late 18th century at the very spot where Captain Francis Light first landed.',
    location: '5.4206,100.3440',
    status: 'published',
    tags: ['Heritage'],
    content: {
      overview: 'Fort Cornwallis stands at the northeastern tip of Penang Island, occupying the exact site where Captain Francis Light landed on 11 August 1786 to establish the British settlement. It is the largest standing fort in Malaysia and one of the best-preserved examples of British colonial military architecture in Southeast Asia. The fort takes the form of a classic star fort — a design developed in Renaissance Europe to deflect cannon fire — with five bastions projecting outward from a central parade ground. Today the fort is a popular heritage attraction, housing a small amphitheatre, a chapel, a lighthouse, historic cannons, and the statue of Francis Light.',
      history: 'The original fort was constructed in 1786 from nibong palm trunks as a temporary defensive structure. Between 1804 and 1805, it was rebuilt in brick by convict labor under the supervision of the East India Company. The fort was named after Charles Cornwallis, the Governor-General of India at the time. Despite its imposing appearance, Fort Cornwallis never fired its cannons in anger — it was never attacked. During World War II, the Japanese used the fort as an internment camp for Allied prisoners of war. After independence, it was gazetted as a national monument.',
      culture: 'Fort Cornwallis is deeply embedded in the founding mythology of Penang. The site where Light landed is marked within the fort grounds, and the fort itself is a symbol of the colonial era that shaped the island\'s multicultural character. The fort hosts cultural events, open-air concerts, and heritage festivals throughout the year. Its central parade ground has been converted into an amphitheatre used for public performances. The fort is also a popular spot for evening walks, with the sea breeze and views of the Straits of Malacca making it a pleasant gathering place.',
      funFacts: 'Legend has it that Captain Francis Light fired silver coins from a cannon into the jungle to motivate his workers to clear the land quickly. The star shape of the fort is a classic example of "trace italienne" military architecture, designed to eliminate blind spots and allow defenders to cover every angle of approach. The fort\'s walls are up to 3 metres thick in places. One of the cannons in the fort, the Seri Rambai, is believed by local women to have fertility-granting powers.'
    },
    pois: [
      {
        name: 'Seri Rambai Cannon',
        description: 'A historic 17th-century Dutch bronze cannon with a storied past spanning three continents, now believed by locals to possess fertility powers.',
        location: '5.4210,100.3442',
        searchPrompts: ['cannon', 'seri_rambai', 'bronze_cannon', 'dutch_cannon'],
        content: {
          overview: 'The Seri Rambai is a large bronze cannon dating to 1603, making it one of the oldest surviving cannons in Malaysia. It is mounted on a carriage near the main entrance of Fort Cornwallis and is one of the most photographed objects in Penang. The cannon is decorated with intricate floral motifs and bears a Dutch inscription. Local tradition holds that women who place flowers in the barrel of the cannon and make a wish will be blessed with fertility and children.',
          history: 'The Seri Rambai was originally cast in the Netherlands in 1603 and was brought to the Malay Archipelago by the Dutch East India Company (VOC). It was captured by the Acehnese of Sumatra during a raid, then seized by pirates, and eventually came into the possession of the Sultan of Selangor. The British acquired it in 1871 as part of a diplomatic settlement and brought it to Penang, where it has remained ever since.',
          culture: 'The fertility legend associated with the Seri Rambai is one of the most enduring folk beliefs in Penang. Women — particularly those hoping to conceive — visit the cannon to place frangipani flowers in its barrel and whisper their wishes. The practice has no historical basis but has been observed for generations and is now considered part of the cultural fabric of the fort. The cannon is also a symbol of the complex colonial and maritime history of the Malay world.',
          funFacts: 'The name "Seri Rambai" means "Beautiful Rambai" in Malay, rambai being a local fruit. The cannon weighs approximately 2 tonnes. Its journey from the Netherlands to Aceh to Selangor to Penang makes it one of the most widely travelled historical artefacts in Southeast Asia.'
        }
      },
      {
        name: 'Fort Cornwallis Lighthouse',
        description: 'A distinctive steel framework lighthouse erected by the British at the northeast corner of the fort, the second oldest lighthouse in Malaysia.',
        location: '5.4211,100.3443',
        searchPrompts: ['lighthouse', 'steel_framework', 'octagonal_lighthouse'],
        content: {
          overview: 'The Fort Cornwallis Lighthouse is a slender octagonal steel structure standing at the northeast bastion of the fort, overlooking the Straits of Malacca. It was erected by the British colonial administration to guide ships navigating the busy strait into the port of Georgetown. The lighthouse is no longer operational as a navigational aid but remains an iconic feature of the fort\'s skyline and a popular photography subject.',
          history: 'The lighthouse was constructed in the late 19th century, making it the second oldest lighthouse in Malaysia. It replaced an earlier wooden beacon that had guided ships into the port since the earliest days of the British settlement. The steel framework design was typical of British colonial engineering of the period, prioritizing durability and low maintenance in the tropical climate.',
          culture: 'The lighthouse is a reminder of Penang\'s historic role as one of the most important ports in the British Empire. At its peak, the port of Georgetown handled more trade than any other port in the region, and the lighthouse was a critical piece of maritime infrastructure. Today it serves as a heritage landmark and a symbol of the island\'s seafaring past.',
          funFacts: 'On clear days, the lighthouse offers a view across the Straits of Malacca to the coast of Kedah on the Malaysian mainland. The lighthouse was decommissioned as a navigational aid in the 20th century when modern electronic navigation made it redundant. It is now lit purely for aesthetic and heritage purposes.'
        }
      },
      {
        name: 'Fort Cornwallis Chapel',
        description: 'The earliest roofed structure in Penang, a tiny military chapel that is the oldest Anglican church in the region.',
        location: '5.4208,100.3441',
        searchPrompts: ['chapel', 'brick_building', 'colonial_chapel', 'anglican_church'],
        content: {
          overview: 'The Fort Cornwallis Chapel is a small, whitewashed brick building tucked within the fort grounds. It is the oldest surviving roofed structure in Penang and the oldest Anglican church in the region. The chapel was built to serve the spiritual needs of the British garrison stationed at the fort and retains much of its original simple colonial architecture — plain walls, arched windows, and a modest altar.',
          history: 'The chapel was constructed in the early 19th century, shortly after the brick fort was completed. It served as the primary place of worship for the British military personnel and their families stationed at Fort Cornwallis. As the civilian population of Georgetown grew, larger churches were built in the town, and the chapel gradually fell out of regular use as a place of worship. It was later preserved as a heritage structure.',
          culture: 'The chapel represents the religious dimension of British colonial life in Penang. The Church of England was the official church of the British Empire, and the establishment of a chapel within the fort was a standard practice at British colonial outposts. The building is now used occasionally for heritage events and small ceremonies.',
          funFacts: 'The chapel is so small that it could accommodate only a few dozen worshippers at a time. Its walls are over a metre thick, providing natural insulation against the tropical heat. The building has survived two world wars, multiple tropical storms, and nearly two centuries of Penang\'s turbulent history largely intact.'
        }
      },
      {
        name: 'Statue of Francis Light',
        description: 'A bronze statue commemorating Captain Francis Light, the founder of the British settlement in Penang, unveiled in 1936.',
        location: '5.4205,100.3439',
        searchPrompts: ['statue', 'bronze_statue', 'francis_light', 'colonial_statue'],
        content: {
          overview: 'The bronze statue of Captain Francis Light stands within the grounds of Fort Cornwallis, near the spot where he is said to have first landed in 1786. The statue depicts Light in full naval uniform, gazing out toward the sea. It was commissioned to mark the 150th anniversary of the founding of the British settlement in Penang and remains one of the most recognizable heritage monuments on the island.',
          history: 'The statue was unveiled on 11 August 1936, exactly 150 years after Light\'s landing. It was commissioned by the Straits Settlements government and sculpted by a British artist. During the Japanese occupation of Penang in World War II, the statue was reportedly moved or hidden to prevent its destruction. It was restored to its current position after the war.',
          culture: 'Francis Light is a complex historical figure in Penang. To the British colonial establishment, he was a heroic founder who opened up a strategically vital port. To later generations of Malaysians, his legacy is more ambiguous — he negotiated the cession of Penang from the Sultan of Kedah under disputed circumstances. The statue is nonetheless a significant heritage landmark and a focal point for commemorations of Penang\'s founding.',
          funFacts: 'Francis Light died in Penang in 1794, just eight years after founding the settlement, from malaria. He is buried at the Protestant Cemetery on Northam Road. The statue is one of only a handful of colonial-era statues still standing in Malaysia. Light\'s son, William Light, went on to found the city of Adelaide in Australia.'
        }
      }
    ]
  },
  {
    name: 'Khoo Kongsi',
    description: 'One of the most magnificent Chinese clan temples in the world, a testament to the wealth and pride of the Khoo clan who settled in Penang from Hokkien province.',
    location: '5.4144,100.3364',
    status: 'published',
    tags: ['Heritage', 'Architecture', 'Culture'],
    content: {
      overview: 'Leong San Tong Khoo Kongsi, commonly known as Khoo Kongsi, is widely regarded as the most magnificent clanhouse in Malaysia and one of the finest examples of southern Chinese clan architecture anywhere in the world. Located in the Cannon Square enclave of the Armenian Street heritage zone, the complex comprises the main clanhouse, a covered stage for opera performances, a row of clan houses, and a large open square. The main hall is an explosion of colour and craftsmanship — every surface is covered in intricate wood carvings, ceramic sculptures, gilded panels, and painted murals depicting scenes from Chinese mythology and history.',
      history: 'The Khoo clan began arriving in Penang from Hokkien province in China in the late 18th century, shortly after the British established the settlement. The first kongsi (clan association) building was erected in the early 19th century. The current main hall was completed in 1906, replacing an earlier structure that was destroyed by fire on the very night of its completion — an event attributed by some to divine punishment for building a structure too grand for mere mortals. The rebuilt version was deliberately made slightly less elaborate than the original, though it remains extraordinarily ornate.',
      culture: 'The kongsi served multiple functions for the Khoo clan: it was a place of ancestral worship, a community centre, a court of justice for settling disputes among clan members, and a welfare organization providing support to newly arrived immigrants. The clan system was the backbone of Chinese immigrant society in Penang, and the kongsi was its physical and spiritual heart. Today Khoo Kongsi is managed by the Khoo clan association and is open to the public as a heritage museum, though it continues to function as an active place of ancestral worship.',
      funFacts: 'The roof of the main hall is decorated with over 200 ceramic figurines depicting characters from Chinese opera and mythology, all hand-crafted in Shantou, China. The wood carvings throughout the complex took teams of master craftsmen years to complete. The kongsi has its own resident deity — Tua Sai Yeah (the Grand Master) — whose birthday is celebrated with elaborate ceremonies each year. The fire that destroyed the original building is still spoken of as a cautionary tale about human hubris.'
    },
    pois: [
      {
        name: 'Leong San Tong Main Hall',
        description: 'The breathtaking main ancestral hall of Khoo Kongsi, covered floor to ceiling in gold leaf carvings, ceramic sculptures, and painted murals.',
        location: '5.4144,100.3364',
        searchPrompts: ['clan_hall', 'gold_carving', 'ceramic_roof', 'ancestral_hall', 'hokkien_architecture'],
        content: {
          overview: 'The main hall of Khoo Kongsi is the centrepiece of the entire complex and one of the most ornately decorated buildings in Southeast Asia. The hall is dedicated to the ancestral worship of the Khoo clan and houses the clan\'s ancestral tablets, deity statues, and ceremonial objects. Every surface — walls, pillars, beams, and roof — is covered in intricate carvings, gilded panels, ceramic figurines, and painted murals. The craftsmanship represents the pinnacle of southern Chinese decorative arts.',
          history: 'The current main hall was completed in 1906 after the original was destroyed by fire. It was built by master craftsmen brought from China specifically for the project, using materials imported from Fujian province. The construction took several years and cost an enormous sum, funded by contributions from Khoo clan members across Southeast Asia.',
          culture: 'The main hall is an active place of worship where clan members come to pray to their ancestors and to the clan deity. Major ceremonies are held here during Chinese New Year, the Qingming Festival (tomb-sweeping), and the birthday of the clan deity. Non-clan visitors are welcome to observe but are asked to be respectful of ongoing religious activities.',
          funFacts: 'The roof of the main hall alone contains over 200 hand-crafted ceramic figurines. The gold leaf used in the carvings throughout the hall is genuine gold. The hall is oriented according to feng shui principles, with its main entrance facing a specific direction to maximize auspicious energy flow.'
        }
      },
      {
        name: 'Cannon Square Opera Stage',
        description: 'An ornate covered stage facing the main hall, used for traditional Chinese opera performances during clan festivals.',
        location: '5.4143,100.3363',
        searchPrompts: ['opera_stage', 'wayang_stage', 'chinese_opera', 'covered_stage'],
        content: {
          overview: 'The opera stage at Khoo Kongsi faces the main ancestral hall across the open square, following the traditional layout of Chinese clan complexes. The stage is used for performances of Hokkien opera (wayang) during major clan festivals and religious celebrations. The performances are offered as entertainment for the deities and ancestors, as well as for the living clan members and their guests.',
          history: 'The tradition of staging opera performances at clan temples and kongsi dates back centuries in southern China. The Khoo Kongsi stage was built as part of the original complex and has been used for performances ever since. During the heyday of the clan system in the 19th and early 20th centuries, opera troupes would be hired from China to perform for weeks at a time during major festivals.',
          culture: 'Chinese opera performances at religious sites are understood as offerings to the deities and ancestors. The stories performed typically draw from Chinese mythology, history, and moral tales. Today performances are less frequent than in the past but are still staged during major clan celebrations, drawing audiences from across the Penang Chinese community.',
          funFacts: 'The stage is designed so that the deities in the main hall have the best view of the performances — the stage faces the hall directly. Traditional Hokkien opera costumes are extraordinarily elaborate, with performers spending hours in makeup and costume before each show.'
        }
      }
    ]
  },
  {
    name: 'Kapitan Keling Mosque',
    description: 'A majestic 19th-century mosque featuring Mughal-style golden domes and a tall minaret, the oldest and most significant mosque in Penang.',
    location: '5.4165,100.3371',
    status: 'published',
    tags: ['Religious', 'Heritage', 'Architecture'],
    content: {
      overview: 'The Kapitan Keling Mosque is the largest and most historically significant mosque in Penang, located in the heart of the UNESCO World Heritage Site of George Town. The mosque is a striking example of Mughal-influenced Islamic architecture, featuring a large central dome flanked by smaller domes, a tall minaret, and an expansive prayer hall capable of accommodating thousands of worshippers. The whitewashed exterior and golden domes make it one of the most visually distinctive buildings in the city.',
      history: 'The mosque was founded in 1801 by the Chulias — Tamil Muslim traders from the Coromandel Coast of India who were among the earliest settlers in Penang. The name "Kapitan Keling" refers to the title given to the head of the Indian Muslim community (Kapitan) and the community itself (Keling, a historical term for South Indians). The original structure was a simple wooden building. It was rebuilt in brick in the early 19th century and has been expanded and renovated multiple times since, with the current structure largely dating from the late 19th and early 20th centuries.',
      culture: 'The Kapitan Keling Mosque remains an active place of worship for the Muslim community of Penang, particularly the Tamil Muslim community. Friday prayers draw large congregations from across the city. The mosque is also a centre for Islamic education and community activities. Non-Muslim visitors are welcome outside of prayer times, provided they dress modestly and remove their shoes. The mosque is a symbol of the Indian Muslim community\'s deep roots in Penang and their contribution to the island\'s multicultural heritage.',
      funFacts: 'The mosque incorporates architectural elements from multiple traditions: Mughal domes, Gothic arched windows, and Moorish decorative details. The minaret is one of the tallest in Penang and can be seen from several blocks away. The mosque was gazetted as a national heritage site in 2012. The Chulias who built the mosque were instrumental in the early economic development of Penang, dominating the textile and money-lending trades.'
    },
    pois: [
      {
        name: 'Main Prayer Hall',
        description: 'The vast, ornately decorated main prayer hall of Kapitan Keling Mosque, capable of accommodating thousands of worshippers.',
        location: '5.4165,100.3371',
        searchPrompts: ['prayer_hall', 'mughal_dome', 'mosque_interior', 'islamic_architecture'],
        content: {
          overview: 'The main prayer hall of Kapitan Keling Mosque is a large, airy space beneath the central dome, decorated with intricate Islamic geometric patterns, calligraphy, and ornamental plasterwork. The hall is oriented toward Mecca and features rows of prayer mats, a carved wooden minbar (pulpit), and a mihrab (prayer niche) indicating the direction of prayer. The hall can accommodate several thousand worshippers during major prayers.',
          history: 'The current prayer hall was largely constructed in the late 19th century during a major renovation of the mosque. The decorative elements reflect the eclectic architectural tastes of the period, blending Mughal, Moorish, and local Malay influences.',
          culture: 'The prayer hall is the spiritual heart of the mosque and the focal point of all religious activities. The Friday khutbah (sermon) delivered from the minbar is an important weekly event for the Muslim community. During Ramadan, the hall is filled to capacity for Tarawih prayers each night.',
          funFacts: 'The dome above the main prayer hall is decorated with verses from the Quran in Arabic calligraphy. The mosque has been visited by numerous heads of state and religious dignitaries over the years. The prayer hall floor is covered with hand-woven carpets donated by various Muslim countries.'
        }
      }
    ]
  },
  {
    name: 'Queen Victoria Memorial Clock Tower',
    description: 'A gleaming white Jubilee clock tower standing 60 feet tall, commissioned to commemorate Queen Victoria\'s Diamond Jubilee in 1897.',
    location: '5.4184,100.3437',
    status: 'published',
    tags: ['Heritage'],
    content: {
      overview: 'The Queen Victoria Memorial Clock Tower is one of the most recognizable landmarks in George Town, standing at the busy intersection of Light Street and Beach Street near the waterfront. The tower is a slender, elegant structure built in the Moorish style, with a clock face on each of its four sides and a pointed spire at the top. It was built to commemorate the Diamond Jubilee of Queen Victoria in 1897 and stands exactly 60 feet tall — one foot for each year of her reign.',
      history: 'The clock tower was commissioned and funded by a wealthy Chinese businessman, Cheah Chen Eok, as a gift to the people of Penang to mark Queen Victoria\'s 60th year on the throne. It was completed in 1897 and has stood at the same location ever since. During World War II, the tower was damaged by Allied bombing raids targeting the Japanese-occupied port. The damage caused the tower to lean slightly to one side, a tilt that is still visible today and has become part of its character.',
      culture: 'The clock tower is a symbol of the complex relationship between the Chinese merchant community and the British colonial administration in Penang. Wealthy Chinese businessmen like Cheah Chen Eok occupied an ambiguous position — they were subjects of the British Crown but maintained their own cultural identity and community institutions. The gift of the clock tower was both a gesture of loyalty to the Crown and a demonstration of the community\'s wealth and civic pride. Today the tower is a beloved landmark and a popular meeting point in the city.',
      funFacts: 'The tower leans slightly as a result of bomb damage during World War II, earning it occasional comparisons to the Leaning Tower of Pisa. The clock mechanism has been replaced and upgraded several times over the decades but the tower itself is largely original. The tower is illuminated at night and is a popular subject for photographers. It is one of the few surviving examples of Moorish-style architecture in Penang.'
    },
    pois: []
  },
  {
    name: 'City Hall & Town Hall Esplanade',
    description: 'Two pristine white Edwardian Baroque buildings overlooking the Padang, representing the pinnacle of British colonial civic architecture in Penang.',
    location: '5.4215,100.3406',
    status: 'published',
    tags: ['Heritage', 'Architecture'],
    content: {
      overview: 'The City Hall and Town Hall of George Town stand side by side on the Esplanade, facing the sea across the Padang (open field). Both buildings are magnificent examples of Edwardian Baroque architecture — symmetrical, imposing, and gleaming white — with colonnaded facades, arched windows, and ornate decorative details. The City Hall, completed in 1903, is the headquarters of the Penang Island City Council. The Town Hall, completed in 1880, is the older of the two and was the centre of colonial civic life. Together they form one of the finest ensembles of colonial architecture in Southeast Asia.',
      history: 'The Town Hall was built in 1880 as a social club and civic centre for the European community of George Town. It hosted balls, concerts, theatrical performances, and official receptions. The City Hall was built in 1903 to house the municipal government as the city grew. Both buildings were designed by British architects and built by local contractors using materials imported from Britain and India. During the Japanese occupation, both buildings were used by the Japanese military administration.',
      culture: 'The Padang in front of the two buildings has been the civic heart of George Town for over two centuries. It was the site of colonial parades, cricket matches, and public gatherings. Today it hosts concerts, festivals, and public events. The buildings themselves are used for official functions, exhibitions, and cultural events. The esplanade promenade along the waterfront is a popular evening gathering spot for residents and tourists alike.',
      funFacts: 'The City Hall clock tower is a prominent feature of the George Town skyline and appears on many postcards and photographs of the city. The Padang in front of the buildings is one of the few remaining open green spaces in the city centre. Both buildings are gazetted as national heritage sites and are part of the UNESCO World Heritage Site of George Town.'
    },
    pois: []
  },
  {
    name: 'St. George\'s Church',
    description: 'The oldest purpose-built Anglican church in Southeast Asia, a neoclassical masterpiece on Farquhar Street.',
    location: '5.4206,100.3392',
    status: 'published',
    tags: ['Religious', 'Heritage'],
    content: {
      overview: 'St. George\'s Church is the oldest Anglican church in Southeast Asia, a serene neoclassical building set in a well-maintained garden on Farquhar Street in the heart of George Town. The church features a majestic Doric-columned portico, a circular domed tower, and a simple but elegant interior with high ceilings and arched windows. The surrounding garden contains several historic graves and memorials, including a memorial to Captain Francis Light, the founder of Penang.',
      history: 'St. George\'s Church was built between 1816 and 1818 by the East India Company, using convict labour. It was designed by Captain Robert Smith, a military engineer who also designed several other notable buildings in Penang. The church was consecrated in 1818 and has been in continuous use ever since. It survived the Japanese occupation of World War II largely intact, though the Japanese used the church grounds for various purposes during the occupation.',
      culture: 'St. George\'s Church has been the spiritual home of the Anglican community in Penang for over two centuries. It continues to hold regular services and is an active parish church. The church is also a significant heritage site and attracts visitors interested in colonial history and architecture. The garden surrounding the church contains memorials to prominent figures in Penang\'s colonial history, making it an open-air museum of sorts.',
      funFacts: 'The memorial to Francis Light in the church garden is one of the few monuments to him in Penang — his actual grave is in the Protestant Cemetery nearby. The church bell was cast in England and shipped to Penang in the early 19th century. The church has been gazetted as a national heritage site and is part of the UNESCO World Heritage Site of George Town. The neoclassical design of the church was influenced by the work of Christopher Wren.'
    },
    pois: []
  },
  // ==========================================
  // NATURE
  // ==========================================
  {
    name: 'Penang Hill',
    description: 'A hill resort comprising a group of peaks rising 833 metres above sea level, offering panoramic views of the island, a cooler climate, and rich biodiversity.',
    location: '5.4239,100.2696',
    status: 'published',
    tags: ['Nature'],
    content: {
      overview: 'Penang Hill, known locally as Bukit Bendera (Flagstaff Hill), is a forested highland retreat rising 833 metres above sea level at its highest point. It offers a dramatic escape from the heat and bustle of George Town below, with temperatures typically 5 to 8 degrees cooler than the city. The hill is home to a rich variety of flora and fauna, including rare orchids, pitcher plants, and numerous bird species. At the summit, visitors find a small village with hotels, restaurants, a mosque, a Hindu temple, and a colonial-era bungalow, as well as sweeping panoramic views across the island, the Straits of Malacca, and the mainland.',
      history: 'Penang Hill was first explored by the British in the 1790s, shortly after the founding of the settlement. Francis Light himself is said to have climbed the hill. The British quickly recognized its value as a cool retreat from the tropical heat and began building bungalows and rest houses on the summit. The funicular railway, opened in 1923, made the hill accessible to a wider public and transformed it into a popular tourist destination. During World War II, the hill was used as a lookout post by both the British and later the Japanese.',
      culture: 'Penang Hill holds a special place in the hearts of Penang residents as a beloved recreational destination and a symbol of the island\'s natural heritage. Families have been making the trip up the hill for generations, whether by funicular or on foot via the jungle trails. The hill is also home to a small permanent community of residents who live in the colonial-era bungalows and newer developments at the summit. The Penang Hill Biosphere Reserve, established in recent years, recognizes the ecological importance of the hill\'s forest cover.',
      funFacts: 'On a clear day, the view from Penang Hill extends to the Thai island of Ko Lipe, over 100 kilometres away. The hill receives significantly more rainfall than the lowlands, making it one of the wettest spots in Penang. The funicular railway at Penang Hill is one of the steepest in the world, with a gradient of up to 1 in 2 on some sections. The hill is home to over 200 species of birds, making it a popular destination for birdwatchers.'
    },
    pois: [
      {
        name: 'Penang Hill Funicular Train',
        description: 'One of the oldest funicular railway systems in the world, carrying visitors from the lower station at Air Itam to the summit of Penang Hill.',
        location: '5.4238,100.2700',
        searchPrompts: ['funicular_train', 'railway_track', 'train_cabin', 'mountain_railway'],
        content: {
          overview: 'The Penang Hill Funicular Railway is a historic mountain railway that has been carrying passengers up the steep slopes of Penang Hill since 1923. The railway consists of two cars that counterbalance each other on a single track, with a passing loop in the middle. The journey takes approximately five minutes and covers a vertical rise of over 700 metres, passing through dense tropical forest and offering glimpses of the city below.',
          history: 'The funicular railway was opened on 21 October 1923, replacing an earlier electric tramway that had operated since 1906. The original tramway was a two-stage system requiring passengers to change cars at an intermediate station. The current single-stage funicular was built by a Swiss engineering firm and uses Swiss-made cars. The railway was modernized in 2010 with new Swiss-built cars and upgraded infrastructure, significantly reducing journey times.',
          culture: 'The funicular railway is an iconic part of the Penang Hill experience and has been a beloved institution for generations of Penang residents. The sight of the red and white cars ascending and descending the steep hillside is one of the most recognizable images of Penang. The railway is also an important piece of engineering heritage, representing the application of Swiss mountain railway technology in a tropical setting.',
          funFacts: 'The funicular railway is one of the steepest in the world, with a maximum gradient of approximately 1 in 2. The two cars are connected by a single cable and counterbalance each other — as one goes up, the other comes down. The modernized railway can carry up to 100 passengers per car. The original 1923 cars were retired in 2010 and one is preserved as a heritage exhibit at the lower station.'
        }
      },
      {
        name: 'Penang Hill Summit Viewpoint',
        description: 'The panoramic viewing platform at the summit of Penang Hill, offering 360-degree views across the island, the Straits of Malacca, and the Malaysian mainland.',
        location: '5.4242,100.2695',
        searchPrompts: ['viewpoint', 'panorama', 'summit', 'observation_deck'],
        content: {
          overview: 'The summit viewpoint at Penang Hill is the primary destination for most visitors, offering breathtaking panoramic views in all directions. On a clear day, the view encompasses the entire island of Penang, the Penang Bridge, the Straits of Malacca, and the mountains of the Malaysian mainland. At night, the city lights of George Town spread out below like a glittering carpet. The viewpoint is equipped with telescopes, information panels, and a café.',
          history: 'The summit of Penang Hill has been a viewpoint since the earliest days of British settlement. The colonial administration maintained a flagstaff at the summit — hence the name Bukit Bendera (Flagstaff Hill) — which was used to signal ships in the strait. The current viewing platform and facilities were developed as part of the 2010 modernization of the hill.',
          culture: 'Watching the sunset from Penang Hill is a beloved tradition for residents and visitors alike. The hill is particularly popular on weekends and public holidays, when families and couples make the trip up to enjoy the views and the cool air. The summit village has a small community of permanent residents who have lived on the hill for generations.',
          funFacts: 'The temperature at the summit is typically 5 to 8 degrees Celsius cooler than at sea level. On exceptionally clear days, the Thai island of Ko Lipe can be seen from the summit, over 100 kilometres away. The hill receives an average of 2,600 mm of rainfall per year, significantly more than the lowlands.'
        }
      },
      {
        name: 'The Habitat Penang Hill',
        description: 'An award-winning eco-tourism attraction on Penang Hill featuring a canopy walkway, guided nature trails, and a treetop walk with panoramic views.',
        location: '5.4245,100.2690',
        searchPrompts: ['canopy_walk', 'treetop', 'jungle_trail', 'nature_walk', 'habitat'],
        content: {
          overview: 'The Habitat is a nature attraction on the upper slopes of Penang Hill that offers visitors an immersive experience in the tropical rainforest. Its centrepiece is the Curtis Crest Treetop Walk, a 1.6-kilometre elevated walkway through the forest canopy that culminates in a 360-degree viewing platform at the highest accessible point on the hill. The Habitat also offers guided nature walks, night walks, and educational programmes focused on the biodiversity of the Penang Hill forest.',
          history: 'The Habitat was developed in the 2010s as part of efforts to promote eco-tourism on Penang Hill and raise awareness of the hill\'s ecological importance. It was designed to provide a structured nature experience while minimizing impact on the forest. The attraction has won several eco-tourism awards and has been recognized as a model for sustainable tourism development.',
          culture: 'The Habitat plays an important role in environmental education, offering school programmes and guided tours that introduce visitors to the biodiversity of the tropical rainforest. It has helped to shift the focus of Penang Hill tourism from purely recreational to also educational and conservation-oriented.',
          funFacts: 'The Curtis Crest Treetop Walk reaches a height of 1,648 feet above sea level, making it the highest publicly accessible point on Penang Hill. The forest on Penang Hill is estimated to be over 130 million years old, making it one of the oldest rainforests in the world. The Habitat has recorded over 200 species of birds within its boundaries.'
        }
      }
    ]
  },
  {
    name: 'Penang National Park',
    description: 'The smallest national park in the world by area, covering pristine beaches, jungle trails, a meromictic lake, and the historic Muka Head Lighthouse.',
    location: '5.4612,100.2014',
    status: 'published',
    tags: ['Nature'],
    content: {
      overview: 'Penang National Park, known in Malay as Taman Negara Pulau Pinang, is located at the northwestern tip of Penang Island and covers approximately 2,562 hectares of protected forest, coastline, and marine environment. Despite being the smallest national park in the world by area, it contains remarkable biodiversity, including rare sea turtles, hornbills, dusky leaf monkeys, and a wide variety of plant species. The park is accessible only on foot or by boat, which has helped preserve its pristine character. Key attractions include Monkey Beach, Turtle Beach, the meromictic Meromictic Lake, and the Muka Head Lighthouse.',
      history: 'The area was gazetted as a national park in 2003, making it one of the newer protected areas in Malaysia. However, the forest itself is ancient, and the coastline has been used by fishermen and traders for centuries. The Muka Head Lighthouse, built by the British in 1883, is the oldest structure in the park and served as a critical navigational aid for ships entering the Straits of Malacca.',
      culture: 'The national park is a popular destination for hikers, nature lovers, and beach-goers from across Penang and beyond. The trails through the park offer a genuine wilderness experience within easy reach of the city. The park is also an important site for sea turtle conservation — both green turtles and leatherback turtles nest on the beaches within the park, and conservation volunteers monitor the nests during nesting season.',
      funFacts: 'The Meromictic Lake within the park is one of only a handful of such lakes in the world — its layers of fresh and salt water never mix, creating distinct ecosystems at different depths. The park is home to the rare and endangered Malayan tapir. Monkey Beach gets its name from the large population of long-tailed macaques that inhabit the area and are known for stealing food from visitors.'
    },
    pois: [
      {
        name: 'Monkey Beach (Pantai Kerachut)',
        description: 'A pristine white-sand beach accessible only by jungle trail or boat, famous for its resident macaques and sea turtle nesting.',
        location: '5.4720,100.2050',
        searchPrompts: ['beach', 'white_sand', 'jungle_trail', 'macaque', 'turtle_beach'],
        content: {
          overview: 'Monkey Beach, officially known as Pantai Kerachut, is one of the most beautiful and unspoiled beaches in Penang. The beach is a long crescent of white sand backed by dense jungle, accessible only via a 3-4 hour jungle trek or a short boat ride from Teluk Bahang. The beach gets its popular name from the large troops of long-tailed macaques that inhabit the surrounding forest and frequently come down to the beach to interact with visitors.',
          history: 'The beach has been known to local fishermen for centuries but remained largely inaccessible to the general public until the development of the national park trail system. It became a popular hiking destination in the 1990s and 2000s as eco-tourism grew in Penang.',
          culture: 'Monkey Beach is a rite of passage for many Penang residents, who make the jungle trek at least once. The hike through the national park forest is considered one of the best nature walks in Penang, passing through diverse habitats and offering opportunities to spot wildlife. The beach itself is a popular camping spot, with basic facilities available.',
          funFacts: 'The macaques at Monkey Beach have become so accustomed to human visitors that they will boldly approach and attempt to steal food. Visitors are advised not to feed them. Sea turtles nest on the beach between May and September, and conservation volunteers monitor the nests to protect the eggs from predators.'
        }
      },
      {
        name: 'Muka Head Lighthouse',
        description: 'A historic British-built lighthouse from 1883 standing on a rocky headland at the northwestern tip of Penang Island.',
        location: '5.4750,100.2000',
        searchPrompts: ['lighthouse', 'colonial_lighthouse', 'headland', 'muka_head'],
        content: {
          overview: 'The Muka Head Lighthouse stands on a rocky promontory at the very northwestern tip of Penang Island, marking the entrance to the Straits of Malacca. Built by the British in 1883, it is one of the oldest lighthouses in Malaysia and remains operational today. The lighthouse is accessible via a steep trail from Monkey Beach and offers spectacular views of the open sea and the surrounding coastline.',
          history: 'The lighthouse was built in 1883 by the British colonial administration to guide ships navigating the northern approach to the Straits of Malacca. The location was chosen for its prominence — the headland is visible from far out to sea. The lighthouse has been in continuous operation since its construction, though the original oil lamp has been replaced with modern electric lighting.',
          culture: 'The lighthouse is a symbol of Penang\'s historic role as a maritime hub. For over a century, it has guided ships safely through one of the busiest shipping lanes in the world. Today it is a heritage landmark and a popular destination for hikers who make the trek through the national park to reach it.',
          funFacts: 'The Muka Head Lighthouse is still operational and is maintained by the Malaysian Maritime Department. The view from the lighthouse on a clear day extends to the Thai islands to the north. The lighthouse keeper\'s quarters are still occupied by the lighthouse keeper and their family.'
        }
      }
    ]
  },
  {
    name: 'Entopia by Penang Butterfly Farm',
    description: 'The world\'s first tropical butterfly farming initiative, now a massive living sanctuary housing thousands of free-flying butterflies and fascinating insects.',
    location: '5.4468,100.2155',
    status: 'published',
    tags: ['Nature'],
    content: {
      overview: 'Entopia by Penang Butterfly Farm is a unique nature attraction on the northwestern coast of Penang Island, near Teluk Bahang. The attraction comprises two main areas: Natureland, a large greenhouse where thousands of free-flying butterflies of over 120 species flutter among tropical plants and waterfalls; and Cocoon, an indoor insectarium housing a remarkable collection of insects, spiders, scorpions, and other invertebrates from around the world. The attraction is both a tourist destination and a working butterfly farm that breeds and exports butterflies for research and conservation purposes.',
      history: 'The Penang Butterfly Farm was founded in 1986 by David Goh, a pioneer in butterfly farming who developed techniques for breeding tropical butterflies in captivity. It was the first butterfly farm of its kind in the world and became a model for similar attractions across Asia. In 2015, the farm was completely redesigned and relaunched as Entopia, with a significantly expanded and upgraded facility.',
      culture: 'Entopia plays an important role in environmental education, offering school programmes and guided tours that introduce visitors to the world of insects and the importance of biodiversity. The butterfly farm has contributed to conservation efforts by breeding and releasing endangered butterfly species into the wild. It is also a popular venue for photography, with the free-flying butterflies providing extraordinary opportunities for close-up nature photography.',
      funFacts: 'The Natureland greenhouse at Entopia is home to over 15,000 free-flying butterflies at any given time. The farm breeds over 120 species of butterflies, some of which have wingspans of over 20 centimetres. The Rajah Brooke\'s Birdwing, Malaysia\'s national butterfly, can be seen at Entopia. The farm exports butterfly pupae to museums and attractions around the world.'
    },
    pois: []
  },
  {
    name: 'Penang Botanic Gardens',
    description: 'A 30-hectare colonial-era botanical garden established in 1884, affectionately known as the Waterfall Gardens, home to diverse tropical flora and playful macaques.',
    location: '5.4385,100.2894',
    status: 'published',
    tags: ['Nature'],
    content: {
      overview: 'The Penang Botanic Gardens, established in 1884, is one of the oldest and most beautiful botanical gardens in Southeast Asia. Spread across 30 hectares at the foot of Penang Hill, the gardens are home to a remarkable collection of tropical plants, including towering rain trees, rare orchids, ferns, palms, and flowering shrubs. The gardens are also home to a large population of long-tailed macaques, who roam freely and have become as much an attraction as the plants themselves. A stream runs through the gardens, and the sound of running water gives the gardens their popular nickname — the Waterfall Gardens.',
      history: 'The Penang Botanic Gardens were established in 1884 by the British colonial administration under the direction of Charles Curtis, the first curator of the gardens. Curtis developed the gardens as both a scientific institution for the study of tropical plants and a recreational space for the residents of George Town. The gardens played an important role in the introduction and cultivation of economically important plants, including rubber, which was first cultivated in Malaya from seeds brought through the Kew Gardens network.',
      culture: 'The Botanic Gardens are one of the most beloved public spaces in Penang, used daily by residents for morning exercise, family outings, and quiet relaxation. The gardens are particularly busy on weekends and public holidays, when families picnic on the lawns and children feed the macaques. The gardens also host occasional cultural events, outdoor concerts, and horticultural exhibitions.',
      funFacts: 'The Penang Botanic Gardens contain over 250 species of trees, many of which are labelled with their scientific and common names. The macaques in the gardens are so accustomed to humans that they will approach visitors looking for food — visitors are advised not to feed them as it disrupts their natural behaviour. The gardens contain several trees that are over 100 years old. The stream running through the gardens originates from the slopes of Penang Hill above.'
    },
    pois: []
  },
  // ==========================================
  // FOOD
  // ==========================================
  {
    name: 'Gurney Drive Hawker Centre',
    description: 'One of the most famous hawker food streets in Asia, offering a dizzying array of authentic Penang street food along the seafront promenade.',
    location: '5.4402,100.3129',
    status: 'published',
    tags: ['Food'],
    content: {
      overview: 'Gurney Drive Hawker Centre is arguably the most famous street food destination in Penang and one of the most celebrated hawker centres in all of Asia. Located along the Gurney Drive seafront promenade, the centre comes alive each evening as dozens of hawker stalls set up their woks, grills, and steamers, filling the air with the intoxicating aromas of Penang\'s legendary cuisine. Visitors can sample virtually the entire canon of Penang street food in a single visit: char kway teow, assam laksa, hokkien mee, rojak, cendol, and much more. The centre is popular with both locals and tourists and is often cited as the best introduction to Penang food culture.',
      history: 'Hawker food has been a part of Penang\'s culinary culture since the earliest days of the settlement, when itinerant food vendors would push their carts through the streets selling cooked food to workers and residents. The Gurney Drive seafront became a popular gathering place in the mid-20th century, and hawker stalls gradually established themselves along the promenade. The current hawker centre was formalized and organized by the local authorities in the latter half of the 20th century.',
      culture: 'Hawker food is central to Penang\'s identity and cultural life. The hawker centre is a democratic space where people of all backgrounds — different races, religions, and income levels — sit side by side and share the same food. Many of the stalls at Gurney Drive have been operated by the same families for two or three generations, and the recipes have been passed down with great care. Eating at a hawker centre is not just about the food — it is a social ritual, a way of connecting with the community and with the island\'s multicultural heritage.',
      funFacts: 'Penang\'s hawker food culture was inscribed on the UNESCO Representative List of the Intangible Cultural Heritage of Humanity in 2022. The char kway teow at Gurney Drive is considered by many food critics to be among the best in the world. Some of the most popular stalls at Gurney Drive have waiting times of 30 minutes or more during peak hours. The hawker centre is busiest between 7pm and 10pm on weekends.'
    },
    pois: [
      {
        name: 'Char Kway Teow Stall',
        description: 'The iconic wok-fried flat rice noodle dish, cooked over high heat with prawns, cockles, eggs, and bean sprouts — the signature dish of Penang.',
        location: '5.4402,100.3130',
        searchPrompts: ['char_kway_teow', 'wok', 'noodles', 'hawker_stall'],
        content: {
          overview: 'Char Kway Teow is the dish most closely associated with Penang and is considered by many to be the island\'s signature street food. The dish consists of flat rice noodles stir-fried over extremely high heat in a wok with prawns, cockles, Chinese sausage, eggs, bean sprouts, and chives, seasoned with soy sauce, chilli paste, and shrimp paste. The key to great char kway teow is "wok hei" — the smoky, slightly charred flavour imparted by the intense heat of the wok.',
          history: 'Char kway teow originated among the Chinese immigrant community in Penang in the early 20th century. It was originally a cheap, filling meal for labourers and dock workers, made from inexpensive ingredients. Over time it evolved into a refined dish with specific techniques and high-quality ingredients, and it became a source of great local pride.',
          culture: 'The best char kway teow in Penang is still cooked by individual hawkers using traditional techniques — each portion is cooked separately in a single wok over a charcoal or gas flame. The skill of the hawker in managing the heat and timing is crucial to the quality of the dish. Many of the most celebrated char kway teow hawkers in Penang are elderly and have been cooking the dish for decades.',
          funFacts: 'The cockles used in Penang char kway teow are a distinctive feature not found in versions of the dish from other parts of Malaysia. The dish is traditionally cooked in pork lard, which contributes significantly to its flavour. Some of the most famous char kway teow hawkers in Penang have been featured in international food media and have attracted visitors from around the world.'
        }
      },
      {
        name: 'Assam Laksa Stall',
        description: 'A tangy, spicy fish-based noodle soup that is one of the most distinctive and beloved dishes in Penang cuisine.',
        location: '5.4401,100.3129',
        searchPrompts: ['assam_laksa', 'noodle_soup', 'fish_broth', 'hawker_stall'],
        content: {
          overview: 'Penang Assam Laksa is a sour and spicy noodle soup made with a rich broth of flaked mackerel, tamarind, lemongrass, galangal, and chilli, served over thick rice noodles and garnished with cucumber, pineapple, onion, mint, and a dollop of shrimp paste. It is one of the most distinctive dishes in Malaysian cuisine and was ranked by CNN as one of the 50 most delicious foods in the world.',
          history: 'Assam laksa is believed to have originated in Penang among the Peranakan (Straits Chinese) community, who blended Chinese noodle-making traditions with Malay spices and ingredients. The use of tamarind (assam in Malay) as the souring agent is a distinctly Malay influence. The dish has been a staple of Penang street food for at least a century.',
          culture: 'Assam laksa is a dish that divides opinion — its strong, pungent flavours are beloved by those who grew up with it but can be challenging for first-time tasters. It is considered a test of one\'s appreciation for Penang food culture. The dish is particularly popular during the hot season, when its sour and spicy flavours are said to be refreshing.',
          funFacts: 'CNN Travel ranked Penang Assam Laksa as one of the 50 most delicious foods in the world. The shrimp paste (hae ko) used as a garnish is a thick, sweet, pungent condiment that is unique to Penang laksa. The dish is traditionally eaten with a spoon and chopsticks simultaneously.'
        }
      }
    ]
  },
  {
    name: 'Chulia Street Night Market',
    description: 'A classic backpacker street in the heart of George Town that comes alive at night with legendary hawker carts and a vibrant street atmosphere.',
    location: '5.4187,100.3361',
    status: 'published',
    tags: ['Food'],
    content: {
      overview: 'Chulia Street is one of the most famous streets in George Town, running through the heart of the heritage zone and lined with budget guesthouses, cafes, bars, and hawker stalls. By night, the street transforms into a lively food destination as hawker carts set up along the roadside, serving classic Penang dishes to a mix of backpackers, tourists, and locals. The street is particularly famous for its wanton mee, char kway teow, and fresh apom (Indian pancakes).',
      history: 'Chulia Street takes its name from the Chulia community — Tamil Muslim traders from South India who were among the earliest settlers in Penang. The street was historically the commercial and residential heart of the Indian Muslim community. Over time it became a mixed-use street catering to the broader population, and in the late 20th century it became a hub for budget travellers and backpackers.',
      culture: 'Chulia Street represents the multicultural character of George Town at its most vivid. On a single block, you might find a Chinese temple, a Muslim prayer hall, an Indian textile shop, and a Western-style café. The night market atmosphere is informal and convivial, with diners sitting at plastic tables on the pavement and hawkers calling out their specialties. It is one of the best places in Penang to experience the city\'s street food culture in an authentic setting.',
      funFacts: 'Chulia Street is one of the oldest streets in George Town, dating back to the earliest days of the British settlement. The street is named after the Chulias, who were instrumental in the early economic development of Penang. The backpacker guesthouses on Chulia Street are among the cheapest accommodation options in Penang and have been hosting budget travellers for decades.'
    },
    pois: []
  },
  {
    name: 'Penang Road Famous Teochew Chendul',
    description: 'A legendary roadside stall serving icy bowls of chendul and rojak for decades, one of the most iconic dessert destinations in Penang.',
    location: '5.4172,100.3307',
    status: 'published',
    tags: ['Food'],
    content: {
      overview: 'The Penang Road Famous Teochew Chendul stall is one of the most iconic food destinations in George Town, drawing long queues of locals and tourists alike for its refreshing bowls of chendul. Chendul is a traditional Southeast Asian dessert consisting of shaved ice, green pandan-flavoured jelly noodles, red beans, and coconut milk, drizzled with dark palm sugar syrup. The stall also serves rojak — a spicy, tangy salad of fruits and vegetables tossed in a thick shrimp paste dressing.',
      history: 'The stall has been operating on Penang Road for several decades and has become a Penang institution. It was established by a Teochew Chinese family and has been passed down through generations. The stall\'s fame spread through word of mouth and later through food media coverage, and it is now one of the most visited food stalls in Penang.',
      culture: 'Chendul is a beloved dessert across Malaysia and Singapore, but Penang\'s version is considered by many to be the definitive version. The combination of coconut milk, palm sugar, and pandan jelly is a classic of Southeast Asian dessert-making, and the quality of each ingredient is crucial to the final result. Eating chendul on a hot Penang afternoon is a quintessential local experience.',
      funFacts: 'The queue at the Penang Road Famous Teochew Chendul stall can stretch for 30 minutes or more during peak hours. The stall has been featured in numerous international food publications and television programmes. The palm sugar used in the chendul is sourced from traditional producers in the region. The stall operates from a simple roadside setup with no air conditioning — part of its authentic charm.'
    },
    pois: []
  },
  {
    name: 'Line Clear Nasi Kandar',
    description: 'A historic alleyway eatery operating since 1930, serving profoundly flavorful rice and curries that define the Penang Nasi Kandar tradition.',
    location: '5.4189,100.3331',
    status: 'published',
    tags: ['Food'],
    content: {
      overview: 'Line Clear is arguably the most famous Nasi Kandar restaurant in Penang, operating from a narrow alleyway off Penang Road since 1930. Nasi Kandar is a Penang institution — a meal of steamed rice served with a selection of curries, gravies, and side dishes, with the distinctive "banjir" (flood) style of service where multiple curries are poured over the rice simultaneously. Line Clear is open 24 hours a day and is perpetually busy, serving a loyal clientele of locals, tourists, and late-night revellers.',
      history: 'Nasi Kandar originated in Penang among the Tamil Muslim community in the 19th century. The name comes from the "kandar" — a shoulder pole used by itinerant food vendors to carry their pots of rice and curry through the streets. Line Clear was established in 1930 and has been operating continuously ever since, making it one of the oldest food establishments in Penang.',
      culture: 'Nasi Kandar is a cornerstone of Penang\'s food culture and a symbol of the Tamil Muslim community\'s contribution to the island\'s culinary heritage. The "banjir" style of serving — where the server pours multiple curries over the rice in a single dramatic gesture — is unique to Penang and is considered an art form by aficionados. Line Clear is a democratic space where people of all backgrounds eat side by side, united by their love of good food.',
      funFacts: 'Line Clear is open 24 hours a day, 365 days a year, and is one of the few places in Penang where you can get a full meal at 3am. The restaurant has no formal seating — diners eat standing at counters or perched on stools in the narrow alleyway. The curries at Line Clear are made fresh daily using recipes that have been refined over 90 years of operation.'
    },
    pois: []
  },
  // ==========================================
  // ART
  // ==========================================
  {
    name: 'Ernest Zacharevic Street Art',
    description: 'A collection of interactive murals scattered across George Town that sparked a global street art trend and transformed the city into an open-air gallery.',
    location: '5.4146,100.3380',
    status: 'published',
    tags: ['Art', 'Heritage'],
    content: {
      overview: 'The street art murals created by Lithuanian artist Ernest Zacharevic for the 2012 George Town Festival are among the most photographed artworks in Southeast Asia. Zacharevic\'s distinctive style combines painted murals with real-world objects — a bicycle, a motorcycle, a swing — to create interactive scenes that invite viewers to become part of the artwork. The murals are scattered across the heritage zone of George Town, turning the city\'s streets into an open-air gallery and encouraging visitors to explore the historic neighbourhoods on foot.',
      history: 'Ernest Zacharevic was commissioned by the George Town Festival in 2012 to create a series of murals celebrating the heritage and community of George Town. The murals were an immediate sensation, attracting visitors from across Malaysia and beyond and generating enormous media coverage. The success of Zacharevic\'s murals inspired a wave of street art commissions across George Town, transforming the city into one of the most vibrant street art destinations in Asia.',
      culture: 'The street art murals have become an integral part of George Town\'s cultural identity and a major driver of tourism. They have also sparked important conversations about the relationship between art, heritage, and urban space. Some residents and heritage advocates have expressed concern that the focus on street art has overshadowed the deeper cultural heritage of the city, while others argue that the murals have brought new life and attention to the historic neighbourhoods.',
      funFacts: 'The "Children on Bicycle" mural on Armenian Street is the most photographed artwork in Malaysia. Zacharevic\'s murals have been replicated and imitated in cities around the world. The original murals are maintained and restored periodically to keep them in good condition. Several of the murals have been damaged or altered over the years, and some have been lost entirely.'
    },
    pois: [
      {
        name: 'Children on Bicycle Mural',
        description: 'The most iconic of Zacharevic\'s murals — two children riding a real bicycle painted onto the wall of a heritage shophouse on Armenian Street.',
        location: '5.4146,100.3380',
        searchPrompts: ['mural', 'bicycle', 'street_art', 'zacharevic', 'armenian_street'],
        content: {
          overview: 'The "Children on Bicycle" mural on Armenian Street is the most famous and most photographed artwork in Penang, and arguably in all of Malaysia. The mural depicts two children — a boy and a girl — riding a bicycle, with the boy steering and the girl sitting behind him with her arms outstretched. The bicycle in the mural is a real bicycle attached to the wall, blurring the boundary between the painted image and the physical world.',
          history: 'The mural was created by Ernest Zacharevic in 2012 as part of his commission for the George Town Festival. It was painted on the wall of a heritage shophouse on Armenian Street, one of the most historic streets in George Town. The mural became an immediate sensation and is credited with sparking the street art tourism boom in Penang.',
          culture: 'The mural has become a symbol of George Town\'s creative renaissance and its emergence as a cultural tourism destination. It is a mandatory stop on any tour of George Town\'s street art and is featured on countless postcards, guidebooks, and social media posts. The mural has also inspired numerous imitations and homages around the world.',
          funFacts: 'The bicycle in the mural is a real bicycle that has been replaced several times as the original wore out. The mural is so popular that there is often a queue of visitors waiting to be photographed with it. The wall on which the mural is painted is part of a heritage shophouse that dates back to the 19th century.'
        }
      },
      {
        name: 'Boy on Motorcycle Mural',
        description: 'A mural depicting a boy riding a real motorcycle, located on Ah Quee Street in the heart of the heritage zone.',
        location: '5.4150,100.3375',
        searchPrompts: ['mural', 'motorcycle', 'street_art', 'zacharevic'],
        content: {
          overview: 'The "Boy on Motorcycle" mural is one of Zacharevic\'s most popular works in George Town, depicting a young boy astride a real motorcycle that is attached to the wall. The mural captures a moment of childhood freedom and adventure, and like all of Zacharevic\'s works, it invites viewers to interact with it — sitting on the motorcycle and posing for photographs.',
          history: 'Created in 2012 as part of the same George Town Festival commission as the other Zacharevic murals, the Boy on Motorcycle mural was painted on a wall in the Ah Quee Street area of the heritage zone.',
          culture: 'The interactive nature of Zacharevic\'s murals — the use of real objects that viewers can touch and interact with — was a key innovation that set his work apart from conventional street art. The murals transformed passive viewers into active participants, creating a new kind of public art experience.',
          funFacts: 'The motorcycle in the mural is a real vintage motorcycle that has been maintained and repainted several times. The mural is located in a relatively quiet part of the heritage zone, making it a pleasant discovery for visitors who venture off the main tourist trail.'
        }
      }
    ]
  },
  {
    name: 'Hin Bus Depot',
    description: 'A ruined colonial-era bus depot transformed into a vibrant community art centre with galleries, studios, markets, and independent cafes.',
    location: '5.4124,100.3283',
    status: 'published',
    tags: ['Art'],
    content: {
      overview: 'Hin Bus Depot is one of the most creative and dynamic spaces in Penang, occupying a large former bus depot in the Macallum Street area of George Town. The complex comprises a series of repurposed industrial buildings and open courtyards that house art galleries, artist studios, a weekend artisan market, independent cafes and restaurants, and a variety of creative businesses. The space is known for its eclectic, bohemian atmosphere and its role as a hub for Penang\'s contemporary art scene.',
      history: 'The site was originally a bus depot operated by the Hin Bus Company, one of the early public transport operators in Penang. The depot fell into disuse as the bus company ceased operations, and the buildings were left to decay for many years. In the 2010s, the site was redeveloped as a creative hub, with the original industrial structures preserved and repurposed. The development was part of a broader trend of adaptive reuse of heritage industrial buildings in George Town.',
      culture: 'Hin Bus Depot has become the epicentre of contemporary art and creative culture in Penang. It hosts regular art exhibitions, live music performances, film screenings, and cultural events. The weekend artisan market is a popular destination for locals and tourists looking for handmade crafts, vintage items, and local food products. The space has also become a popular venue for weddings, corporate events, and private functions.',
      funFacts: 'The original bus depot structures, including the maintenance pits and overhead cranes, have been preserved as part of the aesthetic of the space. The weekend market at Hin Bus Depot is one of the best places in Penang to find locally made crafts and artisanal food products. The space has been featured in numerous international travel publications as one of the must-visit destinations in Penang.'
    },
    pois: []
  },
  // ==========================================
  // SHOPPING
  // ==========================================
  {
    name: 'Queensbay Mall',
    description: 'The largest shopping mall in Penang, located on the waterfront of Bayan Lepas with sweeping views of the Straits of Malacca.',
    location: '5.3331,100.3068',
    status: 'published',
    tags: ['Shopping'],
    content: {
      overview: 'Queensbay Mall is the largest and most comprehensive shopping mall in Penang, located on the waterfront of Bayan Lepas in the southern part of the island. The mall offers over 300 retail outlets across multiple floors, including international fashion brands, electronics stores, a large supermarket, a food court, numerous restaurants, and a multiplex cinema. The mall\'s waterfront location provides views of the Straits of Malacca from its upper floors and outdoor areas.',
      history: 'Queensbay Mall opened in 2006 and was developed as part of a larger mixed-use waterfront development in Bayan Lepas. It was designed to serve the growing population of the southern part of Penang Island, particularly the residents of the Bayan Lepas industrial zone and the surrounding residential areas. The mall has been expanded and renovated several times since its opening.',
      culture: 'Shopping malls are an important part of everyday life in Malaysia, serving not just as retail destinations but as social spaces where families gather, teenagers hang out, and communities come together. Queensbay Mall is particularly popular with families from the southern part of the island and with workers from the nearby industrial zone. The mall\'s food court and restaurants offer a wide range of Malaysian and international cuisine.',
      funFacts: 'Queensbay Mall has a total retail area of over 1 million square feet, making it one of the largest malls in Malaysia. The mall\'s waterfront location makes it one of the few shopping malls in Malaysia with sea views. The mall is connected to a large outdoor waterfront promenade that is popular for evening walks.'
    },
    pois: []
  },
  {
    name: 'Chowrasta Market',
    description: 'A historic wet market famous for local preserves, nutmeg products, dried fruits, and a labyrinthine upper floor of second-hand bookstores.',
    location: '5.4170,100.3323',
    status: 'published',
    tags: ['Shopping', 'Heritage'],
    content: {
      overview: 'Chowrasta Market is one of the oldest and most characterful markets in George Town, located on Penang Road in the heart of the heritage zone. The ground floor is a traditional wet market selling fresh produce, meat, fish, and a remarkable variety of Penang\'s famous preserved foods — pickled fruits, nutmeg products, dried seafood, and local condiments. The upper floor is home to a sprawling collection of second-hand bookstores, selling everything from vintage Penguin paperbacks to old Malay magazines and rare local publications.',
      history: 'Chowrasta Market has been operating on Penang Road for well over a century, making it one of the oldest continuously operating markets in Penang. The market takes its name from the Chowrasta area of George Town. The second-hand bookstores on the upper floor developed organically over the decades as book dealers established themselves in the market.',
      culture: 'Chowrasta Market is a living piece of Penang\'s commercial heritage. The preserved food stalls on the ground floor sell products that have been made in Penang for generations — nutmeg jam, pickled mango, dried cuttlefish, and the famous Penang prawn paste (belacan). These products make popular souvenirs for visitors. The second-hand bookstores on the upper floor are a treasure trove for book lovers, with an eclectic and ever-changing stock.',
      funFacts: 'Chowrasta Market is one of the best places in Penang to buy local preserved foods and condiments as souvenirs. The nutmeg products sold at the market are made from Penang nutmeg, which has been cultivated on the island since the early days of the British settlement. The second-hand bookstores on the upper floor are said to contain some rare and out-of-print titles that cannot be found anywhere else.'
    },
    pois: []
  },
  // ==========================================
  // RELIGIOUS
  // ==========================================
  {
    name: 'Sri Mahamariamman Temple',
    description: 'The oldest Hindu temple in Penang, adorned with an extraordinarily intricate gopuram tower covered in hundreds of hand-sculpted deity figures.',
    location: '5.4168,100.3388',
    status: 'published',
    tags: ['Religious', 'Heritage'],
    content: {
      overview: 'The Sri Mahamariamman Temple is the oldest Hindu temple in Penang, located in the Little India district of George Town. The temple is dedicated to the goddess Mariamman, a form of the Divine Mother particularly venerated by Tamil Hindus for her powers of healing and protection. The temple\'s most striking feature is its towering gopuram (entrance tower), which is covered in hundreds of hand-sculpted and brightly painted figures of deities, mythological creatures, and celestial beings. The gopuram is a masterpiece of Dravidian temple architecture and one of the most visually spectacular structures in George Town.',
      history: 'The Sri Mahamariamman Temple was established in the early 19th century by Tamil Hindu immigrants who came to Penang as traders, labourers, and professionals. The original temple was a simple structure, but it was rebuilt and expanded over the decades as the Tamil community grew and prospered. The current gopuram was constructed in the 20th century and required years of work by master sculptors brought from Tamil Nadu in India.',
      culture: 'The temple is the spiritual heart of the Tamil Hindu community in Penang and an active place of worship. Daily prayers are conducted by the temple priests, and the temple hosts numerous festivals throughout the year, the most important of which is Thaipusam — a spectacular festival during which devotees carry elaborate kavadi (burden structures) in fulfilment of vows to the deity. The Thaipusam procession from the Sri Mahamariamman Temple is one of the most dramatic religious events in Penang.',
      funFacts: 'The gopuram of the Sri Mahamariamman Temple contains over 300 individual sculpted figures. The temple is one of the few Hindu temples in Malaysia that is open to visitors of all faiths, provided they remove their shoes and dress modestly. The Thaipusam festival at the temple draws tens of thousands of devotees and spectators each year. The temple is gazetted as a national heritage site.'
    },
    pois: []
  },
  {
    name: 'Wat Chayamangkalaram',
    description: 'A Thai Buddhist temple famous for housing one of the longest Reclining Buddha statues in the world, a 33-metre gold-plated masterpiece.',
    location: '5.4315,100.3142',
    status: 'published',
    tags: ['Religious', 'Heritage'],
    content: {
      overview: 'Wat Chayamangkalaram is a Thai Buddhist temple located on Lorong Burma in the Pulau Tikus area of Penang. The temple is famous for its magnificent Reclining Buddha statue, which at 33 metres in length is one of the longest in the world. The statue is gold-plated and depicts the Buddha in the parinirvana position — lying on his right side with his head resting on his hand — symbolizing the moment of the Buddha\'s final passing into nirvana. The temple complex also includes a main prayer hall, a crematorium, and a garden with smaller shrines and statues.',
      history: 'The land on which the temple stands was granted to the Thai Buddhist community by the British colonial government in 1845. The original temple was a modest wooden structure. The current temple buildings and the Reclining Buddha statue were constructed in the 20th century, with the statue completed in 1958. The temple has been renovated and expanded several times since then.',
      culture: 'Wat Chayamangkalaram is an active place of worship for the Thai Buddhist community in Penang and attracts devotees from across Malaysia and Thailand. The temple is particularly busy during Thai Buddhist festivals such as Songkran (Thai New Year) and Visakha Bucha (Buddha\'s birthday). Non-Buddhist visitors are welcome to visit the temple, provided they dress modestly and behave respectfully.',
      funFacts: 'The Reclining Buddha at Wat Chayamangkalaram is the third longest in the world. The statue is hollow, and the interior contains the ashes of deceased members of the Thai Buddhist community. The temple is located directly across the road from the Dhammikarama Burmese Temple, making it possible to visit both temples in a single outing. The temple\'s name means "Temple of the Auspicious Garden" in Thai.'
    },
    pois: []
  },
  {
    name: 'Dhammikarama Burmese Temple',
    description: 'The oldest Burmese Buddhist temple in Malaysia, filled with golden stupas, vibrant murals, and mythical chinthe guardian lions.',
    location: '5.4316,100.3137',
    status: 'published',
    tags: ['Religious', 'Heritage'],
    content: {
      overview: 'The Dhammikarama Burmese Temple is the oldest Burmese Buddhist temple in Malaysia, located on Lorong Burma directly across the road from the Thai Wat Chayamangkalaram temple. The temple complex is a serene and beautifully maintained space featuring a main prayer hall, several golden stupas, a large standing Buddha statue, and a garden with ponds and smaller shrines. The entrance to the temple is guarded by a pair of large chinthe — mythical half-lion, half-dragon creatures that are a distinctive feature of Burmese Buddhist architecture.',
      history: 'The Dhammikarama Burmese Temple was established in 1803, making it one of the oldest Buddhist temples in Penang. It was founded by the Burmese Buddhist community that settled in Penang in the early years of the British settlement. The temple has been expanded and renovated numerous times over its two-century history, with the current buildings largely dating from the 20th century.',
      culture: 'The temple is an active place of worship for the Burmese Buddhist community in Penang and attracts devotees from across Malaysia and Myanmar. The temple hosts regular prayer sessions, meditation retreats, and Buddhist festivals. It is also a popular destination for tourists interested in Burmese culture and architecture. The temple\'s peaceful garden is a welcome respite from the bustle of the city.',
      funFacts: 'The Dhammikarama Burmese Temple is over 220 years old, making it one of the oldest religious buildings in Penang. The chinthe guardian lions at the entrance are among the largest examples of this type of sculpture in Malaysia. The temple\'s murals depict scenes from the life of the Buddha and from Burmese Buddhist mythology. The temple is gazetted as a national heritage site.'
    },
    pois: []
  },
];

async function main() {
  console.log('🌱 Starting database seed...');

  console.log('🏷️ Upserting Tags...');
  const dbTags: Record<string, string> = {};
  for (const t of CATEGORIES) {
    const created = await prisma.tag.upsert({
      where: { name: t },
      update: {},
      create: { name: t },
    });
    dbTags[t] = created.id;
  }

  console.log('🧹 Wiping old spots...');
  await prisma.landmarkTag.deleteMany();
  await prisma.poiImage.deleteMany();
  await prisma.pointOfInterest.deleteMany();
  await prisma.landmark.deleteMany();

  console.log(`🗺️ Creating ${MOCK_DATA.length} landmarks and their POIs...`);

  for (const lm of MOCK_DATA) {
    const sourceUrls = lm.location ? [`https://maps.google.com/?q=${encodeURIComponent(lm.location)}`] : [];

    const createdLm = await prisma.landmark.create({
      data: {
        name: lm.name,
        description: lm.description,
        location: lm.location,
        sourceUrls,
        status: lm.status,
        content: lm.content,
        createdBy: null,
      }
    });

    if (lm.tags) {
      for (const tag of lm.tags) {
        if (dbTags[tag]) {
          await prisma.landmarkTag.create({
            data: { landmarkId: createdLm.id, tagId: dbTags[tag] }
          });
        }
      }
    }

    if (lm.pois && lm.pois.length > 0) {
      for (const p of lm.pois) {
        const poi = p as any;
        const pSourceUrls = poi.location ? [`https://maps.google.com/?q=${encodeURIComponent(poi.location)}`] : [];
        await prisma.pointOfInterest.create({
          data: {
            name: poi.name,
            description: poi.description,
            location: poi.location,
            sourceUrls: pSourceUrls,
            searchPrompts: poi.searchPrompts || [],
            status: poi.status || 'published',
            content: poi.content,
            landmarkId: createdLm.id,
          }
        });
      }
    }
  }

  console.log('✅ Seed completed successfully! 🎉');
}

main()
  .catch((e) => {
    console.error('❌ Seeding failed:', e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
