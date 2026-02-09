import os
import sqlite3
import asyncio
import aiohttp
import sys

# Constants
EDOPRO_PATH = "." 
DB_PATH = os.path.join(EDOPRO_PATH, "expansions", "cards.cdb")
CORE_DB_PATH = os.path.join(EDOPRO_PATH, "cards.cdb")
PICS_PATH = os.path.join(EDOPRO_PATH, "pics")

# URL SOURCES (The Secret Sauce)
# We try these in order. If #1 fails, we try #2, then #3.
URL_SOURCES = [
    # 1. Official High-Quality Art (Standard Cards)
    "https://images.ygoprodeck.com/images/cards",
    
    # 2. Project Ignis Pre-Errata / GOAT Art (For IDs like 511000818)
    "https://raw.githubusercontent.com/ProjectIgnis/Card-Patcher/master/pics",
    
    # 3. Project Ignis General Backup (Anime cards, etc)
    "https://raw.githubusercontent.com/ProjectIgnis/Images/master/pics" 
]

CONCURRENCY_LIMIT = 50 

async def get_all_ids_from_db(db_file):
    """Connects to the local EDOPro database to find exactly what cards this game has."""
    if not os.path.exists(db_file):
        return []
    
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM datas")
        ids = [row[0] for row in cursor.fetchall()]
        conn.close()
        return ids
    except Exception as e:
        print(f"Error reading DB {db_file}: {e}")
        return []

async def download_image(session, card_id, semaphore):
    """Downloads a single image, trying multiple sources if the first one fails."""
    filename = f"{card_id}.jpg"
    filepath = os.path.join(PICS_PATH, filename)

    if os.path.exists(filepath):
        return 

    async with semaphore: 
        # Try every URL in our list
        for base_url in URL_SOURCES:
            url = f"{base_url}/{filename}"
            try:
                async with session.get(url) as response:
                    if response.status == 200:
                        content = await response.read()
                        with open(filepath, 'wb') as f:
                            f.write(content)
                        # Nice logging to show where it came from
                        source_name = "YGOProDeck" if "ygoprodeck" in base_url else "Project Ignis (GOAT/Anime)"
                        print(f"✅ Downloaded: {filename} (from {source_name})")
                        return # Success! Stop trying other URLs.
            except Exception as e:
                pass # Just try the next URL

        # If we get here, no URL worked
        print(f"❌ Failed to find image for ID: {card_id}")

async def main():
    print("--- EDOPro HD Sync (Ultimate Edition) ---")
    
    if not os.path.exists(PICS_PATH):
        os.makedirs(PICS_PATH)

    all_ids = set()
    
    # 1. Read Core DB
    if os.path.exists(CORE_DB_PATH):
        print("Reading core database...")
        all_ids.update(await get_all_ids_from_db(CORE_DB_PATH))
        
    # 2. Read Expansions (CRITICAL for GOAT/Pre-Errata)
    expansions_dir = os.path.join(EDOPRO_PATH, "expansions")
    if os.path.exists(expansions_dir):
        for file in os.listdir(expansions_dir):
            if file.endswith(".cdb"):
                print(f"Reading expansion: {file}...")
                all_ids.update(await get_all_ids_from_db(os.path.join(expansions_dir, file)))

    print(f"Found {len(all_ids)} unique card IDs.")

    # DEBUG: Check specifically for Sinister Serpent (GOAT)
    if 511000818 in all_ids:
        print("👀 SPOTTED: Sinister Serpent (GOAT Version) is in your database.")
    else:
        print("⚠️ WARNING: Sinister Serpent (GOAT Version) was NOT found in your DBs.")

    missing_ids = [_id for _id in all_ids if not os.path.exists(os.path.join(PICS_PATH, f"{_id}.jpg"))]
    print(f"Missing images for {len(missing_ids)} cards.")
    
    if not missing_ids:
        print("All cards synced!")
        return

    print("Starting Multi-Source Download...")
    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
    
    async with aiohttp.ClientSession() as session:
        tasks = [download_image(session, _id, semaphore) for _id in missing_ids]
        await asyncio.gather(*tasks)

    print("\nDone! Your EDOPro is now HD ready.")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())