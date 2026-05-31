from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def language_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru")],
        [InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en")]
    ])

def persona_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟢 Добрый HR", callback_data="pers_hr")],
        [InlineKeyboardButton(text="🟡 Душный Тимлид", callback_data="pers_tech")],
        [InlineKeyboardButton(text="🔴 Стрессовый Босс", callback_data="pers_boss")]
    ])

def difficulty_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👶 Junior", callback_data="jun")],
        [InlineKeyboardButton(text="👨‍💻 Middle", callback_data="mid")],
        [InlineKeyboardButton(text="🧙‍♂️ Senior/Expert", callback_data="sen")]
    ])

def question_count_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="5", callback_data="q_5"),
         InlineKeyboardButton(text="10", callback_data="q_10")],
        [InlineKeyboardButton(text="15", callback_data="q_15"),
         InlineKeyboardButton(text="20", callback_data="q_20")]
    ])

def resume_skip_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭️ Пропустить", callback_data="skip_resume")]
    ])

def vacancy_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Вставить ссылку на вакансию", callback_data="add_vacancy")],
        [InlineKeyboardButton(text="⏭️ Пропустить", callback_data="skip_vacancy")]
    ])

def interview_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💡 Подсказка", callback_data="hint"),
         InlineKeyboardButton(text="🛑 Завершить", callback_data="stop_interview")]
    ])

def hint_kb():
    """Кнопка подсказки для социальных сценариев"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💡 Подсказка", callback_data="social_hint")]
    ])

def rating_kb():
    """Кнопки оценки сценария"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👍 Понравилось", callback_data="rate_like"),
         InlineKeyboardButton(text="👎 Не понравилось", callback_data="rate_dislike")]
    ])

def catalog_kb():
    """Единый каталог с фиксированным набором сценариев"""
    from handlers.social_sim import SCENARIOS
    buttons = [
        [InlineKeyboardButton(text="💼 Собеседование", callback_data="scenario_interview")]
    ]
    for key, sc in SCENARIOS.items():
        buttons.append([InlineKeyboardButton(text=sc["name"], callback_data=f"scenario_{key}")])
    buttons.append([InlineKeyboardButton(text="✨ Создать свой сценарий", callback_data="custom_scenario")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
