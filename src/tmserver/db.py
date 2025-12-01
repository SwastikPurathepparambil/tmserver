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
    users_set = None
    resumes_set = None

db = Database()

#Requires atlas mongo db connection -> thats what we have for project
async def connect_to_db_mongo():
    try:
        mongodb_id = os.getenv("MONGO_URI")

        if not mongodb_id:
            raise RuntimeError("MONGO_URI is not available.")

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

#indexes makes db lookup much more effecient (I read 100x)
async def create_indexes():
    try:
        if db.users_set is not None:
            await db.users_set.create_index("google_sub", unique=True)
            await db.users_set.create_index("email")

        if db.resumes_set is not None:
            await db.resumes_set.create_index([("user_id", 1), ("is_deleted", 1)])
            await db.resumes_set.create_index("date_made")
    except Exception as e3:
        print(f"Error with indexes: {e3}")

def get_database():
    return db