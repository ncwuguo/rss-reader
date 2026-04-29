import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

SQLALCHEMY_DATABASE_URL = "sqlite:///./rss_reader.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class Feed(Base):
    __tablename__ = "feeds"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    url = Column(String, unique=True, index=True)
    description = Column(String, nullable=True)
    unread_count = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.datetime.utcnow)

    articles = relationship(
        "Article", back_populates="feed", cascade="all, delete-orphan"
    )


class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True)
    feed_id = Column(Integer, ForeignKey("feeds.id"))
    title = Column(String, index=True)
    link = Column(String, index=True)
    description = Column(Text, nullable=True)
    pub_date = Column(DateTime, nullable=True)
    is_read = Column(Boolean, default=False)
    is_starred = Column(Boolean, default=False)

    feed = relationship("Feed", back_populates="articles")

    __table_args__ = (
        Index("idx_pubdate_id", "pub_date", "id"),
        Index("idx_feed_pubdate_id", "feed_id", "pub_date", "id"),
    )


class StarredArticle(Base):
    __tablename__ = "starred_articles"

    id = Column(Integer, primary_key=True, index=True)
    feed_title = Column(String, nullable=True)
    title = Column(String, index=True)
    link = Column(String, unique=True, index=True)
    description = Column(Text, nullable=True)
    pub_date = Column(DateTime, nullable=True)
    saved_at = Column(DateTime, default=datetime.datetime.utcnow)


def init_db():
    Base.metadata.create_all(bind=engine)
    # Performance optimization: Use SQLite triggers to natively manage unread_count
    from sqlalchemy import text

    with engine.connect() as conn:
        # Enable WAL mode to improve concurrent read/write performance
        conn.execute(text("PRAGMA journal_mode=WAL;"))
        # Increase busy timeout for connection retries (in milliseconds)
        conn.execute(text("PRAGMA busy_timeout=5000;"))
        # Optimize synchronous mode for better I/O throughput
        conn.execute(text("PRAGMA synchronous=NORMAL;"))

        # 0. One-time historical data cleanup: Calibrate current unread counts for all Feeds.
        # Can be commented out after the first run, as triggers will handle subsequent updates.
        # conn.execute(
        #     text("""
        # UPDATE feeds
        # SET unread_count = (
        #     SELECT COUNT(*) FROM articles
        #     WHERE articles.feed_id = feeds.id AND articles.is_read = 0
        # );
        # """)
        # )

        # 1. Increment feed unread_count when a new unread article is inserted
        conn.execute(
            text("""
        CREATE TRIGGER IF NOT EXISTS trg_article_insert_unread
        AFTER INSERT ON articles
        WHEN NEW.is_read = 0
        BEGIN
            UPDATE feeds SET unread_count = unread_count + 1 WHERE id = NEW.feed_id;
        END;
        """)
        )

        # 2. Adjust feed unread_count dynamically when an article's read status changes
        conn.execute(
            text("""
        CREATE TRIGGER IF NOT EXISTS trg_article_update_unread
        AFTER UPDATE OF is_read ON articles
        WHEN OLD.is_read != NEW.is_read
        BEGIN
            UPDATE feeds 
            SET unread_count = unread_count + CASE WHEN NEW.is_read = 1 THEN -1 ELSE 1 END 
            WHERE id = NEW.feed_id;
        END;
        """)
        )

        # 3. Decrement feed unread_count when an unread article is deleted
        conn.execute(
            text("""
        CREATE TRIGGER IF NOT EXISTS trg_article_delete_unread
        AFTER DELETE ON articles
        WHEN OLD.is_read = 0
        BEGIN
            UPDATE feeds SET unread_count = unread_count - 1 WHERE id = OLD.feed_id;
        END;
        """)
        )

        conn.commit()
