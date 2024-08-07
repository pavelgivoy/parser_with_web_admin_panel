from pyrogram import Client


async def answer_in(client: Client, answer: str, chat_id: int, mess_id: int):
    await client.send_message(chat_id=chat_id, text=answer,)