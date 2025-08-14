import os
import random
import re
import requests
from telegram import Update, InputMediaPhoto
from telegram.helpers import escape_markdown
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

TITLES = [
    "🔥 Loot Deal Alert!", "💥 Hot Deal Incoming!", "⚡ Limited Time Offer!",
    "🎯 Grab Fast!", "🚨 Flash Sale!", "💎 Special Deal Just For You!",
    "🛒 Shop Now!", "📢 Price Drop!", "🎉 Mega Offer!", "🤑 Crazy Discount!"
]

def get_final_url_from_redirect(start_url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(start_url, timeout=15, headers=headers, allow_redirects=True)
        return response.url
    except:
        return None

def extract_post_id_from_url(url):
    match = re.search(r"/(?:post|reels)/(\d+)", url)
    return match.group(1) if match else None

def get_product_links_from_post(post_id):
    headers = {
        "accept": "*/*",
        "content-type": "application/json",
        "origin": "https://www.wishlink.com",
        "referer": "https://www.wishlink.com/",
        "user-agent": "Mozilla/5.0",
        "wishlinkid": "1752163729058-1dccdb9e-a0f9-f088-a678-e14f8997f719",
    }
    api_url = f"https://api.wishlink.com/api/store/getPostOrCollectionProducts?page=1&limit=50&postType=POST&postOrCollectionId={post_id}&sourceApp=STOREFRONT"
    try:
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()
        data = response.json()
        products = data.get("data", {}).get("products", [])
        return [p["purchaseUrl"] for p in products if "purchaseUrl" in p]
    except:
        return []

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hey! 👋 Send me a Wishlink or Instagram post/reel link and I’ll fetch the real product links for you."
    )

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Get text from normal message or caption (for media)
    text = update.message.text or update.message.caption
    if not text:
        return  # No link found

    await update.message.reply_text("Processing your link… 🔄")

    all_links = []
    urls = re.findall(r'(https?://\S+)', text)

    for url in urls:
        if "/share/" in url:
            redirected = get_final_url_from_redirect(url)
            if redirected:
                all_links.append(redirected)
        else:
            post_id = extract_post_id_from_url(url)
            if post_id:
                all_links.extend(get_product_links_from_post(post_id))

    if not all_links:
        await update.message.reply_text("❌ No product links found.")
        return

    title = random.choice(TITLES)
    output = f"*{escape_markdown(title, version=2)}*\n\n"

    for link in all_links:
        discount = random.randint(50, 100)
        safe_link = escape_markdown(link, version=2)
        output += f"({discount}% OFF) {safe_link}\n\n"

    await update.message.reply_text(output, parse_mode="MarkdownV2")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT | filters.CAPTION, handle_link))

    app.run_webhook(
        listen="0.0.0.0",
        port=int(os.getenv("PORT", 8080)),
        url_path=TOKEN,
        webhook_url=f"{WEBHOOK_URL}/{TOKEN}"
    )
