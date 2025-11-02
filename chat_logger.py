"""
YouTube Chat Logger for BizHawk Chat Swap Plugin
Requires: pytchat (pip install pytchat)
Only writes messages that are exactly "!swap".
"""

import pytchat
import time
import os

# ===== CONFIG =====
VIDEO_ID = "VIDEO ID HERE"        # Replace with your YouTube live video ID
OUTPUT_FILE = "youtube-chat.txt"  # Path to your plugin chat file
# ==================

def main():
    # Ensure file exists
    if not os.path.exists(OUTPUT_FILE):
        open(OUTPUT_FILE, "w", encoding="utf-8").close()

    chat = pytchat.create(video_id=VIDEO_ID, interruptable=False)
    print(f"Logging !swap messages from video {VIDEO_ID} to {OUTPUT_FILE}...")

    try:
        while chat.is_alive():
            for c in chat.get().sync_items():
                message = c.message.strip().lower()
                if message == "!swap":
                    # Append message to file
                    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
                        f.write("!swap\n")
                        f.flush()  # ensure plugin reads it immediately
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("Stopping chat logger...")
    finally:
        chat.terminate()


if __name__ == "__main__":
    main()
