import os
import subprocess
import time
import requests
from datetime import datetime
from dotenv import load_dotenv

AVI_FOLDER = r"C:\BlueIris\Telegram_Alerts_SSD"
JPG_FOLDER = r"C:\BlueIris\Telegram_Alerts_SSD_jpgs"
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
    # with open(LOG_FILE, "a") as f:
    #     f.write(f"[{timestamp}] {msg}\n")
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
                "-vf", "setpts=0.5*PTS,fps=15,scale=480:-1:flags=lanczos",
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


def ffmpeg_convert(input_path, output_path):
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i", input_path,
                "-an",  # remove audio
                "-vf", "setpts=0.5*PTS,fps=15,scale=480:-1:flags=lanczos",
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "28",
                "-movflags", "+faststart",
                output_path
            ],
            capture_output=True,
            text=True
        )
        log(result.stdout)
        log(result.stderr)
        return result.returncode == 0
    except Exception as e:
        log(f"Exception while running ffmpeg: {e}")
        return False

def upload_to_telegram(file_path):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
    try:
        with open(file_path, "rb") as video:
            response = requests.post(
                url,
                data={"chat_id": TELEGRAM_CHAT_ID, "disable_notification": True},
                files={"video": video}
            )
        if response.status_code == 200:
            log(f"Video uploaded to Telegram: {file_path}")
            return True
        else:
            log(f"Telegram upload failed: {response.status_code} {response.text}")
            return False
    except Exception as e:
        log(f"Exception during Telegram upload: {e}")
        return False

# def upload_to_telegram(file_path):
#     url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
#     try:
#         with open(file_path, "rb") as doc:
#             response = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "disable_notification": True}, files={"document": doc})
#         if response.status_code == 200:
#             log(f"GIF uploaded to Telegram: {file_path}")
#             return True
#         else:
#             log(f"Telegram upload failed: {response.status_code} {response.text}")
#             return False
#     except Exception as e:
#         log(f"Exception during Telegram upload: {e}")
#         return False


def process_jpeg_images():
    log("--- JPEG processing started ---")
    jpeg_files = sorted(
        f for f in os.listdir(JPG_FOLDER)
        if f.lower().endswith((".jpg", ".jpeg"))
    )

    for filename in jpeg_files:

        jpeg_path = os.path.join(JPG_FOLDER, filename)
        log(f"Processing JPEG: {filename}")

        try:
            with open(jpeg_path, "rb") as img:
                response = requests.post(
                    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto",
                    data={"chat_id": TELEGRAM_CHAT_ID, "disable_notification": True},
                    files={"photo": img}
                )

            if response.status_code == 200:
                log(f"JPEG uploaded to Telegram: {filename}")
                os.remove(jpeg_path)
                log(f"Deleted JPEG: {jpeg_path}")
            else:
                log(f"Failed to upload JPEG: {response.status_code} {response.text}")
        except Exception as e:
            log(f"Exception while processing JPEG {filename}: {e}")

    log("--- JPEG processing finished ---")

def process_avi_videos():
    log("--- Script run started ---")
    avi_files = sorted(f for f in os.listdir(AVI_FOLDER) if f.lower().endswith(".avi"))

    for filename in avi_files:

        timestamp = extract_timestamp(filename)
        if not timestamp:
            log(f"Invalid filename format: {filename}, skipping.")
            continue  # Skip and move to the next file

        avi_path = os.path.join(AVI_FOLDER, filename)
        # gif_path = os.path.splitext(avi_path)[0] + ".gif"
        gif_path = os.path.splitext(avi_path)[0] + ".mp4"
    

        log(f"Processing new file: {filename}")

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
            continue  # Move on to the next file even if this one failed

        # Upload
        if upload_to_telegram(gif_path):
            try:
                os.remove(gif_path)
                os.remove(avi_path)
                log(f"Deleted {gif_path} and {avi_path}")
            except Exception as e:
                log(f"Error deleting files: {e}")

    log("--- Script run finished ---")


if __name__ == "__main__":
    process_jpeg_images()
    process_avi_videos()
