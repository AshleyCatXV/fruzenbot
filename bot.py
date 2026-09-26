import asyncio
import logging
import os
import shutil
import sqlite3
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    FSInputFile
)
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

import database as db
from config import BOT_TOKEN, ADMIN_ID
from keyboards import (
    main_kb, admin_kb, back_kb, profile_kb,
    admin_map_kb, admin_rp_kb, admin_factions_kb,
    admin_whitelist_kb, admin_links_kb, paginated_kb,
    paginated_users_kb, user_profile_admin_kb, tags_menu_kb,
    ALL_TAGS
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

SEP = "—" * 10
PER_PAGE = 8


class Form(StatesGroup):
    edit_nick_bot = State()
    edit_nick_server = State()
    edit_uuid = State()

    admin_add_faction = State()
    admin_add_wl = State()
    admin_add_link = State()
    admin_rules_url = State()
    admin_adminchat_url = State()
    admin_set_global = State()
    admin_upload_map = State()
    admin_upload_rp = State()
    admin_rp_instruction = State()
    admin_edit_user = State()
    admin_send_to_user = State()


def is_admin(uid: int) -> bool:
    return uid == ADMIN_ID


def user_label(user_id: int, username: str, first_name: str = "", nick_bot: str = "") -> str:
    if username:
        return f"@{username} ({user_id})"
    if first_name:
        return f"{first_name} ({user_id})"
    return str(user_id)


# ==================== ВСПОМОГАТЕЛЬНОЕ ====================

async def _main_menu_text(user_id: int) -> str:
    user = await db.get_user(user_id)
    if user:
        nick = user[2] or user[1] or "друг"
    else:
        nick = "друг"
    return f"Здравствуйте, {nick}!\n🏠 Главное меню.\n{SEP}"


async def show_main_menu(target, user_id: int):
    text = await _main_menu_text(user_id)
    kb = main_kb(is_admin(user_id))
    if isinstance(target, CallbackQuery):
        try:
            await target.message.edit_text(text, reply_markup=kb)
        except Exception:
            try:
                await target.message.delete()
            except Exception:
                pass
            await bot.send_message(user_id, text, reply_markup=kb)
    else:
        await target.answer(text, reply_markup=kb)


async def safe_edit(c: CallbackQuery, text: str, reply_markup=None):
    try:
        await c.message.edit_text(text, reply_markup=reply_markup)
    except Exception:
        try:
            await c.message.delete()
        except Exception:
            pass
        await bot.send_message(c.from_user.id, text, reply_markup=reply_markup)


async def _fake_cb(m: Message):
    class FakeMsg:
        async def edit_text(self, *a, **kw):
            return await m.answer(*a, **kw)
    class FakeCb:
        from_user = m.from_user
        message = FakeMsg()
        async def answer(self, *a, **kw):
            pass
    return FakeCb()


class _FakeCbForProfile:
    def __init__(self, user):
        self.from_user = user
        self.message = self
    async def edit_text(self, *a, **kw):
        pass
    async def answer(self, *a, **kw):
        pass


async def show_profile(c: CallbackQuery, target_user_id: int, admin_view: bool = False):
    u = await db.get_user(target_user_id)
    if not u:
        await safe_edit(c, "❌ Пользователь не найден.",
                        back_kb("admin_users" if admin_view else "back_main"))
        return

    tags = await db.get_user_tags(target_user_id)
    tags_str = ", ".join(tags) if tags else "—"

    text = (
        f"👤 Профиль {user_label(u[0], u[1], '', u[2])}.\n" + SEP + "\n\n"
        f"Ник в боте: {u[2] or '—'}\n"
        f"Ник на сервере: {u[3] or '—'}\n"
        f"Фракция: {u[4] or '—'}\n"
        f"UUID: {u[5] or '—'}\n"
        f"Теги: {tags_str}"
    )
    if admin_view:
        kb = user_profile_admin_kb(target_user_id, tags)
    else:
        kb = profile_kb()

    if isinstance(c, _FakeCbForProfile):
        await bot.send_message(target_user_id, text, reply_markup=kb)
    else:
        await safe_edit(c, text, kb)


async def check_banned(m: Message) -> bool:
    """Если пользователь забанен — отправляет сообщение и возвращает True."""
    if await db.has_tag(m.from_user.id, "banned"):
        await m.answer(
            "🚫 Вы забанены и не можете пользоваться ботом.\n\n"
            "(В будущем здесь появится кнопка «Заявка на разбан».)"
        )
        return True
    return False


async def check_banned_cb(c: CallbackQuery) -> bool:
    """Для callback-кнопок. Бан не мешает нажимать /start и профиль."""
    # Разрешаем back_main, profile и навигацию по тегам, чтобы не залипало
    allowed = (
        c.data == "back_main" or c.data == "profile" or c.data == "noop"
        or c.data.startswith("tag")
    )
    if allowed:
        return False
    if await db.has_tag(c.from_user.id, "banned"):
        await c.answer(
            "🚫 Вы забанены и не можете пользоваться ботом.",
            show_alert=True
        )
        return True
    return False


# ==================== /start ====================
@dp.message(CommandStart())
async def start(m: Message):
    await db.add_user(
        m.from_user.id,
        m.from_user.username or "",
        m.from_user.first_name or ""
    )
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
    if await check_banned_cb(c):
        return
    rows = await db.get_factions()
    if not rows:
        text = "🚩 Фракции.\n" + SEP + "\n\nПока не добавлено ни одной фракции."
    else:
        lines = [f"{i}) {name}" for i, (_, name) in enumerate(rows, start=1)]
        text = "🚩 Фракции.\n" + SEP + "\n\n" + "\n".join(lines)
    await safe_edit(c, text, back_kb())
    await c.answer()


# ==================== 2. КАРТА ====================
@dp.callback_query(F.data == "map")
async def map_view(c: CallbackQuery):
    if await check_banned_cb(c):
        return
    file_id = await db.get_image("map")
    if not file_id:
        await safe_edit(c, "🗺 Карта.\n" + SEP + "\n\nКарта пока не загружена.", back_kb())
        await c.answer()
        return

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
    if await check_banned_cb(c):
        return
    rows = await db.get_whitelist()
    if not rows:
        text = "👥 Игроки.\n" + SEP + "\n\nБелый список пуст."
    else:
        lines = [f"{i}) {nick}" for i, (_, nick) in enumerate(rows, start=1)]
        text = "👥 Игроки.\n" + SEP + "\n\n" + "\n".join(lines)
    await safe_edit(c, text, back_kb())
    await c.answer()


# ==================== 4. РЕСУРСПАК ====================
@dp.callback_query(F.data == "resourcepack")
async def rp_view(c: CallbackQuery):
    if await check_banned_cb(c):
        return
    row = await db.get_resourcepack()
    if not row or not row[0]:
        await safe_edit(c, "📦 Ресурспак.\n" + SEP + "\n\nРесурспак пока не загружен.", back_kb())
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
    if await check_banned_cb(c):
        return
    rows = await db.get_links()
    user_tags = await db.get_user_tags(c.from_user.id)
    is_admin_tag = "admin" in user_tags

    kb = []
    for _, title, url in rows:
        kb.append([InlineKeyboardButton(text=title, url=url)])

    # Ссылка на чат админов — только для тех, у кого тег admin
    if is_admin_tag:
        admin_chat_url = await db.get_global("admin_chat_url", "")
        if admin_chat_url:
            kb.append([InlineKeyboardButton(text="🛡 Чат админов", url=admin_chat_url)])

    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")])

    if not kb[:-1]:
        text = "🔗 Ссылки.\n" + SEP + "\n\nПока не добавлено ни одной ссылки."
    else:
        text = "🔗 Ссылки.\n" + SEP

    await safe_edit(c, text, InlineKeyboardMarkup(inline_keyboard=kb))
    await c.answer()


# ==================== 6. ПРОФИЛЬ ====================
@dp.callback_query(F.data == "profile")
async def profile_view(c: CallbackQuery):
    await show_profile(c, c.from_user.id, admin_view=False)
    await c.answer()


@dp.callback_query(F.data == "edit_nick_bot")
async def edit_nick_bot(c: CallbackQuery, state: FSMContext):
    if await check_banned_cb(c):
        return
    await c.message.answer("Введи новый ник в боте:")
    await state.set_state(Form.edit_nick_bot)
    await c.answer()


@dp.message(Form.edit_nick_bot)
async def save_nick_bot(m: Message, state: FSMContext):
    if await check_banned(m):
        return
    await db.set_user_field(m.from_user.id, "nick_bot", m.text.strip())
    await state.clear()
    await m.answer("✅ Ник в боте обновлён.")
    await show_profile(_FakeCbForProfile(m.from_user), m.from_user.id, admin_view=False)


@dp.callback_query(F.data == "edit_nick_server")
async def edit_nick_server(c: CallbackQuery, state: FSMContext):
    if await check_banned_cb(c):
        return
    await c.message.answer("Введи свой ник на сервере Minecraft:")
    await state.set_state(Form.edit_nick_server)
    await c.answer()


@dp.message(Form.edit_nick_server)
async def save_nick_server(m: Message, state: FSMContext):
    if await check_banned(m):
        return
    await db.set_user_field(m.from_user.id, "nick_server", m.text.strip())
    await state.clear()
    await m.answer("✅ Ник на сервере обновлён.")
    await show_profile(_FakeCbForProfile(m.from_user), m.from_user.id, admin_view=False)


@dp.callback_query(F.data == "edit_uuid")
async def edit_uuid(c: CallbackQuery, state: FSMContext):
    if await check_banned_cb(c):
        return
    await c.message.answer("Введи свой UUID (или пустое сообщение, чтобы удалить):")
    await state.set_state(Form.edit_uuid)
    await c.answer()


@dp.message(Form.edit_uuid)
async def save_uuid(m: Message, state: FSMContext):
    if await check_banned(m):
        return
    await db.set_user_field(m.from_user.id, "uuid", m.text.strip())
    await state.clear()
    await m.answer("✅ UUID обновлён.")
    await show_profile(_FakeCbForProfile(m.from_user), m.from_user.id, admin_view=False)


# ==================== 7. ПРАВИЛА ====================
@dp.callback_query(F.data == "rules")
async def rules_view(c: CallbackQuery):
    if await check_banned_cb(c):
        return
    url = await db.get_global("rules_url", "")
    if not url:
        await safe_edit(c, "📜 Правила.\n" + SEP + "\n\nСсылка на правила ещё не задана.", back_kb())
    else:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📖 Открыть правила", url=url)],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")],
        ])
        await safe_edit(c, "📜 Правила.\n" + SEP, kb)
    await c.answer()


# ==================== 8. ИНФОРМАЦИЯ ====================
@dp.callback_query(F.data == "info")
async def info_view(c: CallbackQuery):
    if await check_banned_cb(c):
        return
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
    await safe_edit(c, text, back_kb())
    await c.answer()


# ==================== 9. ФОРМА ====================
@dp.callback_query(F.data == "form")
async def form_view(c: CallbackQuery):
    if await check_banned_cb(c):
        return
    await safe_edit(c, "✉️ Отправить форму.\n" + SEP + "\n\nФункция в разработке.", back_kb())
    await c.answer()


# ==================== 10. МЕНЮ СОЗДАТЕЛЯ ====================
@dp.callback_query(F.data == "admin")
async def admin_menu(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    await safe_edit(c, "🛠 Меню создателя.\n" + SEP, admin_kb())
    await c.answer()


# --- Фракции ---
@dp.callback_query(F.data == "admin_factions")
async def admin_factions(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    await safe_edit(c, "🚩 Управление фракциями.\n" + SEP, admin_factions_kb())
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


@dp.callback_query(F.data == "admin_faction_del")
async def admin_faction_del(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    rows = await db.get_factions()
    if not rows:
        await c.answer("Фракций нет.", show_alert=True)
        return
    await _render_faction_del_page(c, 0)


async def _render_faction_del_page(c: CallbackQuery, page: int):
    rows = await db.get_factions()
    kb = paginated_kb(rows, page, PER_PAGE, "faction_del:", "admin_factions")
    await safe_edit(c, "🚩 Выбери фракцию для удаления.\n" + SEP, kb)


@dp.callback_query(F.data.startswith("pg:faction_del:"))
async def faction_del_page(c: CallbackQuery):
    page = int(c.data.split(":")[2])
    await _render_faction_del_page(c, page)
    await c.answer()


@dp.callback_query(F.data.startswith("faction_del:"))
async def faction_del(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    fid = int(c.data.split(":")[1])
    await db.remove_faction_by_id(fid)
    rows = await db.get_factions()
    if not rows:
        await safe_edit(c, "✅ Фракция удалена.\n\nСписок фракций пуст.", admin_factions_kb())
    else:
        await _render_faction_del_page(c, 0)
    await c.answer("Удалено")


@dp.callback_query(F.data == "admin_faction_assign")
async def admin_faction_assign(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    users = await db.get_all_users()
    if not users:
        await c.answer("Пользователей нет.", show_alert=True)
        return
    await _render_user_pick_page(c, 0, "faction_assign_user", "admin_factions")


async def _render_user_pick_page(c: CallbackQuery, page: int, prefix: str, back_target: str):
    users = await db.get_all_users()
    kb = paginated_users_kb(users, page, f"{prefix}:", back_target)
    await safe_edit(c, "🎯 Выбери игрока.\n" + SEP, kb)


@dp.callback_query(F.data.startswith("upg:faction_assign_user:"))
async def faction_assign_user_page(c: CallbackQuery):
    page = int(c.data.split(":")[2])
    await _render_user_pick_page(c, page, "faction_assign_user", "admin_factions")
    await c.answer()


@dp.callback_query(F.data.startswith("faction_assign_user:"))
async def faction_assign_user(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    uid = int(c.data.split(":")[1])
    rows = await db.get_factions()
    if not rows:
        await c.answer("Сначала добавь фракции.", show_alert=True)
        return
    kb = paginated_kb(rows, 0, PER_PAGE, f"faction_pick:{uid}:", "admin_factions",
                      nav_prefix="fpp")
    await safe_edit(c, f"🎯 Выбери фракцию для пользователя {uid}.\n" + SEP, kb)
    await c.answer()


@dp.callback_query(F.data.startswith("fpp:faction_pick:"))
async def faction_pick_page(c: CallbackQuery):
    parts = c.data.split(":")
    uid = int(parts[2])
    page = int(parts[3])
    rows = await db.get_factions()
    kb = paginated_kb(rows, page, PER_PAGE, f"faction_pick:{uid}:", "admin_factions",
                      nav_prefix="fpp")
    await safe_edit(c, f"🎯 Выбери фракцию для пользователя {uid}.\n" + SEP, kb)
    await c.answer()


@dp.callback_query(F.data.startswith("faction_pick:"))
async def faction_pick(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    parts = c.data.split(":")
    uid = int(parts[1])
    fid = int(parts[2])
    rows = await db.get_factions()
    name = next((n for i, n in rows if i == fid), None)
    if name is None:
        return await c.answer("Фракция не найдена.", show_alert=True)
    await db.set_user_field(uid, "fraction", name)
    await c.answer("Готово")
    await show_profile(c, uid, admin_view=True)


# --- Whitelist ---
@dp.callback_query(F.data == "admin_whitelist")
async def admin_whitelist(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    await safe_edit(c, "👥 Белый список.\n" + SEP, admin_whitelist_kb())
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
    await _render_wl_del_page(c, 0)


async def _render_wl_del_page(c: CallbackQuery, page: int):
    rows = await db.get_whitelist()
    kb = paginated_kb(rows, page, PER_PAGE, "wl_del:", "admin_whitelist")
    await safe_edit(c, "👥 Выбери игрока для удаления.\n" + SEP, kb)


@dp.callback_query(F.data.startswith("pg:wl_del:"))
async def wl_del_page(c: CallbackQuery):
    page = int(c.data.split(":")[2])
    await _render_wl_del_page(c, page)
    await c.answer()


@dp.callback_query(F.data.startswith("wl_del:"))
async def wl_del(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    wid = int(c.data.split(":")[1])
    await db.remove_whitelist_by_id(wid)
    rows = await db.get_whitelist()
    if not rows:
        await safe_edit(c, "✅ Игрок удалён.\n\nСписок пуст.", admin_whitelist_kb())
    else:
        await _render_wl_del_page(c, 0)
    await c.answer("Удалено")


# --- Ссылки ---
@dp.callback_query(F.data == "admin_links")
async def admin_links(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    await safe_edit(c, "🔗 Управление ссылками.\n" + SEP, admin_links_kb())
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
    await _render_link_del_page(c, 0)


async def _render_link_del_page(c: CallbackQuery, page: int):
    rows = await db.get_links()
    kb = paginated_kb([(i, t) for i, t, _ in rows], page, PER_PAGE, "link_del:", "admin_links")
    await safe_edit(c, "🔗 Выбери ссылку для удаления.\n" + SEP, kb)


@dp.callback_query(F.data.startswith("pg:link_del:"))
async def link_del_page(c: CallbackQuery):
    page = int(c.data.split(":")[2])
    await _render_link_del_page(c, page)
    await c.answer()


@dp.callback_query(F.data.startswith("link_del:"))
async def link_del(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    lid = int(c.data.split(":")[1])
    await db.remove_link(lid)
    rows = await db.get_links()
    if not rows:
        await safe_edit(c, "✅ Ссылка удалена.\n\nСписок пуст.", admin_links_kb())
    else:
        await _render_link_del_page(c, 0)
    await c.answer("Удалено")


@dp.callback_query(F.data == "admin_rules_url")
async def admin_rules_url(c: CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    current = await db.get_global("rules_url", "не задана")
    await c.message.answer(
        f"Текущая ссылка: {current}\n\nПришли новую ссылку на правила (Telegraph):"
    )
    await state.set_state(Form.admin_rules_url)
    await c.answer()


@dp.message(Form.admin_rules_url)
async def save_rules_url(m: Message, state: FSMContext):
    await db.set_global("rules_url", m.text.strip())
    await state.clear()
    await m.answer("✅ Ссылка на правила сохранена.")
    await admin_links(await _fake_cb(m))


@dp.callback_query(F.data == "admin_adminchat_url")
async def admin_adminchat_url(c: CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    current = await db.get_global("admin_chat_url", "не задана")
    await c.message.answer(
        f"Текущая ссылка: {current}\n\n"
        f"Пришли ссылку на чат админов (для тега admin):"
    )
    await state.set_state(Form.admin_adminchat_url)
    await c.answer()


@dp.message(Form.admin_adminchat_url)
async def save_admin_chat_url(m: Message, state: FSMContext):
    await db.set_global("admin_chat_url", m.text.strip())
    await state.clear()
    await m.answer("✅ Ссылка на чат админов сохранена.")
    await admin_links(await _fake_cb(m))


# --- Карта ---
@dp.callback_query(F.data == "admin_map")
async def admin_map(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    has_map = bool(await db.get_image("map"))
    text = "🗺 Управление картой.\n" + SEP
    text += "\n\nСтатус: " + ("✅ карта загружена" if has_map else "❌ карта не загружена")
    await safe_edit(c, text, admin_map_kb(has_map))
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
    await safe_edit(c, text, admin_rp_kb(has_rp))
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


# --- Пользователи бота ---
@dp.callback_query(F.data == "admin_users")
async def admin_users(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    users = await db.get_all_users()
    if not users:
        await safe_edit(c, "👥 Пользователи.\n" + SEP + "\n\nПока никого нет.",
                        back_kb("admin"))
        await c.answer()
        return
    await _render_users_page(c, 0)


async def _render_users_page(c: CallbackQuery, page: int):
    users = await db.get_all_users()
    kb = paginated_users_kb(users, page, "user_view:", "admin")
    await safe_edit(c, f"👥 Пользователи ({len(users)}).\n" + SEP +
                    "\n\nВыбери пользователя:", kb)


@dp.callback_query(F.data.startswith("upg:user_view:"))
async def users_page(c: CallbackQuery):
    page = int(c.data.split(":")[2])
    await _render_users_page(c, page)
    await c.answer()


@dp.callback_query(F.data.startswith("user_view:"))
async def user_view(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    uid = int(c.data.split(":")[1])
    await show_profile(c, uid, admin_view=True)
    await c.answer()


# --- Редактирование чужого профиля ---
@dp.callback_query(F.data.startswith("aedit:"))
async def admin_edit_field(c: CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    _, field, uid_str = c.data.split(":")
    uid = int(uid_str)

    if field == "fraction":
        rows = await db.get_factions()
        if not rows:
            await c.answer("Сначала добавь фракции.", show_alert=True)
            return
        kb = paginated_kb(rows, 0, PER_PAGE, f"faction_pick:{uid}:", "admin_users",
                          nav_prefix="fpp")
        await safe_edit(c, f"🎯 Выбери фракцию для пользователя {uid}.\n" + SEP, kb)
        await c.answer()
        return

    prompts = {
        "nick_bot": "Введи новый ник в боте:",
        "nick_server": "Введи новый ник на сервере Minecraft:",
        "uuid": "Введи новый UUID (или пустое сообщение, чтобы удалить):",
    }
    await c.message.answer(prompts[field])
    await state.update_data(target_user=uid, target_field=field)
    await state.set_state(Form.admin_edit_user)
    await c.answer()


@dp.message(Form.admin_edit_user)
async def admin_edit_user_save(m: Message, state: FSMContext):
    data = await state.get_data()
    uid = data.get("target_user")
    field = data.get("target_field")
    if uid is None or field is None:
        await m.answer("❌ Сессия истекла.")
        await state.clear()
        return
    await db.set_user_field(int(uid), field, m.text.strip())
    await state.clear()
    await m.answer("✅ Сохранено.")
    await show_profile(_FakeCbForProfile(m.from_user), int(uid), admin_view=True)


# --- Теги пользователя ---
@dp.callback_query(F.data.startswith("tags_menu:"))
async def tags_menu(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    uid = int(c.data.split(":")[1])
    current = await db.get_user_tags(uid)
    kb = tags_menu_kb(uid, current)
    text = f"🏷 Теги пользователя {uid}.\n" + SEP + "\n\nНажми на тег, чтобы добавить/убрать:"
    await safe_edit(c, text, kb)
    await c.answer()


@dp.callback_query(F.data.startswith("tag_toggle:"))
async def tag_toggle(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    _, uid_str, tag = c.data.split(":")
    uid = int(uid_str)
    if tag not in ALL_TAGS:
        return await c.answer("Неизвестный тег", show_alert=True)
    added = await db.toggle_user_tag(uid, tag)
    current = await db.get_user_tags(uid)
    kb = tags_menu_kb(uid, current)
    text = f"🏷 Теги пользователя {uid}.\n" + SEP + "\n\nНажми на тег, чтобы добавить/убрать:"
    await safe_edit(c, text, kb)
    await c.answer(f"Тег {'добавлен' if added else 'убран'}")


# --- Сообщение пользователю ---
@dp.callback_query(F.data.startswith("msg_user:"))
async def msg_user(c: CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    uid = int(c.data.split(":")[1])
    await c.message.answer("Введи текст сообщения для пользователя:")
    await state.update_data(target_user=uid)
    await state.set_state(Form.admin_send_to_user)
    await c.answer()


@dp.message(Form.admin_send_to_user)
async def send_to_user(m: Message, state: FSMContext):
    data = await state.get_data()
    uid = data.get("target_user")
    if uid is None:
        await m.answer("❌ Сессия истекла.")
        await state.clear()
        return
    try:
        await bot.send_message(int(uid), f"📩 Сообщение от админа.\n{SEP}\n\n{m.text}")
        await m.answer("✅ Отправлено.")
    except Exception as e:
        await m.answer(f"❌ Ошибка: {e}")
    await state.clear()
    await show_profile(_FakeCbForProfile(m.from_user), int(uid), admin_view=True)


# ==================== РЕЗЕРВНОЕ КОПИРОВАНИЕ ====================

@dp.message(Command("backup"))
async def backup_cmd(m: Message):
    if not is_admin(m.from_user.id):
        return
    if not os.path.exists(db.DB):
        await m.answer("❌ Файл базы данных не найден.")
        return
    try:
        await m.answer_document(
            FSInputFile(db.DB, filename="bot.db"),
            caption="📦 Резервная копия базы данных."
        )
    except Exception as e:
        await m.answer(f"❌ Ошибка: {e}")


@dp.message(Command("restore"))
async def restore_cmd(m: Message):
    if not is_admin(m.from_user.id):
        return
    await m.answer(
        "📥 Пришли файл bot.db (как документ), и я восстановлю базу данных.\n"
        "⚠️ Текущая база будет перезаписана! После восстановления перезапусти бота."
    )


@dp.message(F.document)
async def restore_file(m: Message):
    if not is_admin(m.from_user.id):
        return
    doc = m.document
    if not doc.file_name or doc.file_name != "bot.db":
        return
    try:
        file = await bot.get_file(doc.file_id)
        temp_path = "bot_restore_tmp.db"
        await bot.download_file(file.file_path, temp_path)

        conn = sqlite3.connect(temp_path)
        conn.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1;")
        conn.close()

        shutil.move(temp_path, db.DB)

        await m.answer(
            "✅ База данных восстановлена.\n\n"
            "⚠️ Не забудь перезапустить бота, чтобы изменения применились."
        )
    except Exception as e:
        await m.answer(f"❌ Ошибка восстановления: {e}")


@dp.callback_query(F.data == "admin_backup")
async def admin_backup(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    if not os.path.exists(db.DB):
        return await c.answer("Файл базы не найден", show_alert=True)
    try:
        await bot.send_document(
            c.from_user.id,
            FSInputFile(db.DB, filename="bot.db"),
            caption="📦 Резервная копия базы данных."
        )
    except Exception as e:
        await bot.send_message(c.from_user.id, f"❌ Ошибка: {e}")
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
