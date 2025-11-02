"""
YouTube Chat Commands (for Shuffler integration)

!swap               - Trigger a game swap (global cooldown 5s). Host bypasses per-user cooldown.
!ban <user>         - Host-only: add user to banned list (updates YAML)
!unban <user>       - Host-only: remove user from banned list
!cooldown <seconds> - Host-only: set per-user cooldown for all except host
!lock [minutes]     - Host-only: disable !swap for everyone except host; optional auto-unlock
!unlock             - Host-only: remove active lock immediately

Notes:
- Only exact "!swap" messages are considered.
- Host defined in YAML 'host'; banned users in YAML 'banned'.
- Python manages cooldowns and locks; Lua plugin displays messages on-screen.
"""

import pytchat
import time
import yaml
import threading

CONFIG_FILE = "chat_config.yaml"
OUTPUT_FILE = "youtube-chat.txt"
PER_USER_COOLDOWN = 60  # default seconds per user (ignored for host)
GLOBAL_COOLDOWN = 5     # seconds for everyone

# Load configuration
with open(CONFIG_FILE, "r") as f:
    config = yaml.safe_load(f)

HOST_USER = config.get("host", "RetroIndieJosh")
VIDEO_ID = config.get("video-id", "")
BANNED_USERS = set(u.strip().lstrip("@") for u in config.get("banned", []))

# Track cooldowns
last_swap_by_user = {}
last_global_swap = 0

# Locked state: when True, only host can trigger !swap
locked = False
lock_timer = None

# Clear the output file at startup
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    pass

chat = pytchat.create(video_id=VIDEO_ID)
print(f"Listening to chat on video ID: {VIDEO_ID}...")

def save_banned():
    """Save current banned list back to YAML."""
    config['banned'] = list(BANNED_USERS)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        yaml.dump(config, f)

def unlock_chat():
    global locked, lock_timer
    locked = False
    lock_timer = None
    print("Swap command automatically unlocked.")

def set_lock(duration_minutes=None):
    """Lock swaps. Optional duration in minutes."""
    global locked, lock_timer
    locked = True
    print(f"Swap command locked. Only host can trigger swaps.")
    if duration_minutes is not None:
        if lock_timer and lock_timer.is_alive():
            lock_timer.cancel()
        # Schedule unlock
        lock_timer = threading.Timer(duration_minutes * 60, unlock_chat)
        lock_timer.start()

while chat.is_alive():
    for c in chat.get().sync_items():
        username = c.author.name.strip().lstrip("@")
        message = c.message.strip()

        # Ignore banned users
        if username in BANNED_USERS:
            continue

        # Print all messages
        print(f"{username}: {message}")

        # Only host can issue commands
        if username == HOST_USER:
            # !ban <user>
            if message.lower().startswith("!ban "):
                parts = message.split()
                if len(parts) == 2:
                    target_user = parts[1].strip().lstrip("@")
                    if target_user and target_user not in BANNED_USERS:
                        BANNED_USERS.add(target_user)
                        save_banned()
                        print(f"{target_user} has been banned by {HOST_USER}")
                continue

            # !unban <user>
            if message.lower().startswith("!unban "):
                parts = message.split()
                if len(parts) == 2:
                    target_user = parts[1].strip().lstrip("@")
                    if target_user in BANNED_USERS:
                        BANNED_USERS.remove(target_user)
                        save_banned()
                        print(f"{target_user} has been unbanned by {HOST_USER}")
                continue

            # !cooldown <seconds>
            if message.lower().startswith("!cooldown "):
                parts = message.split()
                if len(parts) == 2:
                    try:
                        new_cooldown = int(parts[1])
                        PER_USER_COOLDOWN = max(0, new_cooldown)
                        print(f"Per-user cooldown updated to {PER_USER_COOLDOWN} seconds by {HOST_USER}")
                    except ValueError:
                        print("Invalid cooldown value. Must be an integer.")
                continue

            # !lock or !lock <minutes>
            if message.lower().startswith("!lock"):
                parts = message.split()
                if len(parts) == 1:
                    set_lock(None)  # permanent lock
                elif len(parts) == 2:
                    try:
                        minutes = int(parts[1])
                        set_lock(minutes)
                        print(f"Swap command locked for {minutes} minutes.")
                    except ValueError:
                        print("Invalid duration for !lock. Must be integer minutes.")
                continue

            # !unlock
            if message.lower() == "!unlock":
                unlock_chat()
                continue

        # Only act on exact "!swap"
        if message.lower() == "!swap":
            # If locked, only host can swap
            if locked and username != HOST_USER:
                continue

            current_time = time.time()

            # Enforce global cooldown for everyone
            if current_time - last_global_swap < GLOBAL_COOLDOWN:
                continue

            # Enforce per-user cooldown for everyone except host
            if username != HOST_USER:
                last_time_user = last_swap_by_user.get(username, 0)
                if current_time - last_time_user < PER_USER_COOLDOWN:
                    continue

            # Swap triggers
            last_global_swap = current_time
            last_swap_by_user[username] = current_time

            # Write to output file
            with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
                f.write(f"{username}: !swap\n")
                f.flush()
