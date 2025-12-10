import asyncio

from resync.core.async_cache import AsyncTTLCache


async def test():
    cache = AsyncTTLCache()
    await cache.stop()
    print("Cache initialized successfully")


if __name__ == "__main__":
    asyncio.run(test())
