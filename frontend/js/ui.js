// Utility: Extract plain text to mitigate XSS vulnerabilities.
function getSafeText(html) {
    if (!html) return '';

    const doc = new DOMParser().parseFromString(html, 'text/html');
    const text = doc.body.textContent || '';

    return text.replace(/[&<>'"]/g, tag => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
    }[tag] || tag));
}


// Render only the necessary items based on the itemsToRender array
function renderArticles(itemsToRender = articles, append = false) {
    const list = document.getElementById('article-list');

    // Temporarily remove the infinite scroll trigger before rendering
    const oldTrigger = document.getElementById('infinite-scroll-trigger');
    if (oldTrigger) oldTrigger.remove();

    if (!append) {
        // Clear the list only in non-append modes (e.g., view or feed switching)
        list.innerHTML = '';
        list.className = viewLayout;
        // Disconnect existing observer on view reset to prevent memory leaks from detached nodes
        if (virtualNodeObserver) {
            virtualNodeObserver.disconnect();
        }
        setupVirtualObserver();
    } else {
        // Remove empty state message if it exists
        const emptyMsg = list.querySelector('div[style*="padding: 2rem"]');
        if (emptyMsg) emptyMsg.remove();
    }

    // Performance: Cache rendered item IDs in a Set to reduce O(M*N) DOM queries to O(1) lookups
    const existingIds = new Set();
    if (append) {
        const currentItems = list.querySelectorAll('.article-item');
        currentItems.forEach(item => existingIds.add(parseInt(item.getAttribute('data-id'))));
    }

    const filtered = itemsToRender.filter(a => showRead || !a.is_read);

    if (filtered.length === 0 && !append && articles.length === 0) {
        list.innerHTML = '<div style="padding: 2rem; font-family: var(--font-mono); color: var(--muted); text-align: center;">' +
            (hasMore ? 'NO UNREAD IN THIS BATCH - SCROLL FOR MORE' : 'NO ENTRIES FOUND') +
            '</div>';
        // Re-attach scroll trigger if more pages exist, even if current batch has no unread items
        if (hasMore) appendTrigger(list);
        return;
    }

    // Use DocumentFragment for in-memory DOM construction to minimize reflows
    const fragment = document.createDocumentFragment();

    filtered.forEach((a, index) => {
        // Defensive programming: prevent duplicate DOM elements due to concurrent network requests
        if (append && existingIds.has(a.id)) {
            return;
        }

        const li = document.createElement('li');
        li.className = `article-item ${a.is_read ? 'read' : ''}`;
        li.setAttribute('data-id', a.id);

        // Apply stagger animation delay only to newly appended elements
        if (append) li.style.animationDelay = `${Math.min(index * 0.02, 0.5)}s`;

        // Virtualization patch: Render content for the first 20 items, defer the rest as skeletons
        if (index < 20 || append) {
            renderArticleContent(li, a);
            li.setAttribute('data-rendered', 'true');
        } else {
            // Assign an estimated height to skeletons to prevent mass Observer triggering
            li.style.height = viewLayout === 'list' ? '60px' : '200px';
        }

        // Observe the newly created DOM node for virtual list rendering
        virtualNodeObserver.observe(li);

        fragment.appendChild(li);
    });

    // Append the fully constructed fragment to the actual DOM tree
    list.appendChild(fragment);

    // Re-attach the infinite scroll trigger to the bottom
    if (hasMore) appendTrigger(list);
}

// Helper method to attach the intersection observer trigger
function appendTrigger(list) {
    const loadMore = document.createElement('div');
    loadMore.id = 'infinite-scroll-trigger';
    loadMore.style.height = '10px';
    loadMore.style.margin = '2rem 0';
    list.appendChild(loadMore);
    setupIntersectionObserver();
}

function setupIntersectionObserver() {
    if (observer) observer.disconnect();

    observer = new IntersectionObserver((entries) => {
        if (entries[0].isIntersecting && hasMore && !isLoading) {
            loadArticles(currentFeedId, null, null, true);
        }
    }, { threshold: 0.1 });

    const trigger = document.getElementById('infinite-scroll-trigger');
    if (trigger) observer.observe(trigger);
}

// Core mechanism: Configure the virtual viewport observer for DOM recycling
function setupVirtualObserver() {
    virtualNodeObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            const li = entry.target;
            if (entry.isIntersecting) {
                // On entering viewport: Populate DOM and remove hardcoded height for dynamic layout
                if (!li.hasAttribute('data-rendered')) {
                    const articleId = parseInt(li.getAttribute('data-id'));
                    const a = articles.find(x => x.id === articleId);
                    if (a) {
                        renderArticleContent(li, a);
                        li.setAttribute('data-rendered', 'true');
                    }
                    li.style.height = '';
                }
            } else {
                // On exiting viewport: Lock current physical height and purge inner nodes to free memory
                if (li.hasAttribute('data-rendered')) {
                    const rect = entry.boundingClientRect;
                    // Lock height only if the element is actually visible (ignore display:none)
                    if (rect.height > 0) {
                        li.style.height = `${rect.height}px`;
                        li.innerHTML = '';
                        li.removeAttribute('data-rendered');
                    }
                }
            }
        });
    }, {
        root: document.getElementById('main'), // Bind to main scrollable container
        rootMargin: '1500px 0px' // Add a 1500px vertical buffer to prevent flickering during fast scroll
    });
}

// Reusable component logic to populate an individual article node
function renderArticleContent(li, a) {
    // Sync the outer class state to preserve 'read' visual styling after DOM restoration
    li.classList.toggle('read', a.is_read);
    // Strip inline opacity to fix potential permanent invisibility bugs caused by race conditions
    li.style.opacity = '';

    const date = a.pub_date ? new Date(a.pub_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : 'undated';
    const safeSummary = getSafeText(a.description);
    li.innerHTML = `
        <div class="article-meta-top">
            <span>${date}</span>
        </div>
        <div class="article-title" title="${a.title.replace(/"/g, '&quot;')}" onclick="window.open('${a.link}', '_blank'); markRead(${a.id})">${a.title}</div>
        <div class="article-summary">${safeSummary}</div>
        <div class="article-actions">
            <button class="btn-text star-btn ${a.is_starred ? 'active' : ''}" onclick="toggleStar(${a.id}, ${!a.is_starred}, event)">
                ${a.is_starred ? '★' : '☆'}
            </button>
            <button class="btn-text read-btn" onclick="markRead(${a.id}, ${!a.is_read}, event)">
                ${a.is_read ? '●' : '○'}
            </button>
        </div>
    `;
}

function setLayout(layout) {
    viewLayout = layout;
    document.getElementById('view-grid-btn').classList.toggle('active', layout === 'grid');
    document.getElementById('view-list-btn').classList.toggle('active', layout === 'list');
    renderArticles();
}

function toggleShowRead() {
    showRead = !showRead;
    document.getElementById('toggle-read-btn').classList.toggle('active', showRead);
    renderArticles();
}

function setStatus(text) {
    const el = document.getElementById('status-text');
    el.innerText = text;
    setTimeout(() => { if (el.innerText === text) el.innerText = ''; }, 3000);
}