export interface ClassInfo {
  label: string;
  emoji: string;
  description: string;
  significance: string;
}

const CLASS_INFO: Record<string, ClassInfo> = {
  fort_cornwallis_chapel: {
    label: 'Fort Cornwallis Chapel',
    emoji: '⛪',
    description: 'A small Anglican chapel built inside Fort Cornwallis in the early 19th century. It served British colonial officers and soldiers stationed at the fort.',
    significance: 'One of the oldest Christian places of worship in Penang, reflecting the early British colonial presence on the island.',
  },
  fort_cornwallis_lighthouse: {
    label: 'Fort Cornwallis Lighthouse',
    emoji: '🔦',
    description: 'A cast-iron lighthouse erected in 1882 to guide ships entering Penang harbour. It stands at the northeastern tip of the fort.',
    significance: 'A functional maritime landmark that guided trade vessels during Penang\'s peak as a major trading port in Southeast Asia.',
  },
  seri_rambai_cannon: {
    label: 'Seri Rambai Cannon',
    emoji: '💣',
    description: 'A large Dutch bronze cannon cast in 1603, gifted to the Sultan of Johor and later captured by the Dutch. It was brought to Penang in 1871.',
    significance: 'Believed to have fertility powers by locals — women place flowers in its barrel hoping to conceive. A unique blend of history and folk belief.',
  },
  statue_francis_light: {
    label: 'Statue of Francis Light',
    emoji: '🗿',
    description: 'A bronze statue of Captain Francis Light, the British naval officer who founded Penang as a British trading post on 11 August 1786.',
    significance: 'Commemorates the founding of modern Penang. Light negotiated with the Sultan of Kedah to establish the settlement that grew into a major port city.',
  },
  dragon_pillar: {
    label: 'Dragon Pillar',
    emoji: '🐉',
    description: 'Ornate pillars decorated with coiling dragon motifs, commonly found at Chinese temples. Dragons symbolise power, good fortune, and protection.',
    significance: 'A defining feature of Chinese temple architecture in Penang, reflecting the rich Hokkien and Cantonese heritage of the island\'s Chinese community.',
  },
  guan_yin_statue: {
    label: 'Guan Yin Statue',
    emoji: '🙏',
    description: 'A towering statue of Guan Yin (觀音), the Buddhist Goddess of Mercy and Compassion. The statue at Kek Lok Si is one of the largest in Southeast Asia.',
    significance: 'Guan Yin is one of the most venerated deities in Chinese Buddhism. Her statue draws thousands of pilgrims and tourists to Penang annually.',
  },
  holy_vase: {
    label: 'Holy Vase',
    emoji: '🏺',
    description: 'Sacred ceremonial vases placed at temple altars, used to hold incense sticks or offerings. Often decorated with auspicious symbols and Chinese calligraphy.',
    significance: 'An integral part of Chinese religious practice, representing the vessel through which prayers and offerings are presented to deities.',
  },
  lotus_base: {
    label: 'Lotus Base',
    emoji: '🪷',
    description: 'A pedestal or base carved in the shape of a lotus flower, typically supporting a Buddha or deity statue. The lotus symbolises purity and enlightenment.',
    significance: 'In Buddhist iconography, the lotus rising from muddy water represents spiritual awakening. Lotus bases elevate sacred figures both physically and symbolically.',
  },
  three_tiered_pavilion_roof: {
    label: 'Three-Tiered Pavilion Roof',
    emoji: '🏯',
    description: 'A multi-tiered Chinese pavilion roof with upturned eaves at each level. The three tiers represent heaven, earth, and humanity in Chinese cosmology.',
    significance: 'A hallmark of traditional Chinese architecture found throughout Penang\'s heritage temples, symbolising cosmic harmony and divine protection.',
  },
  arched_arcade: {
    label: 'Arched Arcade',
    emoji: '🕌',
    description: 'A series of repeating arches forming a covered walkway along the mosque\'s interior or exterior. Inspired by Moorish and Indo-Saracenic architectural styles.',
    significance: 'The arched arcade at Kapitan Keling Mosque reflects the fusion of Indian Muslim, Moorish, and colonial architectural influences in Penang.',
  },
  arched_gateway: {
    label: 'Arched Gateway',
    emoji: '🚪',
    description: 'A grand entrance arch marking the main gateway into the mosque compound. Decorated with Islamic geometric patterns and calligraphy.',
    significance: 'The gateway serves as a symbolic threshold between the secular world and sacred space, welcoming worshippers into the mosque.',
  },
  crescent_finial: {
    label: 'Crescent Finial',
    emoji: '🌙',
    description: 'A crescent moon and star ornament placed at the very top of mosque minarets and domes. The crescent is the universal symbol of Islam.',
    significance: 'The crescent finial crowning Kapitan Keling Mosque\'s minarets is visible across Georgetown, marking the mosque as a spiritual landmark of the Muslim community.',
  },
  guldastas: {
    label: 'Guldastas',
    emoji: '🌸',
    description: 'Decorative floral pinnacles or turrets found at the corners of mosque parapets. The term comes from Persian, meaning "bouquet of flowers".',
    significance: 'Guldastas are a distinctive feature of Mughal-influenced mosque architecture, adding ornamental elegance to the roofline of Kapitan Keling Mosque.',
  },
  minaret: {
    label: 'Minaret',
    emoji: '🕌',
    description: 'A tall slender tower attached to the mosque from which the call to prayer (azan) is traditionally announced. Kapitan Keling Mosque has two prominent minarets.',
    significance: 'The minarets of Kapitan Keling Mosque are among the most recognisable landmarks in Georgetown, symbolising the presence of Islam in Penang since the early 19th century.',
  },
  onion_dome: {
    label: 'Onion Dome',
    emoji: '🧅',
    description: 'A bulbous dome shaped like an onion, characteristic of Mughal and Indo-Islamic architecture. Found atop the main prayer hall of Kapitan Keling Mosque.',
    significance: 'The onion dome is a signature element of Mughal architecture, connecting Penang\'s Indian Muslim community to the grand mosque traditions of the Indian subcontinent.',
  },
  guardian_lion: {
    label: 'Guardian Lion',
    emoji: '🦁',
    description: 'Pairs of stone or bronze lion statues placed at the entrance of Chinese temples and clan houses. Known as "Shi" (獅) in Chinese, they ward off evil spirits.',
    significance: 'The guardian lions at Khoo Kongsi are intricately carved and represent the power and prestige of the Khoo clan, one of Penang\'s most influential Chinese clans.',
  },
  main_ridge: {
    label: 'Main Ridge',
    emoji: '🏠',
    description: 'The central horizontal ridge running along the top of a traditional Chinese roof. Often decorated with ceramic figurines, dragons, and auspicious motifs.',
    significance: 'The ornate main ridge of Khoo Kongsi\'s clan house is considered one of the finest examples of Hokkien temple architecture in Southeast Asia.',
  },
  swallowtail_roof: {
    label: 'Swallowtail Roof',
    emoji: '🦅',
    description: 'A distinctive roof style where the ridge ends curve dramatically upward like a swallow\'s tail. This style originates from Fujian province in southern China.',
    significance: 'The swallowtail roof is the most iconic feature of Hokkien architecture in Penang, distinguishing clan houses and temples built by Fujian immigrants.',
  },
  burmese_spire: {
    label: 'Burmese Spire',
    emoji: '🗼',
    description: 'A tall, tapering spire of Burmese Buddhist architectural style, typically gilded and multi-tiered. Found at the top of the Pagoda of Rama VI.',
    significance: 'The Burmese spire reflects the Siamese-Burmese Buddhist influence on the Pagoda of Rama VI, built by the Thai community in Penang in the early 20th century.',
  },
  chinese_base: {
    label: 'Chinese Base',
    emoji: '🏛️',
    description: 'The lower foundation tier of the pagoda built in traditional Chinese architectural style, featuring red columns and decorative brackets.',
    significance: 'The Chinese base of the Pagoda of Rama VI represents the Chinese Buddhist influence, creating a unique fusion of Chinese, Thai, and Burmese architectural styles.',
  },
  thai_tier: {
    label: 'Thai Tier',
    emoji: '🏯',
    description: 'The middle section of the Pagoda of Rama VI built in Thai Buddhist architectural style, with gilded decorations and characteristic Thai roof forms.',
    significance: 'The Thai tier honours King Rama VI of Thailand, who donated funds for the pagoda\'s construction. It represents the Thai community\'s deep Buddhist heritage.',
  },
  balcony_tier: {
    label: 'Balcony Tier',
    emoji: '🏢',
    description: 'An open balcony level on the Queen Victoria Memorial Clock Tower, featuring decorative ironwork railings and arched openings.',
    significance: 'The balcony tier allows visitors to appreciate the clock tower\'s Victorian Gothic design and offers views over Georgetown\'s historic waterfront.',
  },
  clock_face: {
    label: 'Clock Face',
    emoji: '🕐',
    description: 'The large ornamental clock face on the Queen Victoria Memorial Clock Tower. The tower was built in 1897 to commemorate Queen Victoria\'s Diamond Jubilee.',
    significance: 'The clock tower is one of Georgetown\'s most beloved landmarks, donated by a wealthy Penang resident to mark 60 years of Queen Victoria\'s reign.',
  },
  golden_cupola: {
    label: 'Golden Cupola',
    emoji: '🔔',
    description: 'The gilded dome-shaped cap at the very top of the Queen Victoria Memorial Clock Tower, gleaming in the Penang sun.',
    significance: 'The golden cupola crowns the clock tower and is visible from the waterfront, serving as a navigational landmark for ships entering Penang harbour.',
  },
  octagonal_base: {
    label: 'Octagonal Base',
    emoji: '🔷',
    description: 'The eight-sided base structure of the Queen Victoria Memorial Clock Tower. The octagonal form is a common feature of Victorian memorial architecture.',
    significance: 'The octagonal base gives the clock tower its distinctive silhouette and provides structural stability for the 18-metre tall tower.',
  },
  pinang_sculpture: {
    label: 'Pinang Sculpture',
    emoji: '🌴',
    description: 'A decorative sculpture or motif featuring the pinang (areca) palm, after which Penang (Pulau Pinang — "Betel Nut Island") is named.',
    significance: 'The pinang palm is the symbol of Penang. Its presence on the clock tower connects the colonial monument to the island\'s indigenous identity and name.',
  },
  church_steeple: {
    label: 'Church Steeple',
    emoji: '⛪',
    description: 'The tall pointed spire of St George\'s Church, rising above the surrounding trees. Built in 1818, it is the oldest Anglican church in Southeast Asia.',
    significance: 'The steeple of St George\'s Church is a defining feature of Georgetown\'s skyline and a symbol of the early British colonial and Christian presence in Penang.',
  },
  dome_pavilion: {
    label: 'Dome Pavilion',
    emoji: '🏛️',
    description: 'A small domed memorial pavilion in the grounds of St George\'s Church, built to honour Francis Light, the founder of Penang.',
    significance: 'The dome pavilion marks the burial site of Francis Light and serves as a memorial to the man who established Penang as a British trading settlement in 1786.',
  },
  front_portico: {
    label: 'Front Portico',
    emoji: '🏛️',
    description: 'The grand columned entrance porch of St George\'s Church, featuring classical Doric columns and a triangular pediment in the neoclassical style.',
    significance: 'The portico is the most photographed feature of St George\'s Church, exemplifying the neoclassical architecture favoured by the British colonial administration.',
  },
  tower_clock: {
    label: 'Tower Clock',
    emoji: '🕰️',
    description: 'The clock mechanism and face mounted on the bell tower of St George\'s Church, added in the 19th century to serve the surrounding community.',
    significance: 'The tower clock of St George\'s Church once served as the primary public timekeeper for Georgetown\'s residents and merchants.',
  },
};

export default CLASS_INFO;
