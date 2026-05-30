from aiogram import Router, types
from aiogram.filters import Command
from database import async_session
from database.crud import get_or_create_user

router = Router()

@router.message(Command("stats"))
async def stats(msg: types.Message):
    async with async_session() as session:
        user = await get_or_create_user(session, msg.from_user.id, msg.from_user.username)
        if not user or not user.stats:
            await msg.answer("Нет данных. Пройдите хотя бы одно собеседование.")
            return
        s = user.stats
        text = (
            f"📊 <b>Ваш профиль</b>\n"
            f"• Собеседований: {s.total_interviews}\n"
            f"• Средний балл: {s.average_score:.1f}/10\n"
            f"• Сильные стороны: {', '.join(s.strengths) if s.strengths else 'пока не определены'}\n"
            f"• Зоны роста: {', '.join(s.weaknesses) if s.weaknesses else 'пока не определены'}"
        )
        if s.recommendations:
            text += f"\n\n📌 {s.recommendations}"
        await msg.answer(text, parse_mode="HTML")
