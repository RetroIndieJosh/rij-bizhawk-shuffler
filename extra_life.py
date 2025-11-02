import yaml
import time
import requests
from datetime import datetime, timedelta

# --- Load configuration ---
with open("config.yaml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

# YouTube config
host_user = config["youtube"]["host"]
chat_file = config["youtube"]["chatfile"]

# Extra Life config
participant_id = config["extra-life"]["participant-id"]
donors_file = config["extra-life"]["donors-file"]
update_interval = config["extra-life"].get("update-interval", 10)  # minutes

# --- State ---
donors_set = set()
last_donor_fetch = datetime.min
last_swap_frame = {}  # user -> timestamp
banned_users = set()
locked = False
cooldown_seconds = 60

# --- Functions ---
def fetch_donors():
    global donors_set, last_donor_fetch
    url = f"https://www.extra-life.org/api/1.4/participants/{participant_id}/donations"
    headers = {"User-Agent": "ExtraLifeLogger/1.0"}
    try:
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        donors_set = set(d.get("displayName") for d in data if d.get("displayName"))
        # Write donor file with amounts
        with open(donors_file, "w", encoding="utf-8") as f:
            for d in data:
                name = d.get("displayName")
                amount = d.get("amount", 0)
                if name:
                    f.write(f"{name}: ${amount:.2f}\n")
        last_donor_fetch = datetime.now()
        print(f"[{last_donor_fetch}] Fetched {len(donors_set)} donors")
    except Exception as e:
        print(f"Error fetching donors: {e}")

def update_donor_list_if_needed():
    if datetime.now() - last_donor_fetch > timedelta(minutes=update_interval):
        fetch_donors()

def trigger_swap():
    # Replace with actual code to trigger the swap in Bizhawk
    print(">>> SWAP TRIGGERED <<<")

def process_chat(user, message):
    global last_swap_frame, locked

    now = time.time()
    message = message.strip()
    is_host = user.lower() == host_user.lower()

    if message != "!swap":
        return

    if locked and not is_host:
        print(f"Ignored !swap from {user}: chat is locked")
        return

    if user in banned_users:
        print(f"Ignored !swap from {user}: user is banned")
        return

    if not is_host:
        last_time = last_swap_frame.get(user, 0)
        if now - last_time < cooldown_seconds:
            remaining = int(cooldown_seconds - (now - last_time))
            print(f"Ignored !swap from {user}: in cooldown ({remaining}s left)")
            return

    if user not in donors_set:
        print(f"Ignored !swap from {user}: not in Extra Life donor list")
        return

    # Passed all checks
    print(f"Swap triggered by {user}!")
    last_swap_frame[user] = now
    trigger_swap()

def process_admin_command(user, message):
    global locked, cooldown_seconds
    if user.lower() != host_user.lower():
        return
    msg = message.strip()
    if msg.startswith("!ban "):
        target = msg[5:].strip()
        banned_users.add(target)
        print(f"User {target} banned by host")
    elif msg.startswith("!cooldown "):
        try:
            val = int(msg.split()[1])
            cooldown_seconds = val
            print(f"Cooldown changed to {val} seconds by host")
        except:
            print("Invalid cooldown value")
    elif msg == "!lock":
        locked = True
        print("Chat locked by host")
    elif msg == "!unlock":
        locked = False
        print("Chat unlocked by host")

# --- Main loop ---
def main():
    fetch_donors()
    while True:
        update_donor_list_if_needed()
        try:
            with open(chat_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except:
            lines = []

        for line in lines:
            if ":" not in line:
                continue
            user, message = line.split(":", 1)
            process_admin_command(user.strip(), message)
            process_chat(user.strip(), message)

        time.sleep(1)  # check every second

if __name__ == "__main__":
    main()
