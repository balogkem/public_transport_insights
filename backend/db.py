import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def get_connection():
    """Get a PostgreSQL connection using DATABASE_URL from .env"""
    url = os.getenv("DATABASE_URL")
    if not url:
        return None
    try:
        return psycopg2.connect(url)
    except Exception as e:
        print(f"Database connection error: {e}")
        return None
