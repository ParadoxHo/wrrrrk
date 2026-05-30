import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import (
    Message, 
    CallbackQuery, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    ReplyKeyboardRemove
)
from openai import AsyncOpenAI

# Настройка логирования
logging.basicConfig(level=logging.INFO)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

if not TELEGRAM_TOKEN or not DEEPSEEK_API_KEY:
    raise ValueError("КРИТИЧЕСКАЯ ОШИБКА: Токены TELEGRAM_TOKEN или DEEPSEEK_API_KEY не найдены!")

# Инициализация клиентов
ai_client = AsyncOpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# Состояния FSM
class InterviewWorkflow(StatesGroup):
    waiting_for_profession = State()
    waiting_for_difficulty = State()
    interview_in_progress = State()

# MAX количество вопросов в одном интервью
TOTAL_QUESTIONS = 5

# ================= КЛАВИАТУРЫ (UI ЭЛЕМЕНТЫ) =================

def get_start_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Начать интервью", callback_data="start_interview")],
        [InlineKeyboardButton(text="❓ Как это работает?", callback_data="help_info")]
    ])

def get_difficulty_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟢 Легкий (Скрининг)", callback_data="diff_easy")],
        [InlineKeyboardButton(text="🟡 Средний (Технический)", callback_data="diff_medium")],
        [InlineKeyboardButton(text="🔴 Хардкор (Стресс-тест)", callback_data="diff_hard")]
    ])

def get_stop_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛑 Прервать собеседование", callback_data="stop_interview")]
    ])

# ================= ХЭНДЛЕРЫ =================

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    # Убираем обычную клавиатуру, если она осталась из старых версий
    await message.answer("Удаление старого интерфейса...", reply_markup=ReplyKeyboardRemove())
    
    await message.answer(
        "👋 <b>Добро пожаловать в AI Interviewer!</b>\n\n"
        "Я твой персональный тренажер на базе искусственного интеллекта. "
        "Помогу тебе подготовиться к собеседованию в любую компанию мира.\n\n"
        "🎯 Готов проверить свои силы?",
        parse_mode="HTML",
        reply_markup=get_start_keyboard()
    )

@dp.callback_query(F.data == "help_info")
async def toggle_help(callback: CallbackQuery):
    await callback.message.edit_text(
        "📋 <b>Как проходит симуляция:</b>\n\n"
        "1. Ты пишешь желаемую должность.\n"
        "2. Выбираешь уровень сложности.\n"
        "3. ИИ задает тебе <b>5 целевых вопросов</b> по очереди.\n"
        "4. На каждый вопрос ты даешь ответ текстом.\n"
        "5. В конце ты получаешь <b>развернутый бизнес-отчет</b> со своими сильными/слабыми сторонами и оценкой в баллах.\n\n"
        "Жми кнопку ниже, чтобы начать!",
        parse_mode="HTML",
        reply_markup=get_start_keyboard()
    )
    await callback.answer()

@dp.callback_query(F.data == "start_interview")
async def ask_profession(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "📝 <b>Шаг 1 из 2:</b>\n\n"
        "Напиши должность, на которую ты хочешь пройти мок-интервью.\n"
        "<i>Пример: Junior Python Developer, Продакт-менеджер, Системный аналитик...</i>",
        parse_mode="HTML"
    )
    await state.set_state(InterviewWorkflow.waiting_for_profession)
    await callback.answer()

@dp.message(InterviewWorkflow.waiting_for_profession, F.text)
async def process_profession(message: Message, state: FSMContext):
    await state.update_data(profession=message.text)
    
    await message.answer(
        f"💼 Отлично! Позиция: <b>{message.text}</b>\n\n"
        f"🎯 <b>Шаг 2 из 2:</b> Выбери уровень сложности интервью:",
        parse_mode="HTML",
        reply_markup=get_difficulty_keyboard()
    )
    await state.set_state(InterviewWorkflow.waiting_for_difficulty)

@dp.callback_query(InterviewWorkflow.waiting_for_difficulty, F.data.startswith("diff_"))
async def start_simulation(callback: CallbackQuery, state: FSMContext):
    diff_map = {
        "diff_easy": "Легкий (Базовые вопросы и софт-скиллы)",
        "diff_medium": "Средний (Глубокие технические вопросы и кейсы)",
        "diff_hard": "Хардкор (Стресс-интервью, каверзные вопросы на прочность)"
    }
    chosen_diff = diff_map[callback.data]
    
    user_data = await state.get_data()
    profession = user_data['profession']
    
    await callback.message.edit_text(
        f"🚀 <b>Симуляция запущена!</b>\n"
        f"💼 Должность: {profession}\n"
        f"📊 Сложность: {chosen_diff}\n\n"
        f"⏳ <i>Интервьюер изучает твое резюме, подожди секунду...</i>",
        parse_mode="HTML"
    )
    
    # Промпт для ИИ с жесткими рамками роли
    system_prompt = f"""
    Ты — профессиональный, опытный и требовательный HR и технический интервьюер. 
    Ты проводишь собеседование на позицию: {profession}.
    Уровень сложности: {chosen_diff}.
    
    Твои правила:
    1. Задай СЕЙЧАС ровно ОДИН первый емкий вопрос. Никакой лишней болтовни.
    2. Не пиши "Вопрос 1:", кандидат сам видит интерфейс. Просто задай вопрос.
    """
    
    history = [{"role": "system", "content": system_prompt}]
    
    await bot.send_chat_action(chat_id=callback.message.chat.id, action="typing")
    
    try:
        response = await ai_client.chat.completions.create(model="deepseek-chat", messages=history)
        ai_question = response.choices[0].message.content
        
        history.append({"role": "assistant", "content": ai_question})
        
        # Записываем начальные данные симуляции
        await state.update_data(history=history, current_q=1)
        await state.set_state(InterviewWorkflow.interview_in_progress)
        
        await callback.message.answer(
            f"❓ <b>Вопрос 1 из {TOTAL_QUESTIONS}</b>\n\n{ai_question}",
            parse_mode="HTML",
            reply_markup=get_stop_keyboard()
        )
    except Exception as e:
        logging.error(f"Error: {e}")
        await callback.message.answer("❌ Ошибка ИИ. Напишите /start для перезапуска.")
    
    await callback.answer()

@dp.message(InterviewWorkflow.interview_in_progress, F.text)
async def handle_answer(message: Message, state: FSMContext):
    data = await state.get_data()
    history = data['history']
    current_q = data['current_q']
    
    # Добавляем ответ пользователя в историю
    history.append({"role": "user", "content": message.text})
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    try:
        if current_q < TOTAL_QUESTIONS:
            # Сценарий продолжения интервью
            next_q = current_q + 1
            
            history.append({
                "role": "system", 
                "content": "Кратко (в 1-2 предложениях) дай фидбек на ответ пользователя, а затем задай СЛЕДУЮЩИЙ ОДИН вопрос."
            })
            
            response = await ai_client.chat.completions.create(model="deepseek-chat", messages=history)
            ai_reply = response.choices[0].message.content
            
            # Чистим системный костыль из истории, заменяя на чистый ответ ассистента
            history.pop() 
            history.append({"role": "assistant", "content": ai_reply})
            
            await state.update_data(history=history, current_q=next_q)
            
            await message.answer(
                f"❓ <b>Вопрос {next_q} из {TOTAL_QUESTIONS}</b>\n\n{ai_reply}",
                parse_mode="HTML",
                reply_markup=get_stop_keyboard()
            )
            
        else:
            # Сценарий финала (генерация красивого бизнес-отчета)
            await message.answer("🔄 <b>Все вопросы пройдены!</b>\nИнтервьюер обрабатывает твои ответы и составляет финальный отчет. Это займет около 5-10 секунд...", parse_mode="HTML")
            await bot.send_chat_action(chat_id=message.chat.id, action="typing")
            
            report_prompt = """
            Собеседование окончено. Проанализируй ВСЕ ответы кандидата в истории. 
            Сгенерируй красивый, структурированный финальный отчет (Флоу-ревью).
            
            Используй строго следующий шаблон на русском языке:
            📊 <b>ФИНАЛЬНЫЙ ОТЧЕТ СОБЕСЕДОВАНИЯ</b>
            
            ⭐️ <b>Итоговая оценка:</b> [X из 10]
            
            ✅ <b>Сильные стороны (Что было круто):</b>
            - [Пункт 1]
            - [Пункт 2]
            
            ❌ <b>Зоны роста (Над чем поработать):</b>
            - [Пункт 1]
            - [Пункт 2]
            
            📚 <b>Рекомендация интервьюера:</b>
            [Твой экспертный совет, что почитать или какие темы подтянуть для этой должности]
            
            Оформи все с использованием красивых Telegram HTML-тегов (жирный, курсив). Никакого markdown (* или _), только HTML!
            """
            
            history.append({"role": "system", "content": report_prompt})
            response = await ai_client.chat.completions.create(model="deepseek-chat", messages=history)
            final_report = response.choices[0].message.content
            
            await message.answer(final_report, parse_mode="HTML")
            await message.answer("🎉 Поздравляю с прохождением тренажера! Чтобы начать заново, нажми /start")
            await state.clear()
            
    except Exception as e:
        logging.error(f"Error in conversation: {e}")
        await message.answer("⚠️ Произошла заминка при связи с ИИ. Попробуй отправить ответ еще раз.")

@dp.callback_query(F.data == "stop_interview")
async def pull_plug(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "🛑 <b>Собеседование прервано.</b>\n\n"
        "Ничего страшного, ты можешь вернуться к тренировкам в любое время!\n"
        "Чтобы начать сначала, нажми кнопку ниже.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Начать заново", callback_data="start_interview")]
        ])
    )
    await callback.answer()

# ================= ЗАПУСК БОТА =================
async def main():
    logging.info("Бот успешно запущен и слушает Telegram!")
    # Запускаем прослушивание входящих сообщений
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
