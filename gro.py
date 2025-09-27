import os
import openai
import requests
import json
import datetime
import logging
from PIL import Image, ImageDraw, ImageFont
import random

# ======== Configuration ========
openai.api_key = os.getenv("OPENAI_API_KEY")
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN").strip()
PAGE_ID = os.getenv("PAGE_ID").strip()
GRAPH_API_VERSION = "v19.0"
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID").strip()

# Hardkodet Instagram Business ID
IG_USER_ID = "17841476888412461"

# ======== Logging ========
logging.basicConfig(
    filename="bot.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ======== OpenAI Generation ========
def generate_text():
    prompt = """
Write a short, poetic and uplifting reflection (max 2 lines).
It should feel timeless and universal, offering hope and courage.
Use clear, simple words — something anyone can understand.
It must not mention religion directly, but let values of love, care and light shine through.
Return only the reflection text.
"""
    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()

def generate_hashtags():
    possible_tags = ["#Love", "#Hope", "#Peace", "#Kindness", "#Inspiration", "#Courage"]
    return " ".join(random.sample(possible_tags, k=random.randint(4,6)))

def generate_image():
    img_prompt = (
        "A symbolic, poetic image representing hope, love and human connection. "
        "Cinematic style, soft natural light, artistic and uplifting atmosphere."
    )
    img_response = openai.images.generate(
        model="dall-e-3",
        prompt=img_prompt,
        size="1024x1024"
    )
    img_url = img_response.data[0].url
    img_filename = f"reflection_{datetime.date.today()}.png"
    with open(img_filename, "wb") as f:
        f.write(requests.get(img_url).content)
    return img_url, img_filename

def add_love_to_image(image_path):
    img = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arialbd.ttf", 120)
    except:
        font = ImageFont.load_default()
    text = "LOVE"
    bbox = draw.textbbox((0, 0), text, font=font)
    x = (img.width - (bbox[2]-bbox[0])) / 2
    y = (img.height - (bbox[3]-bbox[1])) / 2
    draw.text((x+5, y+5), text, font=font, fill="black")
    draw.text((x, y), text, font=font, fill="white")
    new_path = image_path.replace(".png", "_with_love.png")
    img.save(new_path)
    return new_path

# ======== Telegram ========
def send_telegram(message, photo=None):
    try:
        if photo:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
            with open(photo, "rb") as f:
                files = {"photo": f}
                data = {"chat_id": TELEGRAM_CHAT_ID, "caption": message}
                response = requests.post(url, data=data, files=files)
            if response.status_code != 200:
                logging.warning(f"Telegram photo error: {response.text}")
        else:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
            response = requests.post(url, data=data)
            if response.status_code != 200:
                logging.warning(f"Telegram message error: {response.text}")
        return response.json()
    except Exception as e:
        logging.error(f"Telegram exception: {e}")
        print("Telegram exception:", e)

# ======== Instagram API ========
def create_media_container(image_url, caption):
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{IG_USER_ID}/media"
    params = {"image_url": image_url, "caption": caption, "access_token": PAGE_ACCESS_TOKEN}
    r = requests.post(url, params=params)
    r.raise_for_status()
    return r.json()["id"]

def publish_media(container_id):
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{IG_USER_ID}/media_publish"
    params = {"creation_id": container_id, "access_token": PAGE_ACCESS_TOKEN}
    r = requests.post(url, params=params)
    r.raise_for_status()
    return r.json()

def post_to_instagram(image_url, caption):
    container_id = create_media_container(image_url, caption)
    return publish_media(container_id)

# ======== Main Flow ========
if __name__ == "__main__":
    try:
        text = generate_text()
        hashtags = generate_hashtags()
        img_url, img_file = generate_image()
        final_img = add_love_to_image(img_file)

        full_caption = f"🌍 Reflection of the day\n\n{text}\n\n{hashtags}"

        # Send to Telegram first
        send_telegram(full_caption, photo=final_img)
        logging.info("Sent to Telegram.")
        print("✅ Telegram sent.")

        # Post to Instagram
        insta_result = post_to_instagram(img_url, full_caption)
        logging.info(f"Posted to Instagram: {insta_result}")
        print("✅ Instagram post sent:", insta_result)

    except Exception as e:
        logging.error(f"Error in main: {e}")
        print("Exception in main:", e)
