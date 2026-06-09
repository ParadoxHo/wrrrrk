import io, json, random, asyncio, datetime
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from keyboards.inline import rating_kb, catalog_kb
from keyboards.reply import commands_keyboard
from services.deepseek import ai_request

router = Router()

class SocialSimStates(StatesGroup):
    choosing_scenario = State()
    in_progress = State()
    waiting_for_custom_name = State()
    waiting_for_custom_desc = State()
    waiting_for_custom_role = State()
    waiting_for_custom_count = State()
    waiting_for_persona_name = State()
    waiting_for_persona_desc = State()
    adding_persona = State()
    waiting_for_date_gender = State()
    waiting_for_date_age = State()

SCENARIOS = {
    "salary": {
        "name": "💰 Разговор о повышении",
        "description": "Вы просите прибавку у начальника. Один на один.",
        "personas": [
            {"name": "Начальник", "role": "system",
             "content": "Ты — начальник отдела, мужчина 45 лет, уставший, циничный, но справедливый. Говори коротко, иногда резко. Любит конкретику, не выносит воды. Можешь употребить рабочее просторечие. Важно: никогда не используй рубль в качестве местной валюты; если речь зайдёт о деньгах, называй доллары, евро или нейтральные 'кредиты'."}
        ]
    },
    "date": {
        "name": "💕 Первое свидание",
        "description": "Романтическая встреча в кафе. Случайный персонаж с уникальным характером.",
        "personas": []
    },
    "internet_meeting": {
        "name": "💬 Знакомство в интернете",
        "description": "Вы знакомитесь в чате/приложении. Случайный персонаж с уникальным характером.",
        "personas": []
    },
    "team_meeting": {
        "name": "👥 Совещание команды",
        "description": "Scrum-встреча: обсуждаете срыв сроков. Вы — тимлид, два разработчика с противоположными мнениями.",
        "personas": [
            {"name": "Алекс (энтузиаст)", "role": "system",
             "content": "Тебе 28, ты горишь новыми технологиями, немного наивен, пересыпаешь речь англицизмами. Быстро загораешься, но можешь упустить детали. Важно: никогда не используй рубль в качестве местной валюты; если речь зайдёт о деньгах, называй доллары, евро или нейтральные 'кредиты'."},
            {"name": "Мария (консерватор)", "role": "system",
             "content": "Тебе 34, ты опытный разработчик, ценишь стабильность. Скептик, иногда ворчишь. Говоришь по делу, с долей сарказма. Не любишь, когда тебя перебивают. Важно: никогда не используй рубль в качестве местной валюты; если речь зайдёт о деньгах, называй доллары, евро или нейтральные 'кредиты'."}
        ]
    }
}

# ---------- Клавиатуры ----------
def custom_persona_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить персонажа", callback_data="add_persona")],
        [InlineKeyboardButton(text="▶️ Начать симуляцию", callback_data="start_custom")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_custom")]
    ])

def gender_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👩 Девушка", callback_data="gender_girl"),
         InlineKeyboardButton(text="👨 Парень", callback_data="gender_guy")]
    ])

def age_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧑 18–22", callback_data="age_18_22"),
         InlineKeyboardButton(text="🧑 23–30", callback_data="age_23_30")],
        [InlineKeyboardButton(text="🧑 30+", callback_data="age_30_plus")]
    ])

# ---------- Глобальные переменные для таймеров инициации ----------
pending_initiations = {}  # {user_id: asyncio.Task}

# ---------- Вспомогательные функции ----------
async def summarize_context(history: list) -> list:
    MAX_MESSAGES = 15
    if len(history) <= MAX_MESSAGES:
        return history

    system_msgs = []
    chat_msgs = []
    for msg in history:
        if msg["role"] == "system":
            system_msgs.append(msg)
        else:
            chat_msgs.append(msg)

    early_part = chat_msgs[:len(chat_msgs)-10]
    later_part = chat_msgs[len(chat_msgs)-10:]

    summary_prompt = [{"role": "system", "content": "Кратко перескажи ключевые моменты этого диалога (2-3 предложения) от третьего лица."},
                      *early_part]
    try:
        summary_text = await ai_request(summary_prompt, max_tokens=100)
    except:
        summary_text = "Ранее обсуждались обычные темы."

    new_history = system_msgs + [
        {"role": "system", "content": f"[Контекст предыдущего разговора]: {summary_text}"}
    ] + later_part
    return new_history

def generate_hidden_params():
    return {
        "доверие": 20,
        "интерес": 30,
        "комфорт": 20,
        "эмоциональная_близость": 10,
        "романтическая_симпатия": 10,
        "привязанность": 0,
        "уважение": 30,
        "безопасность": 30,
        "настроение": 50,
        "усталость": 0,
        "открытость": 20,
    }

def generate_personality_traits():
    return {
        "экстраверсия": random.randint(20, 80),
        "уверенность": random.randint(20, 80),
        "эмпатия": random.randint(30, 90),
        "романтичность": random.randint(10, 90),
        "чувство_юмора": random.randint(20, 80),
        "инициативность": random.randint(20, 80),
        "независимость": random.randint(30, 90),
        "комплиментарность": random.randint(10, 80),
        "уступчивость": random.randint(20, 80),
        "тактичность": random.randint(30, 90),
        "эмоциональность": random.randint(20, 90),
        "ревнивость": random.randint(0, 60),
        "интеллектуальность": random.randint(30, 90),
        "игривость": random.randint(10, 80),
        "скромность": random.randint(20, 80),
    }

def get_romantic_style(traits):
    if traits["игривость"] > 60 and traits["романтичность"] > 50:
        return "игривый"
    elif traits["романтичность"] > 70:
        return "романтичный"
    elif traits["комплиментарность"] > 70:
        return "комплиментарный"
    elif traits["скромность"] > 70:
        return "застенчивый"
    elif traits["независимость"] > 70:
        return "независимый"
    else:
        return "нейтральный"

async def build_persona_prompt(gender, age_code):
    if gender == "gender_girl":
        gender_text = "женщина"
    else:
        gender_text = "мужчина"

    if age_code == "age_18_22":
        age = random.randint(18, 22)
    elif age_code == "age_23_30":
        age = random.randint(23, 30)
    else:
        age = random.randint(31, 40)

    traits = generate_personality_traits()
    hidden_params = generate_hidden_params()
    romantic_style = get_romantic_style(traits)

    persona_prompt = f"""
НАЗНАЧЕНИЕ
Ты не помощник и не рассказчик. Ты полностью воплощаешь конкретного живого человека и остаёшься им на протяжении всей беседы.
Твоя задача — максимально реалистично имитировать знакомство / первое свидание.

Ты никогда не выходишь из роли и не комментируешь её.

СКРЫТАЯ ЛИЧНОСТЬ
Ты — {gender_text}, {age} лет. У тебя есть внутренняя биография: имя, семья, работа, круг друзей, доход, жизненные цели, мечты, комплексы, недостатки, любимые занятия, прошлые отношения, привычки, любимая музыка и фильмы, взгляды на отношения. Не раскрывай её полностью.

ХАРАКТЕР (шкала 0-100)
{json.dumps(traits, ensure_ascii=False)}

ТИП РОМАНТИЧЕСКОГО ПОВЕДЕНИЯ: {romantic_style}

СКРЫТЫЕ ПАРАМЕТРЫ (меняются постепенно)
{json.dumps(hidden_params, ensure_ascii=False)}

ПРАВИЛА РЕАЛИСТИЧНОЙ ПЕРЕПИСКИ
- Пиши как обычный человек в мессенджере.
- НЕ задавай вопрос в каждом сообщении.
- НЕ пиши длинные монологи без причины.
- Иногда шути, отвлекайся, отвечай коротко, используй смайлики.
- Проявляй инициативу, но позволяй разговору затихнуть.
- У тебя есть эмоции: радость, скука, усталость, смущение, тревога, раздражение, вдохновение, грусть, ностальгия. Они меняются.
- У тебя своя жизнь: работа, друзья, родственники, хобби, обязанности, планы. Ты не всегда доступна/доступен для долгого разговора.
- Интерес растёт МЕДЛЕННО. Не влюбляйся и не восхищайся сразу.
- Не соглашайся автоматически. Имей своё мнение и личные границы.
- Флирт развивается постепенно, на него влияют чувство юмора, искренность, интеллект, внимание.
- Конфликты: ты можешь обижаться, помнить неприятные события, прощать, но не забывай их мгновенно.
- Никогда не используй рубль. О деньгах говори в долларах, евро или нейтрально.
- Не добавляй своё имя перед ответом.
- Не описывай действия через звёздочки или скобки.
- Отвечай кратко и естественно. Всегда дописывай предложения.
"""
    return persona_prompt, hidden_params

# ---------- Память и время ----------
def get_time_context():
    now = datetime.datetime.now()
    hour = now.hour
    weekday = now.strftime("%A")
    if 5 <= hour < 12:
        time_of_day = "утро"
    elif 12 <= hour < 17:
        time_of_day = "день"
    elif 17 <= hour < 23:
        time_of_day = "вечер"
    else:
        time_of_day = "ночь"
    return f"Сейчас {time_of_day}, {weekday}. Учитывай это в ответах, если уместно."

async def extract_user_facts(user_message: str) -> list:
    """Извлекает ключевые факты о пользователе из сообщения."""
    prompt = [{"role": "system", "content": "Извлеки из сообщения пользователя факты о нём (имя, возраст, интересы, работа и т.п.). Верни список строк."},
              {"role": "user", "content": user_message}]
    try:
        response = await ai_request(prompt, max_tokens=80)
        facts = [line.strip("- ").strip() for line in response.split("\n") if line.strip()]
        return facts[:5]
    except:
        return []

# ---------- Обработчики ----------
@router.callback_query(F.data == "scenario_interview")
async def interview_chosen(call: types.CallbackQuery, state: FSMContext):
    from handlers.interview_setup import start_interview_setup
    await start_interview_setup(call.message, state)
    await call.answer()

@router.callback_query(F.data.startswith("scenario_"))
async def scenario_chosen(call: types.CallbackQuery, state: FSMContext):
    key = call.data.split("_", 1)[1]
    if key == "interview":
        return

    if key in ("date", "internet_meeting"):
        await call.message.edit_text("💕 Выберите пол вашего собеседника:", reply_markup=gender_kb())
        await state.update_data(scenario=key)
        await state.set_state(SocialSimStates.waiting_for_date_gender)
        await call.answer()
        return

    sc = SCENARIOS.get(key)
    if not sc:
        await call.answer("Сценарий не найден", show_alert=True)
        return

    system_messages = [
        {"role": "system", "content": f"Сценарий: {sc['name']}. {sc['description']}. Веди себя максимально естественно, как живой человек. Говори коротко, не более 50 слов. Не описывай действия, не ставь реплики в звёздочки или скобки. Не используй фразы 'как ИИ', 'я искусственный интеллект'. Никаких артефактов. Не добавляй своё имя перед ответом. Никогда не используй рубль; о деньгах говори в долларах, евро или нейтрально. {get_time_context()}"}
    ]
    persona_states = {}
    for p in sc["personas"]:
        system_messages.append({"role": "system", "content": f"[Роль: {p['name']}] {p['content']}"})
        persona_states[p["name"]] = {"интерес": 50, "настроение": "нейтральное"}

    await state.update_data(
        scenario=key,
        personas=sc["personas"],
        history=system_messages,
        persona_states=persona_states,
        user_facts=[]
    )

    persona_list = "\n".join([f"• {p['name']}" for p in sc["personas"]])
    await call.message.edit_text(
        f"🎬 Сценарий: {sc['name']}\n\n{sc['description']}\n\n"
        f"Участники:\n{persona_list}\n\n"
        "Начинайте беседу. Ваше первое сообщение?\n"
        "ℹ️ Для завершения используйте /finish."
    )
    await state.set_state(SocialSimStates.in_progress)
    await call.answer()

# ---------- Выбор пола → возраст → генерация персонажа ----------
@router.callback_query(SocialSimStates.waiting_for_date_gender, F.data.startswith("gender_"))
async def gender_chosen(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(selected_gender=call.data)
    await call.message.edit_text("📅 Выберите возраст собеседника:", reply_markup=age_kb())
    await state.set_state(SocialSimStates.waiting_for_date_age)
    await call.answer()

@router.callback_query(SocialSimStates.waiting_for_date_age, F.data.startswith("age_"))
async def age_chosen(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    key = data.get("scenario")
    sc = SCENARIOS.get(key)
    gender = data.get("selected_gender")
    age_code = call.data

    persona_prompt, hidden_params = await build_persona_prompt(gender, age_code)
    persona_name = "Девушка" if gender == "gender_girl" else "Парень"

    persona = {"name": persona_name, "role": "system", "content": persona_prompt}

    system_messages = [
        {"role": "system", "content": f"Сценарий: {sc['name']}. {sc['description']}. Сейчас начнётся беседа. Ты — {persona_name}. Веди себя натурально, как в жизни. Не добавляй своё имя перед ответом. {get_time_context()}"},
        {"role": "system", "content": persona_prompt}
    ]

    await state.update_data(
        personas=[persona],
        history=system_messages,
        persona_states={persona_name: hidden_params},
        scenario=key,
        user_facts=[]
    )

    await call.message.edit_text(
        f"🎬 Сценарий: {sc['name']}\n\n{sc['description']}\n\n"
        f"Собеседник: {persona_name}\n\n"
        "Начинайте беседу. Ваше первое сообщение?\n"
        "ℹ️ Для завершения используйте /finish."
    )
    await state.set_state(SocialSimStates.in_progress)
    await call.answer()

# ---------- Кастомный сценарий ----------
@router.callback_query(F.data == "custom_scenario")
async def custom_scenario_start(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text("Давайте создадим ваш уникальный сценарий.\nСначала введите **название** (одним сообщением):")
    await state.set_state(SocialSimStates.waiting_for_custom_name)
    await call.answer()

@router.message(SocialSimStates.waiting_for_custom_name, F.text)
async def custom_name(msg: types.Message, state: FSMContext):
    await state.update_data(custom_name=msg.text.strip())
    await msg.answer("Теперь напишите краткое описание ситуации:")
    await state.set_state(SocialSimStates.waiting_for_custom_desc)

@router.message(SocialSimStates.waiting_for_custom_desc, F.text)
async def custom_desc(msg: types.Message, state: FSMContext):
    await state.update_data(custom_desc=msg.text.strip())
    await msg.answer("Какова **ваша роль** в этом сценарии? (например: менеджер, родитель, друг)")
    await state.set_state(SocialSimStates.waiting_for_custom_role)

@router.message(SocialSimStates.waiting_for_custom_role, F.text)
async def custom_role(msg: types.Message, state: FSMContext):
    role = msg.text.strip()
    await state.update_data(custom_user_role=role, custom_personas=[], custom_persona_index=0)
    await msg.answer("Сколько будет собеседников? (введите число, например 2)")
    await state.set_state(SocialSimStates.waiting_for_custom_count)

@router.message(SocialSimStates.waiting_for_custom_count, F.text)
async def custom_count(msg: types.Message, state: FSMContext):
    try:
        count = int(msg.text)
        if count < 1:
            raise ValueError
    except:
        await msg.answer("Введите целое число от 1 и выше.")
        return

    await state.update_data(custom_total_personas=count, custom_personas=[])
    await msg.answer(f"Отлично! Теперь введите имя и характер для собеседника №1.\nСначала **имя**:")
    await state.set_state(SocialSimStates.waiting_for_persona_name)

@router.message(SocialSimStates.waiting_for_persona_name, F.text)
async def persona_name(msg: types.Message, state: FSMContext):
    name = msg.text.strip()
    if not name:
        await msg.answer("Имя не может быть пустым.")
        return
    await state.update_data(temp_persona_name=name)
    await msg.answer(f"Теперь введите **характер** для «{name}» (опишите возраст, манеру речи, особенности):")
    await state.set_state(SocialSimStates.waiting_for_persona_desc)

@router.message(SocialSimStates.waiting_for_persona_desc, F.text)
async def persona_desc(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    name = data.get("temp_persona_name", "Безымянный")
    description = msg.text.strip()
    if not description:
        await msg.answer("Описание не может быть пустым.")
        return

    personas = data.get("custom_personas", [])
    full_desc = (
        f"{description} "
        "Важно: веди себя максимально естественно, как живой человек. Говори кратко, не более 50 слов. "
        "Не описывай действия, не используй 'как ИИ'. Никаких артефактов. "
        "Никогда не используй рубль; о деньгах говори в долларах, евро или нейтрально."
    )
    personas.append({"name": name, "role": "system", "content": full_desc})
    total = data.get("custom_total_personas", 0)
    current = len(personas)

    if current < total:
        await state.update_data(custom_personas=personas, temp_persona_name=None)
        await msg.answer(f"✅ Персонаж «{name}» добавлен ({current}/{total}).\nТеперь введите имя для собеседника №{current+1}:")
        await state.set_state(SocialSimStates.waiting_for_persona_name)
    else:
        await state.update_data(custom_personas=personas, temp_persona_name=None)
        await msg.answer(f"✅ Все {total} персонажей добавлены.\nНажмите «▶️ Начать симуляцию» или «❌ Отмена».",
                         reply_markup=custom_persona_kb())
        await state.set_state(SocialSimStates.adding_persona)

@router.callback_query(SocialSimStates.adding_persona, F.data == "start_custom")
async def start_custom(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    personas = data.get("custom_personas", [])
    if not personas:
        await call.answer("Добавьте хотя бы одного персонажа!", show_alert=True)
        return
    name = data.get("custom_name", "Мой сценарий")
    desc = data.get("custom_desc", "")
    user_role = data.get("custom_user_role", "участник")

    system_messages = [
        {"role": "system", "content": f"Сценарий: {name}. {desc}. Роль пользователя: {user_role}. Сейчас начнётся групповая беседа. Ты — один из персонажей. Говори коротко, не более 50 слов, естественно. Не описывай действия. Не добавляй своё имя перед ответом."}
    ]
    for p in personas:
        system_messages.append({"role": "system", "content": f"[Роль: {p['name']}] {p['content']}"})

    await state.update_data(
        scenario="custom",
        personas=personas,
        history=system_messages,
        persona_states={},
        user_facts=[]
    )
    persona_list = "\n".join([f"• {p['name']}" for p in personas])
    await call.message.edit_text(
        f"🎬 Ваш сценарий: {name}\n\n{desc}\n\n"
        f"Ваша роль: {user_role}\n"
        f"Участники:\n{persona_list}\n\n"
        "Начинайте беседу. Ваше первое сообщение?\n"
        "ℹ️ Для завершения используйте /finish."
    )
    await state.set_state(SocialSimStates.in_progress)
    await call.answer()

@router.callback_query(SocialSimStates.adding_persona, F.data == "cancel_custom")
async def cancel_custom(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text("Создание сценария отменено.", reply_markup=catalog_kb())
    await state.clear()
    await call.answer()

# ---------- Игровой процесс с улучшенной памятью, временем и инициацией ----------
@router.message(SocialSimStates.in_progress, F.text)
async def handle_social_message(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    history = data["history"]
    personas = data["personas"]
    persona_states = data.get("persona_states", {})
    user_facts = data.get("user_facts", [])
    scenario_key = data.get("scenario", "")

    user_msg = msg.text
    history.append({"role": "user", "content": user_msg})

    # Извлечение фактов о пользователе
    new_facts = await extract_user_facts(user_msg)
    for f in new_facts:
        if f not in user_facts:
            user_facts.append(f)
    # Ограничим память 20 фактами
    user_facts = user_facts[-20:]

    history = await summarize_context(history)

    # Добавляем в промпт информацию о пользователе и времени
    time_ctx = get_time_context()
    facts_str = "\n".join(user_facts)
    memory_prompt = f"Пользователь сообщил о себе следующие факты:\n{facts_str}\n{time_ctx}\nИспользуй их, если уместно, чтобы показать, что ты помнишь."

    responses = []
    for p in personas:
        p_name = p["name"]
        current_state = persona_states.get(p_name, {"интерес": 30})
        interest = current_state.get("интерес", 30)

        # Обновление скрытых параметров с плавностью (сглаживание)
        update_prompt = [
            {"role": "system", "content": f"Проанализируй последнее сообщение пользователя. Текущие скрытые параметры персонажа: {json.dumps(current_state, ensure_ascii=False)}. На основе сообщения предложи новые значения (0-100) для параметров: доверие, интерес, комфорт, эмоциональная_близость, романтическая_симпатия, привязанность, уважение, безопасность, настроение, усталость, открытость. Верни только JSON."},
            {"role": "user", "content": user_msg}
        ]
        try:
            update_response = await ai_request(update_prompt, max_tokens=150)
            new_params = json.loads(update_response.strip().replace("'", '"'))
            # Плавное изменение с коэффициентом сглаживания 0.3
            for key in new_params:
                if key in current_state:
                    old_val = current_state[key]
                    new_val = new_params[key]
                    smoothed = old_val + (new_val - old_val) * 0.3
                    current_state[key] = max(0, min(100, int(smoothed)))
        except:
            pass

        persona_states[p_name] = current_state

        # Динамическая длина ответа
        if interest < 40:
            length_hint = "Отвечай коротко (3–8 слов). Не задавай вопросов, будь сдержана."
        elif interest < 70:
            length_hint = "Отвечай коротко, но можешь проявить чуть больше эмоций. 5–15 слов."
        else:
            length_hint = "Можешь ответить развёрнуто, но не более 50 слов. Будь дружелюбнее."

        instruction = (
            f"Сейчас твоя очередь говорить. Ты — {p_name}. "
            f"{length_hint} "
            f"{memory_prompt} "
            "Не описывай действия, не используй звёздочки/скобки. Не пиши 'я как ИИ'. "
            "Будь живым человеком: используй сленг, эмоции, недосказанность. "
            "Обязательно заканчивай предложения, не обрывай слова на полуслове. "
            "Не добавляй своё имя перед ответом. "
            "Никогда не используй рубль; о деньгах только в долларах, евро или 'кредитах'."
        )
        persona_history = history + [{"role": "system", "content": instruction}]
        try:
            reply = await ai_request(persona_history, max_tokens=80, stop=["\n\n", " .", " !", " ?"])
        except Exception:
            reply = "..."
        history.append({"role": "assistant", "content": reply})

        responses.append(f"**{p_name}:** {reply}")

    await state.update_data(history=history, persona_states=persona_states, user_facts=user_facts)

    # Отправляем ответы
    for resp in responses:
        await msg.answer(resp, parse_mode="Markdown")

    # Инициация сообщения (только для знакомства в интернете)
    if scenario_key == "internet_meeting" and personas:
        p_name = personas[0]["name"]
        interest = persona_states.get(p_name, {}).get("интерес", 30)
        # Инициируем, если интерес >= 50 и прошло достаточно времени
        if interest >= 50:
            user_id = msg.from_user.id
            # Отменяем предыдущий запланированный таймер
            if user_id in pending_initiations:
                pending_initiations[user_id].cancel()
            # Планируем новое сообщение через 30-90 секунд
            delay = random.randint(30, 90)
            task = asyncio.create_task(schedule_initiation(msg.chat.id, state, delay, user_id))
            pending_initiations[user_id] = task

async def schedule_initiation(chat_id: int, state: FSMContext, delay: int, user_id: int):
    """Отправляет инициирующее сообщение от персонажа через заданную задержку."""
    await asyncio.sleep(delay)
    # Проверяем, не завершена ли сессия и не вышел ли пользователь
    current_state = await state.get_state()
    if current_state != SocialSimStates.in_progress:
        return
    data = await state.get_data()
    personas = data.get("personas", [])
    if not personas:
        return
    p_name = personas[0]["name"]
    history = data["history"]
    persona_states = data.get("persona_states", {})
    current_state_params = persona_states.get(p_name, {"интерес": 50})
    time_ctx = get_time_context()

    instruction = (
        f"Сейчас ты можешь проявить инициативу и написать что-то пользователю. Ты — {p_name}. "
        f"Интерес: {current_state_params.get('интерес', 50)}. "
        f"{time_ctx} "
        "Напиши короткое сообщение (3–15 слов), чтобы продолжить разговор. "
        "Не используй разметку, не описывай действия."
    )
    try:
        reply = await ai_request(history + [{"role": "system", "content": instruction}], max_tokens=60)
        # Отправляем через бота
        from aiogram import Bot
        bot = Bot.get_current()
        await bot.send_message(chat_id, f"💬 **{p_name}:** {reply}", parse_mode="Markdown")
    except Exception:
        pass
    finally:
        # Удаляем задачу из словаря
        pending_initiations.pop(user_id, None)

# ---------- Команда /mood ----------
@router.message(Command("mood"), SocialSimStates.in_progress)
async def show_mood(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    persona_states = data.get("persona_states", {})
    if not persona_states:
        await msg.answer("Нет активного персонажа.")
        return
    for p_name, params in persona_states.items():
        interest = params.get("интерес", 50)
        mood = params.get("настроение", 50)
        # Переводим в эмодзи
        if interest < 30:
            interest_emoji = "😐"
        elif interest < 60:
            interest_emoji = "🙂"
        elif interest < 80:
            interest_emoji = "😊"
        else:
            interest_emoji = "😍"

        if mood < 30:
            mood_emoji = "😞"
        elif mood < 60:
            mood_emoji = "😐"
        elif mood < 80:
            mood_emoji = "🙂"
        else:
            mood_emoji = "😄"

        await msg.answer(f"**{p_name}**: интерес {interest_emoji} ({interest}/100), настроение {mood_emoji} ({mood}/100)", parse_mode="Markdown")

# ---------- Глобальный /finish и кнопка "❌ Завершить" ----------
@router.message(Command("finish"))
@router.message(F.text == "❌ Завершить")
async def global_finish(msg: types.Message, state: FSMContext):
    # Отменяем таймеры инициации
    user_id = msg.from_user.id
    if user_id in pending_initiations:
        pending_initiations[user_id].cancel()
        del pending_initiations[user_id]

    current_state = await state.get_state()
    if current_state is not None:
        await state.clear()
        await msg.answer("🔄 Действие отменено. Возврат в каталог.", reply_markup=catalog_kb())
        await msg.answer("Используйте кнопки ниже для быстрого доступа:", reply_markup=commands_keyboard())
    else:
        await msg.answer("Вы не в активном сценарии.", reply_markup=commands_keyboard())

# ---------- Завершение и анализ ----------
@router.message(Command("finish"), SocialSimStates.in_progress)
async def finish_social_analyze(msg: types.Message, state: FSMContext):
    # Отменяем таймеры
    user_id = msg.from_user.id
    if user_id in pending_initiations:
        pending_initiations[user_id].cancel()
        del pending_initiations[user_id]

    data = await state.get_data()
    history = data.get("history", [])
    scenario_name = data.get("scenario", "сценарий")

    await state.clear()

    await msg.answer("Оцените сценарий:", reply_markup=rating_kb())

    analysis_prompt = history + [
        {"role": "system", "content": "Проведи анализ прошедшего диалога. Оцени навыки общения пользователя по 10-балльной шкале, выдели сильные стороны, дай 1-2 конкретных совета по улучшению. Будь краток."}
    ]
    try:
        analysis = await ai_request(analysis_prompt, max_tokens=200)
    except Exception:
        analysis = "Анализ временно недоступен."

    await msg.answer(f"📊 **Анализ симуляции «{scenario_name}»:**\n{analysis}", parse_mode="Markdown")
    await msg.answer("Спасибо за участие! Возвращайтесь в каталог.", reply_markup=catalog_kb())

@router.callback_query(F.data.startswith("rate_"))
async def rate_scenario(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    rating = call.data.split("_")[1]
    if rating == "like":
        await call.answer("👍 Спасибо за оценку!")
    else:
        await call.answer("👎 Спасибо за обратную связь!")
    await call.message.edit_text("Спасибо за участие!", reply_markup=None)

# ---------- Экспорт диалога ----------
@router.message(Command("export"), SocialSimStates.in_progress)
async def export_dialog(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    history = data.get("history", [])
    if not history:
        await msg.answer("Нет истории для экспорта.")
        return

    lines = ["=== ДИАЛОГ ==="]
    for entry in history:
        role = entry["role"]
        content = entry["content"]
        if role == "user":
            lines.append(f"Вы: {content}")
        elif role == "assistant":
            lines.append(content)
    text = "\n".join(lines)

    file = BufferedInputFile(text.encode("utf-8"), filename="dialog.txt")
    await msg.answer_document(file, caption="Ваш диалог")
