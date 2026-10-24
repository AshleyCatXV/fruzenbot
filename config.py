import os

BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = 5076741028  # Твой личный ID
ADMIN_CHAT_ID = -1001671214807  # ID группы для анкет и форм (начинается с -100...)

if not BOT_TOKEN:
    raise ValueError("Переменная BOT_TOKEN не задана!")
