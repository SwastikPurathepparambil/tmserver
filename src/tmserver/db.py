from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure
from dotenv import load_dotenv
import os
from typing import Optional
import asyncio
import certifi
load_dotenv()
class Database:
    client: Optional[AsyncIOMotorClient] = None
    database = None
    users_collection = None
    resumes_collection = None
db = Database()

async def connect_to_db_mongo():
    try:
        mongodb_id = os.getenv("MONGODB_ID")

        if not mongodb_id:
            raise RuntimeError("MONGODB_ID is not available.")

        db.client = AsyncIOMotorClient(mongodb_id,tlsCAFile=certifi.where())

        await db.client.admin.command("ping")

        db_name = os.getenv("DATABASE_NAME", "taylorMake")
        db.database = db.client[db_name]
        db.users_set = db.database.users
        db.resumes_set = db.database.resumes
        await create_indexes()
    except ConnectionFailure as e1:
        print(f"Connection Failure: {e1}")
        raise
    except Exception as e2:
        print(f"Unexpected error: {e2}")
        raise


async def disconnect_mongo():
    if db.client:
        db.client.close()
        print("Disconnected from MongoDB")


async def create_indexes():
    try:
        await db.users_set.create_index("google_subscription", unique=True)
        await db.users_set.create_index("email")
        await db.resumes_set.create_index([("user_id", 1), ("is_deleted", 1)])
        await db.resumes_set.create_index("date_made")
    except Exception as e3:
        print(f"Error with indexes: {e3}")

def get_database():
    return db