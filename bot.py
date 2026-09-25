import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

import database as db
from config import BOT_TOKEN, ADMIN_ID
from keyboards import (
    main_kb, admin_kb, back_kb, profile_kb,
    admin_map_kb, admin_rp_kb, admin_factions_kb,
    admin_whitelist_kb, admin_links_kb, paginated_kb
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

SEP = "—" * 10  # 10 длинных тире (символ —)
PER_PAGE = 8    # сколько фракций/игроков на странице


class Form(StatesGroup):
    edit_nick_bot = State()
    edit_nick_server = State()
    edit_uuid = State()
    admin_add_faction = State()
    admin_del_faction = State()
    admin_assign_faction = State()
    admin_add_wl = State()
    admin_del_wl = State()
    admin_add_link = State()
    admin_del_link = State()
    admin_set_global = State()
    admin_send_user = State()
    admin_upload_map = State()
    admin_upload_rp = State()
    admin_rp_instruction = State()


def is_admin(uid: int) -> bool:
    return uid == ADMIN_ID


def user_display(row) -> str:
    """
    row: (user_id, username, nick_bot)
    Формат:
      • @username (123456789)
      • 123456789 (если username нет)
    """
    user_id, username, nick_bot = row
    if username:
        return f"• @{username} ({user_id})"
    return f"• {user_id}"


async def show_main_menu(target, user_id: int):
    """Открывает главное меню. target может быть Message или CallbackQuery."""
    user = await db.get_user(user_id)
    nick = user[2] if user and user[2] else (user[1] if user and user[1] else "друг")

    text = f"Здравствуйте, {nick}!\n🏠 Главное меню.\n{SEP}"
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, reply_markup=main_kb(is_admin(user_id)))
    else:
        await target.answer(text, reply_markup=main_kb(is_admin(user_id)))


# ==================== /start ====================
@dp.message(CommandStart())
async def start(m: Message):
    await db.add_user(m.from_user.id, m.from_user.username or "")
    await show_main_menu(m, m.from_user.id)


@dp.callback_query(F.data == "back_main")
async def back_main(c: CallbackQuery):
    await show_main_menu(c, c.from_user.id)
    await c.answer()


@dp.callback_query(F.data == "noop")
async def noop(c: CallbackQuery):
    await c.answer()


# ==================== 1. ФРАКЦИИ ====================
@dp.callback_query(F.data == "factions")
async def factions_view(c: CallbackQuery):
    rows = await db.get_factions()
    if not rows:
        text = "🚩 Фракции.\n" + SEP + "\n\nПока не добавлено ни одной фракции."
    else:
        lines = [f"{i}) {name}" for i, (_, name) in enumerate(rows, start=1)]
        text = "🚩 Фракции.\n" + SEP + "\n\n" + "\n".join(lines)
    await c.message.edit_text(text, reply_markup=back_kb())
    await c.answer()


# ==================== 2. КАРТА ====================
@dp.callback_query(F.data == "map")
async def map_view(c: CallbackQuery):
    file_id = await db.get_image("map")
    if not file_id:
        await c.message.edit_text(
            "🗺 Карта.\n" + SEP + "\n\nКарта пока не загружена.",
            reply_markup=back_kb()
        )
        await c.answer()
        return

    # Если пришли из меню — удаляем старое текстовое сообщение
    try:
        await c.message.delete()
    except Exception:
        pass
    await bot.send_photo(
        c.from_user.id, file_id,
        caption="🗺 Карта сервера.\n" + SEP,
        reply_markup=back_kb()
    )
    await c.answer()


# ==================== 3. ИГРОКИ ====================
@dp.callback_query(F.data == "players")
async def players_view(c: CallbackQuery):
    rows = await db.get_whitelist()
    if not rows:
        text = "👥 Игроки.\n" + SEP + "\n\nБелый список пуст."
    else:
        lines = [f"{i}) {nick}" for i, (_, nick) in enumerate(rows, start=1)]
        text = "👥 Игроки.\n" + SEP + "\n\n" + "\n".join(lines)
    await c.message.edit_text(text, reply_markup=back_kb())
    await c.answer()


# ==================== 4. РЕСУРСПАК ====================
@dp.callback_query(F.data == "resourcepack")
async def rp_view(c: CallbackQuery):
    row = await db.get_resourcepack()
    if not row or not row[0]:
        await c.message.edit_text(
            "📦 Ресурспак.\n" + SEP + "\n\nРесурспак пока не загружен.",
            reply_markup=back_kb()
        )
        await c.answer()
        return

    file_id, instruction = row
    try:
        await c.message.delete()
    except Exception:
        pass
    await bot.send_document(
        c.from_user.id, file_id,
        caption="📦 Ресурспак сервера.\n" + SEP + "\n\n" + (instruction or "Инструкция не указана."),
        reply_markup=back_kb()
    )
    await c.answer()


# ==================== 5. ССЫЛКИ ====================
@dp.callback_query(F.data == "links")
async def links_view(c: CallbackQuery):
    rows = await db.get_links()
    if not rows:
        await c.message.edit_text(
            "🔗 Ссылки.\n" + SEP + "\n\nПока не добавлено ни одной ссылки.",
            reply_markup=back_kb()
        )
    else:
        kb = [[InlineKeyboardButton(text=title, url=url)] for _, title, url in rows]
        kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")])
        await c.message.edit_text("🔗 Ссылки.\n" + SEP,
                                  reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await c.answer()


# ==================== 6. ПРОФИЛЬ ====================
@dp.callback_query(F.data == "profile")
async def profile_view(c: CallbackQuery):
    u = await db.get_user(c.from_user.id)
    if not u:
        await db.add_user(c.from_user.id, c.from_user.username or "")
        u = await db.get_user(c.from_user.id)
    text = (
        "👤 Профиль.\n" + SEP + "\n\n"
        f"Ник в боте: {u[2] or '—'}\n"
        f"Ник на сервере: {u[3] or '—'}\n"
        f"Фракция: {u[4] or '—'}\n"
        f"UUID: {u[5] or '—'}"
    )
    await c.message.edit_text(text, reply_markup=profile_kb())
    await c.answer()


@dp.callback_query(F.data == "edit_nick_bot")
async def edit_nick_bot(c: CallbackQuery, state: FSMContext):
    await c.message.answer("Введи новый ник в боте:")
    await state.set_state(Form.edit_nick_bot)
    await c.answer()


@dp.message(Form.edit_nick_bot)
async def save_nick_bot(m: Message, state: FSMContext):
    await db.set_user_field(m.from_user.id, "nick_bot", m.text.strip())
    await state.clear()
    await m.answer("✅ Ник в боте обновлён.")
    await show_main_menu(m, m.from_user.id)


@dp.callback_query(F.data == "edit_nick_server")
async def edit_nick_server(c: CallbackQuery, state: FSMContext):
    await c.message.answer("Введи свой ник на сервере Minecraft:")
    await state.set_state(Form.edit_nick_server)
    await c.answer()


@dp.message(Form.edit_nick_server)
async def save_nick_server(m: Message, state: FSMContext):
    await db.set_user_field(m.from_user.id, "nick_server", m.text.strip())
    await state.clear()
    await m.answer("✅ Ник на сервере обновлён.")
    await show_main_menu(m, m.from_user.id)


@dp.callback_query(F.data == "edit_uuid")
async def edit_uuid(c: CallbackQuery, state: FSMContext):
    await c.message.answer("Введи свой UUID (или пустое сообщение, чтобы удалить):")
    await state.set_state(Form.edit_uuid)
    await c.answer()


@dp.message(Form.edit_uuid)
async def save_uuid(m: Message, state: FSMContext):
    await db.set_user_field(m.from_user.id, "uuid", m.text.strip())
    await state.clear()
    await m.answer("✅ UUID обновлён.")
    await show_main_menu(m, m.from_user.id)


# ==================== 7. ПРАВИЛА ====================
@dp.callback_query(F.data == "rules")
async def rules_view(c: CallbackQuery):
    url = await db.get_global("rules_url", "")
    if not url:
        await c.message.edit_text(
            "📜 Правила.\n" + SEP + "\n\nСсылка на правила ещё не задана.",
            reply_markup=back_kb()
        )
    else:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📖 Открыть правила", url=url)],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")],
        ])
        await c.message.edit_text("📜 Правила.\n" + SEP, reply_markup=kb)
    await c.answer()


# ==================== 8. ИНФОРМАЦИЯ ====================
@dp.callback_query(F.data == "info")
async def info_view(c: CallbackQuery):
    version = await db.get_global("server_version", "—")
    core = await db.get_global("server_core", "—")
    ip = await db.get_global("server_ip", "скрыт (только для вайтлиста)")
    status = await db.get_global("server_status", "неизвестно")
    articles = await db.get_global("server_articles", "—")

    text = (
        "ℹ️ Информация.\n" + SEP + "\n\n"
        f"Версия: {version}\n"
        f"Ядро: {core}\n"
        f"IP: {ip}\n"
        f"Статус: {status}\n\n"
        f"Полезные статьи:\n{articles}"
    )
    await c.message.edit_text(text, reply_markup=back_kb())
    await c.answer()


# ==================== 9. ФОРМА ====================
@dp.callback_query(F.data == "form")
async def form_view(c: CallbackQuery):
    await c.message.edit_text(
        "✉️ Отправить форму.\n" + SEP + "\n\nФункция в разработке.",
        reply_markup=back_kb()
    )
    await c.answer()


# ==================== 10. МЕНЮ СОЗДАТЕЛЯ ====================
@dp.callback_query(F.data == "admin")
async def admin_menu(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    await c.message.edit_text("🛠 Меню создателя.\n" + SEP, reply_markup=admin_kb())
    await c.answer()


# --- Фракции ---
@dp.callback_query(F.data == "admin_factions")
async def admin_factions(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    await c.message.edit_text("🚩 Управление фракциями.\n" + SEP, reply_markup=admin_factions_kb())
    await c.answer()


@dp.callback_query(F.data == "admin_faction_add")
async def admin_faction_add(c: CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    await c.message.answer("Введи название новой фракции:")
    await state.set_state(Form.admin_add_faction)
    await c.answer()


@dp.message(Form.admin_add_faction)
async def save_faction(m: Message, state: FSMContext):
    await db.add_faction(m.text.strip())
    await state.clear()
    await m.answer("✅ Фракция добавлена.")
    await admin_factions(await _fake_cb(m))


async def _fake_cb(m: Message):
    """Псевдо-CallbackQuery, чтобы вернуть пользователя в меню."""
    class FakeMsg:
        async def edit_text(self, *a, **kw):
            return await m.answer(*a, **kw)
    class FakeCb:
        from_user = m.from_user
        message = FakeMsg()
        async def answer(self, *a, **kw):
            pass
    return FakeCb()


@dp.callback_query(F.data == "admin_faction_del")
async def admin_faction_del(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    rows = await db.get_factions()
    if not rows:
        await c.answer("Фракций нет.", show_alert=True)
        return
    kb = paginated_kb(rows, 0, PER_PAGE, "faction_del:", "admin_factions")
    await c.message.edit_text("🚩 Выбери фракцию для удаления.\n" + SEP, reply_markup=kb)
    await c.answer()


@dp.callback_query(F.data.startswith("pg:faction_del:"))
async def faction_del_page(c: CallbackQuery):
    page = int(c.data.split(":")[2])
    rows = await db.get_factions()
    kb = paginated_kb(rows, page, PER_PAGE, "faction_del:", "admin_factions")
    await c.message.edit_text("🚩 Выбери фракцию для удаления.\n" + SEP, reply_markup=kb)
    await c.answer()


@dp.callback_query(F.data.startswith("faction_del:"))
async def faction_del(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    fid = int(c.data.split(":")[1])
    await db.remove_faction_by_id(fid)
    rows = await db.get_factions()
    if not rows:
        await c.message.edit_text("✅ Фракция удалена.\n\nСписок фракций пуст.",
                                  reply_markup=admin_factions_kb())
    else:
        kb = paginated_kb(rows, 0, PER_PAGE, "faction_del:", "admin_factions")
        await c.message.edit_text(f"✅ Фракция удалена.\n\n🚩 Выбери следующую для удаления.\n" + SEP,
                                  reply_markup=kb)
    await c.answer("Удалено")


@dp.callback_query(F.data == "admin_faction_assign")
async def admin_faction_assign(c: CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    await c.message.answer("Введи ник игрока на сервере, которому назначить фракцию:")
    await state.set_state(Form.admin_assign_faction)
    await c.answer()


@dp.message(Form.admin_assign_faction)
async def assign_faction_nick(m: Message, state: FSMContext):
    nick = m.text.strip()
    user = await db.find_user_by_nick_server(nick)
    if not user:
        await m.answer(f"❌ Игрок с ником «{nick}» не найден в базе бота.")
        await state.clear()
        return
    await state.update_data(target_user=user[0], target_nick=nick)
    rows = await db.get_factions()
    if not rows:
        await m.answer("❌ Фракций нет. Сначала добавь их.")
        await state.clear()
        return
    kb = paginated_kb(rows, 0, PER_PAGE, "faction_pick:", "admin_factions")
    await m.answer(f"Выбери фракцию для игрока «{nick}»:", reply_markup=kb)
    await state.set_state(Form.admin_assign_faction)


@dp.callback_query(F.data.startswith("pg:faction_pick:"))
async def faction_pick_page(c: CallbackQuery, state: FSMContext):
    page = int(c.data.split(":")[2])
    rows = await db.get_factions()
    kb = paginated_kb(rows, page, PER_PAGE, "faction_pick:", "admin_factions")
    await c.message.edit_reply_markup(reply_markup=kb)
    await c.answer()


@dp.callback_query(F.data.startswith("faction_pick:"))
async def faction_pick(c: CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    fid = int(c.data.split(":")[1])
    rows = await db.get_factions()
    name = next((n for i, n in rows if i == fid), None)
    data = await state.get_data()
    target_user = data.get("target_user")
    target_nick = data.get("target_nick")
    if not target_user:
        await c.answer("Сессия истекла, начни заново.", show_alert=True)
        return
    await db.set_user_field(target_user, "fraction", name)
    await state.clear()
    await c.message.edit_text(f"✅ Игроку «{target_nick}» назначена фракция «{name}».",
                              reply_markup=admin_factions_kb())
    await c.answer("Готово")


# --- Whitelist ---
@dp.callback_query(F.data == "admin_whitelist")
async def admin_whitelist(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    await c.message.edit_text("👥 Белый список.\n" + SEP, reply_markup=admin_whitelist_kb())
    await c.answer()


@dp.callback_query(F.data == "admin_wl_add")
async def admin_wl_add(c: CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    await c.message.answer("Введи ник игрока для добавления:")
    await state.set_state(Form.admin_add_wl)
    await c.answer()


@dp.message(Form.admin_add_wl)
async def wl_add(m: Message, state: FSMContext):
    await db.add_whitelist(m.text.strip())
    await state.clear()
    await m.answer("✅ Игрок добавлен.")
    await admin_whitelist(await _fake_cb(m))


@dp.callback_query(F.data == "admin_wl_del")
async def admin_wl_del(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    rows = await db.get_whitelist()
    if not rows:
        await c.answer("Белый список пуст.", show_alert=True)
        return
    kb = paginated_kb(rows, 0, PER_PAGE, "wl_del:", "admin_whitelist")
    await c.message.edit_text("👥 Выбери игрока для удаления.\n" + SEP, reply_markup=kb)
    await c.answer()


@dp.callback_query(F.data.startswith("pg:wl_del:"))
async def wl_del_page(c: CallbackQuery):
    page = int(c.data.split(":")[2])
    rows = await db.get_whitelist()
    kb = paginated_kb(rows, page, PER_PAGE, "wl_del:", "admin_whitelist")
    await c.message.edit_text("👥 Выбери игрока для удаления.\n" + SEP, reply_markup=kb)
    await c.answer()


@dp.callback_query(F.data.startswith("wl_del:"))
async def wl_del(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    wid = int(c.data.split(":")[1])
    await db.remove_whitelist_by_id(wid)
    rows = await db.get_whitelist()
    if not rows:
        await c.message.edit_text("✅ Игрок удалён.\n\nСписок пуст.",
                                  reply_markup=admin_whitelist_kb())
    else:
        kb = paginated_kb(rows, 0, PER_PAGE, "wl_del:", "admin_whitelist")
        await c.message.edit_text("✅ Игрок удалён.\n\n👥 Выбери следующего.\n" + SEP, reply_markup=kb)
    await c.answer("Удалено")


# --- Ссылки ---
@dp.callback_query(F.data == "admin_links")
async def admin_links(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    await c.message.edit_text("🔗 Управление ссылками.\n" + SEP, reply_markup=admin_links_kb())
    await c.answer()


@dp.callback_query(F.data == "admin_link_add")
async def admin_link_add(c: CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    await c.message.answer("Введи в формате: Название | URL")
    await state.set_state(Form.admin_add_link)
    await c.answer()


@dp.message(Form.admin_add_link)
async def link_add(m: Message, state: FSMContext):
    try:
        title, url = m.text.split("|", 1)
        await db.add_link(title.strip(), url.strip())
        await m.answer("✅ Ссылка добавлена.")
    except Exception:
        await m.answer("❌ Формат: Название | URL")
    await state.clear()
    await admin_links(await _fake_cb(m))


@dp.callback_query(F.data == "admin_link_del")
async def admin_link_del(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    rows = await db.get_links()
    if not rows:
        await c.answer("Ссылок нет.", show_alert=True)
        return
    kb = paginated_kb([(i, t) for i, t, _ in rows], 0, PER_PAGE, "link_del:", "admin_links")
    await c.message.edit_text("🔗 Выбери ссылку для удаления.\n" + SEP, reply_markup=kb)
    await c.answer()


@dp.callback_query(F.data.startswith("pg:link_del:"))
async def link_del_page(c: CallbackQuery):
    page = int(c.data.split(":")[2])
    rows = await db.get_links()
    kb = paginated_kb([(i, t) for i, t, _ in rows], page, PER_PAGE, "link_del:", "admin_links")
    await c.message.edit_text("🔗 Выбери ссылку для удаления.\n" + SEP, reply_markup=kb)
    await c.answer()


@dp.callback_query(F.data.startswith("link_del:"))
async def link_del(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    lid = int(c.data.split(":")[1])
    await db.remove_link(lid)
    rows = await db.get_links()
    if not rows:
        await c.message.edit_text("✅ Ссылка удалена.\n\nСписок пуст.",
                                  reply_markup=admin_links_kb())
    else:
        kb = paginated_kb([(i, t) for i, t, _ in rows], 0, PER_PAGE, "link_del:", "admin_links")
        await c.message.edit_text("✅ Ссылка удалена.\n\n🔗 Выбери следующую.\n" + SEP, reply_markup=kb)
    await c.answer("Удалено")


# --- Карта ---
@dp.callback_query(F.data == "admin_map")
async def admin_map(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    has_map = bool(await db.get_image("map"))
    text = "🗺 Управление картой.\n" + SEP
    text += "\n\nСтатус: " + ("✅ карта загружена" if has_map else "❌ карта не загружена")
    await c.message.edit_text(text, reply_markup=admin_map_kb(has_map))
    await c.answer()


@dp.callback_query(F.data == "admin_map_upload")
async def admin_map_upload(c: CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    await c.message.answer("Пришли новое изображение карты (как фото):")
    await state.set_state(Form.admin_upload_map)
    await c.answer()


@dp.message(Form.admin_upload_map, F.photo)
async def save_map(m: Message, state: FSMContext):
    await db.set_image("map", m.photo[-1].file_id)
    await state.clear()
    await m.answer("✅ Карта сохранена.")
    await admin_map(await _fake_cb(m))


@dp.callback_query(F.data == "admin_map_del")
async def admin_map_del(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    await db.delete_image("map")
    await c.answer("Карта удалена")
    await admin_map(c)


# --- Ресурспак ---
@dp.callback_query(F.data == "admin_rp")
async def admin_rp(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    row = await db.get_resourcepack()
    has_rp = bool(row and row[0])
    text = "📦 Управление ресурспаком.\n" + SEP
    text += "\n\nСтатус: " + ("✅ ресурспак загружен" if has_rp else "❌ ресурспак не загружен")
    await c.message.edit_text(text, reply_markup=admin_rp_kb(has_rp))
    await c.answer()


@dp.callback_query(F.data == "admin_rp_upload")
async def admin_rp_upload(c: CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    await c.message.answer("Пришли файл ресурспака (как документ):")
    await state.set_state(Form.admin_upload_rp)
    await c.answer()


@dp.message(Form.admin_upload_rp, F.document)
async def save_rp_file(m: Message, state: FSMContext):
    await state.update_data(rp_file_id=m.document.file_id)
    await m.answer("Теперь пришли текст инструкции по установке:")
    await state.set_state(Form.admin_rp_instruction)


@dp.message(Form.admin_rp_instruction)
async def save_rp_instruction(m: Message, state: FSMContext):
    data = await state.get_data()
    file_id = data.get("rp_file_id")
    await db.set_resourcepack(file_id, m.text.strip())
    await state.clear()
    await m.answer("✅ Ресурспак сохранён.")
    await admin_rp(await _fake_cb(m))


@dp.callback_query(F.data == "admin_rp_del")
async def admin_rp_del(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    await db.delete_resourcepack()
    await c.answer("Ресурспак удалён")
    await admin_rp(c)


# --- Глобальные переменные ---
@dp.callback_query(F.data == "admin_globals")
async def admin_globals(c: CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    await c.message.answer(
        "Введи: ключ значение\n\n"
        "Доступные ключи:\n"
        "rules_url — ссылка на Telegraph\n"
        "server_version — версия сервера\n"
        "server_core — ядро\n"
        "server_ip — IP-адрес\n"
        "server_status — статус работы\n"
        "server_articles — полезные статьи"
    )
    await state.set_state(Form.admin_set_global)
    await c.answer()


@dp.message(Form.admin_set_global)
async def save_global(m: Message, state: FSMContext):
    try:
        key, value = m.text.split(maxsplit=1)
        await db.set_global(key, value)
        await m.answer("✅ Значение сохранено.")
    except Exception:
        await m.answer("❌ Формат: ключ значение")
    await state.clear()
    await admin_menu(await _fake_cb(m))


# --- Написать пользователю ---
@dp.callback_query(F.data == "admin_send")
async def admin_send(c: CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    await c.message.answer(
        "Введи в формате:\n"
        "@username текст сообщения\n"
        "или\n"
        "USER_ID текст сообщения"
    )
    await state.set_state(Form.admin_send_user)
    await c.answer()


@dp.message(Form.admin_send_user)
async def send_user(m: Message, state: FSMContext):
    try:
        target, text = m.text.split(maxsplit=1)
        target = target.strip()
        uid = None
        if target.startswith("@") or not target.lstrip("-").isdigit():
            uname = target.lstrip("@")
            users = await db.get_all_users()
            for u_id, u_name in users:
                if u_name and u_name.lower() == uname.lower():
                    uid = u_id
                    break
            if uid is None:
                await m.answer(f"❌ Пользователь @{uname} не найден в базе.")
                await state.clear()
                return
        else:
            uid = int(target)
        await bot.send_message(uid, f"📩 Сообщение от админа.\n{SEP}\n\n{text}")
        await m.answer("✅ Отправлено.")
    except Exception as e:
        await m.answer(f"❌ Ошибка: {e}")
    await state.clear()
    await admin_menu(await _fake_cb(m))


# --- Список пользователей ---
@dp.callback_query(F.data == "admin_users")
async def admin_users(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    rows = await db.get_all_users()
    if not rows:
        text = "👥 Пользователи.\n" + SEP + "\n\nПока никого нет."
    else:
        lines = []
        for u_id, u_name in rows:
            if u_name:
                lines.append(f"• @{u_name} ({u_id})")
            else:
                lines.append(f"• {u_id}")
        text = f"👥 Пользователи ({len(rows)}).\n" + SEP + "\n\n" + "\n".join(lines)
    await c.message.edit_text(text, reply_markup=back_kb("admin"))
    await c.answer()


# ==================== ЗАПУСК ====================
async def main():
    await db.init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    me = await bot.get_me()
    logging.info(f"✅ Бот запущен: @{me.username} (id={me.id})")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
