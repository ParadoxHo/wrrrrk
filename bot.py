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
    raise ValueError("КРИТИЧЕСКАЯ ОШИБКА: Токены не найдены!")

# Инициализация клиентов
ai_client = AsyncOpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# ================= НАСТРОЙКИ СИМУЛЯЦИИ =================
TOTAL_QUESTIONS = 10  # Теперь 10 вопросов для полноценного раскрытия по методу STAR

class InterviewWorkflow(StatesGroup):
    waiting_for_language = State()
    waiting_for_profession = State()
    waiting_for_persona = State()
    waiting_for_difficulty = State()
    interview_in_progress = State()

# ================= КЛАВИАТУРЫ =================

def get_start_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Начать интервью", callback_data="start_interview")],
        [InlineKeyboardButton(text="❓ Как это работает?", callback_data="help_info")]
    ])

def get_language_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 На русском", callback_data="lang_ru")],
        [InlineKeyboardButton(text="🇬🇧 In English (Mock Interview)", callback_data="lang_en")]
    ])

def get_persona_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟢 Добрый HR", callback_data="pers_hr")],
        [InlineKeyboardButton(text="🟡 Душный Тимлид", callback_data="pers_tech")],
        [InlineKeyboardButton(text="🔴 Стрессовый Босс", callback_data="pers_boss")]
    ])

def get_difficulty_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👶 Junior", callback_data="diff_jun")],
        [InlineKeyboardButton(text="👨‍💻 Middle", callback_data="diff_mid")],
        [InlineKeyboardButton(text="🧙‍♂️ Senior / Expert", callback_data="diff_sen")]
    ])

def get_stop_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛑 Прервать собеседование", callback_data="stop_interview")]
    ])

# ================= ХЭНДЛЕРЫ НАВИГАЦИИ =================

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Удаление старых кнопок...", reply_markup=ReplyKeyboardRemove())
    await message.answer(
        "👋 <b>Добро пожаловать в AI Interviewer!</b>\n\n"
        "Я твой персональный тренажер для подготовки к собеседованиям в топовые международные компании.\n\n"
        "🎯 Готов проверить свои силы?",
        parse_mode="HTML",
        reply_markup=get_start_keyboard()
    )

@dp.callback_query(F.data == "help_info")
async def toggle_help(callback: CallbackQuery):
    await callback.message.edit_text(
        "📋 <b>Как проходит симуляция:</b>\n\n"
        "1. Выбираешь язык (RU / EN) и роль интервьюера.\n"
        "2. Пишешь желаемую должность.\n"
        "3. Выбираешь свой грейд (Junior/Middle/Senior).\n"
        "4. ИИ в роли выбранного персонажа задает тебе <b>10 целевых вопросов</b>.\n"
        "5. В конце ты получаешь <b>развернутый бизнес-отчет</b> с оценкой, разбором ошибок и фидбеком.\n\n"
        "Жми кнопку ниже, чтобы начать!",
        parse_mode="HTML",
        reply_markup=get_start_keyboard()
    )
    await callback.answer()

# Шаг 1: Выбор языка
@dp.callback_query(F.data == "start_interview")
async def ask_language(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🌍 <b>Шаг 1 из 4: Выбери язык интервью</b>\n\n"
        "<i>Совет: Режим English Mock Interview поможет подготовиться к релокации "
        "и подтянуть профессиональную лексику.</i>",
        parse_mode="HTML",
        reply_markup=get_language_keyboard()
    )
    await state.set_state(InterviewWorkflow.waiting_for_language)
    await callback.answer()

# Шаг 2: Ввод должности
@dp.callback_query(InterviewWorkflow.waiting_for_language, F.data.startswith("lang_"))
async def ask_profession(callback: CallbackQuery, state: FSMContext):
    lang = "English" if callback.data == "lang_en" else "Русский"
    await state.update_data(language=lang)
    
    await callback.message.edit_text(
        "💼 <b>Шаг 2 из 4: Должность</b>\n\n"
        "Напиши должность, на которую ты собеседуешься.\n"
        "<i>Пример: Python Backend Developer, Product Manager...</i>",
        parse_mode="HTML"
    )
    await state.set_state(InterviewWorkflow.waiting_for_profession)
    await callback.answer()

# Шаг 3: Выбор персонажа (Геймификация)
@dp.message(InterviewWorkflow.waiting_for_profession, F.text)
async def ask_persona(message: Message, state: FSMContext):
    await state.update_data(profession=message.text)
    
    await message.answer(
        "🎭 <b>Шаг 3 из 4: Кто будет тебя собеседовать?</b>\n\n"
        "🟢 <b>Добрый HR</b> — мягкие вопросы, мотивация, soft-skills.\n"
        "🟡 <b>Душный Тимлид</b> — глубокая теория, придирки к формулировкам.\n"
        "🔴 <b>Стрессовый Босс</b> — давление, перебивания, каверзные логические задачи.\n\n"
        "Выбери интервьюера:",
        parse_mode="HTML",
        reply_markup=get_persona_keyboard()
    )
    await state.set_state(InterviewWorkflow.waiting_for_persona)

# Шаг 4: Выбор сложности (Грейд)
@dp.callback_query(InterviewWorkflow.waiting_for_persona, F.data.startswith("pers_"))
async def ask_difficulty(callback: CallbackQuery, state: FSMContext):
    pers_map = {
        "pers_hr": "Добрый HR. Ты задаешь мягкие вопросы, часто хвалишь за хорошие ответы, фокусируешься на soft-skills, командной работе и мотивации.",
        "pers_tech": "Душный Тимлид. Ты копаешь глубоко в теорию, придираешься к формулировкам, требуешь максимальной технической точности и деталей.",
        "pers_boss": "Стрессовый директор. Ты ведешь себя жестко: перебиваешь кандидата (имитируй это в тексте фразами вроде 'Так, стоп, давайте ближе к делу'), задаешь каверзные вопросы на логику, давишь, проверяешь, как кандидат ведет себя под давлением."
    }
    await state.update_data(persona=pers_map[callback.data])
    
    await callback.message.edit_text(
        "📈 <b>Шаг 4 из 4: Твой уровень</b>\n\n"
        "Выбери грейд, на который претендуешь:",
        parse_mode="HTML",
        reply_markup=get_difficulty_keyboard()
    )
    await state.set_state(InterviewWorkflow.waiting_for_difficulty)

# ================= ЗАПУСК ИНТЕРВЬЮ =================
@dp.callback_query(InterviewWorkflow.waiting_for_difficulty, F.data.startswith("diff_"))
async def start_simulation(callback: CallbackQuery, state: FSMContext):
    diff_map = {"diff_jun": "Junior", "diff_mid": "Middle", "diff_sen": "Senior/Expert"}
    chosen_diff = diff_map[callback.data]
    
    user_data = await state.get_data()
    profession = user_data['profession']
    language = user_data['language']
    persona = user_data['persona']
    
    await callback.message.edit_text(
        f"🚀 <b>Симуляция запущена!</b>\n\n"
        f"🌍 Язык: {language}\n"
        f"💼 Позиция: {profession} ({chosen_diff})\n\n"
        f"⏳ <i>Интервьюер заходит в переговорную...</i>",
        parse_mode="HTML"
    )
    
    # Генерация мощного системного промпта
    system_prompt = f"""
    РОЛЬ
    Ты — профессиональный интервьюер с опытом работы более 15 лет в топовых международных компаниях. 
    Твой текущий характер: {persona}
    Кандидат: {profession}, заявленный грейд: {chosen_diff}.
    Язык собеседования: {language}. Ты должен задавать вопросы и реагировать СТРОГО на этом языке.

    ЦЕЛЬ ИНТЕРВЬЮ
    Определить компетентность, реальный опыт, логику, софт-скиллы и риски найма.

    ПРАВИЛА (СТРОГО):
    1. Задавай вопросы СТРОГО ПО ОДНОМУ. Никогда не выдавай список вопросов.
    2. Не нумеруй свои реплики (не пиши "Вопрос 1:").
    3. После ответа кандидата: дай микро-фидбек В СТИЛЕ СВОЕГО ПЕРСОНАЖА (1-2 предложения) и задай следующий вопрос.
    4. Не привязывайся к законодательству или стандартам какой-либо одной страны (например, ТК РФ). Опирайся на глобальные международные бизнес-практики.
    5. Если кандидат отвечает водой — требуй конкретики и примеров.

    СТРУКТУРА ({TOTAL_QUESTIONS} вопросов в сумме):
    1. Знакомство и бэкграунд.
    2. Техническая оценка (учитывай грейд {chosen_diff}).
    3. Ситуационные кейсы (реальные рабочие проблемы).
    4. Поведенческое интервью (Метод STAR).
    
    НАЧАЛО:
    Поздоровайся в стиле своего персонажа и задай ПЕРВЫЙ вопрос.
    """
    
    history = [{"role": "system", "content": system_prompt}]
    
    await bot.send_chat_action(chat_id=callback.message.chat.id, action="typing")
    
    try:
        response = await ai_client.chat.completions.create(model="deepseek-chat", messages=history)
        ai_question = response.choices[0].message.content
        
        history.append({"role": "assistant", "content": ai_question})
        
        await state.update_data(history=history, current_q=1)
        await state.set_state(InterviewWorkflow.interview_in_progress)
        
        await callback.message.answer(
            f"❓ <b>Вопрос 1 из {TOTAL_QUESTIONS}</b>\n\n{ai_question}",
            parse_mode="HTML",
            reply_markup=get_stop_keyboard()
        )
    except Exception as e:
        logging.error(f"Error: {e}")
        await callback.message.answer("❌ Ошибка связи с ИИ. Напишите /start для перезапуска.")
    
    await callback.answer()

# ================= ОБРАБОТКА ОТВЕТОВ И ФИНАЛ =================
@dp.message(InterviewWorkflow.interview_in_progress, F.text)
async def handle_answer(message: Message, state: FSMContext):
    data = await state.get_data()
    history = data['history']
    current_q = data['current_q']
    language = data['language']
    
    history.append({"role": "user", "content": message.text})
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    try:
        if current_q < TOTAL_QUESTIONS:
            next_q = current_q + 1
            
            history.append({
                "role": "system", 
                "content": "Отреагируй на ответ кандидата в стиле своего персонажа (коротко) и задай СЛЕДУЮЩИЙ вопрос."
            })
            
            response = await ai_client.chat.completions.create(model="deepseek-chat", messages=history)
            ai_reply = response.choices[0].message.content
            
            history.pop() # Удаляем системный костыль
            history.append({"role": "assistant", "content": ai_reply})
            
            await state.update_data(history=history, current_q=next_q)
            
            await message.answer(
                f"❓ <b>Вопрос {next_q} из {TOTAL_QUESTIONS}</b>\n\n{ai_reply}",
                parse_mode="HTML",
                reply_markup=get_stop_keyboard()
            )
            
        else:
            await message.answer("🔄 <b>Интервью завершено!</b>\nАнализирую твои ответы и готовлю детальный отчет. Это займет около 10 секунд...", parse_mode="HTML")
            await bot.send_chat_action(chat_id=message.chat.id, action="typing")
            
            # Доп. блок для английского языка
            english_feedback = ""
            if language == "English":
                english_feedback = (
                    "🇬🇧 <b>Оценка English Mock Interview:</b>\n"
                    "- Оцени уровень английского языка кандидата.\n"
                    "- Укажи на лексические, грамматические или стилистические ошибки, если они были.\n"
                    "- Дай советы по улучшению профессионального английского.\n\n"
                )
            
            report_prompt = f"""
            Собеседование окончено. Выйди из своей роли (персонажа) и стань объективным независимым экспертом-оценщиком.
            Проанализируй ВСЕ ответы кандидата. Сформируй итоговый отчет строго по шаблону ниже на РУССКОМ ЯЗЫКЕ (даже если интервью было на английском).
            Не опирайся на локальное законодательство. Используй HTML-теги для оформления.

            📊 <b>ИТОГОВЫЙ ОТЧЁТ ИНТЕРВЬЮЕРА</b>
            
            ⭐️ <b>Общая оценка:</b> [Балл от 1 до 10] / 10
            
            ✅ <b>Сильные стороны:</b>
            - [Конкретный пункт из ответов]
            - [Конкретный пункт из ответов]
            
            ❌ <b>Зоны роста и слабые стороны:</b>
            - [Над чем нужно поработать]
            - [Что кандидат не смог ответить или ответил плохо]
            
            {english_feedback}
            ⚠️ <b>Риски найма:</b>
            [Потенциальные проблемы: выгорание, недостаток компетенций, софт-скиллы и т.д.]
            
            🎯 <b>Рекомендуемый грейд:</b> [Junior / Middle / Senior / Expert]
            📈 <b>Вероятность реального оффера:</b> [X]%
            
            📝 <b>Вердикт:</b> [Однозначно рекомендовать / Скорее рекомендовать / Рассмотреть дополнительно / Скорее отказать / Отказать]
            """
            
            history.append({"role": "system", "content": report_prompt})
            response = await ai_client.chat.completions.create(model="deepseek-chat", messages=history)
            final_report = response.choices[0].message.content
            
            await message.answer(final_report, parse_mode="HTML")
            await message.answer("🎉 Тренажер пройден! Чтобы начать новое собеседование, нажми /start")
            await state.clear()
            
    except Exception as e:
        logging.error(f"Error in conversation: {e}")
        await message.answer("⚠️ Произошла ошибка. Попробуй отправить ответ еще раз.")

@dp.callback_query(F.data == "stop_interview")
async def pull_plug(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "🛑 <b>Собеседование прервано.</b>\n\n"
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
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
