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
    # --- 性能优化：利用底层的 SQLite 触发器（Trigger）接管 unread_count ---
    from sqlalchemy import text

    with engine.connect() as conn:
        # 开启 WAL 模式，提升并发读写性能
        conn.execute(text("PRAGMA journal_mode=WAL;"))
        # 提升忙碌时的重试超时时间 (单位：毫秒)
        conn.execute(text("PRAGMA busy_timeout=5000;"))
        # 开启同步优化
        conn.execute(text("PRAGMA synchronous=NORMAL;"))

        # 0. 历史脏数据大清洗：一次性精准校准所有 Feed 的当前未读数。运行过后可以注释掉，因为后续触发器会自动维护。
        # conn.execute(
        #     text("""
        # UPDATE feeds
        # SET unread_count = (
        #     SELECT COUNT(*) FROM articles
        #     WHERE articles.feed_id = feeds.id AND articles.is_read = 0
        # );
        # """)
        # )

        # 1. 插入文章时，如果是未读（0），则所属源的未读数 +1
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

        # 2. 更新文章时，如果阅读状态发生变化，动态加减未读数
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

        # 3. 删除文章时，如果被删文章是未读（0），则所属源的未读数 -1
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
