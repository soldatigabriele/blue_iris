import os
import subprocess
import time
from datetime import datetime

WATCH_FOLDER = r"C:\BlueIris\Telegram_Alerts_SSD"
MAX_RETRIES = 20
RETRY_DELAY = 3  # seconds
LOG_FILE = os.path.join(WATCH_FOLDER, "log.txt")

def log(msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    with open(LOG_FILE, "a") as f:
        f.write(f"[{timestamp}] {msg}\n")
    print(f"[{timestamp}] {msg}")


def ffmpeg_convert(input_path, output_path):
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i", input_path,
                "-vf", "fps=10,scale=480:-1:flags=lanczos",
                output_path
            ],
            capture_output=True,
            text=True
        )
        log(result.stdout)
        log(result.stderr)
        return "out#0/gif" in result.stdout or "out#0/gif" in result.stderr
    except Exception as e:
        log(f"Exception while running ffmpeg: {e}")
        return False


def process_avi_files():
    log("--- Script run started ---")
    files = [f for f in os.listdir(WATCH_FOLDER) if f.lower().endswith(".avi")]

    if not files:
        log("No .avi files found.")
        return

    for filename in files:
        avi_path = os.path.join(WATCH_FOLDER, filename)
        gif_path = os.path.splitext(avi_path)[0] + ".gif"

        if os.path.exists(gif_path):
            log(f"Skipping {filename}, GIF already exists.")
            continue

        success = False
        for attempt in range(1, MAX_RETRIES + 1):
            log(f"Attempt {attempt} to convert {filename}...")
            success = ffmpeg_convert(avi_path, gif_path)
            if success:
                log(f"Success: {filename} converted to GIF.")
                break
            else:
                log(f"Conversion failed. Retrying in {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)

        if not success:
            log(f"Failed to convert {filename} after {MAX_RETRIES} attempts. Skipping.")

    log("--- Script run finished ---")


if __name__ == "__main__":
    process_avi_files()
