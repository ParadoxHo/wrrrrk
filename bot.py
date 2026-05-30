import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, 
    ReplyKeyboardMarkup, KeyboardButton
)
from openai import AsyncOpenAI

# Настройка
logging.basicConfig(level=logging.INFO)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

ai_client = AsyncOpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

TOTAL_QUESTIONS = 10

class InterviewWorkflow(StatesGroup):
    waiting_for_language = State()
    waiting_for_profession = State()
    waiting_for_persona = State()
    waiting_for_difficulty = State()
    interview_in_progress = State()

# --- КЛАВИАТУРЫ ---
def get_main_menu_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🚀 Начать собеседование")],
        [KeyboardButton(text="ℹ️ Помощь")]
    ], resize_keyboard=True)

def get_language_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru")],
        [InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en")]
    ])

def get_persona_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟢 Добрый HR", callback_data="pers_hr")],
        [InlineKeyboardButton(text="🟡 Душный Тимлид", callback_data="pers_tech")],
        [InlineKeyboardButton(text="🔴 Стрессовый Босс", callback_data="pers_boss")]
    ])

def get_difficulty_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👶 Junior", callback_data="jun")],
        [InlineKeyboardButton(text="👨‍💻 Middle", callback_data="mid")],
        [InlineKeyboardButton(text="🧙‍♂️ Senior/Expert", callback_data="sen")]
    ])

# --- ЛОГИКА ---
@dp.message(Command("start"))
@dp.message(F.text == "ℹ️ Помощь")
async def cmd_start(message: Message):
    await message.answer("Я профессиональный AI-интервьюер. Нажми кнопку ниже, чтобы начать.", reply_markup=get_main_menu_keyboard())

@dp.message(F.text == "🚀 Начать собеседование")
async def ask_language(message: Message, state: FSMContext):
    await message.answer("🌍 Выберите язык:", reply_markup=get_language_keyboard())
    await state.set_state(InterviewWorkflow.waiting_for_language)

@dp.callback_query(InterviewWorkflow.waiting_for_language, F.data.startswith("lang_"))
async def ask_profession(callback: CallbackQuery, state: FSMContext):
    await state.update_data(language="English" if callback.data == "lang_en" else "Русский")
    await callback.message.edit_text("💼 На какую должность вы претендуете?")
    await state.set_state(InterviewWorkflow.waiting_for_profession)
    await callback.answer()

@dp.message(InterviewWorkflow.waiting_for_profession)
async def ask_persona(message: Message, state: FSMContext):
    await state.update_data(profession=message.text)
    await message.answer("🎭 Выберите характер интервьюера:", reply_markup=get_persona_keyboard())
    await state.set_state(InterviewWorkflow.waiting_for_persona)

@dp.callback_query(InterviewWorkflow.waiting_for_persona, F.data.startswith("pers_"))
async def ask_difficulty(callback: CallbackQuery, state: FSMContext):
    pers_map = {
        "pers_hr": "Добрый и поддерживающий HR-специалист.",
        "pers_tech": "Строгий, требовательный и дотошный технический тимлид.",
        "pers_boss": "Стрессовый директор, который перебивает, давит и проверяет на прочность."
    }
    await state.update_data(persona=pers_map[callback.data])
    await callback.message.edit_text("📈 Выберите ваш уровень:", reply_markup=get_difficulty_keyboard())
    await state.set_state(InterviewWorkflow.waiting_for_difficulty)
    await callback.answer()

@dp.callback_query(InterviewWorkflow.waiting_for_difficulty, F.data.isalpha())
async def start_simulation(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    
    # ВСТРОЕННЫЙ ПОЛНЫЙ ПРОМПТ
    system_prompt = f"""
    Ты — опытный HR-интервьюер и специалист по оценке персонала. 
    Твоя задача — проводить профессиональное собеседование.
    Твоя роль: {data['persona']}. 
    Профессия: {data['profession']}.
    Уровень: {callback.data}.
    Язык: {data['language']}.
    
    АЛГОРИТМ:
    1. Самостоятельно определи ключевые компетенции, навыки и рабочие задачи для этой роли.
    2. Построй интервью по 6 этапам: Знакомство, Проверка опыта, Проф. оценка, Рабочие кейсы, Поведенческое (STAR), Достоверность.
    3. Задавай вопросы ПО ОДНОМУ. Не выводи список вопросов заранее.
    4. Адаптируй сложность динамически. Если ответ поверхностный — требуй конкретики и примеров.
    5. Не показывай кандидату внутреннюю логику оценки.
    6. Веди себя максимально реалистично, как эксперт, от которого зависит решение о найме.
    
    НАЧАЛО: Поздоровайся и задай первый вопрос (Знакомство).
    """
    
    history = [{"role": "system", "content": system_prompt}]
    response = await ai_client.chat.completions.create(model="deepseek-chat", messages=history)
    ai_reply = response.choices[0].message.content
    history.append({"role": "assistant", "content": ai_reply})
    
    await state.update_data(history=history, current_q=1)
    await state.set_state(InterviewWorkflow.interview_in_progress)
    await callback.message.edit_text(f"❓ Вопрос 1 из {TOTAL_QUESTIONS}:\n{ai_reply}")
    await callback.answer()

@dp.message(InterviewWorkflow.interview_in_progress, F.text)
async def handle_answer(message: Message, state: FSMContext):
    data = await state.get_data()
    history = data['history']
    current_q = data['current_q']
    
    history.append({"role": "user", "content": message.text})
    
    if current_q < TOTAL_QUESTIONS:
        history.append({"role": "system", "content": "Проанализируй ответ и задай следующий уточняющий вопрос или вопрос по этапу интервью."})
        response = await ai_client.chat.completions.create(model="deepseek-chat", messages=history)
        ai_reply = response.choices[0].message.content
        history.append({"role": "assistant", "content": ai_reply})
        
        await state.update_data(history=history, current_q=current_q + 1)
        await message.answer(f"❓ Вопрос {current_q + 1} из {TOTAL_QUESTIONS}:\n{ai_reply}")
    else:
        # ФИНАЛЬНЫЙ ОТЧЕТ
        history.append({"role": "system", "content": "Подготовь подробный отчет: Общая оценка (1-10), Сильные стороны, Зоны развития, Риски, Соответствие должности (%), Уровень, Вероятность успеха (%), Итоговая рекомендация."})
        response = await ai_client.chat.completions.create(model="deepseek-chat", messages=history)
        await message.answer(response.choices[0].message.content, parse_mode="HTML")
        await message.answer("Интервью окончено.", reply_markup=get_main_menu_keyboard())
        await state.clear()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
