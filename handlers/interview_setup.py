from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.exceptions import TelegramBadRequest
from keyboards.inline import *
from services.vacancy_parser import parse_hh_vacancy

router = Router()

class SetupStates(StatesGroup):
    waiting_for_language = State()
    waiting_for_profession = State()
    waiting_for_persona = State()
    waiting_for_difficulty = State()
    waiting_for_question_count = State()
    waiting_for_vacancy_choice = State()
    waiting_for_vacancy_url = State()
    waiting_for_resume = State()

async def safe_edit(msg: types.Message, text: str, reply_markup=None):
    try:
        await msg.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest:
        pass

async def start_interview_setup(message: types.Message, state: FSMContext):
    """Запуск цепочки настройки собеседования (вызывается из social_sim)"""
    await state.clear()
    await message.edit_text("🌍 Выберите язык:", reply_markup=language_kb())
    await state.set_state(SetupStates.waiting_for_language)

@router.callback_query(SetupStates.waiting_for_language, F.data.startswith("lang_"))
async def lang_chosen(call: types.CallbackQuery, state: FSMContext):
    lang = "English" if call.data == "lang_en" else "Русский"
    await state.update_data(language=lang)
    await safe_edit(call.message, "💼 На какую должность вы претендуете?")
    await state.set_state(SetupStates.waiting_for_profession)
    await call.answer()

@router.message(SetupStates.waiting_for_profession)
async def profession_entered(msg: types.Message, state: FSMContext):
    if len(msg.text.strip()) < 2:
        await msg.answer("Введите реальную должность.")
        return
    await state.update_data(profession=msg.text.strip())
    await msg.answer("🎭 Выберите характер интервьюера:", reply_markup=persona_kb())
    await state.set_state(SetupStates.waiting_for_persona)

@router.callback_query(SetupStates.waiting_for_persona, F.data.startswith("pers_"))
async def persona_chosen(call: types.CallbackQuery, state: FSMContext):
    pers_map = {
        "pers_hr": "Добрый HR",
        "pers_tech": "Душный Тимлид",
        "pers_boss": "Стрессовый Босс"
    }
    await state.update_data(persona=pers_map[call.data])
    await safe_edit(call.message, "📈 Выберите ваш уровень:", reply_markup=difficulty_kb())
    await state.set_state(SetupStates.waiting_for_difficulty)
    await call.answer()

@router.callback_query(SetupStates.waiting_for_difficulty, F.data.in_({"jun","mid","sen"}))
async def difficulty_chosen(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(level=call.data)
    await safe_edit(call.message, "🔢 Сколько вопросов?", reply_markup=question_count_kb())
    await state.set_state(SetupStates.waiting_for_question_count)
    await call.answer()

@router.callback_query(SetupStates.waiting_for_question_count, F.data.startswith("q_"))
async def qty_chosen(call: types.CallbackQuery, state: FSMContext):
    total = int(call.data.split("_")[1])
    await state.update_data(total_questions=total)
    await safe_edit(call.message, "📎 Хотите привязать вакансию?", reply_markup=vacancy_kb())
    await state.set_state(SetupStates.waiting_for_vacancy_choice)
    await call.answer()

@router.callback_query(SetupStates.waiting_for_vacancy_choice, F.data == "add_vacancy")
async def ask_vacancy_url(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text("🔗 Вставьте ссылку на вакансию (hh.ru):")
    await state.set_state(SetupStates.waiting_for_vacancy_url)
    await call.answer()

@router.message(SetupStates.waiting_for_vacancy_url)
async def receive_vacancy_url(msg: types.Message, state: FSMContext):
    try:
        vac = await parse_hh_vacancy(msg.text)
        await state.update_data(vacancy_text=f"{vac['title']}\n{vac['description']}")
        await msg.answer(f"✅ Вакансия «{vac['title']}» загружена.")
    except Exception:
        await msg.answer("⚠️ Не удалось загрузить вакансию. Продолжим без неё.")
    await msg.answer("📄 Отправьте текст резюме или нажмите Пропустить:", reply_markup=resume_skip_kb())
    await state.set_state(SetupStates.waiting_for_resume)

@router.callback_query(SetupStates.waiting_for_vacancy_choice, F.data == "skip_vacancy")
async def skip_vacancy(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(vacancy_text="")
    await call.message.edit_text("📄 Отправьте текст резюме или нажмите Пропустить:", reply_markup=resume_skip_kb())
    await state.set_state(SetupStates.waiting_for_resume)
    await call.answer()

@router.message(SetupStates.waiting_for_resume)
async def resume_received(msg: types.Message, state: FSMContext):
    await state.update_data(resume_text=msg.text)
    await msg.answer("✅ Резюме принято. Начинаем собеседование...")
    from handlers.interview import start_interview
    await start_interview(msg, state)

@router.callback_query(SetupStates.waiting_for_resume, F.data == "skip_resume")
async def skip_resume(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(resume_text="")
    await call.message.edit_text("Начинаем собеседование...")
    from handlers.interview import start_interview
    await start_interview(call.message, state)
    await call.answer()
