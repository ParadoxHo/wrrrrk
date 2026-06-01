from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from database import async_session
from database.crud import (
    add_to_chat_queue, remove_from_chat_queue, get_random_user_from_queue,
    create_active_chat, get_active_chat_by_user, end_active_chat, get_or_create_user
)
from keyboards.inline import catalog_kb, cancel_search_kb
from keyboards.reply import commands_keyboard

router = Router()

# ---------- Вход в случайный чат ----------
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

        partner = await get_random_user_from_queue(session, exclude_user_id=user_id)
        if partner:
            await remove_from_chat_queue(session, user_id)
            await remove_from_chat_queue(session, partner.user_id)
            chat = await create_active_chat(session, user_id, partner.user_id)

            partner_user = await get_or_create_user(session, partner.user_id)
            user_self = await get_or_create_user(session, user_id)

            try:
                await call.bot.send_message(
                    partner_user.telegram_id,
                    "🎲 Собеседник найден! Можете начинать общение.\n"
                    "Команда /stop или кнопка «❌ Завершить» — выйти из чата.",
                    reply_markup=commands_keyboard()
                )
            except Exception:
                await end_active_chat(session, chat.id)
                await add_to_chat_queue(session, user_id)
                await call.answer("Не удалось связаться с собеседником. Вы снова в очереди.", show_alert=True)
                return

            await call.message.edit_text(
                "🎲 Собеседник найден! Можете начинать общение.\n"
                "Команда /stop или кнопка «❌ Завершить» — выйти из чата."
            )
            await call.message.answer("Используйте кнопки ниже для быстрого доступа:", reply_markup=commands_keyboard())
        else:
            await add_to_chat_queue(session, user_id)
            await call.message.edit_text(
                "🔍 Ищем собеседника... Ожидайте.",
                reply_markup=cancel_search_kb()
            )

# ---------- Отмена поиска ----------
@router.callback_query(F.data == "cancel_search")
async def cancel_search(call: types.CallbackQuery, state: FSMContext):
    async with async_session() as session:
        await remove_from_chat_queue(session, call.from_user.id)
    await call.message.edit_text("Поиск отменён.", reply_markup=catalog_kb())
    await call.answer()

# ---------- Завершение чата (проверяется ПЕРЕД пересылкой сообщений) ----------
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

# ---------- Пересылка сообщений (только если не команда и не кнопка выхода) ----------
@router.message(F.text & ~F.text.startswith("/"), F.text != "❌ Завершить")
async def handle_chat_message(msg: types.Message):
    async with async_session() as session:
        chat = await get_active_chat_by_user(session, msg.from_user.id)
        if not chat:
            return

        partner_id = chat.user2_id if msg.from_user.id == chat.user1_id else chat.user1_id
        partner_user = await get_or_create_user(session, partner_id)

        try:
            await msg.bot.send_message(
                partner_user.telegram_id,
                f"💬 Собеседник: {msg.text}"
            )
        except Exception:
            await msg.answer("Сообщение не доставлено. Чат завершён.")
            await end_active_chat(session, chat.id)
            await msg.answer("Чат завершён.", reply_markup=catalog_kb())
            await msg.answer("Используйте кнопки ниже для быстрого доступа:", reply_markup=commands_keyboard())
