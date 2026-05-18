import asyncio
import datetime
import re

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
    headers=DEFAULT_HEADERS,
    timeout=5.0,
    follow_redirects=True,
    limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
)


async def fetch_and_save_feed(db: Session, feed_url: str):
    feed = db.query(database.Feed).filter(database.Feed.url == feed_url).first()
    mode = (feed.fetch_mode if feed and feed.fetch_mode else "rss").lower()

    if mode == "issn":
        return await _fetch_by_issn(db, feed_url)
    else:
        return await _fetch_by_rss(db, feed_url)


def _get_existing_keys(db: Session, feed_id: int, links: list, titles: list) -> tuple:
    if not links and not titles:
        return set(), set()
    records = (
        db.query(database.Article.link, database.Article.title)
        .filter(database.Article.feed_id == feed_id)
        .filter(
            (database.Article.link.in_(links)) | (database.Article.title.in_(titles))
        )
        .all()
    )
    return {r.link for r in records if r.link}, {r.title for r in records if r.title}


def _save_new_articles(
    db: Session, feed: database.Feed, items: list, extract_fn
) -> int:
    parsed = []
    for item in items:
        entry = extract_fn(item)
        if entry and entry.get("link"):
            parsed.append(entry)

    links = [e["link"] for e in parsed]
    titles = [e["title"] for e in parsed]
    existing_links, existing_titles = _get_existing_keys(db, feed.id, links, titles)

    new_articles = []
    for entry in parsed:
        if entry["link"] in existing_links or entry["title"] in existing_titles:
            continue
        new_articles.append(
            database.Article(
                feed_id=feed.id,
                title=entry["title"],
                link=entry["link"],
                description=entry.get("description", ""),
                pub_date=entry.get("pub_date") or datetime.datetime.utcnow(),
            )
        )

    if new_articles:
        db.add_all(new_articles)
        db.commit()
    return len(new_articles)


async def _fetch_by_issn(db: Session, feed_url: str):
    """Fetch articles via Crossref ISSN lookup."""
    feed = db.query(database.Feed).filter(database.Feed.url == feed_url).first()
    if not feed or not feed.issn:
        log.warning(f"No ISSN found for feed {feed_url}, skipping.")
        return feed

    issn = feed.issn.strip()
    url = f"https://api.crossref.org/journals/{issn}/works"
    params = {"sort": "created", "order": "desc", "rows": 20}
    polite_headers = {
        "User-Agent": "RSSReader/1.0 (mailto:rss_reader@example.com)",
    }

    # Async HTTP with retry for rate-limiting (429)
    items = []
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = await shared_client.get(
                url, params=params, headers=polite_headers, timeout=5.0
            )
            if response.status_code == 429:
                if attempt < max_retries - 1:
                    retry_after = int(
                        response.headers.get("Retry-After", 2 ** (attempt + 1))
                    )
                    log.warning(
                        f"Crossref rate limited for ISSN {issn}, retrying in {retry_after}s (attempt {attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(retry_after)
                    continue
                else:
                    log.error(
                        f"Crossref request failed for ISSN {issn}: 429 Too Many Requests after {max_retries} attempts"
                    )
                    return feed
            response.raise_for_status()
            items = response.json().get("message", {}).get("items", [])
            break
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429 and attempt < max_retries - 1:
                retry_after = int(
                    e.response.headers.get("Retry-After", 2 ** (attempt + 1))
                )
                log.warning(
                    f"Crossref rate limited for ISSN {issn}, retrying in {retry_after}s (attempt {attempt + 1}/{max_retries})"
                )
                await asyncio.sleep(retry_after)
                continue
            log.error(f"Crossref request failed for ISSN {issn}: {e}")
            return feed
        except Exception as e:
            log.error(f"Crossref request failed for ISSN {issn}: {e}")
            return feed

    def _db_operations():
        feed = db.query(database.Feed).filter(database.Feed.url == feed_url).first()
        if not feed:
            return feed

        def _extract(item):
            title_list = item.get("title", [])
            title = title_list[0] if title_list else "No Title"
            doi = item.get("DOI", "")
            link = f"https://doi.org/{doi}" if doi else ""

            pub_date = None
            created_parts = item.get("created", {}).get("date-parts", [[]])[0]
            if created_parts and len(created_parts) >= 1:
                try:
                    pub_date = datetime.datetime(
                        created_parts[0],
                        created_parts[1] if len(created_parts) > 1 else 1,
                        created_parts[2] if len(created_parts) > 2 else 1,
                    )
                except Exception:
                    pub_date = None

            raw_abstract = item.get("abstract", "")
            description = (
                re.sub(r"<[^>]+>", "", raw_abstract).strip() if raw_abstract else ""
            )

            return {
                "title": title,
                "link": link,
                "pub_date": pub_date,
                "description": description,
            }

        _save_new_articles(db, feed, items, _extract)
        db.refresh(feed)
        return feed

    return await asyncio.to_thread(_db_operations)


async def _fetch_by_rss(db: Session, feed_url: str):
    """Fetch articles via RSS/Atom feed."""
    try:
        response = await shared_client.get(feed_url)
        response.raise_for_status()
        content = response.text
    except Exception as e:
        log.error(f"Error fetching {feed_url}: {e}")
        return None

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

        def _extract(entry):
            link = getattr(entry, "link", None)
            if not link:
                return None
            title = entry.get("title", "No Title")

            pub_date = None
            date_str = (
                entry.get("published") or entry.get("pubDate") or entry.get("updated")
            )
            if date_str:
                try:
                    pub_date = date_parser.parse(date_str)
                except Exception:
                    pub_date = None

            if hasattr(entry, "content") and entry.content:
                description = entry.content[0].get("value", "")
            else:
                description = entry.get("summary", entry.get("description", ""))

            return {
                "title": title,
                "link": link,
                "pub_date": pub_date,
                "description": description,
            }

        _save_new_articles(db, feed, d.entries, _extract)
        db.refresh(feed)
        return feed

    return await asyncio.to_thread(_db_operations)
