import yaml
import pytchat
import time
import threading
from datetime import datetime
from collections import deque
import re
import requests
import os
import sys
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle

# ================= CONFIG =================
CONFIG_FILE = "config.yaml"
with open(CONFIG_FILE, "r", encoding="utf-8-sig") as f:
    config = yaml.safe_load(f)

YOUTUBE = config.get("youtube", {})
EXTRALIFE = config.get("extra-life", {})

CHAT_FILE = YOUTUBE.get("chatfile", "youtube-chat.txt")
CHAT_FULL_FILE = YOUTUBE.get("chatfile_full", "youtube-chat-full.txt")
DONORS_FILE = EXTRALIFE.get("donors-file", "extra-life-donors.txt")
VIDEO_ID = YOUTUBE.get("video-id")
HOST = YOUTUBE.get("host", "").lower()

UPDATE_INTERVAL = EXTRALIFE.get("update-interval", 10)
PARTICIPANT_ID = EXTRALIFE.get("participant-id")
per_user_cooldown = EXTRALIFE.get("per-user-cooldown", 60)
global_cooldown = EXTRALIFE.get("global-cooldown", 5)

# ================= STATE =================
donors = {}
last_user_swap = {}
last_global_swap = datetime.min
locked = False
lock_timer = None
banned_users = set()
full_chat_queue = deque()
swap_chat_queue = deque()
send_message_queue = deque()
write_lock = threading.Lock()
WRITE_INTERVAL = 1

PLAYED_GAME_FILE = "youtube-played.txt"

# ================= HELPERS =================
def normalize_name(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())

def is_donor(username):
    username_norm = normalize_name(username)
    if username_norm == normalize_name(HOST):
        return True
    return any(username_norm == normalize_name(donor) for donor in donors)

def fetch_donors():
    url = f"https://extra-life.donordrive.com/api/participants/{PARTICIPANT_ID}/donations"
    try:
        resp = requests.get(url)
        resp.raise_for_status()
        data = resp.json()
        donors.clear()
        for donation in data:
            name = donation.get("displayName", "").strip()
            amount = donation.get("amount", 0)
            donors[name] = amount
        with open(DONORS_FILE, "w", encoding="utf-8") as f:
            for name, amt in donors.items():
                f.write(f"{name}: ${amt:.2f}\n")
        print(f"[INFO] Loaded donors: {len(donors)}")
    except Exception as e:
        print(f"[ERROR] Failed to fetch donors: {e}")

def can_play(username):
    global last_global_swap
    now = datetime.now()
    username_lower = username.lower()
    if (now - last_global_swap).total_seconds() < global_cooldown:
        return False, "Global cooldown"
    if normalize_name(username) != normalize_name(HOST):
        if locked: return False, "Locked"
        if username_lower in banned_users: return False, "Banned"
        if not is_donor(username): return False, "Not a donor"
        last = last_user_swap.get(username_lower, datetime.min)
        if (now - last).total_seconds() < per_user_cooldown:
            return False, "User cooldown"
    return True, ""

def record_play(username):
    global last_global_swap
    now = datetime.now()
    last_global_swap = now
    last_user_swap[username.lower()] = now

def unlock():
    global locked, lock_timer
    locked = False
    if lock_timer:
        lock_timer.cancel()
        lock_timer = None
    print("[INFO] Plays unlocked by host")

def enqueue_write(author, message, play=False):
    author_clean = author.lstrip("@")
    with write_lock:
        full_chat_queue.append(f"{author_clean}: {message}\n")
        if play:
            swap_chat_queue.append(f"{author_clean}: {message}\n")

def process_message(author, message):
    author_clean = author.lstrip("@")
    msg_lower = message.lower().strip()
    # Host commands
    if normalize_name(author) == normalize_name(HOST):
        if msg_lower.startswith("!ban"):
            parts = msg_lower.split()
            if len(parts) == 2:
                banned_users.add(parts[1].lower())
                print(f"[INFO] {parts[1]} banned by host")
            return
        elif msg_lower.startswith("!cooldown"):
            parts = msg_lower.split()
            if len(parts) == 2 and parts[1].isdigit():
                global per_user_cooldown
                per_user_cooldown = int(parts[1])
                print(f"[INFO] Per-user cooldown set to {per_user_cooldown} seconds")
            return
        elif msg_lower.startswith("!lock"):
            global locked, lock_timer
            locked = True
            print("[INFO] Plays locked by host")
            parts = msg_lower.split()
            if len(parts) == 2 and parts[1].isdigit():
                minutes = int(parts[1])
                if lock_timer: lock_timer.cancel()
                lock_timer = threading.Timer(minutes*60, unlock)
                lock_timer.start()
            return
        elif msg_lower.startswith("!unlock"):
            unlock()
            return
    # Play/Swap
    if msg_lower.startswith("!play") or msg_lower.startswith("!swap"):
        ok, reason = can_play(author_clean)
        if not ok:
            print(f"[IGNORED] @{author_clean}: {message} [{reason}]")
            enqueue_write(author_clean, message)
            return
        record_play(author_clean)
        enqueue_write(author_clean, message, play=True)
        print(f"[PLAY/SWAP] @{author_clean}: {message}")
    else:
        enqueue_write(author_clean, message)
        print(f"[CHAT] @{author_clean}: {message}")

# ================= WRITERS =================
def writer_thread():
    while True:
        time.sleep(WRITE_INTERVAL)
        with write_lock:
            if full_chat_queue:
                with open(CHAT_FULL_FILE, "a", encoding="utf-8") as f: f.writelines(full_chat_queue)
                full_chat_queue.clear()
            if swap_chat_queue:
                with open(CHAT_FILE, "a", encoding="utf-8") as f: f.writelines(swap_chat_queue)
                swap_chat_queue.clear()

# ================= PLAYED GAME WATCHER =================
def played_game_watcher():
    """Watch the played-game file written by Lua and enqueue messages for YouTube chat."""
    last_line_index = 0
    while True:
        try:
            with open(YOUTUBE.get('playedfile', 'youtube-played.txt'), 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except FileNotFoundError:
            lines = []

        new_lines = lines[last_line_index:]
        last_line_index = len(lines)

        for line in new_lines:
            line = line.strip()
            if not line:
                continue
            try:
                username, game = line.split(":", 1)
                username = username.strip()
                game = game.strip()

                if game == "__NO_MATCH__":
                    send_message_queue.append(f"@{username} No matching game found!")
                    print(f"[INFO] No match for user '{username}'")
                else:
                    send_message_queue.append(f"@{username} triggered a play: {game}")
                    print(f"[INFO] User '{username}' matched game: {game}")

            except ValueError:
                print(f"[WARN] Malformed line in played-game file: {line}")

        time.sleep(0.1)  # Small delay to avoid busy-looping


# ================= MESSAGE SENDER =================
def message_sender(youtube_service, live_chat_id):
    while True:
        if send_message_queue:
            try:
                batch = []
                while send_message_queue and len(batch) < 5:
                    batch.append(send_message_queue.popleft())
                msg_text = " | ".join(batch)
                if live_chat_id:
                    youtube_service.liveChatMessages().insert(
                        part="snippet",
                        body={
                            "snippet": {
                                "liveChatId": live_chat_id,
                                "type": "textMessageEvent",
                                "textMessageDetails": {"messageText": msg_text},
                            }
                        },
                    ).execute()
                    print(f"[SEND] {msg_text}")
                else:
                    print(f"[SKIP] Cannot send message (no live chat): {msg_text}")
            except Exception as e:
                print(f"[ERROR] Failed to send message: {e}")
        time.sleep(0.1)

# ================= YOUTUBE SERVICE =================
SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]
def get_youtube_service():
    creds = None
    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as f: creds = pickle.load(f)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token: creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.pickle", "wb") as f: pickle.dump(creds, f)
    return build("youtube", "v3", credentials=creds)

def get_live_chat_id_or_fallback(youtube_service, video_id):
    try:
        resp = youtube_service.videos().list(part="liveStreamingDetails", id=video_id).execute()
        items = resp.get("items", [])
        if not items:
            raise ValueError(f"Video {video_id} not found")
        live_details = items[0].get("liveStreamingDetails", {})
        live_chat_id = live_details.get("activeLiveChatId")
        if live_chat_id:
            print(f"[INFO] Connected to live chat ID: {live_chat_id}")
            return live_chat_id
        else:
            raise ValueError("Video not currently live")
    except Exception as e:
        print(f"[WARN] Could not connect to live chat: {e}")
        print(f"[INFO] Falling back to YAML video ID: {video_id}")
        return None

# ================= CHAT LISTENER =================
def youtube_chat_listener(video_id):
    while True:
        try:
            chat = pytchat.create(video_id=video_id)
            print(f"[INFO] Connected to YouTube video: {video_id}")
            while chat.is_alive():
                for c in chat.get().sync_items(): process_message(c.author.name, c.message)
                time.sleep(0.05)
        except Exception as e:
            print(f"[ERROR] Chat connection failed: {e}. Reconnecting in 5s...")
            time.sleep(5)

# ================= DONOR UPDATER =================
def donor_updater():
    while True:
        fetch_donors()
        time.sleep(UPDATE_INTERVAL * 60)

# ================= MAIN =================
if __name__ == "__main__":
    open(CHAT_FILE, "w").close()
    open(CHAT_FULL_FILE, "w").close()
    donors.clear()
    banned_users.clear()
    fetch_donors()

    youtube_service = get_youtube_service()
    live_chat_id = get_live_chat_id_or_fallback(youtube_service, VIDEO_ID)

    # Hello world
    send_message_queue.append("Hello, world!")

    # Threads
    threading.Thread(target=donor_updater, daemon=True).start()
    threading.Thread(target=writer_thread, daemon=True).start()
    threading.Thread(target=played_game_watcher, daemon=True).start()
    threading.Thread(target=message_sender, args=(youtube_service, live_chat_id), daemon=True).start()

    youtube_chat_listener(VIDEO_ID)
