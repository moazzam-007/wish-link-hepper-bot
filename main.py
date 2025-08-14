import os
import random
import re
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
import logging
from flask import Flask
import threading

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

# ADDED: Health check web server for uptime monitoring
def create_health_server():
    app = Flask(__name__)
    
    @app.route('/')
    def home():
        return "🤖 Wishlink Bot is Running! ✅"
    
    @app.route('/health')
    def health():
        return {"status": "ok", "bot": "running", "service": "active"}
    
    @app.route('/status')
    def status():
        return "Bot Status: Active 🟢"
    
    return app

def run_health_server():
    health_app = create_health_server()
    # Run on different port to avoid conflicts
    health_app.run(host='0.0.0.0', port=8080, debug=False)

def main():
    logger.info("Starting bot...")
    
    # Start health server in background
    health_thread = threading.Thread(target=run_health_server, daemon=True)
    health_thread.start()
    logger.info("Health server started on port 8080")
    
    # Create telegram application
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT | filters.CAPTION, handle_link))
    
    # Run with webhook
    logger.info(f"Setting webhook: {WEBHOOK_URL}/{TOKEN}")
    
    app.run_webhook(
        listen="0.0.0.0",
        port=int(os.getenv("PORT", 10000)),
        url_path=TOKEN,
        webhook_url=f"{WEBHOOK_URL}/{TOKEN}"
    )

if __name__ == "__main__":
    main()
