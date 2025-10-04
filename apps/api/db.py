import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()  # reads .env at project root

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL not set in .env")

# Create an engine; future=True gives modern SQLAlchemy behavior
engine = create_engine(DATABASE_URL, future=True)

def ping_db() -> bool:
    """Return True if DB responds to a simple SELECT 1."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False

