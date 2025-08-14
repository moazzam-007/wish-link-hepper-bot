import os
import random
import re
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
import logging
from flask import Flask, jsonify
import threading
import asyncio

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Environment variables
TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Random titles
TITLES = [
    "🔥 Loot Deal Alert!", "💥 Hot Deal Incoming!", "⚡ Limited Time Offer!",
    "🎯 Grab Fast!", "🚨 Flash Sale!", "💎 Special Deal Just For You!",
    "🛒 Shop Now!", "📢 Price Drop!", "🎉 Mega Offer!", "🤑 Crazy Discount!"
]

# Global telegram app
telegram_app = None

def get_final_url_from_redirect(start_url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(start_url, timeout=15, headers=headers, allow_redirects=True)
        return response.url
    except Exception as e:
        logger.error(f"Redirect error: {e}")
        return None

def extract_post_id_from_url(url):
    match = re.search(r"/(?:post|reels)/(\d+)", url)
    result = match.group(1) if match else None
    logger.info(f"Extract post ID from {url}: {result}")
    return result

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
            logger.info(f"Trying API: {api_url}")
            response = requests.get(api_url, headers=headers)
            response.raise_for_status()
            data = response.json()
            products = data.get("data", {}).get("products", [])
            logger.info(f"API response: {len(products)} products found")
            if products:
                links = [p["purchaseUrl"] for p in products if "purchaseUrl" in p]
                logger.info(f"Product links: {len(links)}")
                return links
        except Exception as e:
            logger.error(f"API error: {e}")
            continue
    
    return []

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Start command from user: {update.effective_user.id}")
    await update.message.reply_text(
        "Hey! 👋 Send me a Wishlink or Instagram post/reel link and I'll fetch the real product links for you.\n\nExample:\nhttps://www.wishlink.com/share/dupdx\nor\nhttps://wishlink.com/username/post/123456"
    )

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Message received from user: {update.effective_user.id}")
    
    text = update.message.text or update.message.caption
    
    if not text:
        logger.info("No text found in message")
        return

    logger.info(f"Processing text: {text}")
    
    if not any(word.startswith('http') for word in text.split()):
        logger.info("No HTTP links found in text")
        return
    
    await update.message.reply_text("Processing your link… 🔄")

    all_links = []
    urls = re.findall(r'(https?://\S+)', text)
    logger.info(f"Found URLs: {urls}")
    
    for url in urls:
        logger.info(f"Processing URL: {url}")
        
        if "/share/" in url:
            logger.info(f"Processing share URL: {url}")
            redirected = get_final_url_from_redirect(url)
            if redirected:
                all_links.append(redirected)
                logger.info(f"Redirected to: {redirected}")
        elif "wishlink.com" in url:
            post_id = extract_post_id_from_url(url)
            if post_id:
                logger.info(f"Extracted post ID: {post_id}")
                product_links = get_product_links_from_post(post_id)
                all_links.extend(product_links)
                logger.info(f"Found {len(product_links)} product links")
            else:
                logger.info("No post ID found in wishlink URL")

    logger.info(f"Total links found: {len(all_links)}")

    if not all_links:
        logger.info("No product links found")
        await update.message.reply_text("❌ No product links found. Please check your Wishlink URL format.")
        return
    
    title = random.choice(TITLES)
    max_links = 8
    if len(all_links) > max_links:
        all_links = all_links[:max_links]
    
    output = f"🎉 {title}\n\n"
    
    for i, link in enumerate(all_links, 1):
        discount = random.randint(50, 85)
        output += f"{i}. ({discount}% OFF)\n{link}\n\n"
    
    try:
        await update.message.reply_text(output)
        logger.info("Response sent successfully")
    except Exception as e:
        logger.error(f"Failed to send response: {e}")
        await update.message.reply_text(f"✅ Found {len(all_links)} product links!")

# FIXED: Combined Flask + Telegram on same port
def process_telegram_update(update_dict):
    """Process Telegram update async"""
    global telegram_app
    if telegram_app:
        try:
            update = Update.de_json(update_dict, telegram_app.bot)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(telegram_app.process_update(update))
            loop.close()
            return True
        except Exception as e:
            logger.error(f"Update processing error: {e}")
    return False

# Flask app with webhook handling
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Wishlink Bot is Running! ✅"

@app.route('/health')
def health():
    return jsonify({"status": "ok", "bot": "running", "service": "active"})

@app.route('/status')
def status():
    return "Bot Status: Active 🟢"

# FIXED: Webhook endpoint on same Flask app
@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    try:
        from flask import request
        update_dict = request.get_json()
        
        if not update_dict:
            return jsonify({"error": "No data"}), 400
        
        # Process in background thread
        import threading
        thread = threading.Thread(target=process_telegram_update, args=(update_dict,))
        thread.start()
        
        return jsonify({"status": "ok"})
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"error": "Processing failed"}), 500

def main():
    global telegram_app
    logger.info("Starting bot...")
    
    # Create telegram application
    telegram_app = ApplicationBuilder().token(TOKEN).build()
    
    # Add handlers
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(MessageHandler(filters.TEXT | filters.CAPTION, handle_link))
    
    # Set webhook
    async def setup_webhook():
        await telegram_app.bot.set_webhook(url=f"{WEBHOOK_URL}/{TOKEN}")
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(setup_webhook())
    loop.close()
    
    logger.info(f"Webhook set: {WEBHOOK_URL}/{TOKEN}")
    logger.info("Starting Flask server...")
    
    # Run Flask app (this handles both webhook and health checks)
    port = int(os.getenv("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)

if __name__ == "__main__":
    main()
