/**
 * Toast Notification System
 * A lightweight, non-intrusive notification system for the Archive RSS Reader.
 *
 * Usage:
 *   toast.error({ title: 'Connection Lost', message: 'Unable to reach the server.' });
 *   toast.success({ title: 'Feed Added', message: 'New source synced successfully.' });
 *   toast.warning({ title: 'Slow Response', message: 'Server took longer than expected.' });
 *   toast.info({ title: 'Sync Complete', message: '12 new articles fetched.' });
 *
 *   // With retry action button:
 *   toast.error({
 *       title: 'Sync Failed',
 *       message: 'Could not refresh feeds.',
 *       action: { label: 'Retry', onClick: () => refreshAll() }
 *   });
 *
 *   // With custom duration (ms):
 *   toast.info({ title: 'Tip', message: 'Press S to star an article.', duration: 8000 });
 *
 *   // Dismiss all:
 *   toast.clearAll();
 */

const toast = (() => {
    const ICONS = {
        error: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
        </svg>`,
        success: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>
        </svg>`,
        warning: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
        </svg>`,
        info: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>
        </svg>`,
        close: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
        </svg>`,
    };

    const DURATIONS = {
        error: 6000,
        warning: 5000,
        info: 4000,
        success: 3500,
    };

    const MAX_VISIBLE = 5;

    function getContainer() {
        let container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            container.setAttribute('aria-live', 'polite');
            container.setAttribute('aria-atomic', 'false');
            document.body.appendChild(container);
        }
        return container;
    }

    function show(type, options) {
        const container = getContainer();
        const { title, message, duration, action } = options;

        // Enforce max visible toasts — dismiss oldest
        const existing = container.querySelectorAll('.toast:not(.toast-exit)');
        if (existing.length >= MAX_VISIBLE) {
            dismiss(existing[0]);
        }

        // Build toast element
        const toastEl = document.createElement('div');
        toastEl.className = `toast toast-${type}`;
        toastEl.setAttribute('role', 'alert');

        // Icon
        const iconEl = document.createElement('div');
        iconEl.className = 'toast-icon';
        iconEl.innerHTML = ICONS[type] || ICONS.info;

        // Content
        const contentEl = document.createElement('div');
        contentEl.className = 'toast-content';

        if (title) {
            const titleEl = document.createElement('div');
            titleEl.className = 'toast-title';
            titleEl.textContent = title;
            contentEl.appendChild(titleEl);
        }

        if (message) {
            const msgEl = document.createElement('div');
            msgEl.className = 'toast-message';
            msgEl.textContent = message;
            contentEl.appendChild(msgEl);
        }

        toastEl.appendChild(iconEl);
        toastEl.appendChild(contentEl);

        // Optional action button
        if (action && action.label && typeof action.onClick === 'function') {
            const actionBtn = document.createElement('button');
            actionBtn.className = 'toast-action';
            actionBtn.textContent = action.label;
            actionBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                action.onClick();
                dismiss(toastEl);
            });
            toastEl.appendChild(actionBtn);
        }

        // Dismiss button
        const dismissBtn = document.createElement('button');
        dismissBtn.className = 'toast-dismiss';
        dismissBtn.innerHTML = ICONS.close;
        dismissBtn.setAttribute('aria-label', 'Dismiss notification');
        dismissBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            dismiss(toastEl);
        });
        toastEl.appendChild(dismissBtn);

        // Progress bar for auto-dismiss countdown
        const effectiveDuration = duration || DURATIONS[type] || 4000;
        let progressEl, progressBar;

        if (effectiveDuration > 0) {
            progressEl = document.createElement('div');
            progressEl.className = 'toast-progress';
            progressBar = document.createElement('div');
            progressBar.className = 'toast-progress-bar';
            progressEl.appendChild(progressBar);
            toastEl.appendChild(progressEl);
        }

        // Insert at the top of the container
        container.insertBefore(toastEl, container.firstChild);

        // Animate progress bar
        if (progressBar) {
            // Force a reflow so the animation starts from the correct state
            progressBar.getBoundingClientRect();
            progressBar.style.transition = `transform ${effectiveDuration}ms linear`;
            progressBar.style.transform = 'scaleX(0)';
        }

        // Pause auto-dismiss on hover
        let timeoutId = null;
        let remaining = effectiveDuration;
        let startTime = Date.now();

        function startTimer() {
            if (remaining <= 0) return;
            startTime = Date.now();
            timeoutId = setTimeout(() => dismiss(toastEl), remaining);
            if (progressBar) {
                progressBar.style.transition = `transform ${remaining}ms linear`;
                progressBar.style.transform = 'scaleX(0)';
            }
        }

        function pauseTimer() {
            if (timeoutId) {
                clearTimeout(timeoutId);
                timeoutId = null;
                remaining -= (Date.now() - startTime);
                if (progressBar) {
                    const currentScale = progressBar.getBoundingClientRect().width /
                        progressEl.getBoundingClientRect().width;
                    progressBar.style.transition = 'none';
                    progressBar.style.transform = `scaleX(${currentScale})`;
                }
            }
        }

        if (effectiveDuration > 0) {
            startTimer();
            toastEl.addEventListener('mouseenter', pauseTimer);
            toastEl.addEventListener('mouseleave', startTimer);
        }

        // Store timer references for cleanup
        toastEl._timerFns = { pauseTimer, startTimer, timeoutId };
    }

    function dismiss(toastEl) {
        if (!toastEl || toastEl.classList.contains('toast-exit')) return;

        // Clear timers
        if (toastEl._timerFns) {
            if (toastEl._timerFns.timeoutId) clearTimeout(toastEl._timerFns.timeoutId);
            toastEl.removeEventListener('mouseenter', toastEl._timerFns.pauseTimer);
            toastEl.removeEventListener('mouseleave', toastEl._timerFns.startTimer);
        }

        toastEl.classList.add('toast-exit');
        toastEl.addEventListener('animationend', () => {
            toastEl.remove();
        }, { once: true });
    }

    function clearAll() {
        const container = getContainer();
        container.querySelectorAll('.toast').forEach(toastEl => dismiss(toastEl));
    }

    return {
        error: (opts) => show('error', opts),
        warning: (opts) => show('warning', opts),
        success: (opts) => show('success', opts),
        info: (opts) => show('info', opts),
        clearAll,
    };
})();
