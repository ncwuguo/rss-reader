# 📡 RSS Reader

A lightweight, high-performance RSS reader built with FastAPI, SQLite, and vanilla JavaScript.

RSS Reader is designed for users who value focused reading, local-first data persistence, and simple deployment. It avoids heavy frontend frameworks, microservice overhead, and complex build pipelines, while still providing a responsive reading experience, asynchronous feed synchronization, OPML support, and database-level performance optimizations.

## ✨ Highlights

- **Minimal full-stack architecture**: FastAPI backend, SQLite database, and zero-build frontend.
- **Fast article browsing**: Infinite scrolling with DOM virtualization for large article archives.
- **Efficient persistence**: SQLite WAL mode, native triggers, and composite indexes.
- **Scalable pagination**: Cursor-based pagination instead of `OFFSET`.
- **Asynchronous feed refresh**: Concurrent feed fetching with bounded semaphore control.
- **RSS ecosystem compatibility**: OPML import and export support.
- **Clean reading workflow**: Starred articles, read-state filtering, and distraction-free modal reading.

## 📖 Features

### Reading Experience

- **Distraction-Free Reading Modal** — Open any article in a clean modal reader with full content and a link to the original source.

- **Infinite Scroll with Virtualized DOM** — Uses `IntersectionObserver` and dynamic DOM recycling to keep scrolling smooth across large article collections.

- **Grid and List Views** — Switch between a compact list layout and an editorial-style grid layout.

- **Optimistic UI Updates** — Read and starred states are updated immediately in the interface before server confirmation.

- **Show / Hide Read Articles** — Toggle already-read articles to keep the reading queue focused.

- **XSS-Safe Rendering** — Article content is sanitized through `DOMParser` text extraction before being inserted into the page.

### Feed Management

- **Starred Articles** — Save important articles to a dedicated starred archive.

- **Per-Feed and Global Refresh** — Refresh a single feed or synchronize all subscriptions.

- **OPML Import and Export** — Import and export subscription lists using the standard OPML format.

- **Background Synchronization** — Feeds are refreshed asynchronously with a semaphore-controlled concurrency limit to reduce network timeouts and excessive simultaneous requests.

### Performance and Architecture

- **Zero-Build Frontend** — Built with plain HTML, CSS, and JavaScript. No bundler, no framework runtime, and no frontend build step.

- **Asynchronous Backend** — FastAPI and `httpx` are used for non-blocking API handling and feed fetching.

- **SQLite WAL Mode** — Write-Ahead Logging improves read/write behavior while keeping deployment simple.

- **Database Triggers** — Native SQLite triggers maintain unread counts without repeatedly running expensive aggregate queries.

- **Cursor-Based Pagination** — Articles are paginated by timestamp and ID instead of `OFFSET`, preserving stable performance as the archive grows.

- **Composite Indexes** — Query paths are optimized with indexes such as `(pub_date, id)` and `(feed_id, pub_date, id)`.

- **Structured Logging** — Loguru provides enhanced terminal logging with intercept-based formatting and HTTP status highlighting.

## 🛠️ Tech Stack

| Component | Technology | Purpose |
|----------|------------|---------|
| **Backend** | FastAPI, Python 3.10+ | REST API, background tasks, application lifecycle |
| **Database** | SQLite, SQLAlchemy | Persistent storage, models, triggers, indexes |
| **Feed Fetching** | HTTPX, Feedparser | Async HTTP requests and RSS/Atom parsing |
| **Frontend** | HTML, CSS, Vanilla JavaScript | Single-page interface and client-side interaction |
| **Layout** | CSS Grid | Responsive grid and list views |
| **Typography** | Fraunces, Plus Jakarta Sans, JetBrains Mono | Display, body, and monospace font stack |
| **Logging** | Loguru | Structured and colorized backend logging |
| **OPML** | Listparser | Import and export of subscription lists |

## 🏗️ Architecture

```text
┌──────────────┐     REST API     ┌──────────────┐     ORM      ┌──────────────┐
│   Frontend   │ ◄──────────────► │    FastAPI   │ ◄──────────► │    SQLite    │
│ (Vanilla JS) │   JSON + CORS    │    Backend   │  SQLAlchemy  │  (WAL Mode)  │
└──────────────┘                  └──────────────┘              └──────────────┘
       │                                  │
       │ Article rendering                │ Feed synchronization
       │ Grid/List views                  │ Background tasks
       │ Virtualized DOM recycling        │ Semaphore concurrency
       │ Cursor-based loading             │ Async HTTP fetching
       │ Optimistic UI updates            │ Structured logging
```

The frontend is a static single-page application that communicates with the FastAPI backend through REST endpoints. The backend handles feed synchronization, article persistence, OPML processing, and database updates. SQLite is used as an embedded database, making the system easy to run locally or deploy on a small server.

## 📂 Project Structure

```text
rss_reader/
├── backend/
│   ├── main.py            # FastAPI app, routes, background tasks, and lifecycle management
│   ├── database.py        # SQLAlchemy models, SQLite triggers, indexes, and WAL setup
│   ├── scanner.py         # Async feed fetching and article parsing
│   └── logger_config.py   # Loguru configuration with status code coloring
├── frontend/
│   ├── index.html         # Single-page UI with sidebar, toolbar, and reader modal
│   ├── css/
│   │   └── style.css      # Brutalist editorial design system
│   └── js/
│       ├── state.js       # Global state, API base URL, and pagination cursors
│       ├── api.js         # REST API client functions
│       ├── ui.js          # DOM rendering, virtualized list, and sanitization
│       └── main.js        # Application initialization
├── static/                # Static assets
├── requirements.txt       # Python dependencies
└── README.md
```

## 🚀 Getting Started

### Prerequisites

- Python **3.10+**
- A modern web browser

### Installation

Clone the repository and install the Python dependencies:

```bash
git clone https://github.com/ncwuguo/rss_aca.git
cd rss_aca
pip install -r requirements.txt
```

### Running the Backend

Start the FastAPI server from the project root:

```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

On first launch, the application creates a SQLite database file at:

```text
backend/rss_reader.db
```

The database is initialized with WAL mode, optimized indexes, and triggers for unread-count maintenance.

### Running the Frontend

You can open the frontend directly in a browser:

```bash
# macOS
open frontend/index.html

# Windows
start frontend\index.html
```

Or serve it with a local static server:

```bash
cd frontend
python -m http.server 3000
```

Then open:

```text
http://localhost:3000
```

If the backend is running on a different host or port, update:

```text
frontend/js/state.js
```

and modify the `API_BASE` value accordingly.

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/feeds/` | Add a new RSS feed by URL |
| `GET` | `/feeds/` | List subscribed feeds with unread counts |
| `DELETE` | `/feeds/{feed_id}` | Delete a feed subscription |
| `GET` | `/articles/` | List articles with cursor-based pagination |
| `GET` | `/feeds/{feed_id}/articles` | List articles from a specific feed |
| `PUT` | `/articles/{article_id}/read` | Toggle article read status |
| `PUT` | `/articles/{article_id}/star` | Toggle article starred status |
| `GET` | `/starred/` | List starred articles |
| `POST` | `/refresh/` | Refresh all feeds as a background task |
| `POST` | `/feeds/{feed_id}/refresh` | Refresh a single feed |
| `POST` | `/opml/import` | Import subscriptions from an OPML file |
| `GET` | `/opml/export` | Export subscriptions as an OPML file |

## ⚙️ Configuration

| Setting | File | Description |
|---------|------|-------------|
| API Base URL | `frontend/js/state.js` | Backend API address used by the frontend |
| Database Path | `backend/database.py` | SQLite database location |
| Concurrency Limit | `backend/main.py` | Maximum concurrent feed fetches, default `15` |
| Page Size | `frontend/js/state.js` | Number of articles loaded per request, default `50` |

## 🧠 Design Decisions

### Why Vanilla JavaScript?

The frontend is intentionally implemented without React, Vue, Webpack, or other build tools. This keeps the client lightweight, easy to inspect, and simple to deploy as static files.

### Why SQLite?

SQLite provides a reliable embedded database with minimal operational overhead. Combined with WAL mode, triggers, and carefully selected indexes, it is sufficient for a fast personal RSS reader while remaining easy to back up and deploy.

### Why Cursor-Based Pagination?

Offset-based pagination becomes slower as the number of articles grows because the database must skip an increasing number of rows. Cursor-based pagination avoids this issue by using article timestamps and IDs as stable pagination anchors.

### Why DOM Virtualization?

Rendering thousands of article cards at once can significantly degrade browser performance. DOM virtualization keeps only the necessary elements in the document, reducing layout cost and improving scrolling smoothness.

## ☁️ Deployment

This project can be deployed in several ways:

### VPS Deployment

Run the backend with Uvicorn or Gunicorn with Uvicorn workers, and serve the frontend statically with Nginx or Caddy.

### Static Frontend + Hosted Backend

Deploy the frontend to a static hosting platform and run the FastAPI backend in a persistent server or container environment.

### Docker Deployment

Package the backend in a lightweight Python container and mount the SQLite database as a persistent volume.

> In production, update the CORS configuration in `backend/main.py` and replace wildcard origins with your trusted frontend domain.

## 📌 Limitations

This project is primarily designed for personal or small-scale RSS reading. It does not currently include:

- Multi-user accounts
- Authentication
- Full-text search
- Scheduled refresh configuration
- Cross-device synchronization
- Mobile app packaging

These features can be added as future extensions depending on deployment needs.

## 🗺️ Roadmap

Potential future improvements include:

- [ ] Full-text article search
- [ ] Tagging and custom article organization
- [ ] Scheduled periodic feed refresh
- [ ] Improved duplicate detection

## 📄 License

This project is open source. See the repository license for details.