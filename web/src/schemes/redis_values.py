from pydantic import BaseModel


class UserInfo(BaseModel):
    phone: str = ''
