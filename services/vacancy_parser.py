import re
import aiohttp

async def parse_hh_vacancy(url: str) -> dict:
    match = re.search(r'vacancy/(\d+)', url)
    if not match:
        raise ValueError("Неверная ссылка")
    vac_id = match.group(1)
    api_url = f"https://api.hh.ru/vacancies/{vac_id}"
    async with aiohttp.ClientSession() as session:
        async with session.get(api_url) as resp:
            data = await resp.json()
    title = data.get('name', 'Неизвестно')
    desc = data.get('description', '')
    import html
    desc = html.unescape(desc)
    desc = re.sub(r'<[^>]+>', ' ', desc)
    return {"title": title, "description": desc, "url": url}
