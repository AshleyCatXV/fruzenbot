from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def main_kb(is_admin: bool):
    kb = [
        [InlineKeyboardButton(text="🚩 Фракции", callback_data="factions"),
         InlineKeyboardButton(text="🗺 Карта", callback_data="map")],
        [InlineKeyboardButton(text="👥 Игроки", callback_data="players"),
         InlineKeyboardButton(text="📦 Ресурспак", callback_data="resourcepack")],
        [InlineKeyboardButton(text="🔗 Ссылки", callback_data="links"),
         InlineKeyboardButton(text="👤 Профиль", callback_data="profile")],
        [InlineKeyboardButton(text="📜 Правила", callback_data="rules"),
         InlineKeyboardButton(text="ℹ️ Информация", callback_data="info")],
        [InlineKeyboardButton(text="✉️ Отправить форму", callback_data="form")],
    ]
    if is_admin:
        kb.append([InlineKeyboardButton(text="🛠 Меню создателя", callback_data="admin")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def back_kb(target="back_main"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=target)]
    ])


def admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚩 Управление фракциями", callback_data="admin_factions")],
        [InlineKeyboardButton(text="👥 Белый список", callback_data="admin_whitelist")],
        [InlineKeyboardButton(text="🔗 Управление ссылками", callback_data="admin_links")],
        [InlineKeyboardButton(text="🗺 Загрузить карту", callback_data="admin_map")],
        [InlineKeyboardButton(text="📦 Загрузить ресурспак", callback_data="admin_resourcepack")],
        [InlineKeyboardButton(text="🌍 Глобальные переменные", callback_data="admin_globals")],
        [InlineKeyboardButton(text="📢 Написать пользователю", callback_data="admin_send")],
        [InlineKeyboardButton(text="👥 Список пользователей", callback_data="admin_users")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")],
    ])


def profile_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Изменить ник в боте", callback_data="edit_nick_bot")],
        [InlineKeyboardButton(text="🎮 Указать ник на сервере", callback_data="edit_nick_server")],
        [InlineKeyboardButton(text="🆔 Указать UUID", callback_data="edit_uuid")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")],
    ])
