import os
import openai
import requests
import json
import datetime
import logging
from PIL import Image, ImageDraw, ImageFont
import random

# ======== Configuration ========
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
LONG_LIVED_USER_TOKEN = os.getenv("LONG_LIVED_USER_TOKEN")  # Permanent Page Token
PAGE_ID = os.getenv("PAGE_ID")
INSTAGRAM_APP_ID = os.getenv("INSTAGRAM_APP_ID")
INSTAGRAM_APP_SECRET = os.getenv("INSTAGRAM_APP_SECRET")

# ======== Logging ========
logging.basicConfig(
    filename="bot.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ======== Helper Functions ========
def send_telegram(message, photo=None):
    try:
        if photo:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
            short_caption = "🌍 Reflection of the day"
            with open(photo, "rb") as f:
                files = {"photo": f}
                data = {"chat_id": TELEGRAM_CHAT_ID, "caption": short_caption}
                response = requests.post(url, data=data, files=files)
            if response.status_code != 200:
                logging.warning(f"Telegram error (photo): {response.text}")

        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
        response = requests.post(url, data=data)
        if response.status_code != 200:
            logging.warning(f"Telegram error (text): {response.text}")

    except Exception as e:
        logging.error(f"Error sending to Telegram: {e}")
        print("Exception:", e)

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
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (img.width - text_width) / 2
    y = (img.height - text_height) / 2
    draw.text((x+5, y+5), text, font=font, fill="black")
    draw.text((x, y), text, font=font, fill="white")
    new_path = image_path.replace(".png", "_with_love.png")
    img.save(new_path)
    return new_path

# ======== Instagram Functions ========
def get_instagram_user_id(page_token, page_id):
    url = f"https://graph.facebook.com/v18.0/{page_id}"
    params = {"fields": "instagram_business_account", "access_token": page_token}
    r = requests.get(url, params=params)
    r.raise_for_status()
    return r.json()["instagram_business_account"]["id"]

def create_media_container(ig_user_id, page_token, image_url, caption):
    url = f"https://graph.facebook.com/v18.0/{ig_user_id}/media"
    params = {"image_url": image_url, "caption": caption, "access_token": page_token}
    r = requests.post(url, params=params)
    r.raise_for_status()
    return r.json()["id"]

def publish_media(ig_user_id, container_id, page_token):
    url = f"https://graph.facebook.com/v18.0/{ig_user_id}/media_publish"
    params = {"creation_id": container_id, "access_token": page_token}
    r = requests.post(url, params=params)
    r.raise_for_status()
    return r.json()

def post_to_instagram(page_token, page_id, image_file, caption):
    ig_user_id = get_instagram_user_id(page_token, page_id)
    container_id = create_media_container(ig_user_id, page_token, image_file, caption)
    return publish_media(ig_user_id, container_id, page_token)

# ======== Main Flow ========
if __name__ == "__main__":
    try:
        text = generate_text()
        hashtags = generate_hashtags()
        img_url, img_file = generate_image()
        final_img = add_love_to_image(img_file)

        # Get current hour
        now_hour = datetime.datetime.now().hour

        # Telegram at 07:00
        if now_hour == 7:
            telegram_message = f"🌍 Reflection of the day\n\n{text}\n\n{hashtags}"
            send_telegram(telegram_message, photo=final_img)
            logging.info("✅ Sent to Telegram")

        # Instagram at 09:00
        if now_hour == 9:
            instagram_caption = f"{text}\n\n{hashtags}"
            result = post_to_instagram(LONG_LIVED_USER_TOKEN, PAGE_ID, final_img, instagram_caption)
            logging.info(f"🎉 Posted to Instagram: {result}")

    except Exception as e:
        logging.error(f"Error in main flow: {e}")
        print("Exception in main:", e)
