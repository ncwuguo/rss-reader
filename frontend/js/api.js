async function fetchFeeds() {
    const res = await fetch(`${API_BASE}/feeds/`);
    const feeds = await res.json();
    const list = document.getElementById('feed-list');

    // Re-render subscription section
    const labels = list.querySelectorAll('.feed-group-label');
    const subLabel = labels[1];

    // Remove everything after the subscriptions label
    while (subLabel.nextSibling) {
        list.removeChild(subLabel.nextSibling);
    }

    feeds.forEach(f => {
        const div = document.createElement('div');
        div.className = 'feed-item';
        if (currentFeedId == f.id) div.classList.add('active');
        div.innerHTML = `
            <span onclick="loadArticles(${f.id}, this.parentElement, '${f.title.replace(/'/g, "\\'")}')">${f.title}</span>
            <span class="unread-badge">${f.unread_count}</span>
            <!-- Comment out the 'x' to prevent operational errors -->
            <!-- <span class="delete-feed" onclick="deleteFeed(${f.id}, event)">×</span> -->
        `;
        list.appendChild(div);
    });
}

async function loadArticles(feedId, el, title, append = false) {
    if (isLoading) return;
    isLoading = true;

    if (!append) {
        currentFeedId = feedId;
        lastPubDate = null;
        articles = [];
        hasMore = true;
        document.querySelectorAll('.feed-item').forEach(i => i.classList.remove('active'));
        if (el) el.classList.add('active');
        if (title) document.getElementById('current-view-name').innerText = title;

        // Show loading state
        const list = document.getElementById('article-list');
        list.innerHTML = '<div style="padding: 2rem; font-family: var(--font-mono); color: var(--muted);">RETRIEVING ARCHIVE...</div>';
    }

    // Dynamically construct the cursor pagination URL
    let baseEndpoint = feedId === 'all' ? '/articles/' : `/feeds/${feedId}/articles`;
    let url = `${API_BASE}${baseEndpoint}?limit=${PAGE_SIZE}`;
    if (append && lastPubDate) {
        url += `&cursor=${encodeURIComponent(lastPubDate)}`;
    }

    if (feedId === 'starred') {
        url = `${API_BASE}/starred/`;
        hasMore = false; // Starred usually doesn't have offset in this backend
    }

    try {
        const res = await fetch(url);
        const newArticles = await res.json();

        if (newArticles.length < PAGE_SIZE) {
            hasMore = false;
        }

        // Extract the oldest publication date in this batch to serve as the next cursor anchor
        if (newArticles.length > 0) {
            lastPubDate = newArticles[newArticles.length - 1].pub_date;
        }

        articles = append ? [...articles, ...newArticles] : newArticles;
        renderArticles(append ? newArticles : articles, append);
    } catch (err) {
        const list = document.getElementById('article-list');
        if (!append) list.innerHTML = '<div style="padding: 2rem; color: var(--accent);">CONNECTION ERROR</div>';
    } finally {
        isLoading = false;
    }
}

async function markRead(id, status = true, event) {
    if (event) event.stopPropagation();
    if (currentFeedId === 'starred') return;

    // Optimistic UI update
    const articleEl = document.querySelector(`.article-item[data-id="${id}"]`);
    if (articleEl) {
        if (status && !showRead) {
            articleEl.style.opacity = '0';
            setTimeout(() => {
                articleEl.classList.add('hidden');
                // Clear skeleton height when hidden to prevent layout gaps in flow
                articleEl.style.height = '';
                // Clear inline opacity so the node isn't stuck invisible if recycled by Observer
                articleEl.style.opacity = '';
            }, 300);
        } else {
            articleEl.classList.toggle('read', status);
            const readBtn = articleEl.querySelector('.read-btn');
            if (readBtn) readBtn.innerHTML = status ? '● Unread' : '○ Read';
        }
    }

    // Update local state
    const idx = articles.findIndex(a => a.id === id);
    if (idx !== -1) articles[idx].is_read = status;

    await fetch(`${API_BASE}/articles/${id}/read?read=${status}`, { method: 'PUT' });
}

async function toggleStar(id, status, event) {
    if (event) event.stopPropagation();

    // Optimistic UI update
    const articleEl = document.querySelector(`.article-item[data-id="${id}"]`);
    if (articleEl) {
        const starBtn = articleEl.querySelector('.star-btn');
        if (starBtn) {
            starBtn.classList.toggle('active', status);
            starBtn.innerHTML = status ? '★ Starred' : '☆ Star';
        }

        // If in starred view and unstarring, hide it locally
        if (currentFeedId === 'starred' && !status) {
            articleEl.style.opacity = '0';
            setTimeout(() => {
                articleEl.classList.add('hidden');
                // Clear physical height and inline styles to prevent corrupted state upon Observer restoration
                articleEl.style.height = '';
                articleEl.style.opacity = '';
            }, 300);
        }
    }

    // Update local state
    const idx = articles.findIndex(a => a.id === id);
    if (idx !== -1) articles[idx].is_starred = status;

    await fetch(`${API_BASE}/articles/${id}/star?star=${status}`, { method: 'PUT' });
}

async function addFeed() {
    const urlInput = document.getElementById('feed-url');
    const url = urlInput.value;
    if (!url) return;
    setStatus('Adding source...');
    const res = await fetch(`${API_BASE}/feeds/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url })
    });
    if (res.ok) {
        urlInput.value = '';
        await fetchFeeds();
        loadArticles('all', document.querySelector('.feed-item'), 'All Archive');
        setStatus('Source added');
    } else {
        setStatus('Failed to add');
    }
}

async function deleteFeed(id, event) {
    event.stopPropagation();
    if (!confirm('Are you sure you want to delete this feed?')) return;
    await fetch(`${API_BASE}/feeds/${id}`, { method: 'DELETE' });
    fetchFeeds();
    if (currentFeedId == id) loadArticles('all', document.querySelector('.feed-item'), 'All Archive');
}

async function refreshAll() {
    setStatus('Syncing all sources...');
    await fetch(`${API_BASE}/refresh/`, { method: 'POST' });
    await loadArticles(currentFeedId);
    await fetchFeeds(); // Refresh unread counts
    setStatus('Done');
}

async function refreshCurrent() {
    if (currentFeedId === 'all' || currentFeedId === 'starred') {
        refreshAll();
        return;
    }
    setStatus('Syncing current...');
    const res = await fetch(`${API_BASE}/feeds/${currentFeedId}/refresh`, { method: 'POST' });
    if (res.ok) {
        await loadArticles(currentFeedId);
        await fetchFeeds(); // Refresh unread counts
        setStatus('Done');
    } else {
        setStatus('Failed');
    }
}

async function importOpml(input) {
    if (!input.files || !input.files[0]) return;
    const formData = new FormData();
    formData.append('file', input.files[0]);

    setStatus('Importing archive...');
    const res = await fetch(`${API_BASE}/opml/import`, { method: 'POST', body: formData });
    const data = await res.json();
    setStatus(data.message);
    fetchFeeds();
    input.value = '';
}

function exportOpml() {
    window.location.href = `${API_BASE}/opml/export`;
}