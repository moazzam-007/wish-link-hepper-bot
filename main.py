import os
import random
import re
import requests
from telegram import Update
from telegram.helpers import escape_markdown
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from flask import Flask, request, jsonify
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor

# Environment variables
TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Random titles
TITLES = [
    "🔥 Loot Deal Alert!", "💥 Hot Deal Incoming!", "⚡ Limited Time Offer!",
    "🎯 Grab Fast!", "🚨 Flash Sale!", "💎 Special Deal Just For You!",
    "🛒 Shop Now!", "📢 Price Drop!", "🎉 Mega Offer!", "🤑 Crazy Discount!"
]

# Global variables
telegram_app = None
event_loop = None
executor = ThreadPoolExecutor(max_workers=4)

# Get final URL after redirects
def get_final_url_from_redirect(start_url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(start_url, timeout=15, headers=headers, allow_redirects=True)
        return response.url
    except:
        return None

# Extract post ID from Instagram URL
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

# Proper markdown escaping
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
    max_links_per_message = 8
    link_chunks = [all_links[i:i + max_links_per_message] for i in range(0, len(all_links), max_links_per_message)]
    
    for i, chunk in enumerate(link_chunks):
        if i == 0:
            output = f"*{escape_for_markdown(title)}*\n\n"
        else:
            output = f"*{escape_for_markdown(title)} \\- Part {i+1}*\n\n"
        
        for link in chunk:
            discount = random.randint(50, 90)
            discount_text = escape_for_markdown(f"({discount}% OFF)")
            safe_link = escape_for_markdown(link)
            output += f"{discount_text} {safe_link}\n\n"
        
        try:
            await update.message.reply_text(output, parse_mode="MarkdownV2")
        except Exception as e:
            # Fallback to plain text
            plain_output = title + "\n\n"
            for link in chunk:
                discount = random.randint(50, 90)
                plain_output += f"({discount}% OFF) {link}\n\n"
            await update.message.reply_text(plain_output)

# Health check
async def health_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot is running! 🟢")

# FIXED: Proper async handling in Flask
def process_update_sync(update_dict):
    """Process telegram update in sync context"""
    global telegram_app, event_loop
    
    try:
        if telegram_app and event_loop:
            update = Update.de_json(update_dict, telegram_app.bot)
            
            # Run coroutine in the event loop
            future = asyncio.run_coroutine_threadsafe(
                telegram_app.process_update(update), 
                event_loop
            )
            future.result(timeout=30)  # Wait for completion
            return True
    except Exception as e:
        print(f"Update processing error: {e}")
        return False
    
    return False

# Flask app
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "🤖 Wishlink Bot is Running!"

@web_app.route('/health')
def health():
    return jsonify({"status": "ok", "message": "Bot is running"})

@web_app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    try:
        update_dict = request.get_json()
        
        if not update_dict:
            return jsonify({"error": "No data"}), 400
        
        # Process update in background
        executor.submit(process_update_sync, update_dict)
        
        return jsonify({"status": "ok"})
        
    except Exception as e:
        print(f"Webhook error: {e}")
        return jsonify({"error": "Processing failed"}), 500

# Background event loop for async operations
def run_event_loop():
    global event_loop
    event_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(event_loop)
    event_loop.run_forever()

# Main function
def main():
    global telegram_app
    
    # Start background event loop
    loop_thread = threading.Thread(target=run_event_loop, daemon=True)
    loop_thread.start()
    
    # Wait for event loop to be ready
    import time
    time.sleep(1)
    
    # Create telegram app
    telegram_app = ApplicationBuilder().token(TOKEN).build()
    
    # Add handlers
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(CommandHandler("health", health_check))
    telegram_app.add_handler(MessageHandler(filters.TEXT | filters.CAPTION, handle_link))
    
    # Set webhook
    async def setup_webhook():
        await telegram_app.bot.set_webhook(url=f"{WEBHOOK_URL}/{TOKEN}")
    
    asyncio.run_coroutine_threadsafe(setup_webhook(), event_loop).result()
    
    print("🚀 Bot setup complete!")
    
    # Run Flask app
    port = int(os.getenv("PORT", 10000))
    web_app.run(host='0.0.0.0', port=port, debug=False)

if __name__ == "__main__":
    main()
