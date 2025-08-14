import os
import random
import re
import requests
from telegram import Update
from telegram.helpers import escape_markdown
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from flask import Flask, request, jsonify
import threading
import asyncio

# Environment variables
TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Random titles
TITLES = [
    "🔥 Loot Deal Alert!", "💥 Hot Deal Incoming!", "⚡ Limited Time Offer!",
    "🎯 Grab Fast!", "🚨 Flash Sale!", "💎 Special Deal Just For You!",
    "🛒 Shop Now!", "📢 Price Drop!", "🎉 Mega Offer!", "🤑 Crazy Discount!"
]

# Global app variable
telegram_app = None

# Get final URL after redirects
def get_final_url_from_redirect(start_url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(start_url, timeout=15, headers=headers, allow_redirects=True)
        return response.url
    except:
        return None

# Extract post ID from Instagram URL - FIXED: Added reels support
def extract_post_id_from_url(url):
    match = re.search(r"/(?:post|reels)/(\d+)", url)
    return match.group(1) if match else None

# Get product links from Wishlink API
def get_product_links_from_post(post_id):
    headers = {
        "accept": "*/*",
        "content-type": "application/json",
        "origin": "https://www.wishlink.com",
        "referer": "https://www.wishlink.com/",
        "user-agent": "Mozilla/5.0",
        "wishlinkid": "1752163729058-1dccdb9e-a0f9-f088-a678-e14f8997f719",
    }
    
    api_urls = [
        f"https://api.wishlink.com/api/store/getPostOrCollectionProducts?page=1&limit=50&postType=POST&postOrCollectionId={post_id}&sourceApp=STOREFRONT",
        f"https://api.wishlink.com/api/store/getPostOrCollectionProducts?page=1&limit=50&postType=REELS&postOrCollectionId={post_id}&sourceApp=STOREFRONT"
    ]
    
    for api_url in api_urls:
        try:
            response = requests.get(api_url, headers=headers)
            response.raise_for_status()
            data = response.json()
            products = data.get("data", {}).get("products", [])
            if products:
                return [p["purchaseUrl"] for p in products if "purchaseUrl" in p]
        except:
            continue
    
    return []

# FIXED: Proper markdown escaping
def escape_for_markdown(text):
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hey! 👋 Send me a Wishlink or Instagram post/reel link and I'll fetch the real product links for you."
    )

# Handle links
async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = None
    if update.message.text:
        text = update.message.text
    elif update.message.caption:
        text = update.message.caption
    elif update.message.forward_from and update.message.text:
        text = update.message.text
    elif update.message.forward_from and update.message.caption:
        text = update.message.caption
    
    if not text:
        return

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
                product_links = get_product_links_from_post(post_id)
                all_links.extend(product_links)

    if not all_links:
        await update.message.reply_text("❌ No product links found.")
        return

    title = random.choice(TITLES)
    max_links_per_message = 10
    link_chunks = [all_links[i:i + max_links_per_message] for i in range(0, len(all_links), max_links_per_message)]
    
    for i, chunk in enumerate(link_chunks):
        if i == 0:
            output = f"*{escape_for_markdown(title)}*\n\n"
        else:
            output = f"*{escape_for_markdown(title)} - Part {i+1}*\n\n"
        
        for link in chunk:
            discount = random.randint(50, 100)
            discount_text = escape_for_markdown(f"({discount}% OFF)")
            safe_link = escape_for_markdown(link)
            output += f"{discount_text} {safe_link}\n\n"
        
        try:
            await update.message.reply_text(output, parse_mode="MarkdownV2")
        except Exception as e:
            plain_output = output.replace('\\', '')
            await update.message.reply_text(plain_output)

# Health check
async def health_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot is running! 🟢")

# Flask app for webhook
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Bot is running! 🤖"

@web_app.route('/health')
def health():
    return {"status": "ok", "message": "Bot is running"}

# FIXED: Webhook handler
@web_app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    global telegram_app
    if telegram_app:
        try:
            # Get the update from Telegram
            update_dict = request.get_json()
            
            # Process the update
            asyncio.create_task(
                telegram_app.process_update(
                    Update.de_json(update_dict, telegram_app.bot)
                )
            )
            return jsonify({"status": "ok"})
        except Exception as e:
            print(f"Webhook error: {e}")
            return jsonify({"error": str(e)}), 500
    
    return jsonify({"error": "App not ready"}), 503

# Main function
def main():
    global telegram_app
    
    # Create telegram app
    telegram_app = ApplicationBuilder().token(TOKEN).build()
    
    # Add handlers
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(CommandHandler("health", health_check))
    telegram_app.add_handler(MessageHandler(filters.TEXT | filters.CAPTION | filters.FORWARDED, handle_link))
    
    # Set webhook
    asyncio.run(telegram_app.bot.set_webhook(url=f"{WEBHOOK_URL}/{TOKEN}"))
    
    # Run Flask app
    port = int(os.getenv("PORT", 10000))
    web_app.run(host='0.0.0.0', port=port, debug=False)

if __name__ == "__main__":
    main()
