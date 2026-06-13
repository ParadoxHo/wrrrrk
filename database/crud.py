from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_
from .models import User, Interview, UserStats, ChatQueue, ActiveChat, Relationship

async def get_or_create_user(session: AsyncSession, telegram_id: int, username: str = None):
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if not user:
        user = User(telegram_id=telegram_id, username=username)
        session.add(user)
        await session.commit()
    return user

async def save_interview(session: AsyncSession, user_id: int, data: dict) -> Interview:
    interview = Interview(user_id=user_id, **data)
    session.add(interview)
    await session.commit()
    return interview

async def update_user_stats(session: AsyncSession, user_id: int):
    result = await session.execute(select(Interview).where(Interview.user_id == user_id))
    interviews = result.scalars().all()
    if not interviews:
        return
    scores = []
    for i in interviews:
        if i.metrics and "overall_score" in i.metrics:
            scores.append(i.metrics["overall_score"])
    avg = sum(scores)/len(scores) if scores else 0.0
    stats_result = await session.execute(select(UserStats).where(UserStats.user_id == user_id))
    stats = stats_result.scalar_one_or_none()
    if not stats:
        stats = UserStats(user_id=user_id)
        session.add(stats)
    stats.total_interviews = len(interviews)
    stats.average_score = avg
    stats.updated_at = datetime.utcnow()
    stats.strengths = []
    stats.weaknesses = []
    stats.recommendations = ""
    await session.commit()

async def add_to_chat_queue(session: AsyncSession, user_id: int) -> bool:
    existing = await session.execute(select(ChatQueue).where(ChatQueue.user_id == user_id))
    if existing.scalar_one_or_none():
        return False
    session.add(ChatQueue(user_id=user_id))
    await session.commit()
    return True

async def remove_from_chat_queue(session: AsyncSession, user_id: int):
    entry = await session.execute(select(ChatQueue).where(ChatQueue.user_id == user_id))
    entry = entry.scalar_one_or_none()
    if entry:
        await session.delete(entry)
        await session.commit()

async def get_random_user_from_queue(session: AsyncSession, exclude_user_id: int):
    result = await session.execute(
        select(ChatQueue).where(ChatQueue.user_id != exclude_user_id).order_by(ChatQueue.joined_at).limit(1)
    )
    return result.scalar_one_or_none()

async def create_active_chat(session: AsyncSession, user1_id: int, user2_id: int) -> ActiveChat:
    chat = ActiveChat(user1_id=user1_id, user2_id=user2_id)
    session.add(chat)
    await session.commit()
    return chat

async def get_active_chat_by_user(session: AsyncSession, user_id: int):
    result = await session.execute(
        select(ActiveChat).where(
            and_(
                ActiveChat.active == 1,
                (ActiveChat.user1_id == user_id) | (ActiveChat.user2_id == user_id)
            )
        )
    )
    return result.scalar_one_or_none()

async def end_active_chat(session: AsyncSession, chat_id: int):
    chat = await session.get(ActiveChat, chat_id)
    if chat:
        chat.active = 0
        await session.commit()
    return chat

async def set_allow_random_chat(session: AsyncSession, user_id: int, value: bool):
    user = await session.get(User, user_id)
    if user:
        user.allow_random_chat = 1 if value else 0
        await session.commit()

async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int):
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return result.scalar_one_or_none()

async def find_available_user(session: AsyncSession, exclude_user_id: int):
    result = await session.execute(
        select(User).where(User.allow_random_chat == 1, User.telegram_id != exclude_user_id)
    )
    candidates = result.scalars().all()
    for user in candidates:
        chat = await get_active_chat_by_user(session, user.telegram_id)
        if chat:
            continue
        queue_entry = await session.execute(select(ChatQueue).where(ChatQueue.user_id == user.id))
        if queue_entry.scalar_one_or_none():
            continue
        return user
    return None

async def cleanup_expired_queue(session: AsyncSession, timeout_minutes: int = 5, bot=None):
    from datetime import datetime, timedelta
    cutoff = datetime.utcnow() - timedelta(minutes=timeout_minutes)
    result = await session.execute(
        select(ChatQueue).where(ChatQueue.joined_at < cutoff)
    )
    expired = result.scalars().all()
    for entry in expired:
        await session.delete(entry)
        if bot:
            try:
                await bot.send_message(
                    entry.user_id,
                    "⌛ За 5 минут никто не подключился. Поиск остановлен. Вы можете попробовать снова позже."
                )
            except Exception:
                pass
    await session.commit()

async def get_relationship(session: AsyncSession, user_id: int, scenario_key: str):
    result = await session.execute(
        select(Relationship).where(and_(Relationship.user_id == user_id, Relationship.scenario_key == scenario_key))
    )
    return result.scalar_one_or_none()

async def save_relationship(session: AsyncSession, user_id: int, scenario_key: str,
                           interest: float, trust: float, romance: float,
                           last_history_summary: str = None):
    rel = await get_relationship(session, user_id, scenario_key)
    if not rel:
        rel = Relationship(user_id=user_id, scenario_key=scenario_key)
        session.add(rel)
    rel.interest = interest
    rel.trust = trust
    rel.romance = romance
    rel.interaction_count += 1
    rel.last_history_summary = last_history_summary
    rel.last_interaction = datetime.utcnow()
    await session.commit()
    return rel
