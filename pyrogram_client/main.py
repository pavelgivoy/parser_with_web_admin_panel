import logging
import os.path
from asyncio import run
from pyrogram.errors.exceptions.unauthorized_401 import Unauthorized

from src.client import Application
from src.redis import redis, RedisKeys, sync_redis
from settings import settings


async def main():
    while True:
        try:
            await redis.set(RedisKeys.ready_to_connect, 1)
            app = Application()
            try:
                await app.initialize_pyrogram()
            except Exception as err:
                logging.exception(err)

            await app.start_loop()
        except Unauthorized as err:
            logging.exception(err)
            if os.path.exists(f'{settings.session_name}.session'):
                os.remove(f'{settings.session_name}.session')
            await redis.delete(RedisKeys.authed)
            await redis.delete(RedisKeys.ready_to_connect)

        finally:
            sync_redis.delete(RedisKeys.ready_to_connect)
            logging.info('delete ready status')


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(levelname)s %(message)s',
                        filename='pyrogram_log.log'
                        )

    run(main())
