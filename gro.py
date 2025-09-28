# gro.py
import os
import openai
import requests
import json
import datetime
import logging
from PIL import Image, ImageDraw, ImageFont
import random
import sys

# ===== Configuration =====
openai.api_key = os.getenv("OPENAI_API_KEY", "").strip()
LONG_LIVED_USER_TOKEN = os.getenv("LONG_LIVED_USER_TOKEN", "").strip()  # fallback if PAGE_ACCESS_TOKEN not set
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN", "").strip()          # optional; if empty we will derive from LONG_LIVED_USER_TOKEN
PAGE_ID = os.getenv("PAGE_ID", "").strip()
IG_USER_ID = os.getenv("IG_USER_ID", "17841476888412461").strip()      # optional override
GRAPH_API_VERSION = os.getenv("GRAPH_API_VERSION", "v19.0").strip()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

# quick sanity
if not openai.api_key:
    print("Missing OPENAI_API_KEY", file=sys.stderr); sys.exit(1)
if not PAGE_ID:
    print("Missing PAGE_ID", file=sys.stderr); sys.exit(1)
if not (PAGE_ACCESS_TOKEN or LONG_LIVED_USER_TOKEN):
    print("Missing PAGE_ACCESS_TOKEN and LONG_LIVED_USER_TOKEN (at least one required)", file=sys.stderr); sys.exit(1)
if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    print("Missing TELEGRAM_TOKEN or TELEGRAM_CHAT_ID (Telegram will not work)", file=sys.stderr)

# ===== Logging =====
logging.basicConfig(filename="bot.log", level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
def mask(token):
    if not token: return ""
    return token[:6] + "..." + token[-4:]

logging.info(f"Starting gro.py; PAGE_ID={PAGE_ID}; IG_USER_ID(env)={IG_USER_ID}; PAGE_ACCESS_TOKEN set? {bool(PAGE_ACCESS_TOKEN)}; LONG_LIVED_USER_TOKEN set? {bool(LONG_LIVED_USER_TOKEN)}")

# ===== Helpers =====
def get_page_access_token():
    """Return a Page Access Token. If PAGE_ACCESS_TOKEN set, return it.
       Otherwise try to fetch pages using LONG_LIVED_USER_TOKEN and match PAGE_ID."""
    global PAGE_ACCESS_TOKEN
    if PAGE_ACCESS_TOKEN:
        logging.info("Using PAGE_ACCESS_TOKEN from env (masked): %s", mask(PAGE_ACCESS_TOKEN))
        return PAGE_ACCESS_TOKEN

    # attempt to exchange LONG_LIVED_USER_TOKEN -> page token
    if not LONG_LIVED_USER_TOKEN:
        raise Exception("No LONG_LIVED_USER_TOKEN available to derive page token")

    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/me/accounts"
    params = {"access_token": LONG_LIVED_USER_TOKEN}
    r = requests.get(url, params=params, timeout=30)
    logging.info("GET /me/accounts status=%s body=%s", r.status_code, r.text[:1000])
    r.raise_for_status()
    data = r.json().get("data", [])
    for p in data:
        if str(p.get("id")) == str(PAGE_ID):
            PAGE_ACCESS_TOKEN = p.get("access_token")
            logging.info("Derived PAGE_ACCESS_TOKEN from LONG_LIVED_USER_TOKEN (masked): %s", mask(PAGE_ACCESS_TOKEN))
            return PAGE_ACCESS_TOKEN
    raise Exception(f"Could not find page {PAGE_ID} in /me/accounts. Response: {r.text}")

def ensure_ig_user_id(page_access_token):
    """Ensure IG_USER_ID is known; if not, query {page_id}?fields=instagram_business_account"""
    global IG_USER_ID
    if IG_USER_ID:
        logging.info("Using IG_USER_ID from env: %s", IG_USER_ID)
        return IG_USER_ID

    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{PAGE_ID}"
    params = {"fields": "instagram_business_account", "access_token": page_access_token}
    r = requests.get(url, params=params, timeout=30)
    logging.info("GET /{PAGE_ID}?fields=instagram_business_account status=%s body=%s", r.status_code, r.text[:1000])
    r.raise_for_status()
    body = r.json()
    ig = body.get("instagram_business_account", {})
    if not ig or "id" not in ig:
        raise Exception(f"No instagram_business_account found for page {PAGE_ID}. Response: {body}")
    IG_USER_ID = str(ig["id"])
    logging.info("Found IG_USER_ID: %s", IG_USER_ID)
    return IG_USER_ID

# ===== OpenAI generation =====
def generate_text():
    prompt = """
Write a short, poetic and uplifting reflection (max 2 lines).
It should feel timeless and universal, offering hope and courage.
Use clear, simple words — something anyone can understand.
It must not mention religion directly, but let values of love, care and light shine through.
Return only the reflection text.
"""
    resp = openai.chat.completions.create(model="gpt-4o-mini", messages=[{"role":"user","content":prompt}])
    return resp.choices[0].message.content.strip()

def generate_hashtags():
    possible_tags = ["#Love", "#Hope", "#Peace", "#Kindness", "#Inspiration", "#Courage"]
    return " ".join(random.sample(possible_tags, k=random.randint(4,6)))

def generate_image():
    img_prompt = ("A symbolic, poetic image representing hope, love and human connection. "
                  "Cinematic style, soft natural light, artistic and uplifting atmosphere.")
    img_response = openai.images.generate(model="dall-e-3", prompt=img_prompt, size="1024x1024")
    img_url = img_response.data[0].url
    local_filename = f"reflection_{datetime.date.today()}.png"
    # save local copy for Telegram editing
    r = requests.get(img_url, timeout=30)
    r.raise_for_status()
    with open(local_filename, "wb") as f:
        f.write(r.content)
    logging.info("Downloaded image for Telegram: %s (source url length=%d)", local_filename, len(img_url))
    # return both
    return img_url, local_filename

def add_love_to_image(image_path):
    img = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arialbd.ttf", 120)
    except:
        font = ImageFont.load_default()
    text = "LOVE"
    bbox = draw.textbbox((0,0), text, font=font)
    x = (img.width - (bbox[2]-bbox[0]))/2
    y = (img.height - (bbox[3]-bbox[1]))/2
    draw.text((x+5,y+5), text, font=font, fill="black")
    draw.text((x,y), text, font=font, fill="white")
    new_path = image_path.replace(".png","_with_love.png")
    img.save(new_path)
    logging.info("Wrote LOVE image: %s", new_path)
    return new_path

# ===== Telegram =====
def send_telegram(message, photo_path=None):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logging.warning("Telegram token/chat missing; skipping Telegram send.")
        return None
    try:
        if photo_path:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
            with open(photo_path,"rb") as f:
                files = {"photo": f}
                data = {"chat_id": TELEGRAM_CHAT_ID, "caption": message}
                r = requests.post(url, data=data, files=files, timeout=30)
        else:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
            r = requests.post(url, data=data, timeout=30)
        logging.info("Telegram status=%s body=%s", r.status_code, r.text)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logging.exception("Telegram send failed: %s", e)
        return None

# ===== Instagram posting via image_url (correct flow) =====
def post_to_instagram_via_url(image_url, caption, ig_user_id, page_token):
    try:
        upload_url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{ig_user_id}/media"
        params = {"image_url": image_url, "caption": caption, "access_token": page_token}
        r = requests.post(upload_url, params=params, timeout=30)
        logging.info("POST %s params=%s status=%s body=%s", upload_url, dict((k, (v[:80]+"...") if isinstance(v,str) and len(v)>80 else v) for k,v in params.items()), r.status_code, r.text[:2000])
        # if r.status_code != 200:  # still inspect body
        data = r.json()
        container_id = data.get("id")
        if not container_id:
            raise Exception(f"Instagram upload failed (no container_id). Response: {data}")
        # publish
        publish_url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{ig_user_id}/media_publish"
        params2 = {"creation_id": container_id, "access_token": page_token}
        r2 = requests.post(publish_url, params=params2, timeout=30)
        logging.info("POST %s params=%s status=%s body=%s", publish_url, params2, r2.status_code, r2.text[:2000])
        r2.raise_for_status()
        return r2.json()
    except Exception as e:
        logging.exception("Instagram post failed: %s", e)
        return None

# ===== Main =====
if __name__ == "__main__":
    try:
        text = generate_text()
        hashtags = generate_hashtags()
        img_url, local_file = generate_image()
        final_local = add_love_to_image(local_file)
        caption = f"🌍 Reflection of the day\n\n{text}\n\n{hashtags}"

        # Telegram first (local)
        t = send_telegram(caption, photo_path=final_local)
        print("Telegram sent:", bool(t))

        # Get page access token (if needed)
        page_token = get_page_access_token()

        # Ensure IG user id
        ig_user = ensure_ig_user_id(page_token)

        # Post to Instagram via the public img_url (NOT local file)
        insta_resp = post_to_instagram_via_url(img_url, caption, ig_user, page_token)
        if insta_resp:
            print("Instagram post succeeded:", insta_resp)
            logging.info("Instagram post succeeded: %s", insta_resp)
        else:
            print("Instagram post failed. Check bot.log for details.")
            logging.error("Instagram post failed; see earlier logs.")
    except Exception as e:
        logging.exception("Fatal error in main: %s", e)
        print("Fatal error; see bot.log")
