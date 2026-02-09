import os
import sqlite3
import asyncio
import aiohttp
import sys
import json

# --- CONFIGURATION ---
EDOPRO_PATH = "." 
PICS_PATH = os.path.join(EDOPRO_PATH, "pics")
MANUAL_MAP_FILE = "manual_map.json"

# URL SOURCES
URL_SOURCES = {
    "official": "https://images.ygoprodeck.com/images/cards",
    "backup": "https://raw.githubusercontent.com/ProjectIgnis/Images/master/pics"
}

# THE MAGIC LIST (Based on your discovery)
SUFFIXES_TO_STRIP = [
    " GOAT", 
    " (Pre-Errata)",
    " (GOAT)",
    " Pre-Errata"
]

CONCURRENCY_LIMIT = 50 

# --- HELPERS ---

def get_db_files():
    """Finds all .cdb files in root and expansions."""
    dbs = []
    if os.path.exists("cards.cdb"):
        dbs.append("cards.cdb")
    exp_path = os.path.join(EDOPRO_PATH, "expansions")
    if os.path.exists(exp_path):
        for f in os.listdir(exp_path):
            if f.endswith(".cdb"):
                dbs.append(os.path.join(exp_path, f))
    return dbs

def load_manual_map():
    if os.path.exists(MANUAL_MAP_FILE):
        try:
            with open(MANUAL_MAP_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {}

def scan_databases_for_names(db_files):
    id_to_name = {}
    name_to_official_id = {}
    
    print("Building Name Index...")
    
    for db in db_files:
        try:
            conn = sqlite3.connect(db)
            cursor = conn.cursor()
            cursor.execute("SELECT d.id, t.name FROM datas d INNER JOIN texts t ON d.id = t.id")
            rows = cursor.fetchall()
            conn.close()

            for r in rows:
                card_id = r[0]
                name = r[1]
                id_to_name[card_id] = name
                
                # If it's an official Konami ID (usually < 100 million), index it as a source of truth
                if card_id < 100000000: 
                    if name not in name_to_official_id:
                        name_to_official_id[name] = card_id
                        
        except Exception as e:
            print(f"⚠️ Error scanning {db}: {e}")
            
    return id_to_name, name_to_official_id

def find_official_match(name, name_to_official_id):
    """
    Tries to find the official ID for a given name.
    1. Exact Match
    2. Suffix Strip Match (The 'Leo Fix')
    """
    # 1. Exact Match
    if name in name_to_official_id:
        return name_to_official_id[name]

    # 2. Suffix Strip Match
    for suffix in SUFFIXES_TO_STRIP:
        if name.endswith(suffix):
            clean_name = name.replace(suffix, "")
            if clean_name in name_to_official_id:
                return name_to_official_id[clean_name]
    
    return None

# --- DOWNLOAD LOGIC ---

async def download_worker(session, card_id, name, official_match_id, manual_match_id, semaphore):
    filename = f"{card_id}.jpg"
    filepath = os.path.join(PICS_PATH, filename)

    if os.path.exists(filepath):
        return

    async with semaphore:
        # STRATEGY 1: Manual Override
        if manual_match_id:
            url = f"{URL_SOURCES['official']}/{manual_match_id}.jpg"
            if await try_download(session, url, filepath):
                print(f"✅ {name}: Mapped manually ({card_id} -> {manual_match_id})")
                return

        # STRATEGY 2: Smart Name Match (Official HD)
        if official_match_id:
            url = f"{URL_SOURCES['official']}/{official_match_id}.jpg"
            if await try_download(session, url, filepath):
                # We save the Official HD image as the GOAT ID filename
                print(f"✅ {name}: Auto-Mapped to HD Art ({card_id} -> {official_match_id})")
                return

        # STRATEGY 3: Last Resort (Project Ignis Low Res)
        url = f"{URL_SOURCES['backup']}/{card_id}.jpg"
        if await try_download(session, url, filepath):
            print(f"⚠️ {name}: Fallback to Low-Res ({card_id})")
            return
            
        print(f"❌ {name}: No image found.")

async def try_download(session, url, filepath):
    try:
        async with session.get(url) as resp:
            if resp.status == 200:
                content = await resp.read()
                with open(filepath, 'wb') as f:
                    f.write(content)
                return True
    except:
        pass
    return False

# --- MAIN ---

async def main():
    print("--- EDOPro HD Sync (Suffix-Stripper Edition) ---")
    
    # 0. Test Cleanup
    test_file = os.path.join(PICS_PATH, "511000818.jpg")
    if os.path.exists(test_file):
        os.remove(test_file)
        print("🧹 Cleaned up 511000818.jpg for testing.")

    if not os.path.exists(PICS_PATH):
        os.makedirs(PICS_PATH)

    # 1. Load Data
    dbs = get_db_files()
    id_to_name, name_to_official_id = scan_databases_for_names(dbs)
    manual_map = load_manual_map()
    
    print(f"Indexed {len(id_to_name)} total cards.")
    print(f"Indexed {len(name_to_official_id)} official HD candidates.")

    # 2. Find Missing
    missing_ids = [cid for cid in id_to_name.keys() if not os.path.exists(os.path.join(PICS_PATH, f"{cid}.jpg"))]
    print(f"Missing images: {len(missing_ids)}")
    
    if not missing_ids:
        print("All synced!")
        return

    # 3. Download
    print("Starting download...")
    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
    async with aiohttp.ClientSession() as session:
        tasks = []
        for cid in missing_ids:
            name = id_to_name[cid]
            
            # THE FIX: Run the name through the suffix stripper
            official_match = find_official_match(name, name_to_official_id)
            
            manual_match = manual_map.get(str(cid))
            
            tasks.append(download_worker(session, cid, name, official_match, manual_match, semaphore))
            
        await asyncio.gather(*tasks)

    print("\nDone.")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())