import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from openai import AsyncOpenAI

# Настраиваем логирование, чтобы видеть отчеты в консоли Railway
logging.basicConfig(level=logging.INFO)

# Извлекаем токены из скрытых переменных окружения сервера
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

if not TELEGRAM_TOKEN or not DEEPSEEK_API_KEY:
    raise ValueError("КРИТИЧЕСКАЯ ОШИБКА: Переменные TELEGRAM_TOKEN и DEEPSEEK_API_KEY не заданы!")

# Инициализируем клиента DeepSeek через официальную библиотеку openai
ai_client = AsyncOpenAI(
    api_key=DEEPSEEK_API_KEY, 
    base_url="https://api.deepseek.com"
)

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# Состояния конечного автомата (FSM)
class InterviewState(StatesGroup):
    choosing_profession = State()
    interview_in_progress = State()

# Кнопка для отмены интервью
stop_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="🛑 Завершить собеседование")]],
    resize_keyboard=True
)

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()  # Сбрасываем контекст, если он был
    await message.answer(
        "Привет! Я твой ИИ-тренажер для собеседований. 🎯\n\n"
        "Напиши должность, на которую ты хочешь пройти мок-интервью "
        "(например: <i>Junior Python Developer, Маркетолог, DevOps-инженер</i>).",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove()  # Убираем старые кнопки, если они остались
    )
    await state.set_state(InterviewState.choosing_profession)

@dp.message(InterviewState.choosing_profession, F.text)
async def start_interview(message: Message, state: FSMContext):
    profession = message.text
    
    # Системные инструкции для DeepSeek
    system_prompt = f"""
    Ты опытный, строгий, но справедливый технический интервьюер.
    Пользователь пришел на собеседование на позицию: {profession}.
    
    Твоя задача:
    1. Задавать по одному емкому профессиональному вопросу за раз.
    2. Когда пользователь отвечает, кратко и конструктивно оцени его ответ (укажи на ошибки, похвали за правильные мысли).
    3. Сразу после оценки задай следующий вопрос.
    
    Начни прямо сейчас: поприветствуй кандидата и задай первый вопрос.
    """
    
    messages_history = [{"role": "system", "content": system_prompt}]
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    try:
        response = await ai_client.chat.completions.create(
            model="deepseek-chat",
            messages=messages_history
        )
        ai_reply = response.choices[0].message.content
        messages_history.append({"role": "assistant", "content": ai_reply})
        
        # Сохраняем историю и меняем статус пользователя
        await state.update_data(history=messages_history)
        await state.set_state(InterviewState.interview_in_progress)
        
        await message.answer(ai_reply, reply_markup=stop_keyboard)
    except Exception as e:
        logging.error(f"Ошибка DeepSeek API: {e}")
        await message.answer("Произошла ошибка при подключении к ИИ. Попробуй позже.")
        await state.clear()

@dp.message(InterviewState.interview_in_progress, F.text == "🛑 Завершить собеседование")
async def stop_interview(message: Message, state: FSMContext):
    await message.answer(
        "Собеседование завершено! Надеюсь, это было полезно.\n"
        "Чтобы начать заново, напиши /start", 
        reply_markup=ReplyKeyboardRemove()
    )
    await state.clear()

@dp.message(InterviewState.interview_in_progress, F.text)
async def process_answer(message: Message, state: FSMContext):
    user_answer = message.text
    
    user_data = await state.get_data()
    messages_history = user_data.get('history', [])
    
    messages_history.append({"role": "user", "content": user_answer})
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    try:
        response = await ai_client.chat.completions.create(
            model="deepseek-chat",
            messages=messages_history
        )
        ai_reply = response.choices[0].message.content
        
        messages_history.append({"role": "assistant", "content": ai_reply})
        await state.update_data(history=messages_history)
        
        await message.answer(ai_reply)
    except Exception as e:
        logging.error(f"Ошибка DeepSeek API: {e}")
        await message.answer("Ошибка связи с ИИ. Попробуй отправить ответ еще раз.")

async def main():
    logging.info("Бот успешно запущен и готов к работе!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
