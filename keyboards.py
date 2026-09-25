from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def main_kb(is_admin: bool):
    kb = [
        [InlineKeyboardButton(text="👤 Мой профиль", callback_data="profile")],
        [InlineKeyboardButton(text="🏷 Изменить тег", callback_data="edit_tag")],
        [InlineKeyboardButton(text="📝 Изменить переменную", callback_data="edit_var")],
        [InlineKeyboardButton(text="🌍 Глобальные значения", callback_data="globals")],
    ]
    if is_admin:
        kb.append([InlineKeyboardButton(text="🛠 Админ-панель", callback_data="admin")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Список пользователей", callback_data="admin_users")],
        [InlineKeyboardButton(text="✏️ Изменить данные пользователя", callback_data="admin_user_edit")],
        [InlineKeyboardButton(text="🖼 Обновить картинку", callback_data="admin_image")],
        [InlineKeyboardButton(text="📢 Написать пользователю", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="🌍 Глобальные переменные", callback_data="admin_globals")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")],
    ])