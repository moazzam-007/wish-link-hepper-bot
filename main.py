import os
import random
import re
import requests
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Example: https://your-app.onrender.com/webhook

app = Flask(__name__)

# --- Random Titles ---
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
    if match:
        return match.group(1)
    return None

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
        links = [p["purchaseUrl"] for p in products if "purchaseUrl" in p]
        return links
    except:
        return []

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hey! 👋 Send me a Wishlink or Instagram post/reel link and I’ll fetch the real product links for you.")

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    await update.message.reply_text("Processing your link… 🔄")

    all_links = []

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

    # --- Random title ---
    title = random.choice(TITLES)
    output = f"**{title}**\n\n"

    for link in all_links:
        discount = random.randint(50, 100)
        output += f"({discount}% OFF) {link}\n\n"

    await update.message.reply_text(output, parse_mode="Markdown")

@app.route(f"/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put_nowait(update)
    return "OK", 200

if __name__ == "__main__":
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    application.run_webhook(
        listen="0.0.0.0",
        port=int(os.getenv("PORT", 8080)),
        url_path="webhook",
        webhook_url=f"{WEBHOOK_URL}/webhook"
    )
