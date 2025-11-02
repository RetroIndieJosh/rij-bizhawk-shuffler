import requests
import math
import yaml

CONFIG_FILE = "extra-life.yaml"
OUTPUT_FILE = "extra-life-donors.txt"

def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def sanitize_name(name):
    # Remove spaces and colons, keep original capitalization
    return name.replace(":", "").replace(" ", "")

def fetch_donations(participant_id, limit=100, verbose=False):
    page = 1
    all_donations = []
    while True:
        url = f"https://extra-life.donordrive.com/api/participants/{participant_id}/donations?limit={limit}&page={page}"
        resp = requests.get(url)
        if resp.status_code != 200:
            raise Exception(f"Error fetching donations (status {resp.status_code})")
        
        num_records = int(resp.headers.get("num-records", 0))
        donations = resp.json()
        if verbose:
            print(f"--- Page {page} ---")
            print(f"Headers: {resp.headers}")
            print(f"Raw donations JSON: {donations}\n")
        
        all_donations.extend(donations)
        
        total_pages = math.ceil(num_records / limit)
        if page >= total_pages:
            break
        page += 1
    return all_donations

def main(verbose=False):
    config = load_config()
    participant_id = config.get("participant-id")
    if not participant_id:
        raise ValueError("participant-id must be set in extra-life.yaml")
    
    donations = fetch_donations(participant_id, verbose=verbose)
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for d in donations:
            # Extract displayName and sanitize it
            name = sanitize_name(d.get("displayName", "ANONYMOUS"))
            amount = d.get("amount", 0)
            f.write(f"{name} ${amount:.2f}\n")
            if verbose:
                print(f"Wrote: {name} ${amount:.2f}")
    
    print(f"Fetched {len(donations)} donations for participant {participant_id}.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Fetch Extra Life donations.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print detailed debug information.")
    args = parser.parse_args()
    main(verbose=args.verbose)
