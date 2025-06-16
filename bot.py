# TEST FINAL DE SAUVEGARDE
import logging
# ... le reste du code
import os
import requests
import asyncio
import atexit
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Version de l'application
APP_VERSION = "2024.03.19 - 16:30"

# --- Configuration ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Récupération des clés depuis les variables d'environnement de Render
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CRYPTOCOMPARE_API_KEY = os.getenv("CRYPTOCOMPARE_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Création d'une boucle d'événements globale
loop = None

def get_or_create_eventloop():
    """Crée ou récupère la boucle d'événements."""
    global loop
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop

# --- Fonctions du bot (métier) ---
def escape_markdown(text):
    """Échappe les caractères spéciaux pour MarkdownV2."""
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text

async def get_crypto_news():
    """Récupère les dernières actualités crypto depuis l'API CryptoCompare."""
    url = f"https://min-api.cryptocompare.com/data/v2/news/?lang=FR&api_key={CRYPTOCOMPARE_API_KEY}"
    try:
        logger.info("Début de la récupération des actualités...")
        response = requests.get(url, timeout=5)  # Réduit le timeout à 5 secondes
        logger.info(f"Réponse reçue de l'API: {response.status_code}")
        
        response.raise_for_status()
        data = response.json()
        logger.info("Données JSON reçues avec succès")

        if data.get("Type") == 100 and "Data" in data:
            articles = data["Data"][:5]
            logger.info(f"Nombre d'articles trouvés: {len(articles)}")
            
            formatted_news = []
            for article in articles:
                title = article.get('title', 'Titre non disponible')
                title_escaped = escape_markdown(title)
                
                article_url = article.get('url', '#')
                source = article.get('source', 'Source inconnue')
                source_escaped = escape_markdown(source)
                
                formatted_news.append(
                    f"*{title_escaped}*\n"
                    f"Source: {source_escaped}\n"
                    f"[Lire l'article]({article_url})\n"
                )
            
            result = "\n---\n\n".join(formatted_news)
            logger.info("Formatage des actualités terminé")
            return result
        else:
            logger.error(f"Format de réponse inattendu: {data}")
            return "Désolé, je n'ai pas pu récupérer les actualités (format de réponse inattendu)."
    except requests.exceptions.Timeout:
        logger.error("Timeout lors de l'appel à l'API CryptoCompare")
        return "Désolé, la requête a pris trop de temps. Veuillez réessayer."
    except requests.exceptions.RequestException as e:
        logger.error(f"ERREUR lors de l'appel à CryptoCompare: {e}")
        return "Erreur de connexion à la source d'actualités. Veuillez réessayer plus tard."
    except Exception as e:
        logger.error(f"Erreur inattendue: {e}")
        return "Une erreur inattendue s'est produite. Veuillez réessayer."

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Message de bienvenue pour la commande /start."""
    await update.message.reply_html(
        f"Bonjour ! Envoyez /actus pour les dernières nouvelles crypto.\n\n"
        f"<i>Version du code : {APP_VERSION}</i>"
    )

async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Envoie les actualités crypto."""
    try:
        await update.message.reply_text("Recherche des dernières actualités...")
        logger.info("Commande /actus reçue, début du traitement")
        
        news_message = await get_crypto_news()
        logger.info("Actualités récupérées, envoi du message")
        
        await update.message.reply_text(news_message, parse_mode='MarkdownV2', disable_web_page_preview=True)
        logger.info("Message envoyé avec succès")
    except Exception as e:
        logger.error(f"Erreur lors de l'envoi des actualités: {e}")
        await update.message.reply_text("Désolé, une erreur s'est produite lors de la récupération des actualités.")

# --- Initialisation de l'application Telegram ---
if not TELEGRAM_TOKEN:
    logger.error("La variable d'environnement TELEGRAM_TOKEN n'est pas définie !")
    application = None
else:
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("actus", news_command))

    # --- Partie Serveur Web (Flask) ---
    app = Flask(__name__)

    @app.route("/")
    def index():
        return f"Bot server is running. Version: {APP_VERSION}"

    @app.route(f"/{TELEGRAM_TOKEN}", methods=['POST'])
    async def webhook():
        if application:
            try:
                update_data = request.get_json()
                update = Update.de_json(update_data, application.bot)
                
                # Utiliser la boucle d'événements globale
                loop = get_or_create_eventloop()
                
                # Exécuter le traitement de la mise à jour dans la boucle
                await application.process_update(update)
                return "ok", 200
            except Exception as e:
                logger.error(f"Erreur lors du traitement du webhook: {e}")
                return "error", 500
        return "Bot not configured", 500

    # --- Logique de démarrage et d'arrêt ---
    async def setup():
        if not application or not WEBHOOK_URL:
            logger.error("Application non initialisée ou WEBHOOK_URL manquante.")
            return
        
        try:
            await application.initialize()
            webhook_info = await application.bot.get_webhook_info()
            full_webhook_url = f"{WEBHOOK_URL}/{TELEGRAM_TOKEN}"
            
            if webhook_info.url != full_webhook_url:
                await application.bot.set_webhook(url=full_webhook_url)
                logger.info(f"Webhook configuré sur {full_webhook_url}")
            else:
                logger.info(f"Webhook déjà configuré sur {full_webhook_url}")
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation: {e}")

    async def shutdown():
        if application:
            try:
                await application.shutdown()
                logger.info("Application arrêtée proprement.")
            except Exception as e:
                logger.error(f"Erreur lors de l'arrêt: {e}")

    if __name__ != "__main__" and application:
        try:
            # Initialiser la boucle d'événements globale
            loop = get_or_create_eventloop()
            
            # Exécuter la configuration
            loop.run_until_complete(setup())
            
            # Enregistrer la fonction d'arrêt
            atexit.register(lambda: loop.run_until_complete(shutdown()))
        except Exception as e:
            logger.error(f"Erreur lors du démarrage: {e}")