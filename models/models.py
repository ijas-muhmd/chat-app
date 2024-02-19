from pydantic import BaseModel


class User(BaseModel):
    username: str


class Message(BaseModel):
    sender: str
    recipient: str
    message: str
    delivered: bool = False
    