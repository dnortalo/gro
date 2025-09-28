import os
import openai
import requests
import json
import random
import datetime
import logging

# --- Konfigurasjon ---
openai.api_key = os.getenv("OPENAI_API_KEY")
ACCESS_TOKEN = os.getenv("LONG_LIVED_USER_TOKEN")  # Token med instagram_content_publish
IG_USER_ID = os.getenv("IG_USER_ID")               # Riktig Instagram Business/Creator ID
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

GRAPH_API_VERSION = "v19.0"

# --- Logging ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# --- Dyrebibliotek ---
animals = ["duckling", "kitten", "puppy", "bunny", "hedgehog", "lamb", "koala", "sloth", "otter"]

base_hashtags = ["#Friendship", "#NatureJoy", "#AnimalFriends", "#Cozy", "#CuteAnimals", "#DailyJoy", "#InstaPets"]

STATS_FILE = "stats.json"

# --- Hjelpefunksjoner ---
def load_stats():
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, "r") as f:
            return json.load(f)
    return {"daily": []}

def save_stats(stats):
    with open(STATS_FILE, "w") as f:
        json.dump(stats, f, indent=2)

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

# --- Trendlogikk ---
def trending_animals(stats):
    counter = {}
    for post in stats["daily"]:
        post_animals = post.get("post", "").split("&")
        for a in post_animals:
            counter[a.strip()] = counter.get(a.strip(), 0) + post.get("likes",0)
    if not counter:
        return random.sample(animals, 2)
    top_animals = sorted(counter.items(), key=lambda x: x[1], reverse=True)
    a1 = top_animals[0][0]
    a2 = top_animals[1][0] if len(top_animals) > 1 else random.choice([a for a in animals if a != a1])
    return a1, a2

# --- Generering ---
def generate_caption(a1, a2):
    hashtags = random.sample(base_hashtags, 5)
    prompt = f"Write a cozy short Instagram caption about a {a1} & {a2} with hashtags {hashtags}."
    resp = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role":"user","content":prompt}]
    )
    caption = resp.choices[0].message.content.strip()
    return caption, hashtags

def generate_image(a1, a2):
    prompt = f"Photorealistic photo of a {a1} and {a2}, cinematic, ultra-realistic, natural light"
    resp = openai.images.generate(model="dall-e-3", prompt=prompt, size="1024x1024")
    img_url = resp.data[0].url
    img_file = f"{a1}_{a2}_{datetime.date.today()}.png"
    # Last ned lokalt for Telegram
    with open(img_file, "wb") as f:
        f.write(requests.get(img_url).content)
    return img_url, img_file

def post_to_instagram(caption, img_url):
    try:
        # 1) Upload via URL
        upload_url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{IG_USER_ID}/media"
        params = {"image_url": img_url, "caption": caption, "access_token": ACCESS_TOKEN}
        r = requests.post(upload_url, params=params)
        logging.info(f"Instagram upload response: {r.text}")
        container_id = r.json().get("id")
        if not container_id:
            raise Exception(r.json())
        # 2) Publish
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
    stats = load_stats()
    a1, a2 = trending_animals(stats)
    caption, hashtags = generate_caption(a1, a2)
    img_url, img_file = generate_image(a1, a2)

    # Telegram
    telegram_message = f"{caption}\n\nHashtags: {' '.join(hashtags)}"
    send_telegram(telegram_message, photo=img_file)

    # Instagram
    if post_to_instagram(caption, img_url):
        logging.info("✅ Instagram postet")
        stats["daily"].append({"date": str(datetime.date.today()), "post": f"{a1}&{a2}", "hashtags": hashtags})
        save_stats(stats)
    else:
        logging.warning("❌ Instagram post feilet")
