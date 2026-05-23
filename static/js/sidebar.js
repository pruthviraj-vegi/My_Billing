// ========================================
// SIDEBAR JS — Mobile-Only Sidebar Navigation
// At ≤768px, transforms the horizontal .navbar into
// a slide-in vertical sidebar overlay.
// Desktop uses native CSS hover dropdowns from main.css.
// ========================================

(function () {
  'use strict';

  let sidebar, toggleBtn, overlay;

  function initSidebar() {
    sidebar = document.getElementById('sidebar');
    toggleBtn = document.getElementById('sidebarToggle');
    overlay = document.getElementById('sidebarOverlay');

    if (!sidebar || !toggleBtn) return;

    // Hamburger toggle (mobile only)
    toggleBtn.addEventListener('click', function () {
      if (window.innerWidth <= 768) {
        toggleSidebar();
      }
    });

    // Overlay click closes sidebar
    if (overlay) {
      overlay.addEventListener('click', closeSidebar);
    }

    // Accordion dropdowns (mobile only)
    initAccordion();

    // Close sidebar when leaf link clicked (mobile)
    initMobileNavClose();

    // Resize: reset state when going above mobile
    window.addEventListener('resize', function () {
      if (window.innerWidth > 768) {
        resetSidebar();
        destroyPageActionsDropdowns();
      } else {
        initPageActionsDropdowns();
      }
    });

    // Init on load
    initPageActionsDropdowns();

    // Global: close page-actions dropdown on outside click
    document.addEventListener('click', function (e) {
      if (!e.target.closest('.page-actions')) {
        document.querySelectorAll('.page-actions-dropdown.open').forEach(function (d) {
          d.classList.remove('open');
        });
      }
    });
  }

  function toggleSidebar() {
    if (!sidebar || window.innerWidth > 768) return;

    var isActive = sidebar.classList.toggle('active');
    if (overlay) {
      overlay.classList.toggle('active', isActive);
    }
    document.body.style.overflow = isActive ? 'hidden' : '';
  }

  function closeSidebar() {
    if (!sidebar) return;
    sidebar.classList.remove('active');
    if (overlay) {
      overlay.classList.remove('active');
    }
    document.body.style.overflow = '';
    // Close all dropdowns on close
    closeAllDropdowns();
  }

  function resetSidebar() {
    if (!sidebar) return;
    sidebar.classList.remove('active', 'expanded', 'collapsed');
    if (overlay) overlay.classList.remove('active');
    document.body.style.overflow = '';
    closeAllDropdowns();
  }

  function closeAllDropdowns() {
    if (!sidebar) return;
    sidebar.querySelectorAll('.nav-item.dropdown-open').forEach(function (item) {
      item.classList.remove('dropdown-open');
    });
  }

  // ========================================
  // ACCORDION DROPDOWNS (mobile only)
  // ========================================
  function initAccordion() {
    if (!sidebar) return;

    sidebar.querySelectorAll('.nav-link.has-dropdown').forEach(function (link) {
      link.addEventListener('click', function (e) {
        if (window.innerWidth > 768) return; // desktop uses hover

        e.preventDefault();
        e.stopPropagation();

        var navItem = link.closest('.nav-item');
        var wasOpen = navItem.classList.contains('dropdown-open');

        // Close all other open dropdowns
        sidebar.querySelectorAll('.nav-item.dropdown-open').forEach(function (item) {
          item.classList.remove('dropdown-open');
        });

        // Toggle current
        if (!wasOpen) {
          navItem.classList.add('dropdown-open');

          // Scroll the open dropdown into view
          setTimeout(function () {
            var dropdown = navItem.querySelector('.dropdown-menu');
            if (dropdown) {
              dropdown.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }
          }, 100);
        }
      });
    });
  }

  // ========================================
  // MOBILE: Page actions 3-dots dropdown
  // Collapses extra buttons into a "⋯" menu
  // ========================================
  function initPageActionsDropdowns() {
    if (window.innerWidth > 768) return;

    document.querySelectorAll('.page-actions').forEach(function (actions) {
      if (actions.dataset.collapsed) return;

      var buttons = actions.querySelectorAll(':scope > a.btn, :scope > button.btn');
      if (buttons.length < 1) return;

      // Move ALL buttons into the dots dropdown
      actions.dataset.collapsed = 'true';
      actions.classList.add('has-more');

      var toggle = document.createElement('button');
      toggle.type = 'button';
      toggle.className = 'page-actions-toggle';
      toggle.innerHTML = '<i class="fas fa-ellipsis-v"></i>';

      var dropdown = document.createElement('div');
      dropdown.className = 'page-actions-dropdown';

      buttons.forEach(function (btn) {
        dropdown.appendChild(btn);
      });

      actions.appendChild(dropdown);
      actions.appendChild(toggle);

      toggle.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        var wasOpen = dropdown.classList.toggle('open');
        // Close other open dropdowns
        if (wasOpen) {
          document.querySelectorAll('.page-actions-dropdown.open').forEach(function (d) {
            if (d !== dropdown) d.classList.remove('open');
          });
        }
      });
    });
  }

  function destroyPageActionsDropdowns() {
    document.querySelectorAll('.page-actions[data-collapsed]').forEach(function (actions) {
      actions.classList.remove('has-more');
      delete actions.dataset.collapsed;
      actions.querySelectorAll('.page-actions-toggle, .page-actions-dropdown').forEach(function (el) {
        el.remove();
      });
    });
  }
  // ========================================
  function initMobileNavClose() {
    if (!sidebar) return;

    sidebar.addEventListener('click', function (e) {
      if (window.innerWidth > 768) return;

      var link = e.target.closest('a');
      if (!link) return;

      // Don't close for dropdown toggles
      if (link.classList.contains('nav-link') && link.classList.contains('has-dropdown')) return;

      // Close for any real link click (even active — let user see navigation)
      if (link.href && link.href !== '#' && !link.href.endsWith('#')) {
        closeSidebar();
      }
    });
  }

  // Initialize on DOMContentLoaded
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initSidebar);
  } else {
    initSidebar();
  }

})();
