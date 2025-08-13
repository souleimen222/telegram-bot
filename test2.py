import asyncio
from sofascore_wrapper.api import SofascoreAPI

async def main():
    api = SofascoreAPI()
    data = await api._get("/sport/football/events/live")
    print(data)  # <-- Inspect full JSON here
    await api.close()

asyncio.run(main())
