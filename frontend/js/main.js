// Init
fetchFeeds();

// Set initial state
setTimeout(() => {
    const first = document.querySelector('.feed-item');
    if (first) first.classList.add('active');
}, 100);

loadArticles('all', null, 'All Archive');