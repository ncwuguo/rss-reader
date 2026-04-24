import asyncio
import datetime

import database
import feedparser
import httpx
from dateutil import parser as date_parser
from sqlalchemy.orm import Session


async def fetch_and_save_feed(db: Session, feed_url: str):
    # Use httpx for async fetching
    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            response = await client.get(feed_url)
            response.raise_for_status()
            content = response.text
        except Exception as e:
            print(f"Error fetching {feed_url}: {e}")
            return None

    # Parse the feed content
    d = await asyncio.to_thread(feedparser.parse, content)

    # Check if feed exists, or create it
    feed = db.query(database.Feed).filter(database.Feed.url == feed_url).first()
    if not feed:
        feed = database.Feed(
            title=d.feed.get("title", feed_url),
            url=feed_url,
            description=d.feed.get("description", ""),
        )
        db.add(feed)
        db.commit()
        db.refresh(feed)

    # --- 优化开始：批量预取已存在的文章 ---
    # 1. 收集本次抓取到的所有 link 和 title
    incoming_links = [e.link for e in d.entries if hasattr(e, "link")]
    incoming_titles = [e.get("title", "No Title") for e in d.entries]

    # 2. 一次性查询当前 Feed 下已存在的记录（仅查询必要字段以节省内存）
    existing_records = (
        db.query(database.Article.link, database.Article.title)
        .filter(database.Article.feed_id == feed.id)
        .filter(
            (database.Article.link.in_(incoming_links))
            | (database.Article.title.in_(incoming_titles))
        )
        .all()
    )

    # 3. 转换为集合以实现快速查找
    existing_links = {r.link for r in existing_records if r.link}
    existing_titles = {r.title for r in existing_records if r.title}

    new_articles = []
    # --- 优化结束 ---

    for entry in d.entries:
        # Get link and title
        link = entry.link
        title = entry.get("title", "No Title")

        # 4. 在内存中比对，不再执行数据库查询
        if link not in existing_links and title not in existing_titles:
            pub_date = None
            # Try different date fields commonly used in RSS/Atom
            date_str = (
                entry.get("published") or entry.get("pubDate") or entry.get("updated")
            )
            if date_str:
                try:
                    pub_date = date_parser.parse(date_str)
                except:  # noqa: E722
                    pub_date = datetime.datetime.utcnow()
            else:
                pub_date = datetime.datetime.utcnow()

            article = database.Article(
                feed_id=feed.id,
                title=title,
                link=link,
                description=entry.get("summary", entry.get("description", "")),
                pub_date=pub_date,
            )
            new_articles.append(article)

    # 5. 批量插入新文章
    if new_articles:
        db.add_all(new_articles)
        db.commit()

    # Update unread count
    unread_count = (
        db.query(database.Article)
        .filter(database.Article.feed_id == feed.id)
        .filter(database.Article.is_read == False)
        .count()
    )
    feed.unread_count = unread_count
    db.commit()

    return feed
