import os
import subprocess
import time
import requests
from datetime import datetime
from dotenv import load_dotenv

WATCH_FOLDER = r"C:\BlueIris\Telegram_Alerts_SSD"
LOGS_FOLDER = r"C:\BlueIris\Scripts\logs"
os.makedirs(LOGS_FOLDER, exist_ok=True)

MAX_RETRIES = 20
RETRY_DELAY = 3
LOG_FILE = os.path.join(LOGS_FOLDER, "log.txt")
PROCESSED_FILE = os.path.join(LOGS_FOLDER, "processed.txt")

# Load .env variables
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def log(msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    with open(LOG_FILE, "a") as f:
        f.write(f"[{timestamp}] {msg}\n")
    print(f"[{timestamp}] {msg}")


def load_processed():
    if not os.path.exists(PROCESSED_FILE):
        return set()
    with open(PROCESSED_FILE, "r") as f:
        return set(line.strip() for line in f.readlines())


def mark_processed(name):
    with open(PROCESSED_FILE, "a") as f:
        f.write(name + "\n")


def extract_timestamp(filename):
    try:
        parts = filename.split(".")
        if len(parts) < 2:
            return None
        return parts[1]
    except Exception:
        return None


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


def upload_to_telegram(file_path):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
    try:
        with open(file_path, "rb") as doc:
            response = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "disable_notification": True}, files={"document": doc})
        if response.status_code == 200:
            log(f"GIF uploaded to Telegram: {file_path}")
            return True
        else:
            log(f"Telegram upload failed: {response.status_code} {response.text}")
            return False
    except Exception as e:
        log(f"Exception during Telegram upload: {e}")
        return False


def process_next_unprocessed_file():
    log("--- Script run started ---")
    processed = load_processed()
    avi_files = sorted(f for f in os.listdir(WATCH_FOLDER) if f.lower().endswith(".avi"))

    for filename in avi_files:
        if filename in processed:
            continue

        timestamp = extract_timestamp(filename)
        if not timestamp:
            log(f"Invalid filename format: {filename}, skipping.")
            mark_processed(filename)
            return

        avi_path = os.path.join(WATCH_FOLDER, filename)
        gif_path = os.path.splitext(avi_path)[0] + ".gif"

        log(f"Processing new file: {filename}")
        mark_processed(filename)  # Immediately mark as seen

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
            log(f"Failed to convert {filename} after {MAX_RETRIES} attempts.")
            
            # Send Telegram message on failure
            error_message = f"❌ Failed to convert video to GIF:\n{filename}"
            try:
                response = requests.post(
                    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                    data={"chat_id": TELEGRAM_CHAT_ID, "text": error_message, "disable_notification": False}
                )
                if response.status_code == 200:
                    log("Sent failure notification to Telegram.")
                else:
                    log(f"Failed to send failure notification: {response.status_code} {response.text}")
            except Exception as e:
                log(f"Exception while sending failure notification: {e}")
            return

        # Upload
        if upload_to_telegram(gif_path):
            try:
                os.remove(gif_path)
                os.remove(avi_path)
                log(f"Deleted {gif_path} and {avi_path}")
            except Exception as e:
                log(f"Error deleting files: {e}")

        break  # Only process the first unprocessed file

    log("--- Script run finished ---")


if __name__ == "__main__":
    process_next_unprocessed_file()
