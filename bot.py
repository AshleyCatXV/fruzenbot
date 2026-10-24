import asyncio
import logging
import os
import shutil
import sqlite3
import aiosqlite
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.context import FSMContext

import database as db
from config import BOT_TOKEN, ADMIN_ID
from keyboards import (
    main_kb, admin_kb, back_kb, profile_kb, admin_map_kb, admin_rp_kb, admin_factions_kb,
    admin_whitelist_kb, admin_links_kb, paginated_kb, paginated_users_kb, user_profile_admin_kb,
    tags_menu_kb, intro_start_kb, intro_activity_kb, intro_faction_kb, intro_finish_kb, intro_review_kb
)
from states import Form

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
SEP = "—" * 10
PER_PAGE = 8

def is_admin(uid): return uid == ADMIN_ID
def user_label(uid, uname, fname=""):
    if uname: return f"@{uname} ({uid})"
    if fname: return f"{fname} ({uid})"
    return str(uid)

async def safe_edit(c: CallbackQuery, text: str, reply_markup=None):
    try:
        await c.message.edit_text(text, reply_markup=reply_markup)
    except Exception:
        try: await c.message.delete()
        except Exception: pass
        await bot.send_message(c.from_user.id, text, reply_markup=reply_markup)

async def _fake_cb(m: Message):
    class FakeMsg:
        async def edit_text(self, *a, **kw): return await m.answer(*a, **kw)
    class FakeCb:
        from_user = m.from_user
        message = FakeMsg()
        async def answer(self, *a, **kw): pass
    return FakeCb()

class _FakeCbForProfile:
    def __init__(self, user):
        self.from_user = user
        self.message = self
    async def edit_text(self, *a, **kw): pass
    async def answer(self, *a, **kw): pass

async def show_main_menu(target, user_id: int):
    user = await db.get_user(user_id)
    nick = user[3] or user[1] or "друг" if user else "друг"
    text = f"Здравствуйте, {nick}!\n🏠 Главное меню.\n{SEP}"
    kb = main_kb(is_admin(user_id))
    if isinstance(target, CallbackQuery):
        try: await target.message.edit_text(text, reply_markup=kb)
        except Exception:
            try: await target.message.delete()
            except Exception: pass
            await bot.send_message(user_id, text, reply_markup=kb)
    else: await target.answer(text, reply_markup=kb)

async def show_profile(c: CallbackQuery, target_user_id: int, admin_view: bool = False):
    u = await db.get_user(target_user_id)
    if not u:
        return await safe_edit(c, "❌ Пользователь не найден.", back_kb("admin_users" if admin_view else "back_main"))
    
    text = f"👤 Профиль {user_label(u[0], u[1], u[2])}.\n{SEP}\n\nНик в боте: {u[3] or '—'}\nНик на сервере: {u[4] or '—'}\nФракция: {u[5] or '—'}"
    
    if is_admin(c.from_user.id):
        text += f"\nUUID: {u[6] or '—'}\nТеги: {', '.join(db.parse_tags(u[7])) or '—'}"
        kb = user_profile_admin_kb(target_user_id)
    else:
        if admin_view: return await c.answer("Нет доступа", show_alert=True)
        kb = profile_kb()

    if isinstance(c, _FakeCbForProfile):
        await bot.send_message(target_user_id, text, reply_markup=kb)
    else:
        await safe_edit(c, text, kb)

async def check_access(c: CallbackQuery) -> bool:
    if c.from_user.id == ADMIN_ID:
        return True # Админ всегда имеет доступ
    tags = await db.get_user_tags(c.from_user.id)
    if "banned" in tags:
        await c.answer("🚫 Вы забанены.", show_alert=True)
        return False
    if "whitelisted" not in tags:
        await c.answer("⏳ Вы ещё не в белом списке. Ожидайте одобрения анкеты.", show_alert=True)
        return False
    return True

# ==================== СТАРТ И ИНТРО ====================
@dp.message(CommandStart())
async def start(m: Message):
    await db.add_user(m.from_user.id, m.from_user.username or "", m.from_user.first_name or "")
    u = await db.get_user(m.from_user.id)
    tags = await db.get_user_tags(m.from_user.id)

    if "banned" in tags: return await m.answer("🚫 Вы забанены.")
    if u[8] == 0 and m.from_user.id != ADMIN_ID:
        text = (
            f"👋 Здравствуйте, {m.from_user.first_name}!\n\n"
            "Так как вы обратились ко мне, значит, вы хотите попасть на сервер FruzenWorld Legacy.\n"
            "Это преимущественно ванильный сервер с элементами политики, но на нём есть плагины, несколько меняющие игру.\n\n"
            "Для того, чтобы вступить сервер, вам нужно заполнить небольшую анкету. Готовы?"
        )
        return await m.answer(text, reply_markup=intro_start_kb())
    if "processing" in tags and "whitelisted" not in tags and m.from_user.id != ADMIN_ID:
        return await m.answer("⏳ Ваша анкета находится на рассмотрении.")

    await show_main_menu(m, m.from_user.id)

@dp.message(Command("skip"))
async def cmd_skip(m: Message):
    if not is_admin(m.from_user.id): return
    await db.set_user_field(m.from_user.id, "intro_done", 1)
    tags = await db.get_user_tags(m.from_user.id)
    if "whitelisted" not in tags:
        await db.toggle_user_tag(m.from_user.id, "whitelisted")
    await m.answer("✅ Интро пропущено. Вам выдан тег whitelisted.")
    await show_main_menu(m, m.from_user.id)

@dp.callback_query(F.data == "intro_cancel")
async def intro_cancel(c: CallbackQuery):
    await c.message.edit_text("Вы отменили анкету. Возвращайтесь, когда будете готовы!")
    await c.answer()

@dp.callback_query(F.data == "intro_next")
async def intro_next(c: CallbackQuery, state: FSMContext):
    await c.message.edit_text("✅ Отлично!\n\nСначала нужно разобраться с тем, чтобы вы вообще смогли зайти на сервер. Какой у вас никнейм в игре?")
    await state.set_state(Form.intro_nick)
    await c.answer()

@dp.message(Form.intro_nick)
async def intro_nick(m: Message, state: FSMContext):
    await db.set_user_field(m.from_user.id, "nick_server", m.text.strip())
    await state.update_data(intro_nick=m.text.strip())
    await m.answer("✅ Ваш ник был отправлен администрации.\n\nТеперь вопрос такой: напишите, пожалуйста, как к вам можно обращаться?")
    await state.set_state(Form.intro_name)

@dp.message(Form.intro_name)
async def intro_name(m: Message, state: FSMContext):
    await db.set_user_field(m.from_user.id, "nick_bot", m.text.strip())
    await state.update_data(intro_name=m.text.strip())
    await m.answer("✅ Супер!\n\nНебольшой промежуточный вопрос: являетесь ли вы активным игроком?", reply_markup=intro_activity_kb())
    await state.set_state(None)

@dp.callback_query(F.data.startswith("intro_act:"))
async def intro_act(c: CallbackQuery, state: FSMContext):
    act = c.data.split(":")[1]
    await state.update_data(intro_act=act)
    text = "Понятно. Продолжаем.\n💡 Итак, поясняю.\nНа нашем сервере есть понятие 'фракция' — по сути своей страна, организация, государство и так далее.\nЧтобы играть на сервере, вам необходимо создать свою фракцию, либо присоединиться к уже имеющейся.\nЛимит людей на 1 фракцию — 4 человека, минимум людей должно быть 2.\nЧто вы хотите сделать?"
    await safe_edit(c, text, intro_faction_kb())

@dp.callback_query(F.data == "intro_frac:join")
async def intro_join(c: CallbackQuery, state: FSMContext):
    rows = await db.get_factions()
    if not rows: return await c.answer("Фракций пока нет, придётся создать свою!", show_alert=True)
    kb = paginated_kb([(r[0], r[1]) for r in rows], 0, PER_PAGE, "intro_join_frac:", "intro_restart", nav_prefix="ij")
    await safe_edit(c, "К какой фракции вы хотите присоединиться?", kb)

@dp.callback_query(F.data.startswith("ij:intro_join_frac:"))
async def intro_join_page(c: CallbackQuery):
    page = int(c.data.split(":")[2])
    rows = await db.get_factions()
    kb = paginated_kb([(r[0], r[1]) for r in rows], page, PER_PAGE, "intro_join_frac:", "intro_restart", nav_prefix="ij")
    await safe_edit(c, "К какой фракции вы хотите присоединиться?", kb)
    await c.answer()

@dp.callback_query(F.data.startswith("intro_join_frac:"))
async def intro_join_frac(c: CallbackQuery, state: FSMContext):
    fid = int(c.data.split(":")[1])
    rows = await db.get_factions()
    fname = next((n for i, n, _ in rows if i == fid), None)
    if fname:
        await state.update_data(intro_frac_join=fname)
        await finish_intro(c, state)

@dp.callback_query(F.data == "intro_frac:create")
async def intro_create(c: CallbackQuery, state: FSMContext):
    await safe_edit(c, "✅ Вы решили пойти по такому пути. Прекрасно!\n\nСначала напишите название вашей фракции. Оно должно быть похоже на типичные названия государств/организаций, и должно быть на русском языке.\n\nПримеры: Республика Азурия; Герцогство Света; Аниарку; Зелёное Побережье.")
    await state.set_state(Form.intro_faction_create_name)
    await c.answer()

@dp.message(Form.intro_faction_create_name)
async def intro_create_name(m: Message, state: FSMContext):
    await state.update_data(intro_frac_create=m.text.strip())
    text = "🔰 Вы почти создали свою фракцию!\n\nВам осталось только создать свой флаг. Этот флаг должен быть на баннере в Minecraft и иметь не более 6 слоёв (ванильное ограничение), а также вы должны указать, как именно его нужно создать.\n\nПример того, как нужно отправлять флаг для своей фракции:"
    file_id = await db.get_image("flag_example")
    if file_id: await m.answer_photo(file_id, caption=text)
    else: await m.answer(text + "\n\n(Пример ещё не загружен создателем)")
    await state.set_state(Form.intro_faction_create_flag)

@dp.message(Form.intro_faction_create_flag, F.photo)
async def intro_create_flag(m: Message, state: FSMContext):
    await state.update_data(intro_flag=m.photo[-1].file_id)
    class FakeCb:
        from_user = m.from_user
        message = m
        async def answer(self, *a, **kw): pass
    await finish_intro(FakeCb(), state)

async def finish_intro(c, state: FSMContext):
    text = "✅ Поздравляю, вы завершили создание анкеты!\n\nЕсли вы выбрали создать свою фракцию, ожидайте сообщения о том, успешно ли она создана. Также, когда попадёте в белый список, не забудьте отправить в личные сообщения создателю сервера @AshleyCatXV ваше желаемое местоположение на карте (карта будет видна в боте, а также в чате Telegram).\n\nОдин последний вопрос: вы уверены, что хотите отправить анкету, или вы где-то ошиблись и хотите начать заново?"
    if isinstance(c, CallbackQuery): await safe_edit(c, text, intro_finish_kb())
    else: await c.message.answer(text, reply_markup=intro_finish_kb())
    await state.set_state(None)

@dp.callback_query(F.data == "intro_restart")
async def intro_restart(c: CallbackQuery, state: FSMContext):
    await state.clear()
    await c.message.delete()
    await start(c.message)

@dp.callback_query(F.data == "intro_submit")
async def intro_submit(c: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await db.set_user_field(c.from_user.id, "intro_done", 1)
    await db.toggle_user_tag(c.from_user.id, "processing")
    
    msg = f"📝 Новая анкета!\n{SEP}\nПользователь: @{c.from_user.username or 'нет'} (ID: {c.from_user.id})\nНик в игре: {data.get('intro_nick', '—')}\nОбращение: {data.get('intro_name', '—')}\nАктивность: {data.get('intro_act', '—')}\n"
    if data.get("intro_frac_join"): msg += f"Хочет присоединиться к: {data.get('intro_frac_join')}"
    elif data.get("intro_frac_create"): msg += f"Хочет создать: {data.get('intro_frac_create')}"
    
    await bot.send_message(ADMIN_ID, msg, reply_markup=intro_review_kb(c.from_user.id))
    if data.get("intro_flag"): await bot.send_photo(ADMIN_ID, data.get("intro_flag"), caption="Флаг новой фракции")

    await safe_edit(c, "✅ Анкета отправлена на рассмотрение администрации. Ожидайте ответа!")
    await c.answer()

@dp.callback_query(F.data.startswith("intro_approve:"))
async def intro_approve(c: CallbackQuery):
    if not is_admin(c.from_user.id): return
    uid = int(c.data.split(":")[1])
    tags = await db.get_user_tags(uid)
    if "processing" in tags: await db.toggle_user_tag(uid, "processing")
    if "whitelisted" not in tags: await db.toggle_user_tag(uid, "whitelisted")
    await bot.send_message(uid, "🎉 Ваша анкета одобрена! Добро пожаловать на сервер FruzenWorld Legacy.")
    await c.message.edit_text(c.message.html_text + "\n\n✅ ОДОБРЕНО", reply_markup=None)
    await c.answer("Одобрено")

@dp.callback_query(F.data.startswith("intro_reject:"))
async def intro_reject(c: CallbackQuery):
    if not is_admin(c.from_user.id): return
    uid = int(c.data.split(":")[1])
    tags = await db.get_user_tags(uid)
    if "processing" in tags: await db.toggle_user_tag(uid, "processing")
    await bot.send_message(uid, "❌ Ваша анкета отклонена. Вы можете попробовать снова, нажав /start.")
    await c.message.edit_text(c.message.html_text + "\n\n❌ ОТКЛОНЕНО", reply_markup=None)
    await c.answer("Отклонено")

# ==================== ГЛАВНОЕ МЕНЮ ====================
@dp.callback_query(F.data == "back_main")
async def back_main(c: CallbackQuery):
    if not await check_access(c): return
    await show_main_menu(c, c.from_user.id)
    await c.answer()

@dp.callback_query(F.data == "noop")
async def noop(c: CallbackQuery): await c.answer()

# ==================== ИНФОРМАЦИЯ И КАРТА ====================
@dp.callback_query(F.data == "map")
async def map_view(c: CallbackQuery):
    if not await check_access(c): return
    file_id = await db.get_image("map")
    if not file_id: return await c.answer("Карта не загружена", show_alert=True)
    try: await c.message.delete()
    except: pass
    await bot.send_photo(c.from_user.id, file_id, caption="🗺 Карта сервера.\n" + SEP, reply_markup=back_kb())
    await c.answer()

@dp.callback_query(F.data == "info")
async def info_view(c: CallbackQuery):
    if not await check_access(c): return
    text = f"ℹ️ Информация.\n{SEP}\n\nВерсия: {await db.get_global('server_version', '—')}\nЯдро: {await db.get_global('server_core', '—')}\nСезон: {await db.get_global('server_season', '—')}\nIP: {await db.get_global('server_ip', 'скрыт')}\nСтатус: {await db.get_global('server_status', 'неизвестно')}\n\nПолезные статьи:\n{await db.get_global('server_articles', '—')}"
    await safe_edit(c, text, back_kb())
    await c.answer()

@dp.callback_query(F.data == "rules")
async def rules_view(c: CallbackQuery):
    if not await check_access(c): return
    url = await db.get_global("rules_url", "")
    if not url: return await c.answer("Ссылка на правила не задана", show_alert=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📖 Открыть правила", url=url)], [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")]])
    await safe_edit(c, "📜 Правила.\n" + SEP, kb)
    await c.answer()

@dp.callback_query(F.data == "form")
async def form_view(c: CallbackQuery):
    if not await check_access(c): return
    await safe_edit(c, "✉️ Отправить форму.\n" + SEP + "\n\nВ разработке.", back_kb())
    await c.answer()

@dp.callback_query(F.data == "links")
async def links_view(c: CallbackQuery):
    if not await check_access(c): return
    rows = await db.get_links()
    tags = await db.get_user_tags(c.from_user.id)
    kb = []
    for _, title, url in rows: kb.append([InlineKeyboardButton(text=title, url=url)])
    if "admin" in tags:
        admin_chat_url = await db.get_global("admin_chat_url", "")
        if admin_chat_url: kb.append([InlineKeyboardButton(text="🛡 Чат админов", url=admin_chat_url)])
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")])
    await safe_edit(c, "🔗 Ссылки.\n" + SEP, InlineKeyboardMarkup(inline_keyboard=kb))
    await c.answer()

@dp.callback_query(F.data == "resourcepack")
async def rp_view(c: CallbackQuery):
    if not await check_access(c): return
    row = await db.get_resourcepack()
    if not row or not row[0]: return await c.answer("Ресурспак не загружен", show_alert=True)
    try: await c.message.delete()
    except: pass
    await bot.send_document(c.from_user.id, row[0], caption="📦 Ресурспак сервера.\n" + SEP + "\n\n" + (row[1] or ""), reply_markup=back_kb())
    await c.answer()

# ==================== ПРОФИЛЬ ====================
@dp.callback_query(F.data == "profile")
async def profile_view(c: CallbackQuery):
    if not await check_access(c): return
    await show_profile(c, c.from_user.id, admin_view=False)
    await c.answer()

@dp.callback_query(F.data == "edit_nick_bot")
async def edit_nick_bot(c: CallbackQuery, state: FSMContext):
    if not await check_access(c): return
    await c.message.answer("Введи новый ник в боте:")
    await state.set_state(Form.edit_nick_bot)
    await c.answer()

@dp.message(Form.edit_nick_bot)
async def save_nick_bot(m: Message, state: FSMContext):
    await db.set_user_field(m.from_user.id, "nick_bot", m.text.strip())
    await state.clear()
    await m.answer("✅ Ник в боте обновлён.")
    await show_profile(_FakeCbForProfile(m.from_user), m.from_user.id, admin_view=False)

# ==================== НОВЫЕ ФРАКЦИИ ====================
@dp.callback_query(F.data == "factions")
async def factions_view(c: CallbackQuery):
    if not await check_access(c): return
    rows = await db.get_factions()
    kb = paginated_kb([(r[0], r[1]) for r in rows], 0, PER_PAGE, "faction_view:", "back_main", nav_prefix="fv")
    await safe_edit(c, "🚩 Фракции.\n" + SEP, kb)
    await c.answer()

@dp.callback_query(F.data.startswith("fv:faction_view:"))
async def factions_page(c: CallbackQuery):
    page = int(c.data.split(":")[2])
    rows = await db.get_factions()
    kb = paginated_kb([(r[0], r[1]) for r in rows], page, PER_PAGE, "faction_view:", "back_main", nav_prefix="fv")
    await safe_edit(c, "🚩 Фракции.\n" + SEP, kb)
    await c.answer()

@dp.callback_query(F.data.startswith("faction_view:"))
async def faction_profile(c: CallbackQuery):
    if not await check_access(c): return
    fid = int(c.data.split(":")[1])
    rows = await db.get_factions()
    f = next((r for r in rows if r[0] == fid), None)
    if not f: return await c.answer("Фракция не найдена", show_alert=True)
    fname, leader_id = f[1], f[2]
    leader_name = "—"
    if leader_id:
        lu = await db.get_user(leader_id)
        if lu: leader_name = lu[4] or lu[1] or str(leader_id)
    users = await db.get_all_users()
    members = []
    for u_id, u_name, u_fname in users:
        user_data = await db.get_user(u_id)
        if user_data and user_data[5] == fname: members.append(user_data[4] or user_data[1] or str(u_id))
    text = f"🚩 {fname}.\n{SEP}\n\nГлава: {leader_name}\n\nИгроки:\n" + "\n".join([f"• {m}" for m in members])
    await safe_edit(c, text, back_kb("factions"))
    await c.answer()

# ==================== НОВЫЕ ИГРОКИ ====================
@dp.callback_query(F.data == "players")
async def players_view(c: CallbackQuery):
    if not await check_access(c): return
    rows = await db.get_whitelist()
    kb = paginated_kb(rows, 0, PER_PAGE, "player_view:", "back_main", nav_prefix="pv")
    await safe_edit(c, "👥 Игроки.\n" + SEP, kb)
    await c.answer()

@dp.callback_query(F.data.startswith("pv:player_view:"))
async def players_page(c: CallbackQuery):
    page = int(c.data.split(":")[2])
    rows = await db.get_whitelist()
    kb = paginated_kb(rows, page, PER_PAGE, "player_view:", "back_main", nav_prefix="pv")
    await safe_edit(c, "👥 Игроки.\n" + SEP, kb)
    await c.answer()

@dp.callback_query(F.data.startswith("player_view:"))
async def player_profile(c: CallbackQuery):
    if not await check_access(c): return
    wid = int(c.data.split(":")[1])
    users = await db.get_all_users()
    target = None
    wl = await db.get_whitelist()
    nick = next((n for i, n in wl if i == wid), None)
    if nick:
        for u_id, _, _ in users:
            u_data = await db.get_user(u_id)
            if u_data and u_data[4] == nick: target = u_id; break
    if not target: return await c.answer("Игрок ещё не заходил в бота.", show_alert=True)
    u = await db.get_user(target)
    text = f"👤 Профиль игрока.\n{SEP}\n\nНик: {u[4]}\nФракция: {u[5] or '—'}"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✉️ Написать сообщение", callback_data=f"msg_player:{target}")], [InlineKeyboardButton(text="⬅️ Назад", callback_data="players")]])
    await safe_edit(c, text, kb)
    await c.answer()

@dp.callback_query(F.data.startswith("msg_player:"))
async def msg_player(c: CallbackQuery, state: FSMContext):
    if not await check_access(c): return
    target_id = int(c.data.split(":")[1])
    await c.message.answer("Введи сообщение:")
    await state.update_data(target_user=target_id, is_player_msg=True)
    await state.set_state(Form.admin_send_to_user)
    await c.answer()

# ==================== АДМИН ПАНЕЛЬ ====================
@dp.callback_query(F.data == "admin")
async def admin_menu(c: CallbackQuery):
    if not is_admin(c.from_user.id): return await c.answer("Нет доступа", show_alert=True)
    await safe_edit(c, "🛠 Меню создателя.\n" + SEP, admin_kb())
    await c.answer()

# --- Пользователи (добавление нового) ---
@dp.callback_query(F.data == "admin_users")
async def admin_users(c: CallbackQuery):
    if not is_admin(c.from_user.id): return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить пользователя", callback_data="admin_add_user")],
        [InlineKeyboardButton(text="📋 Все пользователи", callback_data="admin_list_users")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin")]
    ])
    await safe_edit(c, "👥 Управление пользователями.\n" + SEP, kb)
    await c.answer()

@dp.callback_query(F.data == "admin_list_users")
async def admin_list_users(c: CallbackQuery):
    if not is_admin(c.from_user.id): return
    users = await db.get_all_users()
    kb = paginated_users_kb(users, 0, "user_view:", "admin_users")
    await safe_edit(c, f"👥 Пользователи ({len(users)}).\n" + SEP, kb)
    await c.answer()

@dp.callback_query(F.data.startswith("upg:user_view:"))
async def users_page(c: CallbackQuery):
    page = int(c.data.split(":")[2])
    users = await db.get_all_users()
    kb = paginated_users_kb(users, page, "user_view:", "admin_users")
    await safe_edit(c, f"👥 Пользователи.\n" + SEP, kb)
    await c.answer()

@dp.callback_query(F.data.startswith("user_view:"))
async def user_view(c: CallbackQuery):
    if not is_admin(c.from_user.id): return
    await show_profile(c, int(c.data.split(":")[1]), admin_view=True)
    await c.answer()

@dp.callback_query(F.data == "admin_add_user")
async def admin_add_user(c: CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id): return
    await c.message.answer("Введи через пробел: @username или ID, Ник на сервере, Фракция, UUID\n\n(Если чего-то нет, пиши -)")
    await state.set_state(Form.admin_add_user_manually)
    await c.answer()

@dp.message(Form.admin_add_user_manually)
async def save_added_user(m: Message, state: FSMContext):
    parts = m.text.split(maxsplit=3)
    if len(parts) < 4: return await m.answer("❌ Нужно 4 параметра: @username/ID Ник Фракция UUID")
    
    target, n_server, frac, uid_str = parts
    username = target.lstrip("@")
    user_id = int(target) if target.isdigit() else 0
    
    async with aiosqlite.connect(db.DB) as conn:
        if user_id:
            await conn.execute("INSERT OR REPLACE INTO users (user_id, username, nick_server, fraction, uuid, intro_done, tags) VALUES (?, ?, ?, ?, ?, 1, 'whitelisted')",
                               (user_id, username, n_server, frac, uid_str))
        else:
            # Если только юзернейм, создаем "фантомного" пользователя с ID 0
            await conn.execute("INSERT INTO users (user_id, username, nick_server, fraction, uuid, intro_done, tags) VALUES (NULL, ?, ?, ?, ?, 1, 'whitelisted')",
                               (username, n_server, frac, uid_str))
        await conn.commit()
    
    await m.answer("✅ Пользователь добавлен.")
    await state.clear()
    await admin_users(await _fake_cb(m))

# --- Остальные админ-функции ---
@dp.message(Form.admin_send_to_user)
async def send_to_user(m: Message, state: FSMContext):
    data = await state.get_data()
    uid = data.get("target_user")
    is_player = data.get("is_player_msg", False)
    sender_u = await db.get_user(m.from_user.id)
    sender_info = f"{sender_u[4] or '—'} (@{m.from_user.username or m.from_user.id})" if sender_u else "Игрок"
    if is_player: text = f"📩 Вам сообщение от игрока {sender_info}.\n{SEP}\n\n{m.text}"
    else: text = f"📩 Сообщение от админа.\n{SEP}\n\n{m.text}"
    try:
        await bot.send_message(int(uid), text)
        await m.answer("✅ Отправлено.")
    except Exception as e: await m.answer(f"❌ Ошибка: {e}")
    await state.clear()
    await show_main_menu(await _fake_cb(m), m.from_user.id)

@dp.callback_query(F.data.startswith("aedit:"))
async def admin_edit_field(c: CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id): return
    _, field, uid_str = c.data.split(":")
    uid = int(uid_str)
    if field == "fraction":
        rows = await db.get_factions()
        if not rows: return await c.answer("Сначала добавь фракции.", show_alert=True)
        kb = paginated_kb(rows, 0, PER_PAGE, f"faction_pick:{uid}:", "admin_users", nav_prefix="fpp")
        await safe_edit(c, f"🎯 Выбери фракцию для пользователя {uid}.\n" + SEP, kb)
        await c.answer()
        return
    prompts = {"nick_bot": "Введи новый ник в боте:", "nick_server": "Введи новый ник на сервере Minecraft:", "uuid": "Введи новый UUID:"}
    await c.message.answer(prompts[field])
    await state.update_data(target_user=uid, target_field=field)
    await state.set_state(Form.admin_edit_user)
    await c.answer()

@dp.message(Form.admin_edit_user)
async def admin_edit_user_save(m: Message, state: FSMContext):
    data = await state.get_data()
    uid, field = data.get("target_user"), data.get("target_field")
    if uid is None or field is None: return await m.answer("❌ Сессия истекла.")
    await db.set_user_field(int(uid), field, m.text.strip())
    await state.clear()
    await m.answer("✅ Сохранено.")
    await show_profile(_FakeCbForProfile(m.from_user), int(uid), admin_view=True)

@dp.callback_query(F.data == "admin_factions")
async def admin_factions(c: CallbackQuery):
    if not is_admin(c.from_user.id): return
    await safe_edit(c, "🚩 Управление фракциями.\n" + SEP, admin_factions_kb())
    await c.answer()

@dp.callback_query(F.data == "admin_faction_add")
async def admin_faction_add(c: CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id): return
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
    if not is_admin(c.from_user.id): return
    rows = await db.get_factions()
    if not rows: return await c.answer("Фракций нет.", show_alert=True)
    await _render_faction_del_page(c, 0)

async def _render_faction_del_page(c: CallbackQuery, page: int):
    rows = await db.get_factions()
    kb = paginated_kb([(r[0], r[1]) for r in rows], page, PER_PAGE, "faction_del:", "admin_factions")
    await safe_edit(c, "🚩 Выбери фракцию для удаления.\n" + SEP, kb)

@dp.callback_query(F.data.startswith("pg:faction_del:"))
async def faction_del_page(c: CallbackQuery):
    await _render_faction_del_page(c, int(c.data.split(":")[2]))
    await c.answer()

@dp.callback_query(F.data.startswith("faction_del:"))
async def faction_del(c: CallbackQuery):
    if not is_admin(c.from_user.id): return
    await db.remove_faction_by_id(int(c.data.split(":")[1]))
    rows = await db.get_factions()
    if not rows: await safe_edit(c, "✅ Фракция удалена.\n\nСписок пуст.", admin_factions_kb())
    else: await _render_faction_del_page(c, 0)
    await c.answer("Удалено")

@dp.callback_query(F.data.startswith("fpp:faction_pick:"))
async def faction_pick_page(c: CallbackQuery):
    parts = c.data.split(":")
    uid, page = int(parts[2]), int(parts[3])
    rows = await db.get_factions()
    kb = paginated_kb(rows, page, PER_PAGE, f"faction_pick:{uid}:", "admin_users", nav_prefix="fpp")
    await safe_edit(c, f"🎯 Выбери фракцию для пользователя {uid}.\n" + SEP, kb)
    await c.answer()

@dp.callback_query(F.data.startswith("faction_pick:"))
async def faction_pick(c: CallbackQuery):
    if not is_admin(c.from_user.id): return
    parts = c.data.split(":")
    uid, fid = int(parts[1]), int(parts[2])
    rows = await db.get_factions()
    name = next((n for i, n, _ in rows if i == fid), None)
    if not name: return await c.answer("Фракция не найдена.", show_alert=True)
    await db.set_user_field(uid, "fraction", name)
    await c.answer("Готово")
    await show_profile(c, uid, admin_view=True)

@dp.callback_query(F.data == "admin_whitelist")
async def admin_whitelist(c: CallbackQuery):
    if not is_admin(c.from_user.id): return
    await safe_edit(c, "👥 Белый список.\n" + SEP, admin_whitelist_kb())
    await c.answer()

@dp.callback_query(F.data == "admin_wl_add")
async def admin_wl_add(c: CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id): return
    await c.message.answer("Введи ник игрока:")
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
    if not is_admin(c.from_user.id): return
    rows = await db.get_whitelist()
    if not rows: return await c.answer("Список пуст.", show_alert=True)
    await _render_wl_del_page(c, 0)

async def _render_wl_del_page(c: CallbackQuery, page: int):
    rows = await db.get_whitelist()
    kb = paginated_kb(rows, page, PER_PAGE, "wl_del:", "admin_whitelist")
    await safe_edit(c, "👥 Выбери игрока для удаления.\n" + SEP, kb)

@dp.callback_query(F.data.startswith("pg:wl_del:"))
async def wl_del_page(c: CallbackQuery):
    await _render_wl_del_page(c, int(c.data.split(":")[2]))
    await c.answer()

@dp.callback_query(F.data.startswith("wl_del:"))
async def wl_del(c: CallbackQuery):
    if not is_admin(c.from_user.id): return
    await db.remove_whitelist_by_id(int(c.data.split(":")[1]))
    rows = await db.get_whitelist()
    if not rows: await safe_edit(c, "✅ Удалено.\n\nСписок пуст.", admin_whitelist_kb())
    else: await _render_wl_del_page(c, 0)
    await c.answer("Удалено")

@dp.callback_query(F.data == "admin_links")
async def admin_links(c: CallbackQuery):
    if not is_admin(c.from_user.id): return
    await safe_edit(c, "🔗 Управление ссылками.\n" + SEP, admin_links_kb())
    await c.answer()

@dp.callback_query(F.data == "admin_link_add")
async def admin_link_add(c: CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id): return
    await c.message.answer("Введи: Название | URL")
    await state.set_state(Form.admin_add_link)
    await c.answer()

@dp.message(Form.admin_add_link)
async def link_add(m: Message, state: FSMContext):
    try:
        title, url = m.text.split("|", 1)
        await db.add_link(title.strip(), url.strip())
        await m.answer("✅ Ссылка добавлена.")
    except: await m.answer("❌ Формат: Название | URL")
    await state.clear()
    await admin_links(await _fake_cb(m))

@dp.callback_query(F.data == "admin_link_del")
async def admin_link_del(c: CallbackQuery):
    if not is_admin(c.from_user.id): return
    rows = await db.get_links()
    if not rows: return await c.answer("Ссылок нет.", show_alert=True)
    await _render_link_del_page(c, 0)

async def _render_link_del_page(c: CallbackQuery, page: int):
    rows = await db.get_links()
    kb = paginated_kb([(i, t) for i, t, _ in rows], page, PER_PAGE, "link_del:", "admin_links")
    await safe_edit(c, "🔗 Выбери ссылку для удаления.\n" + SEP, kb)

@dp.callback_query(F.data.startswith("pg:link_del:"))
async def link_del_page(c: CallbackQuery):
    await _render_link_del_page(c, int(c.data.split(":")[2]))
    await c.answer()

@dp.callback_query(F.data.startswith("link_del:"))
async def link_del(c: CallbackQuery):
    if not is_admin(c.from_user.id): return
    await db.remove_link(int(c.data.split(":")[1]))
    rows = await db.get_links()
    if not rows: await safe_edit(c, "✅ Удалено.\n\nСписок пуст.", admin_links_kb())
    else: await _render_link_del_page(c, 0)
    await c.answer("Удалено")

@dp.callback_query(F.data == "admin_rules_url")
async def admin_rules_url(c: CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id): return
    await c.message.answer(f"Текущая: {await db.get_global('rules_url', 'нет')}\nПришли новую ссылку:")
    await state.set_state(Form.admin_rules_url)
    await c.answer()

@dp.message(Form.admin_rules_url)
async def save_rules_url(m: Message, state: FSMContext):
    await db.set_global("rules_url", m.text.strip())
    await state.clear()
    await m.answer("✅ Ссылка сохранена.")
    await admin_links(await _fake_cb(m))

@dp.callback_query(F.data == "admin_adminchat_url")
async def admin_adminchat_url(c: CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id): return
    await c.message.answer(f"Текущая: {await db.get_global('admin_chat_url', 'нет')}\nПришли новую ссылку:")
    await state.set_state(Form.admin_adminchat_url)
    await c.answer()

@dp.message(Form.admin_adminchat_url)
async def save_admin_chat_url(m: Message, state: FSMContext):
    await db.set_global("admin_chat_url", m.text.strip())
    await state.clear()
    await m.answer("✅ Ссылка сохранена.")
    await admin_links(await _fake_cb(m))

@dp.callback_query(F.data == "admin_flag_example")
async def admin_flag_example(c: CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id): return
    await c.message.answer("Пришли картинку-пример флага:")
    await state.set_state(Form.admin_flag_example)
    await c.answer()

@dp.message(Form.admin_flag_example, F.photo)
async def save_flag_example(m: Message, state: FSMContext):
    await db.set_image("flag_example", m.photo[-1].file_id)
    await state.clear()
    await m.answer("✅ Пример сохранён.")
    await admin_links(await _fake_cb(m))

@dp.callback_query(F.data == "admin_map")
async def admin_map(c: CallbackQuery):
    if not is_admin(c.from_user.id): return
    has_map = bool(await db.get_image("map"))
    text = "🗺 Управление картой.\n" + SEP + "\n\nСтатус: " + ("✅ загружена" if has_map else "❌ не загружена")
    await safe_edit(c, text, admin_map_kb(has_map))
    await c.answer()

@dp.callback_query(F.data == "admin_map_upload")
async def admin_map_upload(c: CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id): return
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
    if not is_admin(c.from_user.id): return
    await db.delete_image("map")
    await c.answer("Карта удалена")
    await admin_map(c)

@dp.callback_query(F.data == "admin_rp")
async def admin_rp(c: CallbackQuery):
    if not is_admin(c.from_user.id): return
    row = await db.get_resourcepack()
    has_rp = bool(row and row[0])
    text = "📦 Управление ресурспаком.\n" + SEP + "\n\nСтатус: " + ("✅ загружен" if has_rp else "❌ не загружен")
    await safe_edit(c, text, admin_rp_kb(has_rp))
    await c.answer()

@dp.callback_query(F.data == "admin_rp_upload")
async def admin_rp_upload(c: CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id): return
    await c.message.answer("Пришли файл ресурспака (как документ):")
    await state.set_state(Form.admin_upload_rp)
    await c.answer()

@dp.message(Form.admin_upload_rp, F.document)
async def save_rp_file(m: Message, state: FSMContext):
    await state.update_data(rp_file_id=m.document.file_id)
    await m.answer("Теперь пришли текст инструкции:")
    await state.set_state(Form.admin_rp_instruction)

@dp.message(Form.admin_rp_instruction)
async def save_rp_instruction(m: Message, state: FSMContext):
    data = await state.get_data()
    await db.set_resourcepack(data.get("rp_file_id"), m.text.strip())
    await state.clear()
    await m.answer("✅ Сохранено.")
    await admin_rp(await _fake_cb(m))

@dp.callback_query(F.data == "admin_rp_del")
async def admin_rp_del(c: CallbackQuery):
    if not is_admin(c.from_user.id): return
    await db.delete_resourcepack()
    await c.answer("Удалено")
    await admin_rp(c)

@dp.callback_query(F.data == "admin_globals")
async def admin_globals(c: CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id): return
    await c.message.answer("Введи: ключ значение\n\n(server_version, server_core, server_season, server_ip, server_status, server_articles)")
    await state.set_state(Form.admin_set_global)
    await c.answer()

@dp.message(Form.admin_set_global)
async def save_global(m: Message, state: FSMContext):
    try:
        key, value = m.text.split(maxsplit=1)
        await db.set_global(key, value)
        await m.answer("✅ Сохранено.")
    except: await m.answer("❌ Формат: ключ значение")
    await state.clear()
    await admin_menu(await _fake_cb(m))

@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast(c: CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id): return
    await c.message.answer("Введи текст для рассылки всем пользователям:")
    await state.set_state(Form.admin_broadcast_text)
    await c.answer()

@dp.message(Form.admin_broadcast_text)
async def broadcast_text(m: Message, state: FSMContext):
    users = await db.get_all_users()
    ok, fail = 0, 0
    for uid, _, _ in users:
        try:
            await bot.send_message(uid, f"📢 Уведомление:\n{SEP}\n\n{m.text}")
            ok += 1
        except: fail += 1
    await m.answer(f"✅ Рассылка завершена.\nДоставлено: {ok}\nОшибок: {fail}")
    await state.clear()
    await admin_menu(await _fake_cb(m))

@dp.message(Command("backup"))
async def backup_cmd(m: Message):
    if not is_admin(m.from_user.id): return
    if not os.path.exists(db.DB): return await m.answer("Файл БД не найден.")
    try: await m.answer_document(FSInputFile(db.DB, filename="bot.db"), caption="📦 Резервная копия БД.")
    except Exception as e: await m.answer(f"❌ Ошибка: {e}")

@dp.message(Command("restore"))
async def restore_cmd(m: Message):
    if not is_admin(m.from_user.id): return
    await m.answer("📥 Пришли файл bot.db (как документ).\n⚠️ Текущая БД будет перезаписана!")

@dp.message(F.document)
async def restore_file(m: Message):
    if not is_admin(m.from_user.id) or not m.document.file_name.endswith(".db"): return
    if m.document.file_name != "bot.db": return
    try:
        file = await bot.get_file(m.document.file_id)
        temp_path = "bot_restore_tmp.db"
        await bot.download_file(file.file_path, temp_path)
        conn = sqlite3.connect(temp_path)
        conn.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1;")
        conn.close()
        shutil.move(temp_path, db.DB)
        await m.answer("✅ БД восстановлена. Перезапусти бота.")
    except Exception as e: await m.answer(f"❌ Ошибка: {e}")

@dp.callback_query(F.data == "admin_backup")
async def admin_backup(c: CallbackQuery):
    if not is_admin(c.from_user.id): return
    if not os.path.exists(db.DB): return await c.answer("Файл БД не найден", show_alert=True)
    try: await bot.send_document(c.from_user.id, FSInputFile(db.DB, filename="bot.db"), caption="📦 Резервная копия БД.")
    except Exception as e: await bot.send_message(c.from_user.id, f"❌ Ошибка: {e}")
    await c.answer()

@dp.callback_query(F.data.startswith("tags_menu:"))
async def tags_menu(c: CallbackQuery):
    if not is_admin(c.from_user.id): return
    uid = int(c.data.split(":")[1])
    current = await db.get_user_tags(uid)
    await safe_edit(c, f"🏷 Теги пользователя {uid}.\n{SEP}\n\nНажми на тег, чтобы добавить/убрать:", tags_menu_kb(uid, current))
    await c.answer()

@dp.callback_query(F.data.startswith("tag_toggle:"))
async def tag_toggle(c: CallbackQuery):
    if not is_admin(c.from_user.id): return
    _, uid_str, tag = c.data.split(":")
    uid = int(uid_str)
    added = await db.toggle_user_tag(uid, tag)
    current = await db.get_user_tags(uid)
    await safe_edit(c, f"🏷 Теги пользователя {uid}.\n{SEP}\n\nНажми на тег, чтобы добавить/убрать:", tags_menu_kb(uid, current))
    await c.answer(f"Тег {'добавлен' if added else 'убран'}")

# ==================== ЗАПУСК ====================
async def main():
    await db.init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    me = await bot.get_me()
    logging.info(f"✅ Бот запущен: @{me.username} (id={me.id})")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
