from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Your verified working password
SQLALCHEMY_DATABASE_URL="postgresql://knmiet_db_user:LPsYZcZX70OUqScLHufnTZRjAH7H5W9A@dpg-d6e8h27pm1nc73aasstg-a/knmiet_db"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()