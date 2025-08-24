import os
import logging
import base64
import openai

from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters


# Read environment variables
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
REPLY_LANGUAGE = os.environ.get("REPLY_LANGUAGE", "ru").lower()

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a greeting when the /start command is issued."""
    greeting = {
        "ru": "Привет! Отправьте фотографию предмета с барахолки или антиквариата, и я попробую рассказать, что это, для чего используется, когда примерно выпущено и сколько может стоить.",
        "en": "Hi! Send a photo of a flea market or antique object and I'll try to tell you what it is, what it's used for, when it was made and how much it might be worth.",
        "pt": "Olá! Envie uma foto de um objeto de um mercado de pulgas ou antiquário e eu tentarei dizer o que é, para que serve, quando foi feito e quanto pode valer.",
    }.get(REPLY_LANGUAGE, "Hi! Send me a photo and I'll try to identify it.")
    await update.message.reply_text(greeting)


async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming photos: download and send to OpenAI vision for analysis."""
    try:
        if OPENAI_API_KEY is None:
            await update.message.reply_text(
                "API key not configured. Please set OPENAI_API_KEY environment variable."
            )
            return

        # Get the highest resolution photo
        photo = update.message.photo[-1]
        photo_file = await photo.get_file()
        photo_bytes = await photo_file.download_as_bytearray()

        # Encode photo as base64 data URI
        image_b64 = base64.b64encode(photo_bytes).decode("utf-8")
        data_uri = f"data:image/jpeg;base64,{image_b64}"

        # Prepare prompt based on language
        prompt_map = {
            "ru": "Определите объект на фото. Расскажите, что это, для чего используется, примерный период выпуска и примерную стоимость (в евро). Ответь, пожалуйста, на русском языке.",
            "en": "Identify the object in the photo. Describe what it is, what it's used for, the approximate production period and its approximate price (in EUR). Answer in English, please.",
            "pt": "Identifique o objeto na foto. Descreva o que é, para que serve, o período aproximado de produção e o seu preço aproximado (em EUR). Responda em português, por favor.",
        }
        prompt = prompt_map.get(REPLY_LANGUAGE, prompt_map["ru"])

        # Configure OpenAI client
        openai.api_key = OPENAI_API_KEY

        # Build messages for OpenAI Vision
        messages = [
            {
                "role": "system",
                "content": "You are a knowledgeable antique expert. You can identify objects from images and provide descriptions, usage, period of manufacture and price ranges."
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": data_uri},
                ],
            },
        ]

        # Call the GPT-4 Vision model
        response = openai.ChatCompletion.create(
            model="gpt-4-vision-preview",
            messages=messages,
            max_tokens=500,
        )

        reply = response["choices"][0]["message"]["content"].strip()
        await update.message.reply_text(reply)

    except Exception as exc:
        logger.exception("Failed to process image: %s", exc)
        await update.message.reply_text(
            "Произошла ошибка при обработке изображения. Попробуйте ещё раз позже."
        )


def main() -> None:
    """Start the Telegram bot."""
    token = TELEGRAM_BOT_TOKEN
    if not token:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN environment variable is not set."
        )

    application = ApplicationBuilder().token(token).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.PHOTO, photo_handler))

    # Start the bot (polling)
    application.run_polling()


if __name__ == "__main__":
    main()