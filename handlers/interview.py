import logging
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from keyboards.inline import interview_kb
from keyboards.reply import main_menu
from services.deepseek import ai_request
from database.crud import get_or_create_user, save_interview, update_user_stats
from database import async_session

router = Router()
logger = logging.getLogger(__name__)

class InterviewStates(StatesGroup):
    interview_in_progress = State()

async def start_interview(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get('language', 'Русский')
    persona = data.get('persona', 'Добрый HR')
    profession = data.get('profession', 'специалист')
    level = data.get('level', 'middle')
    total = data.get('total_questions', 10)
    resume = data.get('resume_text', '')
    vacancy = data.get('vacancy_text', '')

    extra = ""
    if vacancy:
        extra += f"\nОПИСАНИЕ ВАКАНСИИ:\n{vacancy}\n"
    if resume:
        extra += f"\nРЕЗЮМЕ КАНДИДАТА:\n{resume}\n"

    system = f"""Ты — опытный HR-интервьюер ({persona}). Проводишь собеседование на должность {profession} уровня {level}. Язык: {lang}.
{extra}
АЛГОРИТМ:
- Самостоятельно определи ключевые компетенции.
- Пройди этапы: Знакомство, Опыт, Проф. оценка, Кейсы, Поведенческое (STAR), Достоверность.
- Задавай вопросы ПО ОДНОМУ, адаптируй сложность.
- Не раскрывай логику оценки.
- Не используй разметку.

Начни с приветствия и первого вопроса (Знакомство)."""

    history = [{"role": "system", "content": system}]
    try:
        first = await ai_request(history)
    except Exception as e:
        await message.answer("Ошибка запуска. Попробуйте позже.", reply_markup=main_menu())
        await state.clear()
        return

    history.append({"role": "assistant", "content": first})
    await state.update_data(history=history, current_q=1, total_questions=total, hints_used=0)
    await state.set_state(InterviewStates.interview_in_progress)
    await message.answer(f"❓ Вопрос 1 из {total}:\n{first}", reply_markup=interview_kb())

@router.callback_query(InterviewStates.interview_in_progress, F.data == "hint")
async def hint(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    history = data['history']
    history.append({"role": "system", "content": "Дай наводящую подсказку к текущему вопросу, не отвечай полностью. Без разметки."})
    try:
        hint_text = await ai_request(history)
    except:
        await call.answer("Ошибка подсказки", show_alert=True)
        return
    history.pop()
    history.append({"role": "assistant", "content": hint_text})
    await state.update_data(history=history, hints_used=data.get('hints_used',0)+1)
    await call.message.answer(f"💡 Подсказка: {hint_text}")
    await call.answer()

@router.callback_query(InterviewStates.interview_in_progress, F.data == "stop_interview")
async def early_stop(call: types.CallbackQuery, state: FSMContext):
    await finish_interview(call.message, state, early=True)
    await call.answer()

@router.message(InterviewStates.interview_in_progress, F.text & ~F.text.startswith("/"))
async def handle_answer(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    history = data['history']
    current_q = data['current_q']
    total = data['total_questions']

    history.append({"role": "user", "content": msg.text})

    if current_q < total:
        history.append({"role": "system", "content": "Проанализируй ответ. Задай следующий вопрос по следующему этапу. Без разметки."})
        try:
            next_q = await ai_request(history)
        except:
            await msg.answer("⚠️ Ошибка генерации вопроса. Попробуйте снова или завершите.", reply_markup=interview_kb())
            return
        history.append({"role": "assistant", "content": next_q})
        await state.update_data(history=history, current_q=current_q+1)
        await msg.answer(f"❓ Вопрос {current_q+1} из {total}:\n{next_q}", reply_markup=interview_kb())
    else:
        await finish_interview(msg, state)

async def finish_interview(message: types.Message, state: FSMContext, early=False):
    data = await state.get_data()
    history = data['history']
    if not history:
        return
    hints = data.get('hints_used', 0)
    history.append({"role": "system", "content": f"Подготовь итоговый отчёт: общая оценка (1-10), сильные стороны, зоны роста, риски, соответствие должности (%), вероятность успеха (%), рекомендации. Учти, что кандидат использовал {hints} подсказок. Без разметки."})
    try:
        report = await ai_request(history)
    except:
        report = "Не удалось сформировать отчёт."
    await message.answer(report)
    await message.answer("🏁 Интервью завершено.", reply_markup=main_menu())

    async with async_session() as session:
        user = await get_or_create_user(session, message.from_user.id, message.from_user.username)
        interview_data = {
            "profession": data.get("profession"),
            "level": data.get("level"),
            "persona": data.get("persona"),
            "language": data.get("language"),
            "total_questions": data.get("total_questions"),
            "resume_text": data.get("resume_text"),
            "vacancy_text": data.get("vacancy_text"),
            "history": history,
            "report": report,
            "metrics": {"overall_score": 0},
            "hints_used": hints,
            "early_stop": 1 if early else 0
        }
        await save_interview(session, user.id, interview_data)
        await update_user_stats(session, user.id)
    await state.clear()
