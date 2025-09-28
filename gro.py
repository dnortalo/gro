import os
import openai
import requests
import json
import random
import datetime
import logging

# --- Konfigurasjon ---
openai.api_key = os.getenv("OPENAI_API_KEY")
ACCESS_TOKEN = os.getenv("LONG_LIVED_USER_TOKEN")
IG_USER_ID = os.getenv("IG_USER_ID")  # riktig ID for Instagram Business/Creator account
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

GRAPH_API_VERSION = "v19.0"

# --- Logging ---
logging.basicConfig(
    filename="bot.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# --- Dyrebibliotek (utvidet) ---
animals = [
    "duckling", "baby goat", "kitten", "puppy", "owl", "bunny", "hedgehog", "foal",
    "lamb", "fawn", "chick", "piglet", "calf", "baby elephant", "koala", "sloth",
    "baby panda", "otter", "raccoon", "squirrel", "parrot", "chameleon", "ferret",
    "baby tiger", "baby lion", "kangaroo joey", "baby penguin", "seal pup", "baby monkey",
    "hamster", "guinea pig", "baby donkey", "baby rhino", "baby giraffe", "baby bear",
    "baby wolf", "baby fox", "baby deer", "baby bat", "baby platypus", "baby lemur",
    "baby porcupine", "baby flamingo", "baby swan", "baby crab", "baby dolphin",
    "baby whale", "baby sea turtle", "baby otter"
]

base_hashtags = ["#Friendship", "#NatureJoy", "#AnimalFriends", "#Cozy", "#CuteAnimals", "#DailyJoy", "#InstaPets"]

STATS_FILE = "stats.json"

# --- Hjelpefunksjoner ---
def load_stats():
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, "r") as f:
            return json.load(f)
    return {"daily": [], "monthly": [], "quarterly": []}

def save_stats(stats):
    with open(STATS_FILE, "w") as f:
        json.dump(stats, f, indent=2)

def send_telegram(message, photo=None):
    try:
        if photo:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
            data = {"chat_id": TELEGRAM_CHAT_ID, "caption": message, "parse_mode": "Markdown"}
            with open(photo, "rb") as f:
                files = {"photo": f}
                response = requests.post(url, data=data, files=files)
        else:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
            response = requests.post(url, data=data)
        if response.status_code == 200:
            logging.info("✅ Telegram sendt.")
        else:
            logging.warning(f"Telegram feilmelding: {response.text}")
    except Exception as e:
        logging.error(f"Feil ved sending til Telegram: {e}")

def seasonal_hashtags():
    month = datetime.datetime.now().month
    if month in [12, 1, 2]:
        return ["#Winter", "#Snow", "#Cozy"]
    elif month in [3, 4, 5]:
        return ["#Spring", "#Flowers", "#Sun"]
    elif month in [6, 7, 8]:
        return ["#Summer", "#Sunshine", "#Meadow"]
    else:
        return ["#Autumn", "#Leaves", "#Cozy"]

def story_prompt(a1, a2):
    weekday = datetime.datetime.now().weekday()
    storyline = {
        0: f"Introduce a cozy story where a {a1} meets a {a2} for the first time.",
        1: f"Continue the story: the {a1} and {a2} explore their surroundings together.",
        2: f"Continue: they face a small challenge but stay close friends.",
        3: f"Continue: they discover something new in nature.",
        4: f"Continue: they enjoy a peaceful moment together.",
        5: f"Continue: their bond grows stronger as the week goes on.",
        6: f"Conclude the story with a heartwarming ending on Sunday."
    }
    return storyline.get(weekday, storyline[0])

# --- Trendlogikk ---
def trending_animals(stats, top_n=5):
    counter = {}
    for post in stats["daily"]:
        post_animals = post.get("post", "").split("&")
        for a in post_animals:
            counter[a.strip()] = counter.get(a.strip(), 0) + post.get("likes",0) + post.get("saves",0)
    if not counter:
        return random.sample(animals, 2)
    sorted_animals = sorted(counter.items(), key=lambda x: x[1], reverse=True)
    top_animals = [a for a, _ in sorted_animals[:top_n]]
    a1 = random.choices(top_animals, weights=range(len(top_animals), 0, -1))[0]
    a2_choices = [a for a in top_animals if a != a1]
    a2 = random.choice(a2_choices) if a2_choices else random.choice([a for a in animals if a != a1])
    return a1, a2

def trending_hashtags(stats, top_n=8):
    counter = {}
    for post in stats["daily"]:
        for tag in post.get("hashtags", []):
            counter[tag] = counter.get(tag, 0) + post.get("likes",0) + post.get("saves",0)
    if not counter:
        return random.sample(base_hashtags, min(len(base_hashtags), top_n))
    sorted_tags = sorted(counter.items(), key=lambda x: x[1], reverse=True)
    top_tags = [tag for tag, _ in sorted_tags[:top_n]]
    return top_tags

# --- Generering ---
def generate_caption(a1, a2, learned_hashtags):
    chosen_hashtags = list(set(random.sample(base_hashtags, 2) + seasonal_hashtags() + learned_hashtags))
    chosen_hashtags = random.sample(chosen_hashtags, min(len(chosen_hashtags), 8))
    prompt = (
        f"Write a short, cozy English Instagram caption about a {a1} and {a2}. "
        f"{story_prompt(a1, a2)} "
        f"Make it 2–3 lines, warm and realistic, ending with 5–8 natural hashtags from {chosen_hashtags}. "
        f"Keep it self-contained but hint that the story continues."
    )
    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content, chosen_hashtags

def season_context():
    month = datetime.datetime.now().month
    if month in [12,1,2]:
        return "snowy forest with soft winter light"
    elif month in [3,4,5]:
        return "blooming spring meadow full of flowers"
    elif month in [6,7,8]:
        return "sunny summer field near a calm river"
    else:
        return "colorful autumn forest with falling leaves"

def generate_dynamic_image(a1, a2):
    prompt_image = (
        f"Ultra realistic DSLR photo of a {a1} and {a2}, "
        f"placed in {season_context()}, "
        f"captured with natural light, shallow depth of field, "
        f"high resolution, cinematic style, photorealism."
    )
    img_response = openai.images.generate(model="dall-e-3", prompt=prompt_image, size="1024x1024")
    img_url = img_response.data[0].url
    img_filename = f"daily_image_{datetime.date.today()}.png"
    with open(img_filename, "wb") as f:
        f.write(requests.get(img_url).content)
    return img_url, img_filename

def post_to_instagram(caption, img_url):
    try:
        upload_url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{IG_USER_ID}/media"
        params = {"image_url": img_url, "caption": caption, "access_token": ACCESS_TOKEN}
        r = requests.post(upload_url, params=params)
        logging.info(f"Instagram upload response: {r.text}")
        container_id = r.json().get("id")
        if not container_id:
            raise Exception(f"Instagram upload failed: {r.json()}")
        publish_url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{IG_USER_ID}/media_publish"
        params = {"creation_id": container_id, "access_token": ACCESS_TOKEN}
        r2 = requests.post(publish_url, params=params)
        if r2.status_code != 200:
            raise Exception(f"Instagram publish failed: {r2.json()}")
        return True
    except Exception as e:
        logging.error(f"Instagram error: {e}")
        send_telegram(f"⚠️ Feil under posting til Instagram: {e}")
        return False

# --- Hovedflyt ---
if __name__ == "__main__":
    stats = load_stats()
    learned_tags = trending_hashtags(stats)
    a1, a2 = trending_animals(stats)
    caption, used_tags = generate_caption(a1, a2, learned_tags)
    img_url, img_file = generate_dynamic_image(a1, a2)

    # Lag draft.json
    draft = {"caption": caption, "img_filename": img_file, "img_url": img_url, "hashtags": used_tags}
    with open("draft.json", "w") as f:
        json.dump(draft, f, indent=2)

    telegram_message = f"{caption}\n\nHashtags: {' '.join(used_tags)}"
    send_telegram(telegram_message, photo=img_file)

    if post_to_instagram(caption, img_url):
        post_stats = {"date": str(datetime.date.today()), "post": f"{a1} & {a2}", "hashtags": used_tags,
                      "likes": random.randint(50, 300), "saves": random.randint(5, 50)}
        stats["daily"].append(post_stats)
        save_stats(stats)
        logging.info(f"✅ Postet til Instagram: {a1} & {a2}")
    else:
        logging.warning("❌ Instagram-posting feilet, men Telegram viser bildet og teksten.")
