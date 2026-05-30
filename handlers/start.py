from aiogram import Router, F, types
from aiogram.filters import Command
from keyboards.inline import mode_selection_kb

router = Router()

@router.message(Command("start"))
async def choose_mode(msg: types.Message):
    await msg.answer(
        "👋 Добро пожаловать! Выберите режим работы:",
        reply_markup=mode_selection_kb()
    )

# Кнопку "ℹ️ Помощь" оставим для быстрого доступа к выбору режима
@router.message(F.text == "ℹ️ Помощь")
async def help_handler(msg: types.Message):
    await choose_mode(msg)
