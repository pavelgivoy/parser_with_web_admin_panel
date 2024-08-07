import asyncio
import logging
import pathlib
import os
import re
from datetime import datetime, timedelta

from pyrogram import Client, ContinuePropagation, raw, filters
import pyrogram
from pyrogram.types import Message
from pyrogram.raw.types import UpdateNewMessage, UpdateNewChannelMessage
from apscheduler.schedulers.asyncio import AsyncIOScheduler as Scheduler
from pyrogram.errors import PhoneNumberInvalid
from sqlalchemy import select, update, delete

from settings import settings
from src.redis import redis, RedisKeys
from .db.models import Base, Keyword, Chat, PictureChat
from .filters import chats_filter, picture_chats_filter
from .scheduler_task import answer_in


class StopError(Exception): pass

class Application:
    def __init__(self):
        self.client = Client(name='main', api_id=settings.api_id, api_hash=settings.api_hash)
        self.scheduler = Scheduler()
        # self.scheduler.start()
        # structure is chat_id: datetime with microseconds
        self.prev_received_message_dates = {}
        self.cur_received_message_dates = {}

    async def initialize_pyrogram(self):
        if not self.client.is_connected:
            await self.client.connect()

        await self.on_message_handler()
        await self.client.invoke(raw.functions.updates.GetState())
        await self.client.initialize()
        await self.client.send_message('me', 'started')

        await redis.set(RedisKeys.ready_to_connect, 1)
        await redis.set(RedisKeys.authed, 1)

    async def on_message_handler(self):
        @self.client.on_raw_update()
        async def write_incoming_update(client: Client, update: pyrogram.types.Update, users, chats):
            if isinstance(update, UpdateNewChannelMessage | UpdateNewMessage):
                logging.debug('-----New incoming message update-----')
                logging.debug(update)
                cur_date = datetime.now()
                # logging.debug(update.message.date) # this works!!!
                peer_info = update.message.peer_id
                chat_id = peer_info.channel_id if isinstance(update, UpdateNewChannelMessage) else peer_info.chat_id
                self.cur_received_message_dates[chat_id] = cur_date
                logging.debug('Date of current received message is saved in the dict. See the dict below')
                logging.debug(str(self.cur_received_message_dates))
            raise ContinuePropagation

        @self.client.on_message(filters.incoming)
        async def check_throttling(client: Client, message: Message):
            chat_id = message.chat.id
            logging.debug(f'The message chat id is {chat_id} and the message id is {message.id}')
            # we don't do conversations with users
            # so we just looking for the required chat id saved in the dict
            trunc100_chat_id = int(str(chat_id)[3:]) # -100... -> ...
            truncmin1_chat_id = chat_id // -1
            logging.debug(str(trunc100_chat_id) + '; ' + str(truncmin1_chat_id))
            if trunc100_chat_id in self.cur_received_message_dates:
                self.cur_received_message_dates[chat_id] = self.cur_received_message_dates[trunc100_chat_id]
                self.cur_received_message_dates.pop(trunc100_chat_id)
            if truncmin1_chat_id in self.cur_received_message_dates:
                self.cur_received_message_dates[chat_id] = self.cur_received_message_dates[truncmin1_chat_id]
                self.cur_received_message_dates.pop(truncmin1_chat_id)
            prev_msg = self.prev_received_message_dates[chat_id] if chat_id in self.prev_received_message_dates.keys() else None
            if prev_msg is None:
                logging.debug(f'Nothing to compare with, as it is the first message in the group {chat_id}')
                self.prev_received_message_dates[chat_id] = self.cur_received_message_dates[chat_id]
                message.continue_propagation() # nothing to compare with, as it is the first message in the group
            prev_msg_date = self.prev_received_message_dates[chat_id]
            logging.debug(f'Previous message date: {prev_msg_date.strftime("%Y-%m-%d %H:%M:%S,%f")}')
            cur_msg_date = self.cur_received_message_dates[chat_id]
            logging.debug(f'Current message date: {cur_msg_date.strftime("%Y-%m-%d %H:%M:%S,%f")}')
            date_diff = cur_msg_date - prev_msg_date
            date_diff_in_secs = date_diff.total_seconds()
            if date_diff_in_secs <= 0.1:
                logging.debug('The time difference between compared messages is less than 0.1s. The message was throttled')
                message.stop_propagation()
            else:
                logging.debug('The time difference check is passed. Going deep to next handlers')
                self.prev_received_message_dates[chat_id] = self.cur_received_message_dates[chat_id]
                message.continue_propagation()

        @self.client.on_message(chats_filter & filters.incoming & filters.photo)
        async def photo_answer(client: Client, message: Message):
            logging.info('The message contains a photo')
            async with Base.session() as session:
                keywords = await session.scalars(select(Keyword).filter_by(chat_id=message.chat.id))
                for keyword in keywords:
                    logging.debug(f'Found keyword: {keyword}')
                    if keyword.if_picture:
                        logging.debug('The keyword passed the picture filter')
                        msg = await client.send_message(chat_id=message.chat.id, text=keyword.answer)
                        logging.debug(f'Message is sent. Time of sending is {msg.date}')
                        script_exec_time = msg.date - message.date
                        logging.debug(f'Time of script exec is {script_exec_time.total_seconds()} secs')
                        await session.execute(update(Chat).filter_by(id=message.chat.id).values(is_active=False))
                        await session.commit()
            # async with Base.session() as session:
            #     await session.execute(update(PictureChat).filter_by(id=message.chat.id).values(is_active=False))
            #     await session.commit()
            # async with Base.session() as session:
            #     await session.execute(update(Chat).filter_by(id=message.chat.id).values(is_active=False))
            #     await session.commit()

        @self.client.on_message(chats_filter & filters.incoming)
        async def read_message(client, message):
            logging.debug('callback receive')
            async with Base.session() as session:
                keywords = await session.scalars(select(Keyword).filter_by(chat_id=message.chat.id))

            for keyword in keywords:
                logging.debug(f'Found keyword: {keyword}')
                try:
                    text = message.text
                    try:
                        text = message.text.lower()
                    except Exception:
                        pass
                    new_keywords: list[str] = keyword.keyword.split(',')
                    for _keyword in new_keywords:
                        trans_table = {'.': '\\.', '^': '\\^', '$': '\\$', '*': '\\*', '+': '\\+', '?': '\\?',
                                       '{': '\\{', '}': '\\}', '[': '\\[',
                                       ']': '\\]', '\\': '\\\\', '|': '\\|', '(': '\\(', ')': '\\)'}
                        _keyword = _keyword.translate(_keyword.maketrans(trans_table))
                        if _keyword:
                            if _keyword[0].isalnum():
                                _keyword = r'\b' + _keyword
                            if _keyword[-1].isalnum():
                                _keyword += r'\b'
                            logging.debug(f'Finally translated keyword: {_keyword}')

                        if re.search(_keyword, text):
                            '''delete in future'''
                            logging.debug('The translated keyword is in the message text')
                            async with Base.session() as session:
                                is_active = await session.scalar(select(Chat.is_active).filter_by(id=keyword.chat.id))
                                logging.debug(f'The selected chat is active: {is_active}')
                                if keyword.chat.one_time_answer:
                                    await session.execute(
                                        update(Chat).filter_by(id=message.chat.id).values(is_active=False))
                                    await session.commit()
                                    try:
                                        await session.execute(
                                            update(PictureChat).filter_by(id=message.chat.id).values(is_active=False))
                                        await session.commit()
                                    except Exception: pass
                            if is_active:
                                logging.debug('All filters are passed. Time to send the message')
                                if keyword.answer_in_seconds < 0.1:
                                    logging.debug('Sending the message right now!')
                                    await client.send_message(chat_id=message.chat.id, text=keyword.answer, )
                                    now_time = datetime.datetime.now()
                                    logging.debug(f'Message is sent. Time of sending is {now_time.strftime("%Y-%m-%d %H:%M:S,%f")}')
                                    script_exec_time = now_time - self.cur_received_message_dates[message.chat.id]
                                    logging.debug(f'Time of script exec is {script_exec_time.total_seconds()} secs')
                                else:
                                    logging.debug('Making a scheduled message...')
                                    # self.scheduler.add_job(answer_in, trigger='date',
                                    #                        run_date=datetime.now() + timedelta(seconds=keyword.answer_in_seconds),
                                    #                        kwargs=dict(client=self.client, answer=keyword.answer,
                                    #                                    chat_id=message.chat.id, mess_id=message.id, message=message))
                                    # self.scheduler.start()
                                    await asyncio.sleep(keyword.answer_in_seconds)
                                    await client.send_message(chat_id=message.chat.id, text=keyword.answer, )
                                    now_time = datetime.datetime.now()
                                    logging.debug(f'Message is sent. Time of sending is {now_time.strftime("%Y-%m-%d %H:%M:S,%f")}')
                                    script_exec_time = now_time - self.cur_received_message_dates[message.chat.id]
                                    logging.debug(f'Time of script exec is {script_exec_time.total_seconds()} secs')
                                # if keyword.chat.one_time_answer:
                                #     async with Base.session() as session:
                                #         await session.execute(update(Chat).filter_by(id=message.chat.id).values(is_active=False))
                                #         await session.commit()
                                # raise StopError
                        else:
                            logging.debug('The translated keyword is not in the message text')
                except StopError:
                    break
                except Exception:
                    pass
            logging.info('callback processed')

        @self.client.on_message(filters.incoming)
        async def on_fail_check(client: Client, message: Message):
            logging.debug('No handlers affected by the message')

    async def start_loop(self):
        while True:
            if await redis.get(RedisKeys.send_key):
                logging.info('receive send code signal')
                if not self.client.is_connected:
                    await self.client.connect()
                phone = await redis.get(RedisKeys.phone)
                try:
                    code_hash = await self.client.send_code(phone.decode())
                    await redis.set(RedisKeys.code_hash, code_hash.phone_code_hash)
                except PhoneNumberInvalid:
                    pass
                await redis.delete(RedisKeys.send_key)
            elif code := (await redis.get(RedisKeys.sended_code)):
                try:
                    logging.info('receive sign in signal')
                    code = code.decode()
                    code_hash = await redis.get(RedisKeys.code_hash)
                    code_hash = code_hash.decode()
                    phone = await redis.get(RedisKeys.phone)
                    await self.client.sign_in(phone.decode(), code_hash, code)

                    await self.on_message_handler()
                    await self.initialize_pyrogram()
                finally:
                    await redis.delete(RedisKeys.sended_code)
            elif await redis.get(RedisKeys.logout):
                logging.info('receive logout signal')
                try:
                    await self.client.stop()
                except Exception:
                    ...
                if os.path.exists('main.session'):
                    os.remove('main.session')
                await redis.delete(RedisKeys.authed)
                await redis.delete(RedisKeys.logout)

            await asyncio.sleep(2)
