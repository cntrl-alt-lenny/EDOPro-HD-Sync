import os
import sqlite3
import asyncio
import aiohttp
import sys

# Constants
EDOPRO_PATH = "."  # Current directory (put this script in EDOPro folder)
DB_PATH = os.path.join(EDOPRO_PATH, "expansions", "cards.cdb") # Check expansions first, or root
CORE_DB_PATH = os.path.join(EDOPRO_PATH, "cards.cdb")
PICS_PATH = os.path.join(EDOPRO_PATH, "pics")
BASE_URL = "https://images.ygoprodeck.com/images/cards"
# We can add a secondary fallback URL for alt arts if YGOProDeck misses them
CONCURRENCY_LIMIT = 50 # How many downloads at once

async def get_all_ids_from_db(db_file):
    """Connects to the local EDOPro database to find exactly what cards this game has."""
    if not os.path.exists(db_file):
        return []
    
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        # 'datas' table contains the IDs. This includes Alt Arts.
        cursor.execute("SELECT id FROM datas")
        ids = [row[0] for row in cursor.fetchall()]
        conn.close()
        return ids
    except Exception as e:
        print(f"Error reading DB {db_file}: {e}")
        return []

async def download_image(session, card_id, semaphore):
    """Downloads a single image if it doesn't exist."""
    filename = f"{card_id}.jpg"
    filepath = os.path.join(PICS_PATH, filename)

    if os.path.exists(filepath):
        return # Skip if we already have it

    url = f"{BASE_URL}/{filename}"
    
    async with semaphore: # Respect the concurrency limit
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    content = await response.read()
                    with open(filepath, 'wb') as f:
                        f.write(content)
                    print(f"Downloaded: {filename}")
                else:
                    print(f"Failed to find: {filename} (Status: {response.status})")
        except Exception as e:
            print(f"Error downloading {filename}: {e}")

async def main():
    print("--- EDOPro HD Sync (Vibe Code Edition) ---")
    
    # 1. Setup Folders
    if not os.path.exists(PICS_PATH):
        os.makedirs(PICS_PATH)

    # 2. Get Card List from Local DBs
    # We check both the core DB and the 'expansions' DB (where custom cards/erratas live)
    all_ids = set()
    
    # Check root cards.cdb
    if os.path.exists(CORE_DB_PATH):
        print("Reading core database...")
        all_ids.update(await get_all_ids_from_db(CORE_DB_PATH))
        
    # Check expansions (often used for GOAT/Edison specific card pools)
    expansions_dir = os.path.join(EDOPRO_PATH, "expansions")
    if os.path.exists(expansions_dir):
        for file in os.listdir(expansions_dir):
            if file.endswith(".cdb"):
                print(f"Reading expansion: {file}...")
                all_ids.update(await get_all_ids_from_db(os.path.join(expansions_dir, file)))

    print(f"Found {len(all_ids)} unique card IDs in your game.")

    # 3. Filter for missing images
    missing_ids = [_id for _id in all_ids if not os.path.exists(os.path.join(PICS_PATH, f"{_id}.jpg"))]
    print(f"Missing images for {len(missing_ids)} cards.")
    
    if not missing_ids:
        print("All cards synced! You are good to go.")
        return

    # 4. Blast off (Async Download)
    print("Starting High-Speed Download...")
    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
    
    async with aiohttp.ClientSession() as session:
        tasks = [download_image(session, _id, semaphore) for _id in missing_ids]
        await asyncio.gather(*tasks)

    print("\nDone! Your EDOPro is now HD ready.")

if __name__ == "__main__":
    # Windows loop policy fix
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
