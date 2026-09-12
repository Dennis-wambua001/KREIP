from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Local SQLite file database backend with production connection options
SQLALCHEMY_DATABASE_URL = "sqlite:///./kreip_platform.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False},
    pool_pre_ping=True
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()