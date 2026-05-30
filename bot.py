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
from aiogram.exceptions import TelegramBadRequest
from openai import AsyncOpenAI

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Переменные окружения
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

# Клиент DeepSeek
ai_client = AsyncOpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# --- Клавиатуры ---
def get_main_menu_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🚀 Начать собеседование")],
            [KeyboardButton(text="ℹ️ Помощь")]
        ],
        resize_keyboard=True
    )

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

def get_question_count_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="5", callback_data="q_5"),
            InlineKeyboardButton(text="10", callback_data="q_10")
        ],
        [
            InlineKeyboardButton(text="15", callback_data="q_15"),
            InlineKeyboardButton(text="20", callback_data="q_20")
        ]
    ])

def get_resume_skip_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭️ Пропустить", callback_data="skip_resume")]
    ])

def get_interview_keyboard():
    """Клавиатура во время интервью: Подсказка и Завершить"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💡 Подсказка", callback_data="hint"),
            InlineKeyboardButton(text="🛑 Завершить", callback_data="stop_interview")
        ]
    ])

# --- Состояния ---
class InterviewWorkflow(StatesGroup):
    waiting_for_language = State()
    waiting_for_profession = State()
    waiting_for_persona = State()
    waiting_for_difficulty = State()
    waiting_for_question_count = State()
    waiting_for_resume = State()
    interview_in_progress = State()

# --- Вспомогательные функции ---
async def safe_edit_text(message: Message, text: str, reply_markup=None):
    """Безопасное редактирование сообщения"""
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e).lower():
            logger.warning(f"Ошибка при редактировании: {e}")

async def ai_request_with_retry(messages, max_retries=2):
    """Вызов DeepSeek с повторными попытками"""
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            response = await ai_client.chat.completions.create(
                model="deepseek-chat",
                messages=messages
            )
            return response.choices[0].message.content
        except Exception as e:
            last_exc = e
            logger.error(f"Попытка {attempt+1} к DeepSeek: {e}")
            await asyncio.sleep(2 ** attempt)
    raise last_exc

# --- Команды ---
@dp.message(Command("start"))
@dp.message(F.text == "ℹ️ Помощь")
async def cmd_start(message: Message):
    await message.answer(
        "🤖 Я профессиональный AI-интервьюер. Нажмите кнопку ниже, чтобы начать.",
        reply_markup=get_main_menu_keyboard()
    )

@dp.message(Command("cancel"))
@dp.message(F.text.casefold() == "/cancel")
async def cmd_cancel(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Вы не в процессе собеседования.", reply_markup=get_main_menu_keyboard())
        return
    await state.clear()
    await message.answer("Собеседование прервано. Вы в главном меню.", reply_markup=get_main_menu_keyboard())

# --- Этапы настройки ---
@dp.message(F.text == "🚀 Начать собеседование")
async def start_interview(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🌍 Выберите язык:", reply_markup=get_language_keyboard())
    await state.set_state(InterviewWorkflow.waiting_for_language)

@dp.callback_query(InterviewWorkflow.waiting_for_language, F.data.startswith("lang_"))
async def choose_language(callback: CallbackQuery, state: FSMContext):
    await state.update_data(language="English" if callback.data == "lang_en" else "Русский")
    await safe_edit_text(callback.message, "💼 На какую должность вы претендуете?")
    await state.set_state(InterviewWorkflow.waiting_for_profession)
    await callback.answer()

@dp.message(InterviewWorkflow.waiting_for_profession)
async def choose_profession(message: Message, state: FSMContext):
    profession = message.text.strip()
    if len(profession) < 2:
        await message.answer("Пожалуйста, введите реальное название должности (минимум 2 символа).")
        return
    await state.update_data(profession=profession)
    await message.answer("🎭 Выберите характер интервьюера:", reply_markup=get_persona_keyboard())
    await state.set_state(InterviewWorkflow.waiting_for_persona)

@dp.callback_query(InterviewWorkflow.waiting_for_persona, F.data.startswith("pers_"))
async def choose_persona(callback: CallbackQuery, state: FSMContext):
    pers_map = {
        "pers_hr": "Добрый и поддерживающий HR-специалист.",
        "pers_tech": "Строгий, требовательный и дотошный технический тимлид.",
        "pers_boss": "Стрессовый директор, который перебивает, давит и проверяет на прочность."
    }
    await state.update_data(persona=pers_map[callback.data])
    await safe_edit_text(callback.message, "📈 Выберите ваш уровень:", reply_markup=get_difficulty_keyboard())
    await state.set_state(InterviewWorkflow.waiting_for_difficulty)
    await callback.answer()

@dp.callback_query(InterviewWorkflow.waiting_for_difficulty, F.data.in_({"jun", "mid", "sen"}))
async def choose_difficulty(callback: CallbackQuery, state: FSMContext):
    await state.update_data(level=callback.data)
    await safe_edit_text(callback.message, "🔢 Сколько вопросов задать?", reply_markup=get_question_count_keyboard())
    await state.set_state(InterviewWorkflow.waiting_for_question_count)
    await callback.answer()

@dp.callback_query(InterviewWorkflow.waiting_for_question_count, F.data.startswith("q_"))
async def choose_question_count(callback: CallbackQuery, state: FSMContext):
    total = int(callback.data.split("_")[1])
    await state.update_data(total_questions=total)
    await safe_edit_text(
        callback.message,
        "📄 Хотите загрузить текст вашего резюме? Это поможет задать более точные вопросы.\n"
        "Отправьте текст или нажмите «Пропустить».",
        reply_markup=get_resume_skip_keyboard()
    )
    await state.set_state(InterviewWorkflow.waiting_for_resume)
    await callback.answer()

@dp.callback_query(InterviewWorkflow.waiting_for_resume, F.data == "skip_resume")
async def skip_resume(callback: CallbackQuery, state: FSMContext):
    await state.update_data(resume_text="")
    await start_interview_session(callback.message, state)
    await callback.answer()

@dp.message(InterviewWorkflow.waiting_for_resume, F.text)
async def receive_resume(message: Message, state: FSMContext):
    await state.update_data(resume_text=message.text)
    await message.answer("✅ Резюме принято. Начинаем собеседование...")
    await start_interview_session(message, state)

async def start_interview_session(message: Message, state: FSMContext):
    """Генерация первого вопроса и переход в режим интервью"""
    data = await state.get_data()
    language = data['language']
    persona = data['persona']
    profession = data['profession']
    level = data['level']
    total = data['total_questions']
    resume = data.get('resume_text', '')

    # Системный промпт с резюме (если есть)
    resume_context = f"Вот резюме кандидата (текст):\n{resume}\nИспользуй его для адаптации вопросов." if resume else ""

    system_prompt = f"""
Ты — опытный HR-интервьюер и специалист по оценке персонала. 
Твоя задача — проводить профессиональное собеседование.
Твоя роль: {persona}. 
Профессия: {profession}.
Уровень: {level}.
Язык: {language}.
{resume_context}

АЛГОРИТМ:
1. Самостоятельно определи ключевые компетенции, навыки и рабочие задачи для этой роли.
2. Построй интервью по 6 этапам: Знакомство, Проверка опыта, Проф. оценка, Рабочие кейсы, Поведенческое (STAR), Достоверность.
3. Задавай вопросы ПО ОДНОМУ. Не выводи список вопросов заранее.
4. Адаптируй сложность динамически. Если ответ поверхностный — требуй конкретики и примеров.
5. Не показывай кандидату внутреннюю логику оценки.
6. Веди себя максимально реалистично, как эксперт, от которого зависит решение о найме.
7. **Не используй HTML, Markdown или другую разметку. Отвечай чистым текстом.**

НАЧАЛО: Поздоровайся и задай первый вопрос (Знакомство).
"""

    history = [{"role": "system", "content": system_prompt}]
    await bot.send_chat_action(message.chat.id, "typing")
    try:
        first_question = await ai_request_with_retry(history)
    except Exception as e:
        logger.error(f"Ошибка при старте интервью: {e}")
        await message.answer("😔 Не удалось запустить собеседование. Попробуйте позже.", reply_markup=get_main_menu_keyboard())
        await state.clear()
        return

    history.append({"role": "assistant", "content": first_question})
    await state.update_data(
        history=history,
        current_q=1,
        total_questions=total,
        hints_used=0
    )
    await state.set_state(InterviewWorkflow.interview_in_progress)

    await message.answer(
        f"❓ Вопрос 1 из {total}:\n{first_question}",
        reply_markup=get_interview_keyboard()
    )

# --- Режим интервью ---
@dp.callback_query(InterviewWorkflow.interview_in_progress, F.data == "hint")
async def give_hint(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    history = data['history']
    # Добавляем запрос на подсказку
    history.append({
        "role": "system",
        "content": "Дай кандидату небольшую подсказку или наводящий вопрос по текущей теме, не раскрывая полный ответ. Не используй разметку."
    })
    await bot.send_chat_action(callback.message.chat.id, "typing")
    try:
        hint = await ai_request_with_retry(history)
    except Exception as e:
        logger.error(f"Ошибка при генерации подсказки: {e}")
        await callback.answer("Ошибка, попробуйте позже.", show_alert=True)
        return

    # Удаляем временный system message, заменяем ответ модели
    history.pop()
    history.append({"role": "assistant", "content": hint})

    # Увеличиваем счётчик использованных подсказок
    hints_used = data.get('hints_used', 0) + 1
    await state.update_data(history=history, hints_used=hints_used)

    await callback.message.answer(f"💡 Подсказка: {hint}")
    await callback.answer()

@dp.callback_query(InterviewWorkflow.interview_in_progress, F.data == "stop_interview")
async def stop_interview(callback: CallbackQuery, state: FSMContext):
    await finish_interview(callback.message, state, early_stop=True)
    await callback.answer()

@dp.message(InterviewWorkflow.interview_in_progress, F.text & ~F.text.startswith("/"))
async def handle_answer(message: Message, state: FSMContext):
    data = await state.get_data()
    history = data['history']
    current_q = data['current_q']
    total = data['total_questions']

    # Ответ пользователя
    history.append({"role": "user", "content": message.text})

    if current_q < total:
        history.append({
            "role": "system",
            "content": "Проанализируй ответ и задай следующий уточняющий вопрос по этапу интервью. Не используй разметку."
        })
        await bot.send_chat_action(message.chat.id, "typing")
        try:
            next_question = await ai_request_with_retry(history)
        except Exception as e:
            logger.error(f"Ошибка при генерации вопроса: {e}")
            await message.answer("⚠️ Произошла ошибка. Повторите ответ или нажмите «Завершить».", reply_markup=get_interview_keyboard())
            return

        history.append({"role": "assistant", "content": next_question})
        await state.update_data(history=history, current_q=current_q + 1)
        await message.answer(
            f"❓ Вопрос {current_q + 1} из {total}:\n{next_question}",
            reply_markup=get_interview_keyboard()
        )
    else:
        # Последний вопрос – сразу финальный отчёт
        await finish_interview(message, state)

async def finish_interview(message: Message, state: FSMContext, early_stop: bool = False):
    data = await state.get_data()
    history = data.get('history', [])
    if not history:
        await message.answer("Нет данных для отчёта.")
        return

    hints_used = data.get('hints_used', 0)
    total = data.get('total_questions', '?')

    stop_note = " (досрочное завершение)" if early_stop else ""
    system_msg = (
        "Подготовь подробный итоговый отчёт: Общая оценка (1-10), Сильные стороны, "
        "Зоны развития, Риски, Соответствие должности (%), Вероятность успеха (%), "
        f"Итоговая рекомендация. Учти, что кандидат использовал {hints_used} подсказок. "
        "Не используй разметку."
    )
    history.append({"role": "system", "content": system_msg})

    await bot.send_chat_action(message.chat.id, "typing")
    try:
        report = await ai_request_with_retry(history)
    except Exception as e:
        logger.error(f"Ошибка при генерации отчёта: {e}")
        report = "Не удалось сформировать отчёт из-за технической ошибки."

    await message.answer(report)
    await message.answer(f"🏁 Интервью завершено{stop_note}.", reply_markup=get_main_menu_keyboard())
    await state.clear()

# --- Запуск ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
