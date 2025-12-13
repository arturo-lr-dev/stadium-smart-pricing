import sqlalchemy
from sqlalchemy import create_engine, text
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.config import get_settings

settings = get_settings()
db_url = f"postgresql://{settings.database.user}:{settings.database.password}@{settings.database.host}:{settings.database.port}/{settings.database.name}"
engine = create_engine(db_url)

with engine.connect() as conn:
    print("Enumerations in database:")
    result = conn.execute(text("SELECT t.typname, e.enumlabel FROM pg_type t JOIN pg_enum e ON t.oid = e.enumtypid ORDER BY t.typname, e.enumlabel;"))
    for row in result:
        print(row)
