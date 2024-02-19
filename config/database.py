import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

MONGODB_CONNECTION_URL = os.getenv("MONGODB_CONNECTION_URL")
client = AsyncIOMotorClient(MONGODB_CONNECTION_URL)
db = client['chat_db']
