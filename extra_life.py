import yaml
import time
import threading
from datetime import datetime, timedelta
from collections import deque
import re
import requests
import pytchat
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# ================= Load Config =================
CONFIG_FILE = "config.yaml"
with open(CONFIG_FILE, "r", encoding="utf-8-sig") as f:
    config = yaml.safe_load(f)

YOUTUBE = config.get("youtube", {})
EXTRALIFE = config.get("extra-life", {})

CHAT_FILE = YOUTUBE.get('chatfile', 'youtube-chat.txt')
FULL_CHAT_FILE = YOUTUBE.get('chatfile_full', 'youtube-chat-full.txt')
PLAYED_FILE = YOUTUBE.get('playedfile', 'youtube-played.txt')
VIDEO_ID_FALLBACK = YOUTUBE.get('video-id')
CHANNEL_ID = YOUTUBE.get('channel-id')
HOST = YOUTUBE.get('host', '').lower()
GAMES_FILE = YOUTUBE.get('gamesfile', 'games/.games-list.txt')

# ================= Moderation Config =================
PER_USER_COOLDOWN = EXTRALIFE.get('per-user-cooldown', 60)
GLOBAL_COOLDOWN = EXTRALIFE.get('global-cooldown', 5)
STRIKES_BEFORE_TIMEOUT = EXTRALIFE.get('strikes-before-timeout', 3)
TIMEOUT_MULTIPLIER = EXTRALIFE.get('timeout-multiplier', 10)
TIMEOUTS_BEFORE_BAN = EXTRALIFE.get('timeouts-before-ban', 3)
CONSECUTIVE_COMMANDS_ENABLED = EXTRALIFE.get('consecutive-commands-enabled', True)

# ================= State =================
last_user_swap = {}
last_global_swap = datetime.min
strikes = {}
timeouts = {}
user_timeouts_count = {}
locked = False
lock_timer = None
donors = {}
games_list = []

LIVE_CHAT_ID = None
YOUTUBE_SERVICE = None

# ================= Queues =================
full_chat_queue = deque()
swap_chat_queue = deque()
send_message_queue = deque()
write_lock = threading.Lock()
WRITE_INTERVAL = 1  # seconds

# ================= Helper Functions =================
def normalize_name(name):
    return re.sub(r'[^a-z0-9]', '', name.lower())

def fetch_donors():
    url = f"https://extra-life.donordrive.com/api/participants/{EXTRALIFE['participant-id']}/donations"
    try:
        resp = requests.get(url)
        resp.raise_for_status()
        data = resp.json()
        donors.clear()
        for donation in data:
            name = donation.get('displayName', '').strip()
            donors[name] = donation.get('amount', 0)
        print(f"[INFO] Loaded donors: {len(donors)}")
    except Exception as e:
        print(f"[ERROR] Failed to fetch donors: {e}")

def is_donor(username):
    username_norm = normalize_name(username)
    if username_norm == normalize_name(HOST):
        return True
    return any(username_norm == normalize_name(donor) for donor in donors)

def enqueue_write(author, message, play=False):
    author_clean = author.lstrip('@')
    with write_lock:
        full_chat_queue.append(f"{author_clean}: {message}\n")
        if play:
            swap_chat_queue.append(f"{author_clean}: {message}\n")

def send_chat_message(message):
    send_message_queue.append(message)

def get_remaining_cooldown(username):
    now = datetime.now()
    user_last = last_user_swap.get(username.lower(), datetime.min)
    return max(0, PER_USER_COOLDOWN - (now - user_last).total_seconds())

def get_remaining_timeout(username):
    now = datetime.now()
    timeout_exp = timeouts.get(username.lower(), datetime.min)
    return max(0, (timeout_exp - now).total_seconds())

def apply_strike(username, reason):
    username_lower = username.lower()
    strikes[username_lower] = strikes.get(username_lower, 0) + 1
    print(f"[STRIKE] {username} received a strike for {reason}. Total: {strikes[username_lower]}")
    if strikes[username_lower] >= STRIKES_BEFORE_TIMEOUT:
        strikes[username_lower] = 0
        apply_timeout(username)

def apply_timeout(username):
    username_lower = username.lower()
    now = datetime.now()
    duration = PER_USER_COOLDOWN * TIMEOUT_MULTIPLIER
    if username_lower in timeouts and get_remaining_timeout(username) > 0:
        user_timeouts_count[username_lower] = user_timeouts_count.get(username_lower, 0) + 1
        if user_timeouts_count[username_lower] >= TIMEOUTS_BEFORE_BAN:
            send_chat_message(f"@{username} has been banned for repeated timeouts.")
            ban_user_youtube(username)
        else:
            timeouts[username_lower] = now + timedelta(seconds=duration)
            send_chat_message(f"@{username} timeout extended by {duration} seconds.")
    else:
        timeouts[username_lower] = now + timedelta(seconds=duration)
        user_timeouts_count[username_lower] = user_timeouts_count.get(username_lower, 0) + 1
        send_chat_message(f"@{username} is now timed out for {duration} seconds.")

def ban_user_youtube(username):
    if not LIVE_CHAT_ID:
        print(f"[WARN] Cannot ban {username}, no live chat ID.")
        return
    try:
        YOUTUBE_SERVICE.liveChatBans().insert(
            part="snippet",
            body={
                "snippet": {
                    "liveChatId": LIVE_CHAT_ID,
                    "type": "permanent",
                    "bannedUserDetails": {"displayName": username}
                }
            }
        ).execute()
        print(f"[BAN] {username} banned successfully.")
        send_chat_message(f"@{username} has been banned.")
    except HttpError as e:
        print(f"[ERROR] Failed to ban {username}: {e}")

# ================= Game Matching =================
def load_games():
    global games_list
    try:
        with open(GAMES_FILE, 'r', encoding='utf-8') as f:
            games_list = [line.strip() for line in f if line.strip() and not line.startswith('.')]
    except FileNotFoundError:
        games_list = []

def normalize_game(name):
    return re.sub(r'[^a-z0-9]', '', name.lower())

def match_game(input_name):
    input_norm = normalize_game(input_name)
    for game in games_list:
        if normalize_game(game) == input_norm:
            return game
    for game in games_list:
        if input_norm in normalize_game(game):
            return game
    return None

# ================= Core Functions =================
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
    send_chat_message("Plays unlocked by host.")
    print("[INFO] Plays unlocked by host.")

def process_message(author, message):
    author_clean = author.lstrip('@')
    author_lower = author_clean.lower()
    msg_lower = message.lower().strip()
    now = datetime.now()

    # Host commands
    global locked, lock_timer
    if normalize_name(author) == normalize_name(HOST):
        if msg_lower.startswith("!lock"):
            locked = True
            parts = msg_lower.split()
            if len(parts) == 2 and parts[1].isdigit():
                minutes = int(parts[1])
                if lock_timer:
                    lock_timer.cancel()
                lock_timer = threading.Timer(minutes*60, unlock)
                lock_timer.start()
            send_chat_message("Plays locked by host.")
            return
        elif msg_lower.startswith("!unlock"):
            unlock()
            return
        elif msg_lower.startswith("!timeout"):
            parts = msg_lower.split()
            if len(parts) == 2:
                apply_timeout(parts[1])
            return
        elif msg_lower.startswith("!ban"):
            parts = msg_lower.split()
            if len(parts) == 2:
                ban_user_youtube(parts[1])
            return

    # Locked / timeout / cooldown checks
    if locked and normalize_name(author) != normalize_name(HOST):
        send_chat_message(f"@{author_clean} Plays are currently locked.")
        return

    if author_lower in timeouts and get_remaining_timeout(author_clean) > 0:
        rem = int(get_remaining_timeout(author_clean))
        send_chat_message(f"@{author_clean} You are timed out. Remaining: {rem}s")
        apply_strike(author_clean, "timeout violation")
        return

    if (now - last_global_swap).total_seconds() < GLOBAL_COOLDOWN:
        send_chat_message(f"@{author_clean} Global cooldown active.")
        return

    rem_cd = get_remaining_cooldown(author_clean)
    if rem_cd > 0:
        send_chat_message(f"@{author_clean} You are on cooldown. Remaining: {int(rem_cd)}s")
        apply_strike(author_clean, "cooldown violation")
        return

    # Handle commands
    if msg_lower.startswith("!play"):
        load_games()
        parts = message.split(maxsplit=1)
        if len(parts) < 2:
            send_chat_message(f"@{author_clean} Please specify a game after !play.")
            return
        requested_game = parts[1].strip()
        matched_game = match_game(requested_game)

        if matched_game:
            record_play(author_clean)
            enqueue_write(author_clean, f"!play {matched_game}", play=True)
            send_chat_message(f"@{author_clean} matched game: {matched_game}")
            with open(PLAYED_FILE, 'a', encoding='utf-8') as f:
                f.write(f"{author_clean}:{matched_game}\n")
        else:
            apply_strike(author_clean, "no match")
            send_chat_message(f"@{author_clean} No match found for '{requested_game}'.")
            with open(PLAYED_FILE, 'a', encoding='utf-8') as f:
                f.write(f"{author_clean}:__NO_MATCH__\n")
        return

    elif msg_lower.startswith("!swap"):
        record_play(author_clean)
        enqueue_write(author_clean, message, play=True)
        send_chat_message(f"@{author_clean} swap command accepted.")
        return

    enqueue_write(author_clean, message)
    print(f"[CHAT] @{author_clean}: {message}")

# ================= Writer / Sender Threads =================
def writer_thread():
    while True:
        time.sleep(WRITE_INTERVAL)
        with write_lock:
            if full_chat_queue:
                with open(FULL_CHAT_FILE, 'a', encoding='utf-8') as f:
                    f.writelines(full_chat_queue)
                full_chat_queue.clear()
            if swap_chat_queue:
                with open(CHAT_FILE, 'a', encoding='utf-8') as f:
                    f.writelines(swap_chat_queue)
                swap_chat_queue.clear()

def chat_sender_thread():
    while True:
        if send_message_queue:
            msg = send_message_queue.popleft()
            if LIVE_CHAT_ID:
                try:
                    YOUTUBE_SERVICE.liveChatMessages().insert(
                        part="snippet",
                        body={
                            "snippet": {
                                "liveChatId": LIVE_CHAT_ID,
                                "type": "textMessageEvent",
                                "textMessageDetails": {"messageText": msg}
                            }
                        }
                    ).execute()
                    print(f"[SEND] {msg}")
                except HttpError as e:
                    print(f"[ERROR] Failed to send chat message: {e}")
            else:
                print(f"[WARN] Cannot send message, no live chat ID: {msg}")
        time.sleep(0.1)

# ================= Lua !play Watcher =================
def played_game_watcher():
    last_index = 0
    while True:
        try:
            with open(PLAYED_FILE, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except FileNotFoundError:
            lines = []

        new_lines = lines[last_index:]
        last_index = len(lines)

        for line in new_lines:
            line = line.strip()
            if not line:
                continue
            try:
                username, game = line.split(":", 1)
                username = username.strip()
                game = game.strip()
                if game == "__NO_MATCH__":
                    send_chat_message(f"@{username} No matching game found.")
                else:
                    record_play(username)
                    enqueue_write(username, f"!play {game}", play=True)
                    send_chat_message(f"@{username} triggered a play: {game}")
            except ValueError:
                print(f"[WARN] Malformed line: {line}")

        time.sleep(0.1)

# ================= Live Stream Detection =================
def init_youtube_api():
    global YOUTUBE_SERVICE, LIVE_CHAT_ID
    creds = Credentials.from_authorized_user_file('credentials.json', ['https://www.googleapis.com/auth/youtube.force-ssl'])
    YOUTUBE_SERVICE = build('youtube', 'v3', credentials=creds)
    live_id = None
    try:
        resp = YOUTUBE_SERVICE.liveBroadcasts().list(
            part='id,snippet',
            broadcastStatus='active',
            mine=True
        ).execute()
        items = resp.get('items', [])
        if items:
            live_id = items[0]['id']
            LIVE_CHAT_ID = items[0]['snippet']['liveChatId']
            print(f"[INFO] Connected to active live broadcast {live_id}")
        else:
            if VIDEO_ID_FALLBACK:
                live_id = VIDEO_ID_FALLBACK
                LIVE_CHAT_ID = None
                print(f"[WARN] No active live stream. Falling back to video-id from YAML: {VIDEO_ID_FALLBACK}")
            else:
                print("[ERROR] No live stream and no fallback video. Exiting.")
                exit(1)
    except HttpError as e:
        print(f"[ERROR] Failed to connect to YouTube API: {e}")
        exit(1)
    return live_id

# ================= YouTube Chat Listener =================
def youtube_chat_listener(video_id):
    while True:
        try:
            chat = pytchat.create(video_id=video_id)
            print(f"[INFO] Listening to YouTube chat for video {video_id}")
            send_chat_message("Hello, world!")
            while chat.is_alive():
                for c in chat.get().sync_items():
                    process_message(c.author.name, c.message)
                time.sleep(0.05)
        except Exception as e:
            print(f"[ERROR] Chat connection failed: {e}. Reconnecting in 5 seconds...")
            time.sleep(5)

# ================= Main =================
if __name__ == "__main__":
    open(CHAT_FILE, 'w').close()
    open(FULL_CHAT_FILE, 'w').close()
    open(PLAYED_FILE, 'w').close()

    fetch_donors()
    load_games()

    init_youtube_api()

    threading.Thread(target=writer_thread, daemon=True).start()
    threading.Thread(target=chat_sender_thread, daemon=True).start()
    threading.Thread(target=played_game_watcher, daemon=True).start()

    youtube_chat_listener(VIDEO_ID_FALLBACK or "")
