import logging
import os
import requests
import asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# --- Configuration ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Récupération des clés depuis les variables d'environnement de Render
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CRYPTOCOMPARE_API_KEY = os.getenv("CRYPTOCOMPARE_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# --- Fonctions du bot (métier) ---
async def get_crypto_news():
    """Récupère les dernières actualités crypto depuis l'API CryptoCompare."""
    url = f"https://min-api.cryptocompare.com/data/v2/news/?lang=FR&api_key={CRYPTOCOMPARE_API_KEY}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        if data.get("Type") == 100 and "Data" in data:
            articles = data["Data"][:5]
            formatted_news = []
            for article in articles:
                title = article.get('title', 'Titre non disponible')
                title_escaped = title.replace('\\', '\\\\').replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace(']', '\\]').replace('(', '\\(').replace(')', '\\)').replace('~', '\\~').replace('`', '\\`').replace('>', '\\>').replace('#', '\\#').replace('+', '\\+').replace('-', '\\-').replace('=', '\\=').replace('|', '\\|').replace('{', '\\{').replace('}', '\\}').replace('.', '\\.').replace('!', '\\!')
                
                article_url = article.get('url', '#')
                source = article.get('source', 'Source inconnue')
                formatted_news.append(
                    f"*{title_escaped}*\n"
                    f"Source: {source}\n"
                    f"[Lire l'article]({article_url})\n"
                )
            return "\n---\n\n".join(formatted_news)
        else:
            logger.warning(f"Réponse inattendue de l'API CryptoCompare: {data}")
            return "Désolé, je n'ai pas pu récupérer les actualités pour le moment."
    except requests.exceptions.RequestException as e:
        logger.error(f"Erreur de l'API CryptoCompare: {e}")
        return "Erreur de connexion à la source d'actualités."

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Message de bienvenue pour la commande /start."""
    await update.message.reply_html("Bonjour ! Envoyez /actus pour les dernières nouvelles crypto.")

async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Envoie les actualités crypto."""
    await update.message.reply_text("Recherche des dernières actualités...")
    news_message = await get_crypto_news()
    await update.message.reply_text(news_message, parse_mode='MarkdownV2', disable_web_page_preview=True)

# --- Initialisation de l'application Telegram ---
if not TELEGRAM_TOKEN:
    logger.error("La variable d'environnement TELEGRAM_TOKEN n'est pas définie !")
else:
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("actus", news_command))

    # --- Partie Serveur Web (Flask) ---
    app = Flask(__name__)

    @app.route("/")
    def index():
        return "Bot server is running, but this page is not meant to be accessed directly."

    @app.route(f"/{TELEGRAM_TOKEN}", methods=['POST'])
    async def webhook():
        """Cette fonction est appelée par Telegram à chaque nouveau message."""
        update_data = request.get_json()
        update = Update.de_json(update_data, application.bot)
        await application.process_update(update)
        return "ok", 200

    # --- Logique de démarrage exécutée par Gunicorn ---
    async def setup():
        """Configure le webhook une seule fois au démarrage."""
        if not WEBHOOK_URL:
            logger.error("La variable d'environnement WEBHOOK_URL n'est pas définie !")
            return
        
        webhook_info = await application.bot.get_webhook_info()
        full_webhook_url = f"{WEBHOOK_URL}/{TELEGRAM_TOKEN}"
        if webhook_info.url != full_webhook_url:
            await application.bot.set_webhook(url=full_webhook_url)
            logger.info(f"Webhook configuré sur {full_webhook_url}")
        else:
            logger.info(f"Webhook déjà configuré sur {full_webhook_url}")

    if __name__ != "__main__":
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Si une boucle tourne déjà, on l'utilise pour lancer notre tâche
                loop.create_task(setup())
            else:
                # Sinon, on lance une nouvelle boucle jusqu'à ce que setup() soit terminé
                loop.run_until_complete(setup())
        except RuntimeError:
            # Sécurité si get_event_loop échoue dans certains environnements
            asyncio.run(setup())