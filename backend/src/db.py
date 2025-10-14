from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from .models import Base  
import logging
from dotenv import load_dotenv
import os
load_dotenv()

DB_URL = os.environ["DB_URL"]
SQLALCHEMY_DATABASE_URL = (
    DB_URL
)

# Create standard (synchronous) engine
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    echo=True,
    pool_pre_ping=True,
    pool_recycle=1800, 
    connect_args={},  
)

# Session factory
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

def get_db():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

# Create extensions (idempotent)
def create_extensions():
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))
        conn.commit()

# Create embedding indexes (idempotent)
def create_embedding_index():
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS indexing_vectors
                    ON embedding
                    USING hnsw (embedding vector_cosine_ops)
                    WITH (m = 16, ef_construction = 64);
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS embedding_article_id_idx
                    ON embedding (article_id);
                    """
                )
            )
    except Exception as e:
        logging.exception("Error creating embedding indexes: %s", e)

# Create all tables and indexes (idempotent)
def create_all_tables():
    # create tables
    Base.metadata.create_all(bind=engine)
    # create indexes
    create_embedding_index()
