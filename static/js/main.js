// ========================================
// BILLING SYSTEM - MAIN JAVASCRIPT
// ========================================

document.addEventListener('DOMContentLoaded', function () {
    // Theme Toggle Functionality
    const themeToggle = document.getElementById('themeToggle');
    const body = document.body;

    // Disable autocomplete on all forms
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.setAttribute('autocomplete', 'off');
    });

    // Check for saved theme preference or default to 'light'
    const currentTheme = localStorage.getItem('theme') || 'light';
    body.setAttribute('data-theme', currentTheme);
    updateThemeIcon(currentTheme);

    themeToggle.addEventListener('click', () => {
        const currentTheme = body.getAttribute('data-theme');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';

        body.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', newTheme);
        updateThemeIcon(newTheme);

        // Notify other components (e.g. charts) that the theme changed
        document.dispatchEvent(new CustomEvent('themeChanged', { detail: { theme: newTheme } }));
    });

    function updateThemeIcon(theme) {
        const icon = themeToggle.querySelector('i');
        if (theme === 'dark') {
            icon.className = 'fas fa-sun';
        } else {
            icon.className = 'fas fa-moon';
        }
    }

    // Legacy mobile menu toggle removed — sidebar.js handles this on mobile.
    // Legacy mobile dropdown toggle removed — sidebar.js handles accordion on mobile.

    // Auto-detect system theme preference
    if (localStorage.getItem('theme') === null) {
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        const theme = prefersDark ? 'dark' : 'light';
        body.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);
        updateThemeIcon(theme);
    }

    // Navigation enhancements
    const navItems = document.querySelectorAll('.nav-item');
    navItems.forEach((item, index) => {
        item.style.setProperty('--item-index', index);

        // Add ripple effect on click
        item.addEventListener('click', function (e) {
            const ripple = document.createElement('span');
            const rect = this.getBoundingClientRect();
            const size = Math.max(rect.width, rect.height);
            const x = e.clientX - rect.left - size / 2;
            const y = e.clientY - rect.top - size / 2;

            ripple.style.width = ripple.style.height = size + 'px';
            ripple.style.left = x + 'px';
            ripple.style.top = y + 'px';
            ripple.classList.add('ripple');

            this.appendChild(ripple);

            setTimeout(() => {
                ripple.remove();
            }, 600);
        });
    });

    // Add smooth scroll to dropdown items
    const dropdownItems = document.querySelectorAll('.dropdown-item');
    dropdownItems.forEach(item => {
        item.addEventListener('mouseenter', function () {
            this.style.transform = 'translateX(8px) scale(1.02)';
        });

        item.addEventListener('mouseleave', function () {
            this.style.transform = 'translateX(0) scale(1)';
        });
    });

    // Parallax effect for navbar (desktop only — on mobile .navbar is the sidebar)
    let ticking = false;
    function updateNavbar() {
        if (window.innerWidth <= 768) return; // Sidebar mode: skip parallax
        const navbar = document.querySelector('.navbar');
        if (!navbar) return;
        const scrolled = window.pageYOffset;
        const rate = scrolled * -0.5;

        if (scrolled > 50) {
            navbar.style.transform = `translateY(${rate}px)`;
            navbar.style.backdropFilter = 'blur(20px)';
        } else {
            navbar.style.transform = 'translateY(0)';
            navbar.style.backdropFilter = 'blur(10px)';
        }

        ticking = false;
    }

    function requestTick() {
        if (!ticking) {
            requestAnimationFrame(updateNavbar);
            ticking = true;
        }
    }

    window.addEventListener('scroll', requestTick);
});

// Note: Shared utility functions (formatDate, debounce, throttle, copyToClipboard, etc.)
// are consolidated in static/js/utils.js and loaded globally.

// Auto-bind click-to-copy on elements with data-copy attribute
document.addEventListener('click', function (e) {
    const el = e.target.closest('[data-copy]');
    if (el) {
        e.preventDefault();
        copyToClipboard(el.getAttribute('data-copy'));
    }
});