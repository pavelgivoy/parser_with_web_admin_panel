import asyncio
import json

from fastapi import APIRouter, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from starlette import status
from starlette.requests import Request
from starlette.responses import Response

from ..utils import is_ready_connect
from ..redis import redis, RedisKeys
from ..schemes.redis_values import UserInfo

router = APIRouter()

templates = Jinja2Templates('templates/main')


@router.get('/', name='main_page')
async def index(request: Request):
    is_auth = await redis.get(RedisKeys.authed)
    is_active = await redis.get(RedisKeys.ready_to_connect)
    return templates.TemplateResponse('index.html',
                                      {'request': request, 'is_auth': bool(is_auth), 'is_active': bool(is_active)}
                                      )


@router.get('/logout')
async def logout(request: Request):
    await redis.set(RedisKeys.logout, 1)
    await asyncio.sleep(4)
    return RedirectResponse('/')

@router.get('/change_answer')
async def change_answer(request: Request):
    answer = await redis.get(RedisKeys.answer) or b''
    answer = answer.decode()
    return templates.TemplateResponse('change_answer.html',
                                      {'request': request, 'answer': answer}
                                      )


@router.post('/change_answer')
async def change_answer_post(request: Request, answer: str = Form()):
    await redis.set(RedisKeys.answer, answer)
    return templates.TemplateResponse('change_answer.html',
                                      {'request': request, 'answer': answer}
                                      )


@router.get('/auth')
async def auth(request: Request):
    phone = await redis.get(RedisKeys.phone)
    if phone:
        phone = phone.decode()
    else:
        phone = ''
    return templates.TemplateResponse('auth.html', {'request': request, 'phone': phone})


@router.post('/send_code')
async def send_code(request: Request, phone: str = Form()):
    await redis.set(RedisKeys.phone, phone)
    await redis.set(RedisKeys.send_key, 1)
    return RedirectResponse('/auth', status_code=status.HTTP_302_FOUND)


@router.post('/send_key')
async def send_key(auth_code: str = Form()):
    await redis.set(RedisKeys.sended_code, auth_code)
    await asyncio.sleep(5)
    return RedirectResponse('/', status_code=status.HTTP_302_FOUND)
