import asyncio
import logging
from aiogram import Bot, Dispatcher
from config import TELEGRAM_TOKEN
from database import init_db
from handlers.start import router as start_router
from handlers.interview_setup import router as setup_router
from handlers.interview import router as interview_router
from handlers.stats import router as stats_router

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

async def main():
    await init_db()
    dp.include_router(start_router)
    dp.include_router(setup_router)
    dp.include_router(interview_router)
    dp.include_router(stats_router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
