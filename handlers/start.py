from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from keyboards.inline import catalog_kb
from keyboards.reply import commands_keyboard

router = Router()

@router.message(Command("start"))
async def show_catalog(msg: types.Message, state: FSMContext):
    await state.clear()
    await msg.answer("📋 Выберите сценарий:", reply_markup=catalog_kb())
    await msg.answer("⌨️ Используйте кнопки для управления:", reply_markup=commands_keyboard())

@router.message(Command("help"))
@router.message(F.text == "/help")
async def help_handler(msg: types.Message, state: FSMContext):
    await state.clear()
    await msg.answer("🤖 Я AI-тренажёр общения. Выберите сценарий из каталога ниже или используйте кнопки.")
    await show_catalog(msg, state)
