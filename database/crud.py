from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from .models import User, Interview, UserStats

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
