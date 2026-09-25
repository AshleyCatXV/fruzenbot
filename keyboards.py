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
        [InlineKeyboardButton(text="🗺 Управление картой", callback_data="admin_map")],
        [InlineKeyboardButton(text="📦 Управление ресурспаком", callback_data="admin_rp")],
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


def admin_map_kb(has_map: bool):
    kb = []
    if has_map:
        kb.append([InlineKeyboardButton(text="🗑 Удалить карту", callback_data="admin_map_del")])
    kb.append([InlineKeyboardButton(text="🖼 Загрузить новую карту", callback_data="admin_map_upload")])
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def admin_rp_kb(has_rp: bool):
    kb = []
    if has_rp:
        kb.append([InlineKeyboardButton(text="🗑 Удалить ресурспак", callback_data="admin_rp_del")])
    kb.append([InlineKeyboardButton(text="📥 Загрузить новый ресурспак", callback_data="admin_rp_upload")])
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def admin_factions_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить фракцию", callback_data="admin_faction_add")],
        [InlineKeyboardButton(text="➖ Удалить фракцию", callback_data="admin_faction_del")],
        [InlineKeyboardButton(text="🎯 Назначить игроку", callback_data="admin_faction_assign")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin")],
    ])


def admin_whitelist_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить игрока", callback_data="admin_wl_add")],
        [InlineKeyboardButton(text="➖ Удалить игрока", callback_data="admin_wl_del")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin")],
    ])


def admin_links_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить ссылку", callback_data="admin_link_add")],
        [InlineKeyboardButton(text="➖ Удалить ссылку", callback_data="admin_link_del")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin")],
    ])


def paginated_kb(items, page: int, per_page: int, prefix: str, back_target: str):
    """
    items: список кортежей (id, name)
    prefix: строка, к которой приклеивается id в callback_data, например "faction_del:"
    """
    total_pages = max(1, (len(items) + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))
    start = page * per_page
    end = start + per_page
    page_items = items[start:end]

    kb = []
    for item_id, name in page_items:
        kb.append([InlineKeyboardButton(text=name, callback_data=f"{prefix}{item_id}")])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"pg:{prefix}:{page-1}"))
    if total_pages > 1:
        nav.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"pg:{prefix}:{page+1}"))
    if nav:
        kb.append(nav)

    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=back_target)])
    return InlineKeyboardMarkup(inline_keyboard=kb)
