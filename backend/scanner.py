import asyncio
import datetime

import database
import feedparser
import httpx
from dateutil import parser as date_parser
from logger_config import log
from sqlalchemy.orm import Session


DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

shared_client = httpx.AsyncClient(
    headers=DEFAULT_HEADERS, timeout=20.0, follow_redirects=True
)


async def fetch_and_save_feed(db: Session, feed_url: str):
    try:
        response = await shared_client.get(feed_url)
        response.raise_for_status()
        content = response.text
    except Exception as e:
        log.error(f"Error fetching {feed_url}: {e}")
        return None

    # Parse the feed content
    d = await asyncio.to_thread(feedparser.parse, content)

    def _db_operations():
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

        incoming_links = [e.link for e in d.entries if hasattr(e, "link")]
        incoming_titles = [e.get("title", "No Title") for e in d.entries]

        existing_records = (
            db.query(database.Article.link, database.Article.title)
            .filter(database.Article.feed_id == feed.id)
            .filter(
                (database.Article.link.in_(incoming_links))
                | (database.Article.title.in_(incoming_titles))
            )
            .all()
        )

        existing_links = {r.link for r in existing_records if r.link}
        existing_titles = {r.title for r in existing_records if r.title}

        new_articles = []

        for entry in d.entries:
            link = entry.link
            title = entry.get("title", "No Title")

            if link not in existing_links and title not in existing_titles:
                pub_date = None
                date_str = (
                    entry.get("published")
                    or entry.get("pubDate")
                    or entry.get("updated")
                )
                if date_str:
                    try:
                        pub_date = date_parser.parse(date_str)
                    except Exception:
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

        if new_articles:
            db.add_all(new_articles)
            db.commit()

        db.refresh(feed)
        return feed

    return await asyncio.to_thread(_db_operations)
