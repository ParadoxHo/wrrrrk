from aiogram import Router, F, types
from aiogram.filters import Command
from keyboards.reply import main_menu

router = Router()

@router.message(Command("start"))
@router.message(lambda msg: msg.text == "ℹ️ Помощь")
async def start(msg: types.Message):
    await msg.answer("🤖 Я AI-интервьюер. Нажмите кнопку, чтобы начать.", reply_markup=main_menu())
