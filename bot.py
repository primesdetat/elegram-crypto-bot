# TEST FINAL DE SAUVEGARDE
import logging
import os
import aiohttp
import asyncio
import atexit
import traceback
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.constants import ParseMode
from concurrent.futures import ThreadPoolExecutor

# Version de l'application
APP_VERSION = "2024.03.19 - 19:15"

# --- Configuration ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Récupération des clés depuis les variables d'environnement de Render
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CRYPTOCOMPARE_API_KEY = os.getenv("CRYPTOCOMPARE_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Variables globales
application = None
http_session = None
executor = ThreadPoolExecutor(max_workers=1)

def run_async(coro):
    """Exécute une coroutine dans une nouvelle boucle d'événements."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    except Exception as e:
        logger.error(f"Erreur dans run_async: {str(e)}\n{traceback.format_exc()}")
        raise
    finally:
        loop.close()

async def get_http_session():
    """Crée ou récupère la session HTTP globale."""
    global http_session
    if http_session is None or http_session.closed:
        http_session = aiohttp.ClientSession()
    return http_session

async def close_http_session():
    """Ferme la session HTTP globale."""
    global http_session
    if http_session and not http_session.closed:
        await http_session.close()
        http_session = None

async def get_crypto_news():
    """Récupère les dernières actualités crypto depuis l'API CryptoCompare."""
    url = f"https://min-api.cryptocompare.com/data/v2/news/?lang=FR&api_key={CRYPTOCOMPARE_API_KEY}"
    session = None
    try:
        logger.info("Début de la récupération des actualités...")
        session = await get_http_session()
        
        async with session.get(url, timeout=5) as response:
            logger.info(f"Réponse reçue de l'API: {response.status}")
            response.raise_for_status()
            data = await response.json()
            logger.info("Données JSON reçues avec succès")

            if data.get("Type") == 100 and "Data" in data:
                articles = data["Data"][:5]
                logger.info(f"Nombre d'articles trouvés: {len(articles)}")
                
                formatted_news = []
                for article in articles:
                    title = article.get('title', 'Titre non disponible')
                    article_url = article.get('url', '#')
                    source = article.get('source', 'Source inconnue')
                    
                    # Déterminer l'émoji en fonction du titre
                    emoji = "📰"  # Émoji par défaut
                    title_lower = title.lower()
                    
                    if any(word in title_lower for word in ['bitcoin', 'btc']):
                        emoji = "₿"
                    elif any(word in title_lower for word in ['ethereum', 'eth']):
                        emoji = "Ξ"
                    elif any(word in title_lower for word in ['prix', 'price', 'cours']):
                        emoji = "📊"
                    elif any(word in title_lower for word in ['régulation', 'regulation', 'loi', 'law']):
                        emoji = "⚖️"
                    elif any(word in title_lower for word in ['hack', 'piratage', 'vol']):
                        emoji = "🔒"
                    elif any(word in title_lower for word in ['adoption', 'partenariat', 'partnership']):
                        emoji = "🤝"
                    
                    # Formatage amélioré avec HTML
                    formatted_news.append(
                        f"{emoji} <b>{title}</b>\n"
                        f"📌 Source: {source}\n"
                        f"🔗 <a href='{article_url}'>Lire l'article</a>\n"
                    )
                
                # Séparateur plus élégant entre les articles
                result = "\n\n" + "✨" + "—" * 20 + "✨" + "\n\n".join(formatted_news)
                logger.info("Formatage des actualités terminé")
                return result
            else:
                logger.error(f"Format de réponse inattendu: {data}")
                return "Désolé, je n'ai pas pu récupérer les actualités (format de réponse inattendu)."
    except asyncio.TimeoutError:
        logger.error("Timeout lors de l'appel à l'API CryptoCompare")
        return "Désolé, la requête a pris trop de temps. Veuillez réessayer."
    except aiohttp.ClientError as e:
        logger.error(f"ERREUR lors de l'appel à CryptoCompare: {e}")
        return "Erreur de connexion à la source d'actualités. Veuillez réessayer plus tard."
    except Exception as e:
        logger.error(f"Erreur inattendue: {str(e)}\n{traceback.format_exc()}")
        return "Une erreur inattendue s'est produite. Veuillez réessayer."

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Message de bienvenue pour la commande /start."""
    try:
        await update.message.reply_html(
            f"Bonjour ! Envoyez /actus pour les dernières nouvelles crypto.\n\n"
            f"<i>Version du code : {APP_VERSION}</i>"
        )
    except Exception as e:
        logger.error(f"Erreur dans start_command: {str(e)}\n{traceback.format_exc()}")
        raise

async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Envoie les actualités crypto."""
    try:
        await update.message.reply_text("Recherche des dernières actualités...")
        logger.info("Commande /actus reçue, début du traitement")
        
        news_message = await get_crypto_news()
        logger.info("Actualités récupérées, envoi du message")
        
        await update.message.reply_text(
            news_message,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        logger.info("Message envoyé avec succès")
    except Exception as e:
        logger.error(f"Erreur lors de l'envoi des actualités: {str(e)}\n{traceback.format_exc()}")
        await update.message.reply_text("Désolé, une erreur s'est produite lors de la récupération des actualités.")

async def setup():
    """Initialise l'application et configure le webhook."""
    global application
    if not TELEGRAM_TOKEN:
        logger.error("La variable d'environnement TELEGRAM_TOKEN n'est pas définie !")
        return
    
    try:
        # Initialisation de l'application
        application = Application.builder().token(TELEGRAM_TOKEN).build()
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("actus", news_command))
        
        # Configuration du webhook
        if WEBHOOK_URL:
            await application.initialize()
            webhook_info = await application.bot.get_webhook_info()
            full_webhook_url = f"{WEBHOOK_URL}/{TELEGRAM_TOKEN}"
            
            if webhook_info.url != full_webhook_url:
                await application.bot.set_webhook(url=full_webhook_url)
                logger.info(f"Webhook configuré sur {full_webhook_url}")
            else:
                logger.info(f"Webhook déjà configuré sur {full_webhook_url}")
        else:
            logger.error("WEBHOOK_URL n'est pas définie !")
    except Exception as e:
        logger.error(f"Erreur lors de l'initialisation: {str(e)}\n{traceback.format_exc()}")

async def shutdown():
    """Ferme proprement toutes les ressources."""
    global application, http_session
    try:
        if application:
            await application.shutdown()
            logger.info("Application arrêtée proprement.")
        
        if http_session and not http_session.closed:
            await http_session.close()
            logger.info("Session HTTP fermée proprement.")
    except Exception as e:
        logger.error(f"Erreur lors de l'arrêt: {str(e)}\n{traceback.format_exc()}")

# --- Partie Serveur Web (Flask) ---
app = Flask(__name__)

@app.route("/")
def index():
    return f"Bot server is running. Version: {APP_VERSION}"

@app.route(f"/{TELEGRAM_TOKEN}", methods=['POST'])
def webhook():
    if not application:
        logger.error("Application non initialisée")
        return "Bot not configured", 500
    
    try:
        update_data = request.get_json()
        if not update_data:
            logger.error("Données de mise à jour vides")
            return "No data", 400
        
        logger.info(f"Webhook reçu: {update_data}")
        update = Update.de_json(update_data, application.bot)
        
        # Exécuter le traitement de la mise à jour dans un thread séparé
        future = executor.submit(run_async, application.process_update(update))
        try:
            future.result(timeout=30)  # Attendre le résultat avec un timeout
            logger.info("Traitement de la mise à jour terminé avec succès")
            return "ok", 200
        except Exception as e:
            logger.error(f"Erreur lors du traitement de la mise à jour: {str(e)}\n{traceback.format_exc()}")
            return "error", 500
    except Exception as e:
        logger.error(f"Erreur lors du traitement du webhook: {str(e)}\n{traceback.format_exc()}")
        return "error", 500

def init_app():
    """Initialise l'application Flask."""
    try:
        logger.info("Démarrage de l'initialisation de l'application...")
        # Initialisation de l'application dans un thread séparé
        future = executor.submit(run_async, setup())
        try:
            future.result(timeout=30)  # Attendre l'initialisation avec un timeout
            logger.info("Initialisation de l'application terminée avec succès")
            return app
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation: {str(e)}\n{traceback.format_exc()}")
            return None
    except Exception as e:
        logger.error(f"Erreur lors de l'initialisation de l'application: {str(e)}\n{traceback.format_exc()}")
        return None

# Initialisation de l'application
app = init_app()

# Enregistrement de la fonction d'arrêt
atexit.register(lambda: executor.submit(run_async, shutdown()))