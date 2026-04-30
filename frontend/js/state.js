const API_BASE = 'http://localhost:8000';
let currentFeedId = 'all';
let showRead = false;
let viewLayout = 'list'; // 'grid' or 'list'
let articles = [];

// Use timestamp-based cursor instead of relative pagination
let lastPubDate = null;
let isLoading = false;
let hasMore = true;
const PAGE_SIZE = 50;

// Observers
let observer;
let virtualNodeObserver;