import os.path

from src.redis import redis, RedisKeys


async def is_ready_connect():
    if not await redis.get(RedisKeys.ready_to_connect):
        return False
    # if not os.path.exists('main.session'):
    #     return False
    return True