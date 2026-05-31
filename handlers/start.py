from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from keyboards.inline import catalog_kb
from keyboards.reply import commands_keyboard

router = Router()

@router.message(Command("start"))
@router.message(F.text == "🏠 Главная")
async def show_catalog(msg: types.Message, state: FSMContext):
    await state.clear()
    await msg.answer("📋 Выберите сценарий:", reply_markup=catalog_kb())
    await msg.answer("Используйте кнопки ниже для быстрого доступа:", reply_markup=commands_keyboard())

@router.message(Command("help"))
@router.message(F.text == "ℹ️ Помощь")
async def help_handler(msg: types.Message, state: FSMContext):
    await state.clear()
    await msg.answer(
        "🤖 Я AI-тренажёр общения.\n"
        "• 🏠 Главная — вернуться в каталог\n"
        "• ❌ Завершить — выйти из сценария\n"
        "• 📊 Статистика — ваш прогресс\n"
        "• ℹ️ Помощь — это сообщение"
    )
    await show_catalog(msg, state)
