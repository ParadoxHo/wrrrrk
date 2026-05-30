from aiogram import Router, F, types
from aiogram.filters import Command
from keyboards.inline import catalog_kb

router = Router()

@router.message(Command("start"))
async def show_catalog(msg: types.Message):
    await msg.answer("📋 Выберите сценарий:", reply_markup=catalog_kb())

@router.message(F.text == "ℹ️ Помощь")
async def help_handler(msg: types.Message):
    await show_catalog(msg)
