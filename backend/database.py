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
