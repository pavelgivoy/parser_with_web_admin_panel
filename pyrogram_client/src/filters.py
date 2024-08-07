import logging

from pyrogram import filters
from sqlalchemy import select

from src.db.models import Base, Chat, PictureChat



async def _chats_filter(_, __, m):
    found_chat_id = m.chat.id
    logging.debug(f"Chat id is {found_chat_id} and message id is {m.id}")
    async with Base.session() as session:
        chats = await session.scalars(select(Chat))
        chats = chats.all()
        digit_chats = list(map(lambda chat: chat.id, chats))
        logging.debug(f"The search will be provided between selected chats: {digit_chats}")

        for chat in chats:
            logging.debug(f'Loop through chat id: {chat.id}')
            if m.chat.id == chat.id and chat.is_active:
                logging.debug(f'Chat with id {chat.id} is passed. Loop done')
                return True
        logging.debug('No chats found for this scope')
        return False

async def _picture_chats_filter(_, __, m):
    found_chat_id = m.chat.id
    logging.debug(f"Chat id is {found_chat_id} and message id is {m.id}")
    async with Base.session() as session:
        chats = await session.scalars(select(PictureChat))
        chats = chats.all()
        digit_chats = list(map(lambda chat: chat.id, chats))
        logging.debug(f"The search will be provided between selected chats: {digit_chats}")
        for chat in chats:
            if m.chat.id == chat.id and chat.is_active:
                logging.debug(f'Chat with id {chat.id} is passed. Loop done')
                return True
        logging.debug('No chats found for this scope')
        return False


chats_filter = filters.create(_chats_filter)
picture_chats_filter = filters.create(_picture_chats_filter)
