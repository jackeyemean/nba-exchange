import os
from dotenv import load_dotenv
import psycopg2
import redis

load_dotenv()

DATABASE_URL = os.getenv("ENGINE_DATABASE_URL", os.getenv("DATABASE_URL", ""))
REDIS_URL = os.getenv("ENGINE_REDIS_URL", os.getenv("REDIS_URL", "redis://localhost:6379/0"))
SCALING_FACTOR = float(os.getenv("SCALING_FACTOR", "2.08"))


def get_db_connection():
    return psycopg2.connect(DATABASE_URL)


def get_redis():
    return redis.Redis.from_url(REDIS_URL, decode_responses=True)
