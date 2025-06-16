import logging
import os
import re
from dotenv import load_dotenv
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from flask import Flask, request
import asyncio

# Configuration du logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Chargement des variables d'environnement
load_dotenv()
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CRYPTOCOMPARE_API_KEY = os.getenv('CRYPTOCOMPARE_API_KEY')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')

# Vérification des variables d'environnement
logger.info("Vérification des variables d'environnement...")
if not all([TELEGRAM_TOKEN, CRYPTOCOMPARE_API_KEY, WEBHOOK_URL]):
    logger.error("Variables d'environnement manquantes!")
    missing = []
    if not TELEGRAM_TOKEN: missing.append("TELEGRAM_TOKEN")
    if not CRYPTOCOMPARE_API_KEY: missing.append("CRYPTOCOMPARE_API_KEY")
    if not WEBHOOK_URL: missing.append("WEBHOOK_URL")
    logger.error(f"Variables manquantes: {', '.join(missing)}")

def escape_markdown(text):
    """Échappe les caractères spéciaux pour le formatage MarkdownV2"""
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text

async def get_crypto_news():
    """Récupère les actualités crypto depuis l'API CryptoCompare"""
    try:
        url = f"https://min-api.cryptocompare.com/data/v2/news/?lang=FR&api_key={CRYPTOCOMPARE_API_KEY}"
        logger.info(f"Requête API vers: {url}")
        response = requests.get(url)
        response.raise_for_status()
        
        data = response.json()
        logger.info(f"Réponse API reçue: {data}")
        
        # Vérification de la présence des données
        if not data.get('Data'):
            logger.warning("Aucune donnée trouvée dans la réponse API")
            return "❌ Aucune actualité trouvée."
        
        news = data['Data'][:5]  # Prend les 5 premiers articles
        message = "📰 Dernières actualités crypto :\n\n"
        
        for article in news:
            try:
                # Nettoyage du titre et de la source
                title = article.get('title', '').replace('*', '').replace('_', '').replace('[', '').replace(']', '')
                source = article.get('source', '').replace('*', '').replace('_', '')
                url = article.get('url', '')
                
                # Construction du message pour cet article
                article_message = f"• {title}\n"
                article_message += f"Source: {source}\n"
                article_message += f"Lien: {url}\n\n"
                
                message += article_message
            except Exception as e:
                logger.error(f"Erreur lors du formatage d'un article: {e}")
                continue
        
        if not message.strip():
            logger.warning("Message vide après formatage")
            return "❌ Aucune actualité trouvée."
            
        logger.info(f"Message final préparé: {message}")
        return message
    
    except requests.RequestException as e:
        logger.error(f"Erreur de requête: {e}")
        return f"❌ Erreur de connexion à l'API: {str(e)}"
    except Exception as e:
        logger.error(f"Erreur inattendue: {e}")
        return f"❌ Une erreur inattendue s'est produite: {str(e)}"

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestionnaire de la commande /start"""
    logger.info(f"Commande /start reçue de {update.effective_user.id}")
    welcome_message = (
        "👋 Bienvenue sur le Bot d'Actualités Crypto !\n\n"
        "Je peux vous tenir informé des dernières actualités du monde des cryptomonnaies.\n\n"
        "Commandes disponibles :\n"
        "/actus - Afficher les dernières actualités crypto\n"
        "/start - Afficher ce message d'aide"
    )
    await update.message.reply_text(welcome_message)

async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestionnaire de la commande /actus"""
    try:
        logger.info(f"Commande /actus reçue de {update.effective_user.id}")
        # Message de chargement
        loading_message = await update.message.reply_text("🔍 Recherche des dernières actualités...")
        
        # Récupération et envoi des actualités
        news = await get_crypto_news()
        logger.info(f"Tentative d'envoi du message: {news}")
        
        await loading_message.edit_text(
            news,
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.error(f"Erreur lors de l'envoi du message: {e}")
        await update.message.reply_text(f"❌ Erreur lors de l'envoi du message: {str(e)}")

# Initialisation de l'application Flask
app = Flask(__name__)

# Initialisation de l'application Telegram
application = Application.builder().token(TELEGRAM_TOKEN).build()

# Ajout des gestionnaires de commandes
application.add_handler(CommandHandler("start", start_command))
application.add_handler(CommandHandler("actus", news_command))

@app.route('/')
def index():
    """Route principale pour vérifier que le serveur est en ligne"""
    return "Bot server is running"

@app.route(f"/{TELEGRAM_TOKEN}", methods=['POST'])
async def webhook():
    """Route pour le webhook Telegram"""
    try:
        update = Update.de_json(request.get_json(), application.bot)
        await application.process_update(update)
        return "ok"
    except Exception as e:
        logger.error(f"Erreur dans le webhook: {e}")
        return "error", 500

async def setup():
    """Configuration du webhook au démarrage"""
    webhook_url = f"{WEBHOOK_URL}/{TELEGRAM_TOKEN}"
    logger.info(f"Configuration du webhook: {webhook_url}")
    await application.bot.set_webhook(url=webhook_url)

# Configuration du webhook au démarrage
@app.before_first_request
def before_first_request():
    """Configure le webhook avant la première requête"""
    asyncio.run(setup())

# Démarrage du serveur Flask en mode développement
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8000) 