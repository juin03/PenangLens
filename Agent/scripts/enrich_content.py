"""
Enrich thin landmark content in Azure AI Search text index.
Run: python scripts/enrich_content.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()

from src.indexer import index_spot

ENRICHED = [
    {
        "id": "sister-curry-mee",
        "type": "landmark",
        "name": "Sister Curry Mee",
        "tags": ["Food"],
        "location": "5.3975,100.2838",
        "description": "A legendary curry mee stall in Air Itam, known for its rich coconut-based curry broth with prawns and cockles. Run by two sisters for over 40 years.",
        "content": {
            "overview": "Sister Curry Mee is one of the most iconic food stalls in Penang, located in Air Itam. The stall is famous for its rich, coconut milk-based curry broth served with yellow noodles, rice vermicelli, prawns, cockles, tofu puffs, and a dollop of sambal chilli.",
            "history": "The stall has been operating for over 40 years. The two sisters who run it are known for their consistent quality and the secret recipe passed down through generations. It is a must-visit for food lovers exploring Penang's hawker culture.",
            "culture": "Sister Curry Mee is open in the mornings and typically sells out by noon. It is located near the Air Itam market. Arrive early to avoid long queues. The stall is cash-only and very popular with locals.",
        }
    },
    {
        "id": "kapitan-keling-mosque",
        "type": "landmark",
        "name": "Kapitan Keling Mosque",
        "tags": ["Religious", "Heritage", "Architecture"],
        "location": "5.4164,100.3327",
        "description": "The oldest and most significant mosque in Penang, built in the early 19th century by Indian Muslim traders. Features striking Mughal-style architecture with golden domes and a tall minaret.",
        "content": {
            "history": "The mosque was established around 1801 by the Kapitan Keling, the leader of the Indian Muslim community in Penang. The name refers to the title given to the community leader. The mosque has undergone several renovations but retains its original Mughal architectural character.",
            "overview": "Kapitan Keling Mosque features a large central golden dome flanked by smaller domes, a tall minaret visible from across George Town, arched arcades along the perimeter, and intricate decorative elements reflecting Mughal and Indian Islamic architectural traditions. The interior can accommodate over 2,000 worshippers.",
            "culture": "Non-Muslim visitors are welcome outside prayer times. Modest dress is required — robes are available at the entrance. The mosque is open daily and is a short walk from Fort Cornwallis and the Penang State Museum.",
        }
    },
    {
        "id": "gurney-drive-hawker-centre",
        "type": "landmark",
        "name": "Gurney Drive Hawker Centre",
        "tags": ["Food"],
        "location": "5.4366,100.3072",
        "description": "One of the most famous hawker food streets in Asia, located along the Gurney Drive seafront promenade. Offers authentic Penang street food including char koay teow, assam laksa, cendol, and rojak.",
        "content": {
            "overview": "Gurney Drive Hawker Centre is best known for its char koay teow (wok-fried flat rice noodles with prawns, cockles, eggs, and bean sprouts), assam laksa (tangy fish-based noodle soup), cendol (shaved ice dessert with coconut milk and palm sugar), and Penang rojak (fruit and vegetable salad with prawn paste dressing).",
            "culture": "The hawker centre is open in the evenings from around 5pm to midnight. It is busiest on weekends. Located along Persiaran Gurney, it is easily accessible by taxi or Grab. Parking is available along the seafront road.",
        }
    },
    {
        "id": "pinang-peranakan-mansion",
        "type": "landmark",
        "name": "Pinang Peranakan Mansion",
        "tags": ["Heritage", "Culture"],
        "location": "5.4175,100.3328",
        "description": "A beautifully restored 19th-century mansion showcasing the opulent lifestyle of the Straits Chinese (Peranakan or Baba-Nyonya) community. Houses over 1,000 antiques and artefacts.",
        "content": {
            "history": "The mansion was built in the late 1800s and belonged to a wealthy Peranakan merchant. The Peranakan community are descendants of Chinese immigrants who settled in the Malay Archipelago and adopted local Malay customs while retaining Chinese traditions, creating a unique hybrid culture.",
            "overview": "The mansion features a blend of Chinese, Malay, and European architectural styles typical of Peranakan design. It includes ornate carved wooden panels, colourful ceramic tiles, gilded furniture, and a central courtyard. The facade is painted in the distinctive Peranakan style with intricate decorative motifs.",
            "culture": "The mansion is open daily from 9:30am to 5pm. Admission is charged. Guided tours are available. It is located on Church Street (Lebuh Gereja) in George Town, a short walk from Khoo Kongsi.",
        }
    },
    {
        "id": "penang-war-museum",
        "type": "landmark",
        "name": "Penang War Museum",
        "tags": ["Heritage", "Historical"],
        "location": "5.2833,100.2667",
        "description": "A WWII heritage site built by the British in the 1930s as a coastal defence fortress. Visitors can explore tunnels, bunkers, ammunition stores, and military barracks.",
        "content": {
            "history": "The fortress was constructed between 1936 and 1941 as part of Britain's coastal defence strategy. When Japan invaded Malaya in December 1941, the fortress fell without a fight as the Japanese attacked from the north. The Japanese used it as a detention and torture centre during their occupation from 1941 to 1945.",
            "overview": "The Penang War Museum is located on Bukit Batu Maung in southern Penang. The site covers 8 acres and includes over 20 structures including tunnels, bunkers, barracks, and a command post. It provides an immersive experience of Penang's wartime history.",
            "culture": "The museum is open daily from 9am to 6pm. Admission is charged. It is located about 20km from George Town and is best reached by car or taxi. Allow 2-3 hours to explore the extensive grounds.",
        }
    },
    {
        "id": "clan-jetties-penang",
        "type": "landmark",
        "name": "Clan Jetties of Penang",
        "tags": ["Heritage", "Culture"],
        "location": "5.4108,100.3397",
        "description": "Chinese clan settlements built on stilts over the water along Weld Quay in George Town, dating back to the 19th century. One of the last surviving examples of traditional Chinese waterfront communities in Southeast Asia.",
        "content": {
            "history": "The jetties were established by Chinese immigrants who arrived in Penang in the 1800s. Each jetty is named after a Chinese clan — Chew Jetty (Chew clan), Tan Jetty (Tan clan), Lee Jetty (Lee clan), Lim Jetty (Lim clan), Mixed Surname Jetty, and Yeoh Jetty. The Chew Jetty is the largest and most visited, with over 70 houses and a clan temple.",
            "culture": "The jetty communities maintain their traditional way of life, with residents still living in the wooden houses built on stilts. The Chew Jetty has a clan temple dedicated to Tua Pek Kong, a deity worshipped by the Hokkien community. During Chinese New Year, the jetties are decorated with lanterns and host traditional celebrations.",
            "overview": "The Clan Jetties are open to visitors daily and free to enter. The Chew Jetty is the most accessible and has souvenir shops and a small museum. It is located at the end of Weld Quay, a 10-minute walk from Fort Cornwallis.",
        }
    },
    {
        "id": "cheong-fatt-tze-blue-mansion",
        "type": "landmark",
        "name": "Cheong Fatt Tze - The Blue Mansion",
        "tags": ["Heritage", "Architecture"],
        "location": "5.4189,100.3316",
        "description": "An iconic 19th-century Chinese courtyard mansion famous for its distinctive indigo-blue exterior. One of the finest examples of Chinese Baroque architecture in Southeast Asia and a UNESCO World Heritage Site.",
        "content": {
            "history": "The mansion was built between 1896 and 1904 by Cheong Fatt Tze, a Hakka Chinese merchant known as the Rockefeller of the East. He rose from poverty to become one of the wealthiest men in Southeast Asia with business interests across China and Southeast Asia.",
            "overview": "The mansion features 38 rooms, 5 granite-paved courtyards, 7 staircases, and 220 louvred windows. The architecture blends Chinese, British colonial, and Art Nouveau styles. Notable features include hand-painted glass panels, cast-iron spiral staircases imported from Glasgow, and intricate Chinese wood carvings.",
            "culture": "Guided tours of the mansion are available daily at 11am and 3pm. The mansion also operates as a boutique hotel. It is located on Leith Street (Lebuh Leith) in George Town, a short walk from Penang Road.",
        }
    },
]


def main():
    print("Enriching landmark content in Azure AI Search...\n")
    success = 0
    for spot in ENRICHED:
        print(f"  Indexing: {spot['name']}...", end=" ", flush=True)
        ok = index_spot(spot)
        if ok:
            print("✅")
            success += 1
        else:
            print("❌")
    print(f"\nDone: {success}/{len(ENRICHED)} spots enriched.")
    print("Re-run test_ragas.py to see improved scores.")


if __name__ == "__main__":
    main()
