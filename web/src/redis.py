from redis.asyncio import Redis

from settings import settings

redis = Redis.from_url(settings.redis_url.unicode_string())

class RedisKeys:
    user_info = 'user_info'
    ready_to_connect = 'ready_to_connect'
    send_key = 'send_key'
    sended_code = 'sended_code'
    answer = 'answer'
    status = 'status'
    authed = 'authed'
    logout = 'logout'
    phone = 'phone'
