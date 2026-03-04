"""
Environment variables and connection helpers for the engine.
Provides DATABASE_URL, SCALING_FACTOR, and get_db_connection().
"""

import os

import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("ENGINE_DATABASE_URL", os.getenv("DATABASE_URL", ""))
SCALING_FACTOR = float(os.getenv("SCALING_FACTOR", "2.08"))


def get_db_connection():
    """Return a new PostgreSQL connection."""
    return psycopg2.connect(DATABASE_URL)
