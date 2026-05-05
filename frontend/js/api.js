// Debounce timer dictionary — prevents rapid-fire PUT requests per article ID
const _debounceTimers = {};

async function fetchFeeds() {
    try {
        const res = await fetch(`${API_BASE}/feeds/`);
        if (!res.ok) throw new Error(`Server responded with ${res.status}`);
        feeds = await res.json();
    } catch (err) {
        toast.error({
            title: 'Feed Sync Failed',
            message: 'Could not load subscription list. The sidebar may be outdated.',
            action: { label: 'Retry', onClick: () => fetchFeeds() }
        });
        return;
    }

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
        if (!res.ok) throw new Error(`Server responded with ${res.status}`);
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
        // Preserve the existing article list; show a toast with retry instead
        if (!append) {
            // If this is an initial load and there are no articles yet, show a minimal placeholder
            const list = document.getElementById('article-list');
            if (articles.length === 0) {
                list.innerHTML = '<div style="padding: 2rem; font-family: var(--font-mono); color: var(--muted); text-align: center;">UNABLE TO LOAD ARCHIVE</div>';
            }
            // If articles exist from a previous successful load, keep them visible
        }
        toast.error({
            title: append ? 'Load More Failed' : 'Connection Error',
            message: append
                ? 'Could not fetch additional articles.'
                : 'Unable to retrieve articles. The previous content has been preserved.',
            action: {
                label: 'Retry',
                onClick: () => {
                    // Reset cursor for fresh loads to avoid stale pagination
                    if (!append) lastPubDate = null;
                    loadArticles(feedId, el, title, append);
                }
            }
        });
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
            if (readBtn) readBtn.classList.toggle('active', status);
        }
    }

    // Update local state
    const idx = articles.findIndex(a => a.id === id);
    if (idx !== -1) articles[idx].is_read = status;

    // Debounce: delay 500ms to coalesce rapid clicks into a single PUT request
    const timerKey = `read_${id}`;
    clearTimeout(_debounceTimers[timerKey]);
    _debounceTimers[timerKey] = setTimeout(() => {
        fetch(`${API_BASE}/articles/${id}/read?read=${status}`, { method: 'PUT', keepalive: true })
            .catch(err => console.error('Failed to sync read state:', err));
        delete _debounceTimers[timerKey];
    }, 500);
}

async function toggleStar(id, status, event) {
    if (event) event.stopPropagation();

    // Optimistic UI update
    const articleEl = document.querySelector(`.article-item[data-id="${id}"]`);
    if (articleEl) {
        const starBtn = articleEl.querySelector('.star-btn');
        if (starBtn) {
            starBtn.classList.toggle('active', status);
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

    // Debounce: delay 500ms to coalesce rapid clicks into a single PUT request
    const timerKey = `star_${id}`;
    clearTimeout(_debounceTimers[timerKey]);
    _debounceTimers[timerKey] = setTimeout(() => {
        fetch(`${API_BASE}/articles/${id}/star?star=${status}`, { method: 'PUT', keepalive: true })
            .catch(err => console.error('Failed to sync star state:', err));
        delete _debounceTimers[timerKey];
    }, 500);
}

async function addFeed() {
    const urlInput = document.getElementById('feed-url');
    const url = urlInput.value;
    if (!url) return;
    setStatus('Adding source...');
    try {
        const res = await fetch(`${API_BASE}/feeds/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url })
        });
        if (res.ok) {
            urlInput.value = '';
            await fetchFeeds();
            loadArticles('all', document.querySelector('.feed-item'), 'All Archive');
            toast.success({ title: 'Source Added', message: 'New subscription synced successfully.' });
        } else {
            const data = await res.json().catch(() => ({}));
            toast.error({ title: 'Add Failed', message: data.detail || 'Server rejected this feed URL.' });
        }
    } catch (err) {
        toast.error({ title: 'Connection Error', message: 'Could not reach the server to add this source.' });
    }
}

async function deleteFeed(id, event) {
    event.stopPropagation();
    if (!confirm('Are you sure you want to delete this feed?')) return;
    try {
        const res = await fetch(`${API_BASE}/feeds/${id}`, { method: 'DELETE' });
        if (!res.ok) throw new Error(`Server responded with ${res.status}`);
        fetchFeeds();
        if (currentFeedId == id) loadArticles('all', document.querySelector('.feed-item'), 'All Archive');
        toast.info({ title: 'Source Removed', message: 'Feed has been deleted.' });
    } catch (err) {
        toast.error({ title: 'Delete Failed', message: 'Could not remove this feed. Please try again.' });
    }
}

async function refreshAll() {
    setStatus('Syncing all sources...');
    try {
        const res = await fetch(`${API_BASE}/refresh/`, { method: 'POST' });
        if (!res.ok) throw new Error(`Server responded with ${res.status}`);
        await loadArticles(currentFeedId);
        await fetchFeeds();
        toast.success({ title: 'Sync Complete', message: 'All sources have been refreshed.' });
    } catch (err) {
        toast.error({
            title: 'Sync Failed',
            message: 'Could not refresh feeds from the server.',
            action: { label: 'Retry', onClick: () => refreshAll() }
        });
    }
}

async function refreshCurrent() {
    if (currentFeedId === 'all' || currentFeedId === 'starred') {
        refreshAll();
        return;
    }
    setStatus('Syncing current...');
    try {
        const res = await fetch(`${API_BASE}/feeds/${currentFeedId}/refresh`, { method: 'POST' });
        if (!res.ok) throw new Error(`Server responded with ${res.status}`);
        await loadArticles(currentFeedId);
        await fetchFeeds();
        toast.success({ title: 'Sync Complete', message: 'Current feed has been refreshed.' });
    } catch (err) {
        toast.error({
            title: 'Sync Failed',
            message: 'Could not refresh this feed.',
            action: { label: 'Retry', onClick: () => refreshCurrent() }
        });
    }
}

async function importOpml(input) {
    if (!input.files || !input.files[0]) return;
    const formData = new FormData();
    formData.append('file', input.files[0]);

    setStatus('Importing archive...');
    try {
        const res = await fetch(`${API_BASE}/opml/import`, { method: 'POST', body: formData });
        if (!res.ok) throw new Error(`Server responded with ${res.status}`);
        const data = await res.json();
        toast.success({ title: 'Import Complete', message: data.message || 'OPML file imported successfully.' });
        fetchFeeds();
    } catch (err) {
        toast.error({ title: 'Import Failed', message: 'Could not import OPML file. Please check the format and try again.' });
    }
    input.value = '';
}

function exportOpml() {
    window.location.href = `${API_BASE}/opml/export`;
}