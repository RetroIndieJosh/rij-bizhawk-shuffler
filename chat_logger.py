import pytchat
import time

# Load the YouTube URL from a file
with open("youtube-url.txt", "r") as f:
    YOUTUBE_URL = f.read().strip()

OUTPUT_FILE = "youtube-chat.txt"
COOLDOWN = 60  # seconds per user
last_swap_by_user = {}

# Clear the output file at startup
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    pass  # open and close to empty the file

chat = pytchat.create(video_id=YOUTUBE_URL)

print(f"Listening to chat on {YOUTUBE_URL}...")

while chat.is_alive():
    for c in chat.get().sync_items():
        username = c.author.name
        message = c.message.strip()

        # Print every message to console
        print(f"{username}: {message}")

        # Only log !swap messages to file with per-user cooldown
        if message.lower() == "!swap":
            current_time = time.time()
            last_time = last_swap_by_user.get(username, 0)
            if current_time - last_time >= COOLDOWN:
                last_swap_by_user[username] = current_time
                with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
                    f.write(f"{username}: !swap\n")
                    f.flush()
