import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

import database as db
from config import BOT_TOKEN, ADMIN_ID
from keyboards import main_kb, admin_kb, back_kb, profile_kb

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

SEP = "—" * 10  # 10 длинных тире


# ==================== FSM ====================
class Form(StatesGroup):
    # Пользователь
    edit_nick_bot = State()
    edit_nick_server = State()
    edit_uuid = State()
    # Админ - фракции
    admin_add_faction = State()
    admin_del_faction = State()
    admin_assign_faction = State()
    # Админ - whitelist
    admin_add_wl = State()
    admin_del_wl = State()
    # Админ - ссылки
    admin_add_link = State()
    admin_del_link = State()
    # Админ - прочее
    admin_set_global = State()
    admin_send_user = State()
    admin_upload_map = State()
    admin_upload_rp = State()
    admin_rp_instruction = State()


def is_admin(uid: int) -> bool:
    return uid == ADMIN_ID


# ==================== /start ====================
@dp.message(CommandStart())
async def start(m: Message):
    await db.add_user(m.from_user.id, m.from_user.username or "")
    await m.answer("🏠 Главное меню\n" + SEP, reply_markup=main_kb(is_admin(m.from_user.id)))


@dp.callback_query(F.data == "back_main")
async def back_main(c: CallbackQuery):
    await c.message.edit_text(
        "🏠 Главное меню\n" + SEP,
        reply_markup=main_kb(is_admin(c.from_user.id))
    )
    await c.answer()


# ==================== 1. ФРАКЦИИ ====================
@dp.callback_query(F.data == "factions")
async def factions_view(c: CallbackQuery):
    rows = await db.get_factions()
    if not rows:
        text = "🚩 Фракции\n" + SEP + "\n\nПока не добавлено ни одной фракции."
    else:
        lines = [f"{i}) {name}" for i, (_, name) in enumerate(rows, start=1)]
        text = "🚩 Фракции\n" + SEP + "\n\n" + "\n".join(lines)
    await c.message.edit_text(text, reply_markup=back_kb())
    await c.answer()


# ==================== 2. КАРТА ====================
@dp.callback_query(F.data == "map")
async def map_view(c: CallbackQuery):
    file_id = await db.get_image("map")
    if not file_id:
        await c.message.edit_text(
            "🗺 Карта\n" + SEP + "\n\nКарта пока не загружена.",
            reply_markup=back_kb()
        )
    else:
        await c.message.delete()
        await c.message.answer_photo(file_id, caption="🗺 Карта сервера\n" + SEP,
                                      reply_markup=back_kb())
    await c.answer()


# ==================== 3. ИГРОКИ ====================
@dp.callback_query(F.data == "players")
async def players_view(c: CallbackQuery):
    rows = await db.get_whitelist()
    if not rows:
        text = "👥 Игроки\n" + SEP + "\n\nБелый список пуст."
    else:
        lines = [f"{i}) {nick}" for i, (_, nick) in enumerate(rows, start=1)]
        text = "👥 Игроки\n" + SEP + "\n\n" + "\n".join(lines)
    await c.message.edit_text(text, reply_markup=back_kb())
    await c.answer()


# ==================== 4. РЕСУРСПАК ====================
@dp.callback_query(F.data == "resourcepack")
async def rp_view(c: CallbackQuery):
    row = await db.get_resourcepack()
    if not row or not row[0]:
        await c.message.edit_text(
            "📦 Ресурспак\n" + SEP + "\n\nРесурспак пока не загружен.",
            reply_markup=back_kb()
        )
    else:
        file_id, instruction = row
        await c.message.delete()
        await c.message.answer_document(
            file_id,
            caption="📦 Ресурспак сервера\n" + SEP + "\n\n" + (instruction or "Инструкция не указана."),
            reply_markup=back_kb()
        )
    await c.answer()


# ==================== 5. ССЫЛКИ ====================
@dp.callback_query(F.data == "links")
async def links_view(c: CallbackQuery):
    rows = await db.get_links()
    if not rows:
        await c.message.edit_text(
            "🔗 Ссылки\n" + SEP + "\n\nПока не добавлено ни одной ссылки.",
            reply_markup=back_kb()
        )
    else:
        # Отправляем текстом + кнопками-ссылками
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        kb = [[InlineKeyboardButton(text=title, url=url)] for _, title, url in rows]
        kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")])
        await c.message.edit_text(
            "🔗 Ссылки\n" + SEP,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
        )
    await c.answer()


# ==================== 6. ПРОФИЛЬ ====================
@dp.callback_query(F.data == "profile")
async def profile_view(c: CallbackQuery):
    u = await db.get_user(c.from_user.id)
    if not u:
        await db.add_user(c.from_user.id, c.from_user.username or "")
        u = await db.get_user(c.from_user.id)
    text = (
        "👤 Профиль\n" + SEP + "\n\n"
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
    await m.answer("✅ Ник в боте обновлён", reply_markup=main_kb(is_admin(m.from_user.id)))


@dp.callback_query(F.data == "edit_nick_server")
async def edit_nick_server(c: CallbackQuery, state: FSMContext):
    await c.message.answer("Введи свой ник на сервере Minecraft:")
    await state.set_state(Form.edit_nick_server)
    await c.answer()


@dp.message(Form.edit_nick_server)
async def save_nick_server(m: Message, state: FSMContext):
    await db.set_user_field(m.from_user.id, "nick_server", m.text.strip())
    await state.clear()
    await m.answer("✅ Ник на сервере обновлён", reply_markup=main_kb(is_admin(m.from_user.id)))


@dp.callback_query(F.data == "edit_uuid")
async def edit_uuid(c: CallbackQuery, state: FSMContext):
    await c.message.answer("Введи свой UUID (или оставь пустым, чтобы удалить):")
    await state.set_state(Form.edit_uuid)
    await c.answer()


@dp.message(Form.edit_uuid)
async def save_uuid(m: Message, state: FSMContext):
    await db.set_user_field(m.from_user.id, "uuid", m.text.strip())
    await state.clear()
    await m.answer("✅ UUID обновлён", reply_markup=main_kb(is_admin(m.from_user.id)))


# ==================== 7. ПРАВИЛА ====================
@dp.callback_query(F.data == "rules")
async def rules_view(c: CallbackQuery):
    url = await db.get_global("rules_url", "")
    if not url:
        await c.message.edit_text(
            "📜 Правила\n" + SEP + "\n\nСсылка на правила ещё не задана.",
            reply_markup=back_kb()
        )
    else:
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📖 Открыть правила", url=url)],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")],
        ])
        await c.message.edit_text("📜 Правила\n" + SEP, reply_markup=kb)
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
        "ℹ️ Информация о сервере\n" + SEP + "\n\n"
        f"Версия: {version}\n"
        f"Ядро: {core}\n"
        f"IP: {ip}\n"
        f"Статус: {status}\n\n"
        f"Полезные статьи:\n{articles}"
    )
    await c.message.edit_text(text, reply_markup=back_kb())
    await c.answer()


# ==================== 9. ФОРМА (заглушка) ====================
@dp.callback_query(F.data == "form")
async def form_view(c: CallbackQuery):
    await c.message.edit_text(
        "✉️ Отправить форму\n" + SEP + "\n\nФункция в разработке.",
        reply_markup=back_kb()
    )
    await c.answer()


# ==================== 10. МЕНЮ СОЗДАТЕЛЯ ====================
@dp.callback_query(F.data == "admin")
async def admin_menu(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    await c.message.edit_text("🛠 Меню создателя\n" + SEP, reply_markup=admin_kb())
    await c.answer()


# --- Фракции: управление ---
@dp.callback_query(F.data == "admin_factions")
async def admin_factions(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить фракцию", callback_data="admin_faction_add")],
        [InlineKeyboardButton(text="➖ Удалить фракцию", callback_data="admin_faction_del")],
        [InlineKeyboardButton(text="🎯 Назначить игроку фракцию", callback_data="admin_faction_assign")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin")],
    ])
    await c.message.edit_text("🚩 Управление фракциями\n" + SEP, reply_markup=kb)
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
    await m.answer("✅ Фракция добавлена", reply_markup=admin_kb())


@dp.callback_query(F.data == "admin_faction_del")
async def admin_faction_del(c: CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    await c.message.answer("Введи название фракции для удаления:")
    await state.set_state(Form.admin_del_faction)
    await c.answer()


@dp.message(Form.admin_del_faction)
async def del_faction(m: Message, state: FSMContext):
    await db.remove_faction(m.text.strip())
    await state.clear()
    await m.answer("✅ Фракция удалена", reply_markup=admin_kb())


@dp.callback_query(F.data == "admin_faction_assign")
async def admin_faction_assign(c: CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    await c.message.answer("Введи: <code>USER_ID Название фракции</code>")
    await state.set_state(Form.admin_assign_faction)
    await c.answer()


@dp.message(Form.admin_assign_faction)
async def assign_faction(m: Message, state: FSMContext):
    try:
        uid, frac = m.text.split(maxsplit=1)
        await db.set_user_field(int(uid), "fraction", frac.strip())
        await m.answer("✅ Фракция назначена")
    except Exception:
        await m.answer("❌ Формат: USER_ID Название фракции")
    await state.clear()


# --- Whitelist ---
@dp.callback_query(F.data == "admin_whitelist")
async def admin_whitelist(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить игрока", callback_data="admin_wl_add")],
        [InlineKeyboardButton(text="➖ Удалить игрока", callback_data="admin_wl_del")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin")],
    ])
    await c.message.edit_text("👥 Белый список\n" + SEP, reply_markup=kb)
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
    await m.answer("✅ Игрок добавлен", reply_markup=admin_kb())


@dp.callback_query(F.data == "admin_wl_del")
async def admin_wl_del(c: CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    await c.message.answer("Введи ник для удаления:")
    await state.set_state(Form.admin_del_wl)
    await c.answer()


@dp.message(Form.admin_del_wl)
async def wl_del(m: Message, state: FSMContext):
    await db.remove_whitelist(m.text.strip())
    await state.clear()
    await m.answer("✅ Игрок удалён", reply_markup=admin_kb())


# --- Ссылки ---
@dp.callback_query(F.data == "admin_links")
async def admin_links(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить ссылку", callback_data="admin_link_add")],
        [InlineKeyboardButton(text="➖ Удалить ссылку", callback_data="admin_link_del")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin")],
    ])
    await c.message.edit_text("🔗 Управление ссылками\n" + SEP, reply_markup=kb)
    await c.answer()


@dp.callback_query(F.data == "admin_link_add")
async def admin_link_add(c: CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    await c.message.answer("Введи: <code>Название | URL</code>")
    await state.set_state(Form.admin_add_link)
    await c.answer()


@dp.message(Form.admin_add_link)
async def link_add(m: Message, state: FSMContext):
    try:
        title, url = m.text.split("|", 1)
        await db.add_link(title.strip(), url.strip())
        await m.answer("✅ Ссылка добавлена")
    except Exception:
        await m.answer("❌ Формат: Название | URL")
    await state.clear()


@dp.callback_query(F.data == "admin_link_del")
async def admin_link_del(c: CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    rows = await db.get_links()
    listing = "\n".join(f"{i}) {t}" for i, (_, t, _) in enumerate(rows, 1))
    await c.message.answer(f"Введи номер ссылки для удаления:\n\n{listing}")
    await state.set_state(Form.admin_del_link)
    await c.answer()


@dp.message(Form.admin_del_link)
async def link_del(m: Message, state: FSMContext):
    try:
        rows = await db.get_links()
        idx = int(m.text) - 1
        await db.remove_link(rows[idx][0])
        await m.answer("✅ Ссылка удалена")
    except Exception:
        await m.answer("❌ Неверный номер")
    await state.clear()


# --- Карта ---
@dp.callback_query(F.data == "admin_map")
async def admin_map(c: CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    await c.message.answer("Пришли новое изображение карты (как фото, без сжатия):")
    await state.set_state(Form.admin_upload_map)
    await c.answer()


@dp.message(Form.admin_upload_map, F.photo)
async def save_map(m: Message, state: FSMContext):
    await db.set_image("map", m.photo[-1].file_id)
    await state.clear()
    await m.answer("✅ Карта обновлена", reply_markup=admin_kb())


# --- Ресурспак ---
@dp.callback_query(F.data == "admin_resourcepack")
async def admin_rp(c: CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    await c.message.answer("Пришли файл ресурспака (как документ):")
    await state.set_state(Form.admin_upload_rp)
    await c.answer()


@dp.message(Form.admin_upload_rp, F.document)
async def save_rp_file(m: Message, state: FSMContext):
    # Сохраняем file_id, инструкцию спросим следом
    await state.update_data(rp_file_id=m.document.file_id)
    await m.answer("Теперь пришли текст инструкции по установке:")
    await state.set_state(Form.admin_rp_instruction)


@dp.message(Form.admin_rp_instruction)
async def save_rp_instruction(m: Message, state: FSMContext):
    data = await state.get_data()
    file_id = data.get("rp_file_id")
    await db.set_resourcepack(file_id, m.text.strip())
    await state.clear()
    await m.answer("✅ Ресурспак и инструкция обновлены", reply_markup=admin_kb())


# --- Глобальные переменные ---
@dp.callback_query(F.data == "admin_globals")
async def admin_globals(c: CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    await c.message.answer(
        "Введи: <code>ключ значение</code>\n\n"
        "Доступные ключи:\n"
        "<code>rules_url</code> — ссылка на Telegraph\n"
        "<code>server_version</code>, <code>server_core</code>, "
        "<code>server_ip</code>, <code>server_status</code>, <code>server_articles</code>"
    )
    await state.set_state(Form.admin_set_global)
    await c.answer()


@dp.message(Form.admin_set_global)
async def save_global(m: Message, state: FSMContext):
    try:
        key, value = m.text.split(maxsplit=1)
        await db.set_global(key, value)
        await m.answer("✅ Сохранено")
    except Exception:
        await m.answer("❌ Формат: ключ значение")
    await state.clear()


# --- Написать пользователю ---
@dp.callback_query(F.data == "admin_send")
async def admin_send(c: CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    await c.message.answer("Введи: <code>USER_ID текст</code>")
    await state.set_state(Form.admin_send_user)
    await c.answer()


@dp.message(Form.admin_send_user)
async def send_user(m: Message, state: FSMContext):
    try:
        uid, text = m.text.split(maxsplit=1)
        await bot.send_message(int(uid), f"📩 Сообщение от админа:\n\n{text}")
        await m.answer("✅ Отправлено")
    except Exception as e:
        await m.answer(f"❌ Ошибка: {e}")
    await state.clear()


# --- Список пользователей ---
@dp.callback_query(F.data == "admin_users")
async def admin_users(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    users = await db.get_all_users()
    ids = "\n".join(str(u) for u in users[:50])
    await c.message.edit_text(f"👥 Пользователи ({len(users)}):\n{SEP}\n\n{ids}", reply_markup=admin_kb())
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
