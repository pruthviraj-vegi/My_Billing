// ===================================
// KEYBOARD SHORTCUTS SYSTEM
// ===================================

(function () {
    'use strict';

    // Shortcut Configuration
    const shortcuts = {
        navigation: [
            { keys: 'Ctrl+1', action: 'focusMenu', target: 0, label: 'Dashboard', icon: 'fa-tachometer-alt' },
            { keys: 'Ctrl+2', action: 'focusMenu', target: 1, label: 'Carts', icon: 'fa-shopping-cart' },
            { keys: 'Ctrl+3', action: 'focusMenu', target: 2, label: 'Invoices', icon: 'fa-file-invoice-dollar' },
            { keys: 'Ctrl+4', action: 'focusMenu', target: 3, label: 'Inventory', icon: 'fa-boxes' },
            { keys: 'Ctrl+5', action: 'focusMenu', target: 4, label: 'Customers', icon: 'fa-users' },
            { keys: 'Ctrl+6', action: 'focusMenu', target: 5, label: 'Suppliers', icon: 'fa-truck' },
            { keys: 'Ctrl+7', action: 'focusMenu', target: 6, label: 'Users', icon: 'fa-users-cog' },
            { keys: 'Ctrl+8', action: 'focusMenu', target: 7, label: 'Settings', icon: 'fa-cog' }
        ],
        direct: [
            { keys: 'Ctrl+Shift+N', action: 'navigate', url: '{% url "cart:create_cart" %}', label: 'Create New Cart', icon: 'fa-plus-circle', target: '_blank' },
            { keys: 'Ctrl+Shift+C', action: 'navigate', url: '{% url "customer:create" %}', label: 'Add Customer', icon: 'fa-user-plus', target: '_blank' },
            { keys: 'Ctrl+Shift+S', action: 'navigate', url: '{% url "supplier:create" %}', label: 'Add Supplier', icon: 'fa-truck-loading', target: '_blank' }
        ],
        help: [
            { keys: 'Ctrl+Shift+?', action: 'showHelp', label: 'Show Shortcuts Help', icon: 'fa-question-circle' }
        ]
    };

    // Initialize shortcuts when DOM is ready
    function initShortcuts() {
        document.addEventListener('keydown', handleKeyPress);
        createHelpModal();
        setupClickOutsideHandler();
        setupHoverDropdownNavigation();
        setupNavLinkArrowKeys();
    }

    // Setup keyboard navigation for dropdowns opened via hover
    function setupHoverDropdownNavigation() {
        const navItems = document.querySelectorAll('.nav-menu > .nav-item');

        navItems.forEach(navItem => {
            const dropdown = navItem.querySelector('.dropdown-menu');
            const navLink = navItem.querySelector('.nav-link');
            if (!dropdown || !navLink) return;

            // Make nav link focusable
            if (!navLink.hasAttribute('tabindex')) {
                navLink.setAttribute('tabindex', '0');
            }

            // When mouse enters nav item, enable keyboard navigation
            navItem.addEventListener('mouseenter', () => {
                // Small delay to ensure dropdown is visible
                setTimeout(() => {
                    if (isDropdownVisible(dropdown)) {
                        enableDropdownKeyboardNavigation(navItem, dropdown);
                        // Don't auto-focus - let user use Tab or Arrow keys to navigate
                    }
                }, 50);
            });
        });
    }

    // Check if dropdown is currently visible
    function isDropdownVisible(dropdown) {
        const style = window.getComputedStyle(dropdown);
        return style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
    }

    // Unified function to enable keyboard navigation for any dropdown
    function enableDropdownKeyboardNavigation(navItem, dropdown) {
        // Make nav link focusable if not already
        const navLink = navItem.querySelector('.nav-link');
        if (navLink && !navLink.hasAttribute('tabindex')) {
            navLink.setAttribute('tabindex', '0');
        }

        // Make dropdown items focusable
        const dropdownItems = dropdown.querySelectorAll('.dropdown-item:not(.dropdown-divider)');
        dropdownItems.forEach(item => {
            if (!item.hasAttribute('tabindex')) {
                item.setAttribute('tabindex', '0');
            }
        });

        // Setup keyboard navigation (same function used by shortcuts)
        setupDropdownKeyboardNav(dropdown, navItem);

        // Add a marker class to track that this dropdown is keyboard-enabled
        navItem.classList.add('dropdown-keyboard-enabled');
    }

    // Handle clicks outside to close dropdowns opened via shortcuts
    function setupClickOutsideHandler() {
        document.addEventListener('click', (e) => {
            const navItems = document.querySelectorAll('.nav-item.dropdown-shortcut-open');
            if (navItems.length === 0) return;

            // Check if click is on a dropdown item - if so, close dropdown
            const clickedDropdownItem = e.target.closest('.dropdown-item');
            if (clickedDropdownItem) {
                // Small delay to allow navigation to proceed
                setTimeout(() => closeAllDropdowns(), 100);
                return;
            }

            // Check if click is outside all nav items
            let clickedInside = false;
            navItems.forEach(navItem => {
                if (navItem.contains(e.target)) {
                    clickedInside = true;
                }
            });

            if (!clickedInside) {
                closeAllDropdowns();
            }
        });

        // Also close on Escape key (only if dropdown is open, not if modal is open)
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                const navItems = document.querySelectorAll('.nav-item.dropdown-shortcut-open');
                const helpModal = document.getElementById('shortcuts-help-modal');
                const isModalOpen = helpModal && helpModal.style.display === 'flex';

                // Only close dropdowns if modal is not open
                if (navItems.length > 0 && !isModalOpen) {
                    closeAllDropdowns();
                    // Return focus to the nav link
                    const firstNavItem = navItems[0];
                    const navLink = firstNavItem.querySelector('.nav-link');
                    if (navLink) navLink.focus();
                }
            }
        });
    }

    // Handle keyboard events
    function handleKeyPress(e) {
        // Ignore if typing in input, textarea, or contenteditable
        const target = e.target;
        if (target.tagName === 'INPUT' ||
            target.tagName === 'TEXTAREA' ||
            target.isContentEditable ||
            target.closest('input, textarea, [contenteditable="true"]')) {
            return;
        }

        // Ignore modifier keys pressed alone
        if (e.key === 'Control' || e.key === 'Shift' || e.key === 'Alt' || e.key === 'Meta') {
            return;
        }

        const key = [];
        if (e.ctrlKey) key.push('Ctrl');
        if (e.shiftKey) key.push('Shift');
        if (e.altKey) key.push('Alt');

        // Get the actual key pressed
        // Use e.code for number keys to handle Shift+number correctly
        // e.code gives us 'Digit1', 'Digit2', etc. regardless of Shift
        let pressedKey = null;

        // Check if it's a number key using code (works with Shift)
        if (e.code && e.code.startsWith('Digit')) {
            pressedKey = e.code.replace('Digit', ''); // Extract '1', '2', etc.
        }
        // Handle regular number keys (when Shift not pressed)
        else if (e.key >= '0' && e.key <= '9') {
            pressedKey = e.key;
        }
        // Handle special keys
        else if (e.key === '?') {
            pressedKey = '?';
        }
        // Handle letter keys
        else if (e.key.length === 1 && /[A-Za-z]/.test(e.key)) {
            pressedKey = e.key.toUpperCase();
        }
        // For other keys, use the key name
        else {
            pressedKey = e.key;
        }

        if (pressedKey) {
            key.push(pressedKey);
        }

        const combination = key.join('+');
        console.log('Key combination pressed:', combination, '| e.key:', e.key, '| e.code:', e.code);

        // Check all shortcuts
        const allShortcuts = [...shortcuts.navigation, ...shortcuts.direct, ...shortcuts.help];
        const matchedShortcut = allShortcuts.find(s => s.keys === combination);

        if (matchedShortcut) {
            console.log('Shortcut matched:', matchedShortcut);
            e.preventDefault();
            e.stopPropagation();
            executeShortcut(matchedShortcut);
        }
    }

    // Execute shortcut action
    function executeShortcut(shortcut) {
        switch (shortcut.action) {
            case 'focusMenu':
                focusMenuItem(shortcut.target);
                break;
            case 'navigate':
                navigateTo(shortcut.url);
                break;
            case 'showHelp':
                toggleHelpModal();
                break;
        }
    }

    // Focus on menu item and open dropdown
    function focusMenuItem(index) {
        const navItems = document.querySelectorAll('.nav-menu > .nav-item');
        console.log(`Focusing menu item at index ${index}, found ${navItems.length} nav items`);

        if (navItems[index]) {
            const navItem = navItems[index];
            const navLink = navItem.querySelector('.nav-link');
            const dropdown = navItem.querySelector('.dropdown-menu');

            if (!navLink) {
                console.log('No nav link found');
                return;
            }

            // Make sure nav link is focusable
            if (!navLink.hasAttribute('tabindex')) {
                navLink.setAttribute('tabindex', '0');
            }

            // Close all other dropdowns first
            closeAllDropdowns();

            // Focus on the link
            navLink.focus();

            // Visual feedback
            const linkText = navLink.querySelector('span')?.textContent || navLink.textContent.trim();
            showShortcutFeedback(linkText);

            // Handle dropdown or direct navigation
            if (dropdown) {
                console.log('Dropdown found, opening...');
                // Has dropdown - open it
                openDropdown(navItem, dropdown);
            } else {
                console.log('No dropdown found, navigating directly');
                // No dropdown - navigate directly
                const href = navLink.getAttribute('href');
                if (href && href !== '#') {
                    setTimeout(() => {
                        window.location.href = href;
                    }, 300); // Small delay for visual feedback
                }
            }
        } else {
            console.log(`Nav item at index ${index} not found`);
        }
    }

    // Open dropdown properly (for keyboard shortcuts)
    function openDropdown(navItem, dropdown) {
        console.log('Opening dropdown for:', navItem);

        // Add a class to force the dropdown to show
        navItem.classList.add('dropdown-shortcut-open');

        // Show dropdown - the CSS class should handle this, but set inline as backup
        dropdown.style.display = 'block';

        // Use unified keyboard navigation function
        enableDropdownKeyboardNavigation(navItem, dropdown);

        // Focus first dropdown item after a tiny delay
        setTimeout(() => {
            const firstItem = dropdown.querySelector('.dropdown-item:not(.dropdown-divider)');
            if (firstItem) {
                console.log('Focusing first dropdown item');
                firstItem.focus();
            } else {
                console.log('No dropdown items found');
            }
        }, 150);
    }

    // Setup keyboard navigation for dropdown items
    function setupDropdownKeyboardNav(dropdown, navItem) {
        const items = Array.from(dropdown.querySelectorAll('.dropdown-item:not(.dropdown-divider)'));

        const handleKeyDown = (e) => {
            // Get currently focused item
            const focusedIndex = items.findIndex(item => item === document.activeElement);
            let currentIndex = focusedIndex >= 0 ? focusedIndex : 0;

            if (e.key === 'ArrowDown') {
                e.preventDefault();
                currentIndex = (currentIndex + 1) % items.length;
                items[currentIndex].focus();
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                currentIndex = (currentIndex - 1 + items.length) % items.length;
                items[currentIndex].focus();
            } else if (e.key === 'Enter') {
                e.preventDefault();
                const focusedItem = document.activeElement;
                if (items.includes(focusedItem)) {
                    focusedItem.click();
                } else if (items[currentIndex]) {
                    items[currentIndex].click();
                }
            } else if (e.key === 'Escape') {
                e.preventDefault();
                closeAllDropdowns();
                const navLink = navItem.querySelector('.nav-link');
                if (navLink) navLink.focus();
            }
        };

        // Remove old listener if exists
        if (dropdown._keyHandler) {
            dropdown.removeEventListener('keydown', dropdown._keyHandler);
        }

        // Add new listener
        dropdown._keyHandler = handleKeyDown;
        dropdown.addEventListener('keydown', handleKeyDown);
    }

    // Close all open dropdowns (both shortcut-opened and keyboard-enabled)
    function closeAllDropdowns() {
        // Close shortcut-opened dropdowns
        document.querySelectorAll('.nav-item.dropdown-shortcut-open').forEach(item => {
            item.classList.remove('dropdown-shortcut-open');
            const dropdown = item.querySelector('.dropdown-menu');
            if (dropdown) {
                // Remove inline styles to allow CSS hover to work again
                dropdown.style.removeProperty('display');
                dropdown.style.removeProperty('opacity');
                dropdown.style.removeProperty('visibility');
                dropdown.style.removeProperty('z-index');

                // Remove keyboard handler
                if (dropdown._keyHandler) {
                    dropdown.removeEventListener('keydown', dropdown._keyHandler);
                    delete dropdown._keyHandler;
                }
            }
        });

        // Also cleanup keyboard-enabled dropdowns (opened via hover)
        document.querySelectorAll('.nav-item.dropdown-keyboard-enabled').forEach(item => {
            item.classList.remove('dropdown-keyboard-enabled');
            const dropdown = item.querySelector('.dropdown-menu');
            if (dropdown && dropdown._keyHandler) {
                dropdown.removeEventListener('keydown', dropdown._keyHandler);
                delete dropdown._keyHandler;
            }
        });
    }

    // Handle arrow key navigation from nav link to dropdown
    function setupNavLinkArrowKeys() {
        const navItems = document.querySelectorAll('.nav-menu > .nav-item');

        navItems.forEach(navItem => {
            const navLink = navItem.querySelector('.nav-link');
            const dropdown = navItem.querySelector('.dropdown-menu');
            if (!navLink || !dropdown) return;

            navLink.addEventListener('keydown', (e) => {
                // If dropdown is visible and ArrowDown is pressed, focus first item
                if (e.key === 'ArrowDown' && isDropdownVisible(dropdown)) {
                    e.preventDefault();
                    const firstItem = dropdown.querySelector('.dropdown-item:not(.dropdown-divider)');
                    if (firstItem) {
                        // Ensure keyboard navigation is enabled
                        if (!navItem.classList.contains('dropdown-keyboard-enabled')) {
                            enableDropdownKeyboardNavigation(navItem, dropdown);
                        }
                        firstItem.focus();
                    }
                }
            });
        });
    }

    // Navigate to URL
    function navigateTo(url) {
        showShortcutFeedback('Navigating...');
        window.location.href = url;
    }

    // Show visual feedback
    function showShortcutFeedback(text) {
        // Remove existing feedback
        const existing = document.getElementById('shortcut-feedback');
        if (existing) existing.remove();

        // Create feedback element
        const feedback = document.createElement('div');
        feedback.id = 'shortcut-feedback';
        feedback.textContent = text;
        feedback.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: #4CAF50;
            color: white;
            padding: 12px 24px;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
            z-index: 10000;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            animation: slideIn 0.3s ease-out;
        `;

        document.body.appendChild(feedback);

        // Remove after 2 seconds
        setTimeout(() => {
            feedback.style.animation = 'slideOut 0.3s ease-out';
            setTimeout(() => feedback.remove(), 300);
        }, 2000);
    }

    // Create help modal
    function createHelpModal() {
        const modal = document.createElement('div');
        modal.id = 'shortcuts-help-modal';
        modal.style.cssText = `
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.7);
            z-index: 9999;
            justify-content: center;
            align-items: center;
        `;

        const content = document.createElement('div');
        content.style.cssText = `
            background: white;
            padding: 30px;
            border-radius: 12px;
            max-width: 700px;
            width: 90%;
            max-height: 80vh;
            overflow-y: auto;
            box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        `;

        content.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                <h2 style="margin: 0; color: #333; font-size: 24px;">
                    <i class="fas fa-keyboard"></i> Keyboard Shortcuts
                </h2>
                <button id="close-shortcuts-modal" style="
                    background: #f44336;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 6px;
                    cursor: pointer;
                    font-size: 14px;
                    font-weight: 600;
                ">
                    <i class="fas fa-times"></i> Close
                </button>
            </div>

            <div style="margin-bottom: 25px;">
                <h3 style="color: #555; font-size: 18px; margin-bottom: 15px; border-bottom: 2px solid #4CAF50; padding-bottom: 8px;">
                    <i class="fas fa-compass"></i> Navigation Shortcuts
                </h3>
                ${generateShortcutList(shortcuts.navigation)}
            </div>

            <div style="margin-bottom: 25px;">
                <h3 style="color: #555; font-size: 18px; margin-bottom: 15px; border-bottom: 2px solid #2196F3; padding-bottom: 8px;">
                    <i class="fas fa-bolt"></i> Quick Actions
                </h3>
                ${generateShortcutList(shortcuts.direct)}
            </div>

            <div>
                <h3 style="color: #555; font-size: 18px; margin-bottom: 15px; border-bottom: 2px solid #FF9800; padding-bottom: 8px;">
                    <i class="fas fa-info-circle"></i> Help
                </h3>
                ${generateShortcutList(shortcuts.help)}
            </div>

            <div style="margin-top: 25px; padding: 15px; background: #f5f5f5; border-radius: 8px; font-size: 13px; color: #666;">
                <strong>💡 Tips:</strong>
                <ul style="margin: 10px 0 0 0; padding-left: 20px;">
                    <li>Use <kbd>Arrow Keys</kbd> to navigate dropdown menus</li>
                    <li>Press <kbd>Enter</kbd> to select an option</li>
                    <li>Press <kbd>Esc</kbd> to close dropdowns or this help modal</li>
                </ul>
            </div>
        `;

        modal.appendChild(content);
        document.body.appendChild(modal);

        // Close modal handlers
        document.getElementById('close-shortcuts-modal').addEventListener('click', toggleHelpModal);
        modal.addEventListener('click', (e) => {
            if (e.target === modal) toggleHelpModal();
        });

        // ESC key to close
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && modal.style.display === 'flex') {
                toggleHelpModal();
            }
        });
    }

    // Generate shortcut list HTML
    function generateShortcutList(shortcutList) {
        return shortcutList.map(s => `
            <div style="
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 12px;
                margin-bottom: 8px;
                background: #f9f9f9;
                border-radius: 6px;
                border-left: 4px solid #4CAF50;
            ">
                <div style="display: flex; align-items: center; gap: 10px;">
                    <i class="fas ${s.icon}" style="color: #666; width: 20px;"></i>
                    <span style="color: #333; font-weight: 500;">${s.label}</span>
                </div>
                <kbd style="
                    background: white;
                    padding: 6px 12px;
                    border-radius: 4px;
                    border: 1px solid #ddd;
                    font-family: monospace;
                    font-size: 12px;
                    font-weight: 600;
                    color: #555;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                ">${s.keys}</kbd>
            </div>
        `).join('');
    }

    // Toggle help modal
    function toggleHelpModal() {
        const modal = document.getElementById('shortcuts-help-modal');
        if (modal.style.display === 'flex') {
            modal.style.display = 'none';
        } else {
            modal.style.display = 'flex';
        }
    }

    // Add required CSS animations and styles
    const style = document.createElement('style');
    style.id = 'shortcuts-styles';
    style.textContent = `
        @keyframes slideIn {
            from {
                transform: translateX(100%);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }

        @keyframes slideOut {
            from {
                transform: translateX(0);
                opacity: 1;
            }
            to {
                transform: translateX(100%);
                opacity: 0;
            }
        }

        /* Dropdown navigation support */
        .nav-item .dropdown-menu .dropdown-item:focus {
            background-color: #4CAF50;
            color: white;
            outline: none;
        }

        .nav-link:focus {
            outline: 2px solid #4CAF50;
            outline-offset: 2px;
        }

        /* Force dropdown to show when opened via shortcut - must override :hover rule */
        .navbar .nav-item.dropdown-shortcut-open > .dropdown-menu {
            display: block !important;
        }

        /* Ensure dropdown stays visible when item has focus or is hovered */
        .navbar .nav-item.dropdown-shortcut-open:hover > .dropdown-menu,
        .navbar .nav-item.dropdown-shortcut-open:focus-within > .dropdown-menu,
        .navbar .nav-item.dropdown-shortcut-open.dropdown-shortcut-open > .dropdown-menu {
            display: block !important;
        }
    `;

    // Only add if not already added
    if (!document.getElementById('shortcuts-styles')) {
        document.head.appendChild(style);
    }

    // Initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initShortcuts);
    } else {
        initShortcuts();
    }

})();