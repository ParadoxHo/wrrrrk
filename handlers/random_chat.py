import asyncio
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from database import async_session
from database.crud import (
    add_to_chat_queue, remove_from_chat_queue, get_random_user_from_queue,
    create_active_chat, get_active_chat_by_user, end_active_chat, get_or_create_user,
    cleanup_expired_queue, set_allow_random_chat, find_available_user
)
from keyboards.inline import catalog_kb, cancel_search_kb
from keyboards.reply import commands_keyboard
from handlers.start import show_catalog, help_handler
from handlers.stats import stats as stats_handler

router = Router()

# Убираем класс состояний, он больше не нужен

async def _create_chat_and_notify(call, partner_telegram_id):
    async with async_session() as session:
        chat = await create_active_chat(session, call.from_user.id, partner_telegram_id)
        partner_user = await get_or_create_user(session, partner_telegram_id)
        try:
            await call.bot.send_message(
                partner_telegram_id,
                "🎲 Собеседник найден! Можете начинать общение.\n"
                "Кнопки «Главная» и «Завершить» закроют чат.",
                reply_markup=commands_keyboard()
            )
        except Exception:
            await end_active_chat(session, chat.id)
            await call.answer("Не удалось связаться с собеседником.", show_alert=True)
            return
        await call.message.edit_text("🎲 Собеседник найден! Можете начинать общение.")
        await call.message.answer("Используйте кнопки ниже для быстрого доступа:", reply_markup=commands_keyboard())

async def _end_chat_and_notify(bot, user_id: int):
    """Завершает активный чат пользователя и уведомляет партнёра."""
    async with async_session() as session:
        chat = await get_active_chat_by_user(session, user_id)
        if not chat:
            return
        partner_id = chat.user2_id if user_id == chat.user1_id else chat.user1_id
        await end_active_chat(session, chat.id)
        partner_user = await get_or_create_user(session, partner_id)
        try:
            await bot.send_message(partner_user.telegram_id, "🔚 Собеседник завершил чат.")
        except:
            pass

async def _send_chat_request(call, partner_telegram_id):
    # Отправляем запрос пассивному пользователю с кнопками, где callback_data содержит ID искателя
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    accept_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Принять", callback_data=f"accept_chat:{call.from_user.id}"),
         InlineKeyboardButton(text="❌ Отклонить", callback_data=f"decline_chat:{call.from_user.id}")]
    ])
    try:
        await call.bot.send_message(
            partner_telegram_id,
            "📩 Кто-то хочет начать с вами случайный чат. Принять?",
            reply_markup=accept_kb
        )
        await call.message.edit_text("📩 Запрос отправлен пользователю. Ожидайте ответа...")
    except:
        await call.message.edit_text("Не удалось отправить запрос. Попробуйте позже.", reply_markup=catalog_kb())

# ---------- Основной поиск ----------
@router.callback_query(F.data == "random_chat")
async def random_chat_start(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = call.from_user.id

    async with async_session() as session:
        if await get_active_chat_by_user(session, user_id):
            await call.answer("Вы уже в чате! Завершите его командой /stop.", show_alert=True)
            return

        from sqlalchemy import select
        from database.models import ChatQueue
        q = await session.execute(select(ChatQueue).where(ChatQueue.user_id == user_id))
        if q.scalar_one_or_none():
            await call.answer("Вы уже в очереди. Ожидайте собеседника.", show_alert=True)
            return

        await cleanup_expired_queue(session, bot=call.bot)

        # 1. Ищем активного искателя в очереди
        partner = await get_random_user_from_queue(session, exclude_user_id=user_id)
        if partner:
            await remove_from_chat_queue(session, user_id)
            await remove_from_chat_queue(session, partner.user_id)
            await _create_chat_and_notify(call, partner.user_id)
            return

        # 2. Ищем пассивного пользователя с allow_random_chat=1
        available_user = await find_available_user(session, exclude_user_id=user_id)
        if available_user:
            await _send_chat_request(call, available_user.telegram_id)
            return

        # 3. Никого нет – встаём в очередь
        await add_to_chat_queue(session, user_id)
        await call.message.edit_text("🔍 Ищем собеседника... Ожидайте.", reply_markup=cancel_search_kb())

# ---------- Отмена поиска ----------
@router.callback_query(F.data == "cancel_search")
async def cancel_search(call: types.CallbackQuery, state: FSMContext):
    async with async_session() as session:
        await remove_from_chat_queue(session, call.from_user.id)
    await call.message.edit_text("Поиск отменён.", reply_markup=catalog_kb())
    await call.answer()

# ---------- Обработка запроса (глобальные колбэки) ----------
@router.callback_query(F.data.startswith("accept_chat:"))
async def accept_chat_request(call: types.CallbackQuery):
    requester_id = int(call.data.split(":")[1])
    async with async_session() as session:
        # Проверяем, не в чате ли уже кто-то из них
        if await get_active_chat_by_user(session, call.from_user.id) or await get_active_chat_by_user(session, requester_id):
            await call.answer("Кто-то уже в чате.", show_alert=True)
            return
        chat = await create_active_chat(session, requester_id, call.from_user.id)
        # Уведомляем искателя
        try:
            await call.bot.send_message(requester_id, "🎲 Собеседник принял запрос! Начинайте общение.")
        except:
            pass
        await call.message.edit_text("Вы приняли запрос. Сейчас начнётся чат.", reply_markup=None)
        await call.message.answer("Используйте кнопки ниже для быстрого доступа:", reply_markup=commands_keyboard())
    await call.answer()

@router.callback_query(F.data.startswith("decline_chat:"))
async def decline_chat_request(call: types.CallbackQuery):
    requester_id = int(call.data.split(":")[1])
    try:
        await call.bot.send_message(requester_id, "📩 Пользователь отклонил запрос. Вы вернулись в меню.")
    except:
        pass
    await call.message.edit_text("Вы отклонили запрос.", reply_markup=None)
    await call.answer()

# ---------- Быстрые кнопки и завершение ----------
@router.message(F.text == "🏠 Главная")
async def main_menu_from_chat(msg: types.Message, state: FSMContext):
    await _end_chat_and_notify(msg.bot, msg.from_user.id)
    await show_catalog(msg, state)

@router.message(F.text == "📊 Статистика")
async def stats_from_chat(msg: types.Message):
    await stats_handler(msg)

@router.message(F.text == "ℹ️ Помощь")
async def help_from_chat(msg: types.Message, state: FSMContext):
    await help_handler(msg, state)

@router.message(Command("stop"))
@router.message(Command("finish"))
@router.message(F.text == "❌ Завершить")
async def stop_chat(msg: types.Message):
    async with async_session() as session:
        chat = await get_active_chat_by_user(session, msg.from_user.id)
        if not chat:
            await msg.answer("Вы не в чате.")
            return
        await end_active_chat(session, chat.id)
        partner_id = chat.user2_id if msg.from_user.id == chat.user1_id else chat.user1_id
        partner_user = await get_or_create_user(session, partner_id)
        try:
            await msg.bot.send_message(partner_user.telegram_id, "🔚 Собеседник завершил чат.")
        except:
            pass
        await msg.answer("🔚 Чат завершён.", reply_markup=catalog_kb())
        await msg.answer("Используйте кнопки ниже для быстрого доступа:", reply_markup=commands_keyboard())

# ---------- Пересылка сообщений ----------
@router.message(F.text & ~F.text.startswith("/"), F.text.notin_(["🏠 Главная", "📊 Статистика", "ℹ️ Помощь", "❌ Завершить"]))
async def handle_chat_message(msg: types.Message):
    async with async_session() as session:
        chat = await get_active_chat_by_user(session, msg.from_user.id)
        if not chat:
            return
        partner_id = chat.user2_id if msg.from_user.id == chat.user1_id else chat.user1_id
        partner_user = await get_or_create_user(session, partner_id)
        try:
            await msg.bot.send_message(partner_user.telegram_id, f"💬 Собеседник: {msg.text}")
        except Exception:
            await msg.answer("Сообщение не доставлено. Чат завершён.")
            await end_active_chat(session, chat.id)
            await msg.answer("Чат завершён.", reply_markup=catalog_kb())
            await msg.answer("Используйте кнопки ниже для быстрого доступа:", reply_markup=commands_keyboard())

# ---------- Настройка allow_random_chat ----------
@router.callback_query(F.data == "toggle_random_chat")
async def toggle_random_chat(call: types.CallbackQuery):
    async with async_session() as session:
        user = await get_or_create_user(session, call.from_user.id, call.from_user.username)
        new_value = not user.allow_random_chat
        await set_allow_random_chat(session, user.id, new_value)
        if new_value:
            status_text = "включён ✅\nТеперь другие пользователи могут найти вас и предложить чат."
        else:
            status_text = "выключен ❌\nВы в безопасности — вас никто не побеспокоит."
        await call.message.edit_text(
            f"🔔 Приём запросов на случайный чат: {status_text}",
            reply_markup=catalog_kb()
        )
        await call.answer()
