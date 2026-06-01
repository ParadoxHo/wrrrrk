from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from .models import User, Interview, UserStats, ChatQueue, ActiveChat
from sqlalchemy import and_
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_
from .models import User, Interview, UserStats, ChatQueue, ActiveChat

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
        select(ChatQueue).where(ChatQueue.user_id != exclude_user_id).order_by(ChatQueue.created_at).limit(1)
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
