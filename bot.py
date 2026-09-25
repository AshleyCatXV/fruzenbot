import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

import database as db
from config import BOT_TOKEN, ADMIN_ID
from keyboards import main_kb, admin_kb

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# ---------- FSM состояния ----------
class Form(StatesGroup):
    edit_tag = State()
    edit_var = State()
    admin_set_user = State()
    admin_set_global = State()
    admin_send_user = State()
    admin_upload_image = State()


def is_admin(uid: int) -> bool:
    return uid == ADMIN_ID


# ---------- /start ----------
@dp.message(CommandStart())
async def start(m: Message):
    await db.add_user(m.from_user.id, m.from_user.username or "")
    await m.answer(
        "Привет! Выбери действие:",
        reply_markup=main_kb(is_admin(m.from_user.id))
    )


# ---------- Профиль ----------
@dp.callback_query(F.data == "profile")
async def profile(c: CallbackQuery):
    u = await db.get_user(c.from_user.id)
    if not u:
        await db.add_user(c.from_user.id, c.from_user.username or "")
        u = await db.get_user(c.from_user.id)
    text = (
        f"👤 ID: <code>{u[0]}</code>\n"
        f"Логин: @{u[1] or '—'}\n"
        f"🏷 Тег: {u[2] or '—'}\n"
        f"📝 Переменная: {u[3] or '—'}"
    )
    await c.message.edit_text(text, reply_markup=main_kb(is_admin(c.from_user.id)))
    await c.answer()


# ---------- Свой тег ----------
@dp.callback_query(F.data == "edit_tag")
async def edit_tag(c: CallbackQuery, state: FSMContext):
    await c.message.answer("Пришли новый тег:")
    await state.set_state(Form.edit_tag)
    await c.answer()


@dp.message(Form.edit_tag)
async def save_tag(m: Message, state: FSMContext):
    await db.set_user_field(m.from_user.id, "tag", m.text.strip())
    await state.clear()
    await m.answer("✅ Тег обновлён", reply_markup=main_kb(is_admin(m.from_user.id)))


# ---------- Своя переменная ----------
@dp.callback_query(F.data == "edit_var")
async def edit_var(c: CallbackQuery, state: FSMContext):
    await c.message.answer("Пришли значение переменной:")
    await state.set_state(Form.edit_var)
    await c.answer()


@dp.message(Form.edit_var)
async def save_var(m: Message, state: FSMContext):
    await db.set_user_field(m.from_user.id, "custom_var", m.text.strip())
    await state.clear()
    await m.answer("✅ Переменная обновлена", reply_markup=main_kb(is_admin(m.from_user.id)))


# ---------- Глобальные значения ----------
@dp.callback_query(F.data == "globals")
async def show_globals(c: CallbackQuery):
    val = await db.get_global("global_var", "не задано")
    await c.message.edit_text(
        f"🌍 Глобальная переменная: {val}",
        reply_markup=main_kb(is_admin(c.from_user.id))
    )
    await c.answer()


@dp.callback_query(F.data == "back_main")
async def back_main(c: CallbackQuery):
    await c.message.edit_text(
        "Главное меню:",
        reply_markup=main_kb(is_admin(c.from_user.id))
    )
    await c.answer()


# ==================== АДМИН ====================

@dp.callback_query(F.data == "admin")
async def admin(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    await c.message.edit_text("🛠 Админ-панель", reply_markup=admin_kb())
    await c.answer()


# --- Список пользователей ---
@dp.callback_query(F.data == "admin_users")
async def admin_users(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    users = await db.get_all_users()
    ids = "\n".join(str(u) for u in users[:30])
    await c.message.edit_text(
        f"👥 Всего: {len(users)}\n\n{ids}",
        reply_markup=admin_kb()
    )
    await c.answer()


# --- Изменить данные пользователя ---
@dp.callback_query(F.data == "admin_user_edit")
async def admin_user_edit(c: CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    await c.message.answer(
        "Введи в формате:\n"
        "<code>USER_ID tag значение</code>\n"
        "или\n"
        "<code>USER_ID custom_var значение</code>"
    )
    await state.set_state(Form.admin_set_user)
    await c.answer()


@dp.message(Form.admin_set_user)
async def admin_save_user(m: Message, state: FSMContext):
    try:
        uid, field, value = m.text.split(maxsplit=2)
        if field not in ("tag", "custom_var"):
            raise ValueError("Неверное поле")
        await db.set_user_field(int(uid), field, value)
        await m.answer("✅ Готово")
    except Exception:
        await m.answer("❌ Формат: USER_ID tag значение")
    await state.clear()


# --- Обновление картинки ---
@dp.callback_query(F.data == "admin_image")
async def admin_image(c: CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    await c.message.answer("Пришли новую картинку — она заменит 'main_image'.")
    await state.set_state(Form.admin_upload_image)
    await c.answer()


@dp.message(Form.admin_upload_image, F.photo)
async def save_image(m: Message, state: FSMContext):
    await db.set_image("main_image", m.photo[-1].file_id)
    await state.clear()
    await m.answer("✅ Картинка обновлена")


# --- Глобальные переменные ---
@dp.callback_query(F.data == "admin_globals")
async def admin_globals(c: CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    await c.message.answer("Введи: <code>ключ значение</code>")
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
@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast(c: CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа", show_alert=True)
    await c.message.answer("Введи: <code>USER_ID текст сообщения</code>")
    await state.set_state(Form.admin_send_user)
    await c.answer()


@dp.message(Form.admin_send_user)
async def send_to_user(m: Message, state: FSMContext):
    try:
        uid_str, text = m.text.split(maxsplit=1)
        await bot.send_message(int(uid_str), f"📩 Сообщение от админа:\n\n{text}")
        await m.answer("✅ Отправлено")
    except Exception as e:
        await m.answer(f"❌ Ошибка: {e}")
    await state.clear()


# --- Быстрая отправка через /send ---
@dp.message(Command("send"))
async def cmd_send(m: Message):
    if not is_admin(m.from_user.id):
        return
    try:
        _, uid, text = m.text.split(maxsplit=2)
        await bot.send_message(int(uid), text)
        await m.answer("✅ Отправлено")
    except Exception as e:
        await m.answer(f"Ошибка: {e}")


# ==================== ЗАПУСК ====================

async def main():
    await db.init_db()

    # ⚠️ Сброс webhook — решает конфликт getUpdates vs webhook
    await bot.delete_webhook(drop_pending_updates=True)

    me = await bot.get_me()
    logging.info(f"✅ Бот запущен: @{me.username} (id={me.id})")
    logging.info("Начинаю polling...")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
