import asyncio, logging
from openai import AsyncOpenAI
from config import DEEPSEEK_API_KEY

logger = logging.getLogger(__name__)
client = AsyncOpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

async def ai_request(messages, max_retries=2, max_tokens=80, stop=None):
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            response = await client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.7,
                stop=stop
            )
            return response.choices[0].message.content
        except Exception as e:
            last_exc = e
            logger.error(f"DeepSeek attempt {attempt+1}: {e}")
            await asyncio.sleep(2 ** attempt)
    raise last_exc
