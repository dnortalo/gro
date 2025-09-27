import os
import openai
import requests
import json
import datetime
import logging
from PIL import Image, ImageDraw, ImageFont
import random

# ======== Configuration ========
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY").strip()
LONG_LIVED_USER_TOKEN = os.getenv("LONG_LIVED_USER_TOKEN").strip()  # user token
PAGE_ID = os.getenv("PAGE_ID").strip()
INSTAGRAM_APP_ID = os.getenv("INSTAGRAM_APP_ID").strip()
INSTAGRAM_APP_SECRET = os.getenv("INSTAGRAM_APP_SECRET").strip()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID").strip()
GRAPH_API_VERSION = "v19.0"

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

# ======== Telegram Function ========
def send_telegram_message(bot_token, chat_id, message_text):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message_text
    }
    r = requests.post(url, json=payload)
    r.raise_for_status()
    return r.json()

# ======== Facebook/Instagram API Helpers ========
def refresh_long_lived_token(user_token):
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/oauth/access_token"
    params = {
        "grant_type": "fb_exchange_token",
        "client_id": INSTAGRAM_APP_ID,
        "client_secret": INSTAGRAM_APP_SECRET,
        "fb_exchange_token": user_token.strip(),
    }
    r = requests.get(url, params=params)
    r.raise_for_status()
    new_token = r.json()["access_token"]

    # Optional: save token to file
    with open("refreshed_token.txt", "w") as f:
        f.write(new_token)

    logging.info("🔄 Refreshed long-lived user token")
    return new_token

def get_page_access_token(user_token, page_id):
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/me/accounts"
    params = {"access_token": user_token.strip()}
    r = requests.get(url, params=params)

    if r.status_code == 400 and "expired" in r.text.lower():
        logging.warning("⚠️ Long-lived token expired – refreshing...")
        user_token = refresh_long_lived_token(user_token)
        params["access_token"] = user_token
        r = requests.get(url, params=params)

    r.raise_for_status()
    pages = r.json().get("data", [])
    for p in pages:
        if p["id"] == page_id:
            return p["access_token"]
    raise Exception(f"Page token not found for {page_id}")

def get_instagram_user_id(page_token, page_id):
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{page_id}"
    params = {"fields": "instagram_business_account", "access_token": page_token.strip()}
    r = requests.get(url, params=params)
    r.raise_for_status()
    return r.json()["instagram_business_account"]["id"]

def create_media_container(ig_user_id, page_token, image_url, caption):
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{ig_user_id}/media"
    params = {"image_url": image_url, "caption": caption, "access_token": page_token.strip()}
    r = requests.post(url, params=params)
    r.raise_for_status()
    return r.json()["id"]

def publish_media(ig_user_id, container_id, page_token):
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{ig_user_id}/media_publish"
    params = {"creation_id": container_id, "access_token": page_token.strip()}
    r = requests.post(url, params=params)
    r.raise_for_status()
    return r.json()

def post_to_instagram(user_token, page_id, image_url, caption):
    page_token = get_page_access_token(user_token, page_id)
    ig_user_id = get_instagram_user_id(page_token, page_id)
    container_id = create_media_container(ig_user_id, page_token, image_url, caption)
    return publish_media(ig_user_id, container_id, page_token)

# ======== Main Flow ========
if __name__ == "__main__":
    try:
        text = generate_text()
        hashtags = generate_hashtags()
        img_url, img_file = generate_image()
        final_img = add_love_to_image(img_file)

        instagram_caption = f"{text}\n\n{hashtags}"

        # --- Send message to Telegram first ---
        telegram_message = f"✨ Klar til Instagram-post:\n\n{text}\n\n{hashtags}"
        send_result = send_telegram_message(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, telegram_message)
        logging.info(f"📨 Sent Telegram message: {send_result}")
        print("✅ Telegram message sent:", send_result)

        # --- Post to Instagram ---
        insta_result = post_to_instagram(LONG_LIVED_USER_TOKEN, PAGE_ID, img_url, instagram_caption)
        logging.info(f"🎉 Posted to Instagram: {insta_result}")
        print("✅ Instagram post sent:", insta_result)

    except Exception as e:
        logging.error(f"Error in main flow: {e}")
        print("Exception in main:", e)
