/* ═══════════════════════════════════════════════════════════════
   HACKADEMICS — Core JavaScript Utilities
   Toast notifications, AI thinking, counters, sidebar
   ═══════════════════════════════════════════════════════════════ */

// ── Toast Notification System ──────────────────────────────────
const Toast = {
  _container: null,

  _getContainer() {
    if (!this._container) {
      this._container = document.createElement('div');
      this._container.className = 'toast-container';
      document.body.appendChild(this._container);
    }
    return this._container;
  },

  show(message, type = 'info', duration = 3000) {
    const container = this._getContainer();
    const icons = {
      success: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 6L9 17l-5-5"/></svg>',
      error: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M15 9l-6 6M9 9l6 6"/></svg>',
      warning: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><path d="M12 9v4M12 17h.01"/></svg>',
      info: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>',
    };

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
      <span style="color: var(--${type === 'error' ? 'danger' : type}); display: flex;">${icons[type] || icons.info}</span>
      <span>${message}</span>
    `;

    container.appendChild(toast);

    setTimeout(() => {
      toast.classList.add('toast-out');
      setTimeout(() => toast.remove(), 300);
    }, duration);
  },

  success(msg, dur) { this.show(msg, 'success', dur); },
  error(msg, dur) { this.show(msg, 'error', dur); },
  warning(msg, dur) { this.show(msg, 'warning', dur); },
  info(msg, dur) { this.show(msg, 'info', dur); },
};

window.Toast = Toast;

// ── Sidebar Toggle (Mobile) ────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  const toggle = document.getElementById('sidebar-toggle');
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebar-overlay');

  if (toggle && sidebar) {
    toggle.addEventListener('click', () => {
      sidebar.classList.toggle('open');
      if (overlay) overlay.classList.toggle('open');
    });
  }

  if (overlay) {
    overlay.addEventListener('click', () => {
      sidebar.classList.remove('open');
      overlay.classList.remove('open');
    });
  }
});

// ── Animated Counters ──────────────────────────────────────────
function animateCounter(el) {
  const target = parseFloat(el.dataset.countTo);
  const suffix = el.dataset.countSuffix || '';
  const decimals = (el.dataset.countDecimals || '0') | 0;
  const duration = 1200;
  const start = performance.now();

  function update(now) {
    const elapsed = now - start;
    const progress = Math.min(elapsed / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
    const current = eased * target;
    el.textContent = current.toFixed(decimals) + suffix;
    if (progress < 1) requestAnimationFrame(update);
  }

  requestAnimationFrame(update);
}

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-count-to]').forEach(el => {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          animateCounter(el);
          observer.disconnect();
        }
      });
    });
    observer.observe(el);
  });
});

// ── Career Score Ring Animation ────────────────────────────────
function animateScoreRing(el) {
  const score = parseFloat(el.dataset.score || 0);
  const radius = parseFloat(el.dataset.radius || 80);
  const circumference = 2 * Math.PI * radius;
  const fillCircle = el.querySelector('.ring-fill');
  if (!fillCircle) return;

  fillCircle.style.strokeDasharray = circumference;
  fillCircle.style.strokeDashoffset = circumference;

  requestAnimationFrame(() => {
    const offset = circumference - (score / 100) * circumference;
    fillCircle.style.strokeDashoffset = offset;
  });
}

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.career-score-ring').forEach(el => {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          animateScoreRing(el);
          observer.disconnect();
        }
      });
    });
    observer.observe(el);
  });
});

// ── AI Thinking State Management ───────────────────────────────
const AIThinking = {
  show(containerId, message = 'AI is thinking...') {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.innerHTML = `
      <div class="ai-thinking">
        <div class="ai-thinking-dots">
          <span></span><span></span><span></span>
        </div>
        <span class="ai-thinking-text">${message}</span>
      </div>
    `;
    container.style.display = 'block';
  },

  hide(containerId) {
    const container = document.getElementById(containerId);
    if (container) container.style.display = 'none';
  },

  streamText(containerId, text) {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.innerHTML = `<div class="ai-stream">${text}</div>`;
    container.style.display = 'block';
  }
};

window.AIThinking = AIThinking;

// ── Skeleton Loader Helper ─────────────────────────────────────
function showSkeleton(containerId, type = 'card') {
  const container = document.getElementById(containerId);
  if (!container) return;

  const templates = {
    card: `
      <div class="glass-card-static" style="padding: 1.5rem;">
        <div class="skeleton skeleton-heading"></div>
        <div class="skeleton skeleton-text"></div>
        <div class="skeleton skeleton-text"></div>
        <div class="skeleton skeleton-text"></div>
      </div>
    `,
    list: `
      ${Array(4).fill('<div class="skeleton skeleton-text" style="margin-bottom: 1rem; height: 48px;"></div>').join('')}
    `,
    stats: `
      <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem;">
        ${Array(4).fill('<div class="skeleton" style="height: 90px; border-radius: 12px;"></div>').join('')}
      </div>
    `,
  };

  container.innerHTML = templates[type] || templates.card;
}

window.showSkeleton = showSkeleton;

// ── Form Submit with AI Loading ────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('form[data-ai-form]').forEach(form => {
    form.addEventListener('submit', function() {
      const btn = form.querySelector('button[type="submit"], input[type="submit"]');
      if (btn) {
        btn.disabled = true;
        btn.dataset.originalText = btn.textContent;
        btn.innerHTML = `
          <div class="ai-thinking-dots" style="display: inline-flex;">
            <span></span><span></span><span></span>
          </div>
          <span>AI is working...</span>
        `;
      }

      const loadingTarget = form.dataset.aiLoadingTarget;
      if (loadingTarget) {
        AIThinking.show(loadingTarget, form.dataset.aiLoadingMessage || 'AI is analyzing...');
      }
    });
  });
});

// ── Collapsible Sections ───────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.collapsible-header').forEach(header => {
    header.addEventListener('click', () => {
      const content = header.nextElementSibling;
      if (content && content.classList.contains('collapsible-content')) {
        content.classList.toggle('open');
        const arrow = header.querySelector('.collapsible-arrow');
        if (arrow) arrow.style.transform = content.classList.contains('open') ? 'rotate(180deg)' : '';
      }
    });
  });
});

// ── Django Messages → Toast Bridge ─────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-django-message]').forEach(el => {
    const type = el.dataset.djangoMessageType || 'info';
    const msg = el.textContent.trim();
    if (msg) {
      const typeMap = { 'success': 'success', 'error': 'error', 'warning': 'warning', 'info': 'info', 'debug': 'info' };
      Toast.show(msg, typeMap[type] || 'info');
    }
    el.remove();
  });
});
