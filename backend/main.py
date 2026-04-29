import asyncio
import datetime
from contextlib import asynccontextmanager
from typing import List

import database
import listparser
import scanner
from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    HTTPException,
    Response,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from logger_config import log
from pydantic import BaseModel
from sqlalchemy.orm import Session

database.init_db()


# Global lifespan hook to gracefully close the HTTP client connection pool
@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await scanner.shared_client.aclose()
    log.info("HTTP client connection pool safely closed.")


app = FastAPI(lifespan=lifespan)

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# Dependency
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Helper to avoid blocking the main thread for synchronous DB operations
async def run_sync_in_thread(func, *args, **kwargs):
    return await asyncio.to_thread(func, *args, **kwargs)


# Pydantic models
class FeedBase(BaseModel):
    url: str


class FeedCreate(FeedBase):
    pass


class ArticleSchema(BaseModel):
    id: int
    title: str
    link: str
    description: str | None
    pub_date: datetime.datetime | None
    is_read: bool
    is_starred: bool
    feed_id: int | None = None

    class Config:
        from_attributes = True


class StarredSchema(BaseModel):
    id: int
    title: str
    link: str
    description: str | None
    pub_date: datetime.datetime | None
    feed_title: str | None

    class Config:
        from_attributes = True


class FeedSchema(BaseModel):
    id: int
    title: str
    url: str
    description: str | None
    unread_count: int

    class Config:
        from_attributes = True


@app.post("/feeds/", response_model=FeedSchema)
async def create_feed(feed: FeedCreate, db: Session = Depends(get_db)):
    try:
        new_feed = await scanner.fetch_and_save_feed(db, feed.url)
        if not new_feed:
            raise HTTPException(status_code=400, detail="Failed to fetch feed")
        return new_feed
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/feeds/", response_model=List[FeedSchema])
async def get_feeds(db: Session = Depends(get_db)):
    return await run_sync_in_thread(lambda: db.query(database.Feed).all())


@app.delete("/feeds/{feed_id}")
async def delete_feed(feed_id: int, db: Session = Depends(get_db)):
    def perform_delete():
        feed = db.query(database.Feed).filter(database.Feed.id == feed_id).first()
        if not feed:
            return False
        db.delete(feed)
        db.commit()
        return True

    deleted = await run_sync_in_thread(perform_delete)
    if not deleted:
        raise HTTPException(status_code=404, detail="Feed not found")
    return {"message": "Feed deleted"}


# Shared cursor-based pagination query builder
def _get_paginated_articles(
    db: Session, feed_id: int | None, cursor: datetime.datetime | None, limit: int
):
    query = db.query(database.Article)
    if feed_id is not None:
        query = query.filter(database.Article.feed_id == feed_id)

    if cursor:
        query = query.filter(database.Article.pub_date <= cursor)

    return (
        query.order_by(database.Article.pub_date.desc(), database.Article.id.desc())
        .limit(limit)
        .all()
    )


@app.get("/articles/", response_model=List[ArticleSchema])
async def get_articles(
    cursor: datetime.datetime | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    return await run_sync_in_thread(
        lambda: _get_paginated_articles(db, None, cursor, limit)
    )


@app.get("/feeds/{feed_id}/articles", response_model=List[ArticleSchema])
async def get_feed_articles(
    feed_id: int,
    cursor: datetime.datetime | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    return await run_sync_in_thread(
        lambda: _get_paginated_articles(db, feed_id, cursor, limit)
    )


@app.put("/articles/{article_id}/read")
async def toggle_read(
    article_id: int, read: bool = True, db: Session = Depends(get_db)
):
    def perform_toggle():
        article = (
            db.query(database.Article).filter(database.Article.id == article_id).first()
        )
        if article:
            article.is_read = read
            db.commit()
            return True
        return False

    success = await run_sync_in_thread(perform_toggle)
    if not success:
        raise HTTPException(status_code=404, detail="Article not found")
    return {"message": "Updated read status"}


@app.put("/articles/{article_id}/star")
async def toggle_star(
    article_id: int, star: bool = True, db: Session = Depends(get_db)
):
    def perform_star():
        article = (
            db.query(database.Article).filter(database.Article.id == article_id).first()
        )
        if not article:
            return None
        article.is_starred = star
        if star:
            existing = (
                db.query(database.StarredArticle)
                .filter(database.StarredArticle.link == article.link)
                .first()
            )
            if not existing:
                starred = database.StarredArticle(
                    title=article.title,
                    link=article.link,
                    description=article.description,
                    pub_date=article.pub_date,
                    feed_title=article.feed.title if article.feed else "Unknown",
                )
                db.add(starred)
        else:
            db.query(database.StarredArticle).filter(
                database.StarredArticle.link == article.link
            ).delete()
        db.commit()
        return True

    success = await run_sync_in_thread(perform_star)
    if not success:
        raise HTTPException(status_code=404, detail="Article not found")
    return {"message": "Updated star status"}


@app.get("/starred/", response_model=List[ArticleSchema])
async def get_starred_articles(db: Session = Depends(get_db)):
    def perform_query():
        starred_list = (
            db.query(database.StarredArticle)
            .order_by(database.StarredArticle.saved_at.desc())
            .all()
        )
        results = []
        for s in starred_list:
            results.append(
                {
                    "id": s.id,
                    "title": s.title,
                    "link": s.link,
                    "description": s.description,
                    "pub_date": s.pub_date,
                    "is_read": False,
                    "is_starred": True,
                    "feed_id": -1,
                }
            )
        return results

    return await run_sync_in_thread(perform_query)


@app.post("/refresh/")
async def refresh_all_feeds(
    background_tasks: BackgroundTasks, db: Session = Depends(get_db)
):
    async def run_refresh_task():
        # Get URLs in the main thread to avoid session issues in background
        feeds = db.query(database.Feed).all()
        urls = [f.url for f in feeds]

        # Limit maximum concurrency to prevent file descriptor exhaustion
        sem = asyncio.Semaphore(15)

        async def fetch_worker(url):
            async with sem:
                # Establish an independent DB session per task; never share sessions across coroutines
                session = database.SessionLocal()
                try:
                    await scanner.fetch_and_save_feed(session, url)
                except Exception:
                    pass
                finally:
                    session.close()

        # Execute all feed fetching tasks concurrently
        await asyncio.gather(*(fetch_worker(url) for url in urls))

    background_tasks.add_task(run_refresh_task)
    return {"message": "Refresh started in background"}


@app.post("/feeds/{feed_id}/refresh")
async def refresh_single_feed(feed_id: int, db: Session = Depends(get_db)):
    feed = await run_sync_in_thread(
        lambda: db.query(database.Feed).filter(database.Feed.id == feed_id).first()
    )
    if not feed:
        raise HTTPException(status_code=404, detail="Feed not found")
    try:
        await scanner.fetch_and_save_feed(db, feed.url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"message": f"Feed '{feed.title}' refreshed"}


# OPML Import/Export
@app.post("/opml/import")
async def import_opml(file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = await file.read()
    try:
        opml_data = listparser.parse(content.decode("utf-8"))
        count = 0
        for entry in opml_data.feeds:
            # Check if feed already exists
            existing = (
                db.query(database.Feed).filter(database.Feed.url == entry.url).first()
            )
            if not existing:
                try:
                    await scanner.fetch_and_save_feed(db, entry.url)
                    count += 1
                except Exception as e:
                    log.error(
                        f"Error occurred while fetching feed {entry.url}: {str(e)}"
                    )
                    continue
        return {"message": f"Imported {count} new feeds", "total": len(opml_data.feeds)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse OPML: {str(e)}")


@app.get("/opml/export")
def export_opml(db: Session = Depends(get_db)):
    feeds = db.query(database.Feed).all()

    opml_template = """<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0">
    <head>
        <title>RSS ACA Subscriptions</title>
        <dateCreated>{date}</dateCreated>
    </head>
    <body>
        <outline text="Subscriptions" title="Subscriptions">
            {outlines}
        </outline>
    </body>
</opml>"""

    outlines = ""
    for feed in feeds:
        title = feed.title.replace('"', "&quot;").replace("&", "&amp;")
        url = feed.url.replace('"', "&quot;").replace("&", "&amp;")
        outlines += f'            <outline type="rss" text="{title}" title="{title}" xmlUrl="{url}" htmlUrl="{url}"/>\n'

    opml_content = opml_template.format(
        date=datetime.datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT"),
        outlines=outlines,
    )

    return Response(
        content=opml_content,
        media_type="application/xml",
        headers={"Content-Disposition": "attachment; filename=subscriptions.opml"},
    )
