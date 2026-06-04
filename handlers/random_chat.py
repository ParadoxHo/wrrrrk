import asyncio
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
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

class RandomChatStates(StatesGroup):
    in_chat = State()          # пользователь находится в активном чате

async def _create_chat_and_notify(call, partner_telegram_id, partner_db_id: int, state: FSMContext):
    async with async_session() as session:
        initiator = await get_or_create_user(session, call.from_user.id)
        chat = await create_active_chat(session, initiator.id, partner_db_id)
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
        # Устанавливаем состояние in_chat обоим (инициатору и партнёру)
        await state.set_state(RandomChatStates.in_chat)
        # Партнёру также нужно установить состояние, но мы не можем управлять его FSM.
        # Вместо этого при входе в чат через принятие запроса тоже будет установлено состояние.
        # Для инициатора состояние уже установлено.
        await call.message.edit_text("🎲 Собеседник найден! Можете начинать общение.")
        await call.message.answer("Используйте кнопки ниже для быстрого доступа:", reply_markup=commands_keyboard())

async def _end_chat_and_notify(bot, user_telegram_id: int, state: FSMContext = None):
    """Завершает активный чат пользователя, уведомляет партнёра и сбрасывает состояние."""
    async with async_session() as session:
        user = await get_or_create_user(session, user_telegram_id)
        chat = await get_active_chat_by_user(session, user.id)
        if not chat:
            return
        partner_id = chat.user2_id if user.id == chat.user1_id else chat.user1_id
        await end_active_chat(session, chat.id)
        from database.models import User
        partner = await session.get(User, partner_id)
        if partner:
            try:
                await bot.send_message(partner.telegram_id, "🔚 Собеседник завершил чат.")
            except:
                pass
    # Сбрасываем состояние
    if state:
        await state.clear()

async def _send_chat_request(call, partner_telegram_id: int, requester_db_id: int):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    accept_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Принять", callback_data=f"accept_chat:{requester_db_id}"),
         InlineKeyboardButton(text="❌ Отклонить", callback_data=f"decline_chat:{requester_db_id}")]
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
    async with async_session() as session:
        user = await get_or_create_user(session, call.from_user.id)
        if await get_active_chat_by_user(session, user.id):
            await call.answer("Вы уже в чате! Завершите его командой /stop.", show_alert=True)
            return

        from sqlalchemy import select
        from database.models import ChatQueue
        q = await session.execute(select(ChatQueue).where(ChatQueue.user_id == user.id))
        if q.scalar_one_or_none():
            await call.answer("Вы уже в очереди. Ожидайте собеседника.", show_alert=True)
            return

        await cleanup_expired_queue(session, bot=call.bot)

        # 1. Ищем активного искателя в очереди
        partner = await get_random_user_from_queue(session, exclude_user_id=user.id)
        if partner:
            await remove_from_chat_queue(session, user.id)
            await remove_from_chat_queue(session, partner.user_id)
            from database.models import User as DBUser
            partner_user = await session.get(DBUser, partner.user_id)
            if partner_user:
                # Устанавливаем состояние обоим (функция установит инициатору)
                await _create_chat_and_notify(call, partner_user.telegram_id, partner.user_id, state)
                # Отправляем партнёру сообщение, что чат начат, и тоже пытаемся установить ему состояние
                # Но мы не можем управлять его FSM напрямую, поэтому состояние партнёра будет установлено при его следующем сообщении
                # (он получит клавиатуру и сможет писать)
            return

        # 2. Ищем пассивного пользователя с allow_random_chat=1
        available_user = await find_available_user(session, exclude_user_id=user.id)
        if available_user:
            await _send_chat_request(call, available_user.telegram_id, user.id)
            return

        # 3. Никого нет – встаём в очередь
        await add_to_chat_queue(session, user.id)
        await call.message.edit_text("🔍 Ищем собеседника... Ожидайте.", reply_markup=cancel_search_kb())

# ---------- Отмена поиска ----------
@router.callback_query(F.data == "cancel_search")
async def cancel_search(call: types.CallbackQuery, state: FSMContext):
    async with async_session() as session:
        user = await get_or_create_user(session, call.from_user.id)
        await remove_from_chat_queue(session, user.id)
    await call.message.edit_text("Поиск отменён.", reply_markup=catalog_kb())
    await call.answer()

# ---------- Обработка запроса ----------
@router.callback_query(F.data.startswith("accept_chat:"))
async def accept_chat_request(call: types.CallbackQuery, state: FSMContext):
    requester_db_id = int(call.data.split(":")[1])
    async with async_session() as session:
        user = await get_or_create_user(session, call.from_user.id)
        if await get_active_chat_by_user(session, user.id) or await get_active_chat_by_user(session, requester_db_id):
            await call.answer("Кто-то уже в чате.", show_alert=True)
            return
        chat = await create_active_chat(session, requester_db_id, user.id)
        from database.models import User as DBUser
        requester = await session.get(DBUser, requester_db_id)
        if requester:
            try:
                await call.bot.send_message(requester.telegram_id, "🎲 Собеседник принял запрос! Начинайте общение.")
            except:
                pass
        await call.message.edit_text("Вы приняли запрос. Сейчас начнётся чат.", reply_markup=None)
        await call.message.answer("Используйте кнопки ниже для быстрого доступа:", reply_markup=commands_keyboard())
        # Устанавливаем состояние in_chat для того, кто принял запрос
        await state.set_state(RandomChatStates.in_chat)
    await call.answer()

@router.callback_query(F.data.startswith("decline_chat:"))
async def decline_chat_request(call: types.CallbackQuery):
    requester_db_id = int(call.data.split(":")[1])
    from database.models import User as DBUser
    async with async_session() as session:
        requester = await session.get(DBUser, requester_db_id)
        if requester:
            try:
                await call.bot.send_message(requester.telegram_id, "📩 Пользователь отклонил запрос. Вы вернулись в меню.")
            except:
                pass
    await call.message.edit_text("Вы отклонили запрос.", reply_markup=None)
    await call.answer()

# ---------- Быстрые кнопки и завершение ----------
@router.message(F.text == "🏠 Главная")
async def main_menu_from_chat(msg: types.Message, state: FSMContext):
    await _end_chat_and_notify(msg.bot, msg.from_user.id, state)
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
async def stop_chat(msg: types.Message, state: FSMContext):
    await _end_chat_and_notify(msg.bot, msg.from_user.id, state)
    await msg.answer("🔚 Чат завершён.", reply_markup=catalog_kb())
    await msg.answer("Используйте кнопки ниже для быстрого доступа:", reply_markup=commands_keyboard())

# ---------- Пересылка сообщений (только в состоянии in_chat) ----------
@router.message(RandomChatStates.in_chat, F.text & ~F.text.startswith("/"))
async def handle_chat_message(msg: types.Message, state: FSMContext):
    async with async_session() as session:
        user = await get_or_create_user(session, msg.from_user.id)
        chat = await get_active_chat_by_user(session, user.id)
        if not chat:
            # Если чата вдруг нет, сбрасываем состояние
            await state.clear()
            return
        partner_db_id = chat.user2_id if user.id == chat.user1_id else chat.user1_id
        from database.models import User as DBUser
        partner = await session.get(DBUser, partner_db_id)
        if not partner:
            await msg.answer("Собеседник больше не доступен.")
            await end_active_chat(session, chat.id)
            await state.clear()
            return
        try:
            await msg.bot.send_message(partner.telegram_id, f"💬 Собеседник: {msg.text}")
        except Exception:
            await msg.answer("Сообщение не доставлено. Чат завершён.")
            await end_active_chat(session, chat.id)
            await state.clear()
            await msg.answer("Чат завершён.", reply_markup=catalog_kb())
            await msg.answer("Используйте кнопки ниже для быстрого доступа:", reply_markup=commands_keyboard())

# ---------- Настройка allow_random_chat ----------
@router.callback_query(F.data == "toggle_random_chat")
async def toggle_random_chat(call: types.CallbackQuery):
    async with async_session() as session:
        user = await get_or_create_user(session, call.from_user.id)
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
