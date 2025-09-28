import os
import openai
import requests
import json
import datetime
import logging
import random
from PIL import Image, ImageDraw, ImageFont

# --- Konfigurasjon ---
openai.api_key = os.getenv("OPENAI_API_KEY")
ACCESS_TOKEN = os.getenv("LONG_LIVED_USER_TOKEN")  # Token med instagram_content_publish
IG_USER_ID = os.getenv("IG_USER_ID")               # Instagram Business/Creator ID
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GRAPH_API_VERSION = "v19.0"

# --- Logging ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# --- Hjelpefunksjoner ---
def send_telegram(message, photo=None):
    try:
        if photo:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
            with open(photo, "rb") as f:
                files = {"photo": f}
                data = {"chat_id": TELEGRAM_CHAT_ID, "caption": message}
                r = requests.post(url, data=data, files=files)
        else:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
            r = requests.post(url, data=data)
        logging.info(f"Telegram sendt: {r.status_code}")
    except Exception as e:
        logging.error(f"Feil ved sending til Telegram: {e}")

# --- Generering av refleksjon ---
def generate_reflection():
    prompt = (
        "Write a short, poetic and uplifting reflection (max 2 lines) for a daily post. "
        "It should be timeless, universal, and offer hope and courage. "
        "Use simple, clear language. Do not mention religion directly."
    )
    resp = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role":"user","content":prompt}]
    )
    return resp.choices[0].message.content.strip()

def generate_hashtags():
    possible_tags = ["#Love", "#Hope", "#Peace", "#Kindness", "#Inspiration", "#Courage"]
    return " ".join(random.sample(possible_tags, k=random.randint(4,6)))

def generate_image(reflection_text):
    img_prompt = (
        "A symbolic, poetic image representing hope, love and human connection. "
        "Soft natural light, artistic, cinematic style, uplifting."
    )
    img_response = openai.images.generate(model="dall-e-3", prompt=img_prompt, size="1024x1024")
    img_url = img_response.data[0].url
    img_file = f"reflection_{datetime.date.today()}.png"
    with open(img_file, "wb") as f:
        f.write(requests.get(img_url).content)
    return img_url, img_file

def post_to_instagram(caption, img_url):
    try:
        upload_url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{IG_USER_ID}/media"
        params = {"image_url": img_url, "caption": caption, "access_token": ACCESS_TOKEN}
        r = requests.post(upload_url, params=params)
        logging.info(f"Instagram upload response: {r.text}")
        container_id = r.json().get("id")
        if not container_id:
            raise Exception(r.json())
        publish_url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{IG_USER_ID}/media_publish"
        r2 = requests.post(publish_url, params={"creation_id": container_id, "access_token": ACCESS_TOKEN})
        logging.info(f"Instagram publish response: {r2.text}")
        if r2.status_code != 200:
            raise Exception(r2.json())
        return True
    except Exception as e:
        logging.error(f"Instagram error: {e}")
        send_telegram(f"⚠️ Feil under posting til Instagram: {e}")
        return False

# --- Main ---
if __name__ == "__main__":
    reflection = generate_reflection()
    hashtags = generate_hashtags()
    full_caption = f"🌍 Reflection of the day\n\n{reflection}\n\n{hashtags}"
    img_url, img_file = generate_image(reflection)

    # Telegram
    send_telegram(full_caption, photo=img_file)

    # Instagram
    if post_to_instagram(full_caption, img_url):
        logging.info("✅ Instagram postet")
    else:
        logging.warning("❌ Instagram post feilet")
