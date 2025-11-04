import yaml
import pytchat
import time
import threading
from datetime import datetime
from collections import deque
import re
import requests
import os
import pickle
import sys

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# ================= Load Config =================
CONFIG_FILE = "config.yaml"
with open(CONFIG_FILE, "r") as f:
    config = yaml.safe_load(f)

YOUTUBE = config['youtube']
EXTRALIFE = config['extra-life']

CHAT_FILE = YOUTUBE.get('chatfile', 'youtube-chat.txt')
CHAT_FULL_FILE = YOUTUBE.get('chatfile_full', 'youtube-chat-full.txt')
DONORS_FILE = EXTRALIFE.get('donors-file', 'extra-life-donors.txt')

HOST = YOUTUBE['host'].lower()

UPDATE_INTERVAL = EXTRALIFE.get('update-interval', 10)
PARTICIPANT_ID = EXTRALIFE['participant-id']

per_user_cooldown = EXTRALIFE.get('per-user-cooldown', 60)
global_cooldown = EXTRALIFE.get('global-cooldown', 5)

# ================= State =================
donors = {}
last_user_swap = {}
last_global_swap = datetime.min
locked = False
lock_timer = None
banned_users = set()

# Queues
full_chat_queue = deque()
swap_chat_queue = deque()
send_message_queue = deque()
write_lock = threading.Lock()
WRITE_INTERVAL = 1  # seconds

# ================= Helper Functions =================
def normalize_name(name):
    return re.sub(r'[^a-z0-9]', '', name.lower())

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
            name = donation.get('displayName', '').strip()
            amount = donation.get('amount', 0)
            donors[name] = amount
        with open(DONORS_FILE, 'w', encoding='utf-8') as f:
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
        if locked:
            return False, "Locked"
        if username_lower in banned_users:
            return False, "Banned"
        if not is_donor(username):
            return False, "Not a donor"
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
    print(f"[INFO] Plays unlocked by host")

def enqueue_write(author, message, play=False):
    author_clean = author.lstrip('@')
    with write_lock:
        full_chat_queue.append(f"{author_clean}: {message}\n")
        if play:
            swap_chat_queue.append(f"{author_clean}: {message}\n")
            send_message_queue.append(f"{author_clean} triggered a play!")

def process_message(author, message):
    author_clean = author.lstrip('@')
    author_lower = author_clean.lower()
    msg_lower = message.lower().strip()

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
            print(f"[INFO] Plays locked by host")
            parts = msg_lower.split()
            if len(parts) == 2 and parts[1].isdigit():
                minutes = int(parts[1])
                if lock_timer:
                    lock_timer.cancel()
                lock_timer = threading.Timer(minutes*60, unlock)
                lock_timer.start()
            return
        elif msg_lower.startswith("!unlock"):
            unlock()
            return

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

# ================= Writer Thread =================
def writer_thread():
    while True:
        time.sleep(WRITE_INTERVAL)
        with write_lock:
            if full_chat_queue:
                with open(CHAT_FULL_FILE, 'a', encoding='utf-8') as f:
                    f.writelines(full_chat_queue)
                full_chat_queue.clear()
            if swap_chat_queue:
                with open(CHAT_FILE, 'a', encoding='utf-8') as f:
                    f.writelines(swap_chat_queue)
                swap_chat_queue.clear()

# ================= Donor Updater Thread =================
def donor_updater():
    while True:
        fetch_donors()
        time.sleep(UPDATE_INTERVAL * 60)

# ================= YouTube API Setup =================
SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]

def get_youtube_service():
    creds = None
    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.pickle", "wb") as token:
            pickle.dump(creds, token)
    return build("youtube", "v3", credentials=creds)

# ================= Updated Live Detection =================
def get_current_live_video(youtube):
    """
    Returns the video ID of the currently active live stream on your channel.
    Works for public or unlisted streams.
    """
    response = youtube.liveBroadcasts().list(
        part="id,snippet",
        mine=True
    ).execute()

    items = response.get("items", [])
    active_items = [i for i in items if i.get('snippet', {}).get('liveBroadcastContent') == 'live']

    if not active_items:
        raise ValueError("No active live stream found on this channel")

    return active_items[0]['id']

def get_live_chat_id(youtube, video_id):
    response = youtube.videos().list(part="liveStreamingDetails", id=video_id).execute()
    items = response.get("items", [])
    if not items:
        raise ValueError(f"No video found with ID {video_id}")

    live_details = items[0].get("liveStreamingDetails", {})
    live_chat_id = live_details.get("activeLiveChatId")
    actual_start = live_details.get("actualStartTime")

    if not live_chat_id or not actual_start:
        raise ValueError(f"Video {video_id} is not currently live")

    return live_chat_id

def send_message(youtube, live_chat_id, text):
    try:
        youtube.liveChatMessages().insert(
            part="snippet",
            body={
                "snippet": {
                    "liveChatId": live_chat_id,
                    "type": "textMessageEvent",
                    "textMessageDetails": {"messageText": text}
                }
            }
        ).execute()
    except Exception as e:
        print(f"[ERROR] Failed to send message: {e}")

def message_sender(youtube, live_chat_id):
    while True:
        if send_message_queue:
            batch = []
            with write_lock:
                while send_message_queue and len(batch) < 5:
                    batch.append(send_message_queue.popleft())
            msg_text = " | ".join(batch)
            send_message(youtube, live_chat_id, msg_text)
            time.sleep(3)
        else:
            time.sleep(1)

def youtube_chat_listener(video_id):
    while True:
        try:
            chat = pytchat.create(video_id=video_id)
            print(f"[INFO] Connected to YouTube video: {video_id}")
            while chat.is_alive():
                for c in chat.get().sync_items():
                    process_message(c.author.name, c.message)
                time.sleep(0.05)
        except Exception as e:
            print(f"[ERROR] Chat connection failed: {e}. Reconnecting in 5 seconds...")
            time.sleep(5)

# ================= Main =================
if __name__ == "__main__":
    # Clear old files
    open(CHAT_FILE, 'w').close()
    open(CHAT_FULL_FILE, 'w').close()
    donors.clear()
    banned_users.clear()

    fetch_donors()
    youtube_service = get_youtube_service()

    # Attempt to detect currently live video automatically
    VIDEO_ID = None
    try:
        VIDEO_ID = get_current_live_video(youtube_service)
        print(f"[INFO] Connected to live video: {VIDEO_ID}")
    except ValueError as e:
        # Fallback to video-id defined in YAML
        VIDEO_ID = YOUTUBE.get("video-id")
        if VIDEO_ID:
            print(f"[WARNING] No active live stream detected. "
                  f"Falling back to video-id from config.yaml: {VIDEO_ID}")
        else:
            print(f"[ERROR] No active live stream found and no fallback video-id defined. Exiting bot.")
            sys.exit(1)

    # Confirm live chat is active
    try:
        live_chat_id = get_live_chat_id(youtube_service, VIDEO_ID)
    except ValueError as e:
        print(f"[ERROR] Video {VIDEO_ID} is not currently live. Cannot connect to live chat. Exiting bot.")
        sys.exit(1)

    print(f"[INFO] Live chat ID: {live_chat_id}")

    # Send initial greeting
    send_message(youtube_service, live_chat_id, "Hello, world!")

    # Start threads
    threading.Thread(target=donor_updater, daemon=True).start()
    threading.Thread(target=writer_thread, daemon=True).start()
    threading.Thread(target=message_sender, args=(youtube_service, live_chat_id), daemon=True).start()

    # Start chat listener (blocks here)
    youtube_chat_listener(VIDEO_ID)
