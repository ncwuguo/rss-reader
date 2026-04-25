# 📡 RSS READER

A brutalist, high-performance, and lightweight RSS reader. 

Built for those who prefer reading over managing complex systems. No bloated frontend frameworks, no microservices—just pure HTML/JS, FastAPI, and a deeply optimized SQLite database.

## ✨ Features

* **Zero-Build Frontend**: Pure HTML/CSS/JS. No Webpack, no React, no `node_modules` black hole.
* **Asynchronous Backend**: Powered by FastAPI and `httpx` for fast, non-blocking feed fetching.
* **SQLite on Steroids**: Utilizes WAL (Write-Ahead Logging) mode and native database triggers to keep unread counts synced in real-time without expensive SQL aggregations.
* **Cursor-Based Pagination**: Deep-dive into your archives without the performance hit of traditional `OFFSET` queries.
* **OPML Support**: One-click import and export of your subscriptions.
* **Background Sync**: Feeds are refreshed in the background with semaphore-controlled concurrency to prevent connection timeouts.

## 🛠️ Tech Stack

| Component | Technology | Description |
| - | - | - |
| Backend | FastAPI & Python 3.10+ | Handles API routing and background tasks. |
| Database | SQLite & SQLAlchemy | Disk-backed storage with WAL mode enabled. |
| Fetcher | HTTPX & Feedparser | Async fetching and robust XML parsing. |
| Frontend | Vanilla JS & CSS Grid | Responsive editorial layout (List/Grid views). |

## 🚀 Getting Started

### 1. Prerequisites

Ensure you have Python 3.10+ installed on your system.

### 2. Installation

Clone the repository and install the backend dependencies:

```bash
git clone https://github.com/ncwuguo/rss_aca.git
cd rss_aca
pip install -r requirements.txt
```

### 3. Running the Server

Navigate into the backend directory and start the FastAPI application using Uvicorn:

```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The database (`rss_reader.db`) will be automatically initialized in the `backend` folder on the first run.

### 4. Accessing the UI

Since the frontend is vanilla HTML, simply open `frontend/index.html` in your browser. 
*(For the best experience in production, serve it via a simple HTTP server or configure Nginx/Caddy).*

## ☁️ Deployment Recommendations

This architecture is portable and deployable almost anywhere:

* **Cloud VMs (e.g., AWS/DigitalOcean)**: Deploy on any standard VPS. Run the backend with Gunicorn and Uvicorn workers, and serve the frontend statically via Nginx.
* **Edge Platforms (e.g., Vercel/Cloudflare Pages)**: While SQLite's disk requirement limits pure serverless functions, you can deploy the static frontend on edge networks and host the FastAPI backend in a persistent containerized environment.