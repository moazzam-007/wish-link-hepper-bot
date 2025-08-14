import os
import random
import re
import requests
from telegram import Update
from telegram.helpers import escape_markdown
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# Environment variables
TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Random titles
TITLES = [
    "🔥 Loot Deal Alert!", "💥 Hot Deal Incoming!", "⚡ Limited Time Offer!",
    "🎯 Grab Fast!", "🚨 Flash Sale!", "💎 Special Deal Just For You!",
    "🛒 Shop Now!", "📢 Price Drop!", "🎉 Mega Offer!", "🤑 Crazy Discount!"
]

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
    # Support both /post/ and /reels/
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
    
    # Try both POST and REELS API endpoints
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
            if products:  # If we found products, return them
                return [p["purchaseUrl"] for p in products if "purchaseUrl" in p]
        except:
            continue
    
    return []

# FIXED: Proper markdown escaping
def escape_for_markdown(text):
    # Escape all special characters for MarkdownV2
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hey! 👋 Send me a Wishlink or Instagram post/reel link and I'll fetch the real product links for you."
    )

# FIXED: Handle forwarded messages and images with captions
async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Get text from message, caption, or forwarded message
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

    # FIXED: Handle long messages by splitting
    title = random.choice(TITLES)
    
    # Split links into chunks to avoid "Message too long" error
    max_links_per_message = 10
    link_chunks = [all_links[i:i + max_links_per_message] for i in range(0, len(all_links), max_links_per_message)]
    
    for i, chunk in enumerate(link_chunks):
        if i == 0:
            output = f"*{escape_for_markdown(title)}*\n\n"
        else:
            output = f"*{escape_for_markdown(title)} - Part {i+1}*\n\n"
        
        for link in chunk:
            discount = random.randint(50, 100)
            # FIXED: Proper escaping for discount and link
            discount_text = escape_for_markdown(f"({discount}% OFF)")
            safe_link = escape_for_markdown(link)
            output += f"{discount_text} {safe_link}\n\n"
        
        # Send message with proper error handling
        try:
            await update.message.reply_text(output, parse_mode="MarkdownV2")
        except Exception as e:
            # Fallback to plain text if markdown fails
            plain_output = output.replace('\\', '')
            await update.message.reply_text(plain_output)

# FIXED: Add health check endpoint for render
async def health_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot is running! 🟢")

# Main app
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("health", health_check))
    app.add_handler(MessageHandler(filters.TEXT | filters.CAPTION | filters.FORWARDED, handle_link))
    
    # Add a simple web endpoint for render health check
    from flask import Flask
    import threading
    
    web_app = Flask(__name__)
    
    @web_app.route('/')
    def home():
        return "Bot is running! 🤖"
    
    @web_app.route('/health')
    def health():
        return {"status": "ok", "message": "Bot is running"}
    
    # Run Flask app in background thread
    def run_web():
        web_app.run(host='0.0.0.0', port=int(os.getenv("PORT", 8080)))
    
    web_thread = threading.Thread(target=run_web)
    web_thread.daemon = True
    web_thread.start()
    
    # Run telegram bot
    app.run_webhook(
        listen="0.0.0.0",
        port=int(os.getenv("PORT", 8080)) + 1,  # Use different port for telegram
        url_path=TOKEN,
        webhook_url=f"{WEBHOOK_URL}/{TOKEN}"
    )
