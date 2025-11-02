import pytchat
import time

# Load the YouTube URL from a file
with open("youtube-url.txt", "r") as f:
    YOUTUBE_URL = f.read().strip()

OUTPUT_FILE = "youtube-chat.txt"
PER_USER_COOLDOWN = 60  # seconds per user (ignored for RetroIndieJosh)
GLOBAL_COOLDOWN = 5     # seconds for everyone
last_swap_by_user = {}
last_global_swap = 0

# Clear the output file at startup
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    pass

chat = pytchat.create(video_id=YOUTUBE_URL)

print(f"Listening to chat on {YOUTUBE_URL}...")

while chat.is_alive():
    for c in chat.get().sync_items():
        username = c.author.name.strip().lstrip("@")
        message = c.message.strip()

        # Print all messages
        print(f"{username}: {message}")

        # Only act on exact "!swap"
        if message.lower() == "!swap":
            current_time = time.time()

            # Enforce global cooldown for everyone
            if current_time - last_global_swap < GLOBAL_COOLDOWN:
                continue

            # Enforce per-user cooldown for everyone except RetroIndieJosh
            if username != "RetroIndieJosh":
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
