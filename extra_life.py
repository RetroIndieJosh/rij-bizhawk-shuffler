import yaml
import time
import requests
import argparse
from datetime import datetime, timedelta

# ----------------- HELPER FUNCTIONS -----------------
def load_config(path="config.yaml"):
    with open(path, "r") as f:
        return yaml.safe_load(f)

def save_donors(donors, filename):
    with open(filename, "w", encoding="utf-8") as f:
        for donor in donors:
            f.write(f"{donor}\n")

def fetch_extra_life_donors(participant_id, verbose=False):
    """Fetch usernames of donors for the given participant ID."""
    url = f"https://www.extra-life.org/api/participants/{participant_id}/donations"
    try:
        resp = requests.get(url)
        resp.raise_for_status()
        donations = resp.json()
        donors = []
        for donation in donations:
            display_name = donation.get("displayName", "").replace(":", "").replace(" ", "")
            if display_name:
                donors.append(display_name)
        if verbose:
            print(f"[{datetime.now()}] Fetched {len(donors)} donors: {donors}")
        return donors
    except Exception as e:
        print(f"[{datetime.now()}] Error fetching donations: {e}")
        return []

def read_chat_messages(chatfile):
    """Read all lines from chatfile and return as list."""
    try:
        with open(chatfile, "r", encoding="utf-8") as f:
            return [line.strip() for line in f.readlines()]
    except FileNotFoundError:
        return []

def append_new_messages(old_messages, chatfile):
    """Return list of new messages not in old_messages."""
    current_messages = read_chat_messages(chatfile)
    new_messages = [msg for msg in current_messages if msg not in old_messages]
    return new_messages, current_messages

# ----------------- MAIN LOOP -----------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    args = parser.parse_args()

    config = load_config()

    yt_config = config.get("youtube", {})
    el_config = config.get("extra-life", {})

    chatfile = yt_config.get("chatfile", "youtube-chat.txt")
    participant_id = el_config.get("participant-id")
    donors_file = el_config.get("donors-file", "extra-life-donors.txt")
    update_interval = el_config.get("update-interval", 10)  # minutes

    if participant_id is None:
        print("Error: participant-id is required in YAML under extra-life section.")
        return

    donors = fetch_extra_life_donors(participant_id, args.verbose)
    save_donors(donors, donors_file)
    last_update_time = datetime.now()
    old_chat_messages = []

    per_user_cooldown = {}
    global_cooldown = timedelta(seconds=5)
    host_user = yt_config.get("host", "")

    while True:
        # Update donors every update_interval minutes
        if datetime.now() - last_update_time >= timedelta(minutes=update_interval):
            donors = fetch_extra_life_donors(participant_id, args.verbose)
            save_donors(donors, donors_file)
            last_update_time = datetime.now()

        # Read new chat messages
        new_msgs, old_chat_messages = append_new_messages(old_chat_messages, chatfile)

        for msg in new_msgs:
            # Expect format "@Username: message"
            if not msg.startswith("@") or ":" not in msg:
                continue

            user, message = msg[1:].split(":", 1)
            user = user.strip()
            message = message.strip()

            if message != "!swap":
                continue

            # Skip banned users (extra feature)
            if user not in donors and user != host_user:
                if args.verbose:
                    print(f"[{datetime.now()}] Ignoring {user}, not in donors list.")
                continue

            # Check per-user cooldown
            last_swap = per_user_cooldown.get(user)
            now = datetime.now()
            if last_swap and (now - last_swap).total_seconds() < 60 and user != host_user:
                if args.verbose:
                    print(f"[{datetime.now()}] {user} is on cooldown, skipping !swap.")
                continue

            # Check global cooldown
            last_swap_global = per_user_cooldown.get("__global__")
            if last_swap_global and (now - last_swap_global) < global_cooldown:
                if args.verbose:
                    print(f"[{datetime.now()}] Global cooldown active, skipping !swap from {user}.")
                continue

            # Register swap
            per_user_cooldown[user] = now
            per_user_cooldown["__global__"] = now

            print(f"[{datetime.now()}] SWAP triggered by {user}")

        time.sleep(1)

if __name__ == "__main__":
    main()
