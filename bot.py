import logging
import os
import re
from dotenv import load_dotenv
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

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

# Vérification des variables d'environnement
logger.info("Vérification des variables d'environnement...")
if not TELEGRAM_TOKEN:
    logger.error("TELEGRAM_TOKEN non trouvé!")
if not CRYPTOCOMPARE_API_KEY:
    logger.error("CRYPTOCOMPARE_API_KEY non trouvé!")

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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

async def send_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

def main():
    """Fonction principale du bot"""
    # Vérification des variables d'environnement
    if not TELEGRAM_TOKEN or not CRYPTOCOMPARE_API_KEY:
        logger.error("Variables d'environnement manquantes !")
        return

    # Initialisation de l'application
    logger.info("Initialisation du bot...")
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Ajout des gestionnaires de commandes
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("actus", send_news))

    # Démarrage du bot
    logger.info("Bot démarré !")
    application.run_polling()

if __name__ == "__main__":
    main() 