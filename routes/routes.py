import json
from typing import Dict
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from bson import ObjectId

from config.database import db
from models.models import User, Message

router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, username: str):
        if username in self.active_connections:
            await websocket.close(code=4001, reason='Username already in use')
            return False
        await websocket.accept()
        self.active_connections[username] = websocket
        # Deliver undelivered messages
        async for message in db['messages'].find({'recipient': username, 'delivered': False}):
            await websocket.send_text(json.dumps({'sender': message['sender'], 'message': message['message']}))
            await db['messages'].update_one({'_id': message['_id']}, {'$set': {'delivered': True}})
        return True

    async def disconnect(self, username: str):
        del self.active_connections[username]

    async def send_message(self, message: str, sender: str, recipient: str):
        websocket = self.active_connections.get(recipient)
        if websocket:
            await websocket.send_text(json.dumps({'sender': sender, 'message': message}))
            return True
        else:
            return False


manager = ConnectionManager()


@router.post("/create-users/")
async def create_user(user: User):
    user = dict(user)
    existing_user = await db['users'].find_one({'username': user['username']})
    if existing_user:
        return {"error": "A user with this username already exists"}
    user['_id'] = str(ObjectId())
    await db['users'].insert_one(user)
    return user


@router.get("/get-users/")
async def get_users():
    users = []
    async for user in db['users'].find():
        user['_id'] = str(user['_id'])
        users.append(user)
    return users


@router.get("/user-exists/{username}")
async def user_exists(username: str):
    existing_user = await db['users'].find_one({'username': username})
    if existing_user is None:
        return {"exists": False}
    else:
        return {"exists": True}


@router.post("/send-messages/")
async def send_message(message: Message):
    message = dict(message)
    message['_id'] = str(ObjectId())
    delivered = await manager.send_message(message['message'], message['sender'], message['recipient'])
    message['delivered'] = delivered if delivered else False
    await db['messages'].insert_one(message)
    return message


@router.get("/get-messages/")
async def get_messages(sender: str = None, recipient: str = None):
    messages = []
    query = {
        '$or': [
            {'sender': sender, 'recipient': recipient},
            {'sender': recipient, 'recipient': sender}
        ]
    }

    async for message in db['messages'].find(query):
        message['_id'] = str(message['_id'])
        messages.append(message)
    return messages


@router.websocket("/ws/{username}")
async def websocket_endpoint(websocket: WebSocket, username: str):
    connected = await manager.connect(websocket, username)
    if not connected:
        return # Exit if connection wasn't successful due to username conflict
    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            recipient = message_data["recipient"]
            message_text = message_data["message"]

            delivered = await manager.send_message(message_text, username, recipient)
            db_message = {'sender': username, 'recipient': recipient, 'message': message_text, 'delivered': delivered}
            await db['messages'].insert_one(db_message)

    except WebSocketDisconnect:
        await manager.disconnect(username)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
