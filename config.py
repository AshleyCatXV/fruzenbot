import os

# Токен берётся из переменной окружения BotHost
BOT_TOKEN = os.getenv('BOT_TOKEN')

# Твой Telegram ID (впиши сюда свой ID, полученный от @userinfobot)
ADMIN_ID = 5076741028  # ЗАМЕНИ НА СВОЙ ID, например 123456789

if not BOT_TOKEN:
    raise ValueError("Переменная BOT_TOKEN не задана! Проверь настройки в BotHost.")