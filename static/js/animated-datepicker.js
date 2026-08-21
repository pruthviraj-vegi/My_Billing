/**
 * Animated Theme-Matching Date & Time Picker Component
 * Ultra-smooth, lively micro-animations, theme support, and seamless Django form integration.
 */

(function (window, document) {
  'use strict';

  const MONTH_NAMES = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
  ];
  const WEEKDAY_NAMES = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'];

  let activePickerInstance = null;
  let sharedListenersRegistered = false;

  /**
   * Register document/window listeners once for all picker instances.
   * Only the activePickerInstance responds, avoiding duplicate listeners.
   */
  function registerSharedListeners() {
    if (sharedListenersRegistered) return;
    sharedListenersRegistered = true;

    // Close on outside click
    const handleOutsideClick = (e) => {
      const inst = activePickerInstance;
      if (!inst || !inst.isOpen || !inst.popup) return;
      if (!inst.popup.contains(e.target) &&
          !inst.input.contains(e.target) &&
          (!inst.wrapper || !inst.wrapper.contains(e.target))) {
        inst.close();
      }
    };

    document.addEventListener('mousedown', handleOutsideClick);
    document.addEventListener('touchstart', handleOutsideClick, { passive: true });

    // Escape key to close
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && activePickerInstance && activePickerInstance.isOpen) {
        activePickerInstance.close();
      }
    });

    // Recalculate position on scroll/resize
    window.addEventListener('scroll', () => {
      if (activePickerInstance && activePickerInstance.isOpen && activePickerInstance.popup) {
        activePickerInstance.positionPopup();
      }
    }, { passive: true });

    window.addEventListener('resize', () => {
      if (activePickerInstance && activePickerInstance.isOpen && activePickerInstance.popup) {
        activePickerInstance.positionPopup();
      }
    }, { passive: true });
  }

  class AnimatedDatePicker {
    constructor(inputElement, options = {}) {
      this.input = typeof inputElement === 'string' ? document.querySelector(inputElement) : inputElement;
      if (!this.input) return;
      if (this.input._animatedDatePickerInstance) {
        return this.input._animatedDatePickerInstance;
      }
      this.input._animatedDatePickerInstance = this;
      this.input.dataset.datepickerAttached = "true";

      this.options = Object.assign({
        enableTime: true,
        onSelect: null
      }, options);

      // Parse initial value or default to now
      this.selectedDate = this.parseDate(this.input.value) || new Date();
      this.viewYear = this.selectedDate.getFullYear();
      this.viewMonth = this.selectedDate.getMonth();

      // Time state (12-hour basis for UI display)
      let hours = this.selectedDate.getHours();
      this.ampm = hours >= 12 ? 'PM' : 'AM';
      this.displayHours = hours % 12 || 12;
      this.displayMinutes = this.selectedDate.getMinutes();

      this.popup = null;
      this.isOpen = false;
      this._closeTimeout = null;

      registerSharedListeners();
      this.initTrigger();
    }

    parseDate(str) {
      if (!str || typeof str !== 'string') return null;
      const trimmed = str.trim();
      if (!trimmed) return null;

      // Parse YYYY-MM-DD and YYYY-MM-DD[T/ ]HH:mm(:ss) directly with local components
      const parts = trimmed.split(/[\sT]+/);
      const dateParts = parts[0].split('-').map(Number);
      if (dateParts.length === 3 && !dateParts.some(isNaN)) {
        const year = dateParts[0];
        const month = dateParts[1] - 1;
        const day = dateParts[2];
        let hours = 0;
        let minutes = 0;
        let seconds = 0;
        if (parts[1]) {
          const timeParts = parts[1].split(':').map(Number);
          hours = timeParts[0] || 0;
          minutes = timeParts[1] || 0;
          seconds = timeParts[2] || 0;
        }

        const d = new Date(year, month, day, hours, minutes, seconds);
        return isNaN(d.getTime()) ? null : d;
      }

      // Fallback for other standard formats
      const d = new Date(trimmed.replace(' ', 'T'));
      return isNaN(d.getTime()) ? null : d;
    }

    padZero(num) {
      return String(num).padStart(2, '0');
    }

    formatValue(d) {
      if (!d) return '';
      const year = d.getFullYear();
      const month = this.padZero(d.getMonth() + 1);
      const day = this.padZero(d.getDate());
      if (!this.options.enableTime) {
        return `${year}-${month}-${day}`;
      }
      const hours = this.padZero(d.getHours());
      const minutes = this.padZero(d.getMinutes());
      return `${year}-${month}-${day}T${hours}:${minutes}`;
    }

    initTrigger() {
      this.wrapper = this.input.closest('.input-date-wrapper') || this.input.parentElement;
      this._boundListeners = [];

      const triggerOpen = (e) => {
        if (this.input.disabled ||
            this.input.getAttribute('data-disabled') === 'true' ||
            (this.wrapper && this.wrapper.classList.contains('field-disabled')) ||
            this.input.closest('.field-disabled')) {
          return;
        }
        e.preventDefault();
        e.stopPropagation();
        this.toggle();
      };

      // Single click path: input handles its own clicks,
      // wrapper handles clicks on the icon and empty area (no separate icon listener).
      this.input.addEventListener('click', triggerOpen);
      this._boundListeners.push({ target: this.input, event: 'click', handler: triggerOpen });

      if (this.wrapper) {
        const wrapperHandler = (e) => {
          if (e.target !== this.input) {
            triggerOpen(e);
          }
        };
        this.wrapper.addEventListener('click', wrapperHandler);
        this._boundListeners.push({ target: this.wrapper, event: 'click', handler: wrapperHandler });

        // Icon is clickable via the wrapper's listener (event bubbling).
        // Only set cursor style — no separate click handler to avoid double-toggle.
        const icon = this.wrapper.querySelector('.input-date-icon');
        if (icon) {
          icon.style.pointerEvents = 'auto';
          icon.style.cursor = 'pointer';
        }
      }
    }

    toggle() {
      if (this.isOpen && this.popup && document.body.contains(this.popup)) {
        this.close();
      } else {
        this.open();
      }
    }

    open() {
      // If already open and attached, nothing to do
      if (this.isOpen && this.popup && document.body.contains(this.popup)) return;

      // Close any other active picker immediately
      if (activePickerInstance && activePickerInstance !== this) {
        activePickerInstance.close(true);
      }

      // Cancel any pending close animation on THIS instance
      if (this._closeTimeout) {
        clearTimeout(this._closeTimeout);
        this._closeTimeout = null;
      }

      // Clean up previous popup element if it exists
      if (this.popup && this.popup.parentElement) {
        this.popup.remove();
      }
      this.popup = null;

      activePickerInstance = this;
      this.isOpen = true;

      // Sync state from input if changed
      const currentValDate = this.parseDate(this.input.value);
      if (currentValDate) {
        this.selectedDate = currentValDate;
        this.viewYear = currentValDate.getFullYear();
        this.viewMonth = currentValDate.getMonth();
        let hours = currentValDate.getHours();
        this.ampm = hours >= 12 ? 'PM' : 'AM';
        this.displayHours = hours % 12 || 12;
        this.displayMinutes = currentValDate.getMinutes();
      }

      this.buildPopup();
      this.positionPopup();
    }

    close(immediate = false) {
      if (!this.isOpen && !this.popup) {
        this.isOpen = false;
        if (activePickerInstance === this) {
          activePickerInstance = null;
        }
        return;
      }

      this.isOpen = false;
      if (activePickerInstance === this) {
        activePickerInstance = null;
      }

      if (this._closeTimeout) {
        clearTimeout(this._closeTimeout);
        this._closeTimeout = null;
      }

      const popupToClose = this.popup;
      this.popup = null;

      if (!popupToClose) return;

      if (immediate || !popupToClose.parentElement) {
        if (popupToClose.parentElement) {
          popupToClose.remove();
        }
        return;
      }

      popupToClose.classList.add('closing');
      this._closeTimeout = setTimeout(() => {
        if (popupToClose && popupToClose.parentElement) {
          popupToClose.remove();
        }
        this._closeTimeout = null;
      }, 160);
    }

    positionPopup() {
      if (!this.popup) return;
      const rect = this.input.getBoundingClientRect();

      // Measure actual popup dimensions instead of hardcoding
      const popupWidth = this.popup.offsetWidth || 310;
      const popupHeight = this.popup.offsetHeight || 280;

      const spaceBelow = window.innerHeight - rect.bottom;
      const spaceAbove = rect.top;

      let top = rect.bottom + 6;
      let left = rect.left;

      // Flip above if needed or clamp strictly inside viewport
      if (spaceBelow < popupHeight && spaceAbove > spaceBelow) {
        top = Math.max(10, rect.top - popupHeight - 6);
      } else {
        if (top + popupHeight > window.innerHeight - 10) {
          top = Math.max(10, window.innerHeight - popupHeight - 10);
        }
      }

      // Constrain horizontally
      if (left + popupWidth > window.innerWidth - 12) {
        left = Math.max(10, window.innerWidth - popupWidth - 12);
      }
      if (left < 10) left = 10;

      this.popup.style.position = 'fixed';
      this.popup.style.top = `${top}px`;
      this.popup.style.left = `${left}px`;
      this.popup.style.zIndex = '999999';
    }

    buildPopup() {
      if (this.popup) this.popup.remove();

      this.popup = document.createElement('div');
      this.popup.className = 'adp-popup' + (this.options.enableTime ? ' has-time' : '');

      // Calendar Column
      const calendarCol = document.createElement('div');
      calendarCol.className = 'adp-calendar-col';

      // Header (Month / Year Navigation)
      const header = document.createElement('div');
      header.className = 'adp-header';

      const titleGroup = document.createElement('div');
      titleGroup.className = 'adp-title-group';

      // Month select dropdown
      const monthSelect = document.createElement('select');
      monthSelect.className = 'adp-month-select';
      monthSelect.setAttribute('aria-label', 'Select Month');
      MONTH_NAMES.forEach((m, idx) => {
        const opt = document.createElement('option');
        opt.value = idx;
        opt.textContent = m;
        if (idx === this.viewMonth) opt.selected = true;
        monthSelect.appendChild(opt);
      });
      monthSelect.addEventListener('change', (e) => {
        this.viewMonth = parseInt(e.target.value, 10);
        this.renderCalendar();
      });

      // Year select dropdown
      const yearSelect = document.createElement('select');
      yearSelect.className = 'adp-year-select';
      yearSelect.setAttribute('aria-label', 'Select Year');
      const currentYear = new Date().getFullYear();
      for (let y = currentYear - 10; y <= currentYear + 10; y++) {
        const opt = document.createElement('option');
        opt.value = y;
        opt.textContent = y;
        if (y === this.viewYear) opt.selected = true;
        yearSelect.appendChild(opt);
      }
      yearSelect.addEventListener('change', (e) => {
        this.viewYear = parseInt(e.target.value, 10);
        this.renderCalendar();
      });

      titleGroup.appendChild(monthSelect);
      titleGroup.appendChild(yearSelect);

      // Nav buttons (Prev / Next)
      const navBtns = document.createElement('div');
      navBtns.className = 'adp-nav-btns';

      const prevBtn = document.createElement('button');
      prevBtn.type = 'button';
      prevBtn.className = 'adp-nav-btn';
      prevBtn.innerHTML = '<i class="fa-solid fa-chevron-left"></i>';
      prevBtn.setAttribute('aria-label', 'Previous month');
      prevBtn.addEventListener('click', () => {
        this.viewMonth--;
        if (this.viewMonth < 0) {
          this.viewMonth = 11;
          this.viewYear--;
        }
        this.renderCalendar();
      });

      const nextBtn = document.createElement('button');
      nextBtn.type = 'button';
      nextBtn.className = 'adp-nav-btn';
      nextBtn.innerHTML = '<i class="fa-solid fa-chevron-right"></i>';
      nextBtn.setAttribute('aria-label', 'Next month');
      nextBtn.addEventListener('click', () => {
        this.viewMonth++;
        if (this.viewMonth > 11) {
          this.viewMonth = 0;
          this.viewYear++;
        }
        this.renderCalendar();
      });

      navBtns.appendChild(prevBtn);
      navBtns.appendChild(nextBtn);

      header.appendChild(titleGroup);
      header.appendChild(navBtns);
      calendarCol.appendChild(header);

      // Weekdays Header
      const weekdays = document.createElement('div');
      weekdays.className = 'adp-weekdays';
      WEEKDAY_NAMES.forEach(w => {
        const wd = document.createElement('div');
        wd.className = 'adp-weekday';
        wd.textContent = w;
        weekdays.appendChild(wd);
      });
      calendarCol.appendChild(weekdays);

      // Days Grid container
      this.daysContainer = document.createElement('div');
      this.daysContainer.className = 'adp-days';
      calendarCol.appendChild(this.daysContainer);

      // Assemble Layout
      if (this.options.enableTime) {
        const bodyGrid = document.createElement('div');
        bodyGrid.className = 'adp-body-grid';
        bodyGrid.appendChild(calendarCol);

        // Side Column (Time + Action Presets)
        const sideCol = document.createElement('div');
        sideCol.className = 'adp-side-col';

        // Time Box
        const timeBox = document.createElement('div');
        timeBox.className = 'adp-time-box';

        const timeTitle = document.createElement('div');
        timeTitle.className = 'adp-time-title';
        timeTitle.innerHTML = '<i class="fa-solid fa-clock"></i> Time';

        const timeControls = document.createElement('div');
        timeControls.className = 'adp-time-controls';

        // Hours input
        this.hoursInput = document.createElement('input');
        this.hoursInput.type = 'number';
        this.hoursInput.className = 'adp-time-input';
        this.hoursInput.min = 1;
        this.hoursInput.max = 12;
        this.hoursInput.value = this.padZero(this.displayHours);
        this.hoursInput.setAttribute('aria-label', 'Hours');
        this.hoursInput.addEventListener('change', () => {
          let val = parseInt(this.hoursInput.value, 10);
          if (isNaN(val) || val < 1) val = 1;
          if (val > 12) val = 12;
          this.displayHours = val;
          this.hoursInput.value = this.padZero(val);
          this.commitDate();
        });

        // Colon
        const colon = document.createElement('span');
        colon.className = 'adp-time-colon';
        colon.textContent = ':';

        // Minutes input
        this.minutesInput = document.createElement('input');
        this.minutesInput.type = 'number';
        this.minutesInput.className = 'adp-time-input';
        this.minutesInput.min = 0;
        this.minutesInput.max = 59;
        this.minutesInput.value = this.padZero(this.displayMinutes);
        this.minutesInput.setAttribute('aria-label', 'Minutes');
        this.minutesInput.addEventListener('change', () => {
          let val = parseInt(this.minutesInput.value, 10);
          if (isNaN(val) || val < 0) val = 0;
          if (val > 59) val = 59;
          this.displayMinutes = val;
          this.minutesInput.value = this.padZero(val);
          this.commitDate();
        });

        // AM/PM Button
        this.ampmBtn = document.createElement('button');
        this.ampmBtn.type = 'button';
        this.ampmBtn.className = 'adp-ampm-btn';
        this.ampmBtn.textContent = this.ampm;
        this.ampmBtn.setAttribute('aria-label', 'Toggle AM/PM');
        this.ampmBtn.addEventListener('click', () => {
          this.ampm = this.ampm === 'AM' ? 'PM' : 'AM';
          this.ampmBtn.textContent = this.ampm;
          this.commitDate();
        });

        timeControls.appendChild(this.hoursInput);
        timeControls.appendChild(colon);
        timeControls.appendChild(this.minutesInput);
        timeControls.appendChild(this.ampmBtn);

        timeBox.appendChild(timeTitle);
        timeBox.appendChild(timeControls);
        sideCol.appendChild(timeBox);

        // Side Actions
        const sideActions = document.createElement('div');
        sideActions.className = 'adp-side-actions';

        const nowBtn = document.createElement('button');
        nowBtn.type = 'button';
        nowBtn.className = 'adp-preset-btn';
        nowBtn.textContent = 'Now';
        nowBtn.addEventListener('click', () => {
          const now = new Date();
          this.selectedDate = now;
          this.viewYear = now.getFullYear();
          this.viewMonth = now.getMonth();
          let hours = now.getHours();
          this.ampm = hours >= 12 ? 'PM' : 'AM';
          this.displayHours = hours % 12 || 12;
          this.displayMinutes = now.getMinutes();
          if (this.hoursInput) this.hoursInput.value = this.padZero(this.displayHours);
          if (this.minutesInput) this.minutesInput.value = this.padZero(this.displayMinutes);
          if (this.ampmBtn) this.ampmBtn.textContent = this.ampm;
          this.commitDate();
          this.renderCalendar();
        });

        const clearBtn = document.createElement('button');
        clearBtn.type = 'button';
        clearBtn.className = 'adp-preset-btn';
        clearBtn.textContent = 'Clear';
        clearBtn.addEventListener('click', () => {
          this.input.value = '';
          this.selectedDate = null;
          this.renderCalendar();
          this.input.dispatchEvent(new Event('input', { bubbles: true }));
          this.input.dispatchEvent(new Event('change', { bubbles: true }));
        });

        const doneBtn = document.createElement('button');
        doneBtn.type = 'button';
        doneBtn.className = 'adp-done-btn';
        doneBtn.textContent = 'Done';
        doneBtn.addEventListener('click', () => {
          this.commitDate();
          this.close();
        });

        sideActions.appendChild(nowBtn);
        sideActions.appendChild(clearBtn);
        sideActions.appendChild(doneBtn);
        sideCol.appendChild(sideActions);

        bodyGrid.appendChild(sideCol);
        this.popup.appendChild(bodyGrid);
      } else {
        this.popup.appendChild(calendarCol);

        // Date-only footer
        const footer = document.createElement('div');
        footer.className = 'adp-footer';

        const todayBtn = document.createElement('button');
        todayBtn.type = 'button';
        todayBtn.className = 'adp-preset-btn';
        todayBtn.textContent = 'Today';
        todayBtn.addEventListener('click', () => {
          const now = new Date();
          this.selectedDate = now;
          this.viewYear = now.getFullYear();
          this.viewMonth = now.getMonth();
          this.commitDate();
          this.renderCalendar();
        });

        const clearBtn = document.createElement('button');
        clearBtn.type = 'button';
        clearBtn.className = 'adp-preset-btn';
        clearBtn.textContent = 'Clear';
        clearBtn.addEventListener('click', () => {
          this.input.value = '';
          this.selectedDate = null;
          this.renderCalendar();
          this.input.dispatchEvent(new Event('input', { bubbles: true }));
          this.input.dispatchEvent(new Event('change', { bubbles: true }));
        });

        const doneBtn = document.createElement('button');
        doneBtn.type = 'button';
        doneBtn.className = 'adp-done-btn';
        doneBtn.textContent = 'Done';
        doneBtn.addEventListener('click', () => {
          this.commitDate();
          this.close();
        });

        footer.appendChild(todayBtn);
        footer.appendChild(clearBtn);
        footer.appendChild(doneBtn);
        this.popup.appendChild(footer);
      }

      document.body.appendChild(this.popup);
      this.renderCalendar();
    }

    renderCalendar() {
      if (!this.popup) return;

      // Sync Header Dropdowns
      const monthSelect = this.popup.querySelector('.adp-month-select');
      const yearSelect = this.popup.querySelector('.adp-year-select');
      if (monthSelect) monthSelect.value = this.viewMonth;
      if (yearSelect) yearSelect.value = this.viewYear;

      this.daysContainer.innerHTML = '';

      const firstDay = new Date(this.viewYear, this.viewMonth, 1).getDay();
      const daysInMonth = new Date(this.viewYear, this.viewMonth + 1, 0).getDate();
      const daysInPrevMonth = new Date(this.viewYear, this.viewMonth, 0).getDate();

      const today = new Date();
      const isCurrentMonthToday = today.getFullYear() === this.viewYear && today.getMonth() === this.viewMonth;

      // Previous month trailing days
      for (let i = firstDay - 1; i >= 0; i--) {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'adp-day other-month';
        btn.textContent = daysInPrevMonth - i;
        btn.addEventListener('click', () => {
          this.viewMonth--;
          if (this.viewMonth < 0) {
            this.viewMonth = 11;
            this.viewYear--;
          }
          this.selectDate(this.viewYear, this.viewMonth, daysInPrevMonth - i);
        });
        this.daysContainer.appendChild(btn);
      }

      // Current month days
      for (let d = 1; d <= daysInMonth; d++) {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'adp-day';
        btn.textContent = d;

        if (isCurrentMonthToday && today.getDate() === d) {
          btn.classList.add('today');
        }

        if (this.selectedDate &&
            this.selectedDate.getFullYear() === this.viewYear &&
            this.selectedDate.getMonth() === this.viewMonth &&
            this.selectedDate.getDate() === d) {
          btn.classList.add('selected');
        }

        btn.addEventListener('click', () => {
          this.selectDate(this.viewYear, this.viewMonth, d);
        });

        this.daysContainer.appendChild(btn);
      }

      // Next month leading days (fill up 6 rows = 42 cells total for consistent height)
      const totalRendered = firstDay + daysInMonth;
      const remainingCells = totalRendered <= 35 ? 35 - totalRendered : 42 - totalRendered;
      for (let n = 1; n <= remainingCells; n++) {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'adp-day other-month';
        btn.textContent = n;
        btn.addEventListener('click', () => {
          this.viewMonth++;
          if (this.viewMonth > 11) {
            this.viewMonth = 0;
            this.viewYear++;
          }
          this.selectDate(this.viewYear, this.viewMonth, n);
        });
        this.daysContainer.appendChild(btn);
      }
    }

    selectDate(year, month, day) {
      let finalHours = this.displayHours % 12;
      if (this.ampm === 'PM') finalHours += 12;

      this.selectedDate = new Date(year, month, day, finalHours, this.displayMinutes, 0);
      this.viewYear = year;
      this.viewMonth = month;
      this.commitDate();
      this.renderCalendar();

      // If date-only mode, close immediately on date selection
      if (!this.options.enableTime) {
        this.close();
      }
    }

    commitDate() {
      if (!this.selectedDate) return;

      let finalHours = this.displayHours % 12;
      if (this.ampm === 'PM') finalHours += 12;

      this.selectedDate.setHours(finalHours);
      this.selectedDate.setMinutes(this.displayMinutes);

      const formatted = this.formatValue(this.selectedDate);
      this.input.value = formatted;
      this.input.dispatchEvent(new Event('input', { bubbles: true }));
      this.input.dispatchEvent(new Event('change', { bubbles: true }));

      if (typeof this.options.onSelect === 'function') {
        this.options.onSelect(this.selectedDate, formatted);
      }
    }

    destroy() {
      if (this._closeTimeout) {
        clearTimeout(this._closeTimeout);
        this._closeTimeout = null;
      }
      if (this.isOpen) {
        this.close(true);
      }
      if (this.popup && this.popup.parentElement) {
        this.popup.remove();
        this.popup = null;
      }
      if (this._boundListeners) {
        this._boundListeners.forEach(({ target, event, handler }) => {
          try {
            target.removeEventListener(event, handler);
          } catch (e) { /* ignore */ }
        });
        this._boundListeners = [];
      }
      if (this.input) {
        delete this.input._animatedDatePickerInstance;
        if (this.input.dataset) {
          delete this.input.dataset.datepickerAttached;
        }
      }
      if (activePickerInstance === this) {
        activePickerInstance = null;
      }
    }
  }

  // Global helper
  window.attachAnimatedDatePicker = function (selectorOrEl, options) {
    const el = typeof selectorOrEl === 'string' ? document.querySelector(selectorOrEl) : selectorOrEl;
    if (!el) return null;
    return new AnimatedDatePicker(el, options);
  };

  // Global auto-attach helper
  function initAllDatePickers(root = document) {
    if (!root || !root.querySelectorAll) return;
    root.querySelectorAll('.form-date-input, input[type="date"], input[type="datetime-local"]').forEach(input => {
      if (input.dataset.datepickerAttached || input._animatedDatePickerInstance) return;

      const isDateType = input.type === 'date';
      const isDateTimeType = input.type === 'datetime-local';

      let enableTime = true;
      if (input.dataset.datepickerTime !== undefined) {
        enableTime = input.dataset.datepickerTime !== 'false';
      } else if (isDateType) {
        enableTime = false;
      }

      if (isDateType || isDateTimeType) {
        input.type = 'text';
        input.readOnly = true;
        input.style.cursor = 'pointer';
        input.classList.add('form-date-input');
        if (!input.placeholder) {
          input.placeholder = enableTime ? 'Select Date & Time' : 'Select Date';
        }
      }

      window.attachAnimatedDatePicker(input, { enableTime: enableTime });
      input.dataset.datepickerAttached = 'true';
    });
  }

  // Auto-attach on page load
  document.addEventListener('DOMContentLoaded', () => {
    initAllDatePickers(document);

    // Watch for dynamically added date inputs (e.g. modals, popups, AJAX content)
    if (window.MutationObserver) {
      const observer = new MutationObserver(mutations => {
        for (const mutation of mutations) {
          if (mutation.addedNodes && mutation.addedNodes.length > 0) {
            mutation.addedNodes.forEach(node => {
              if (node.nodeType === Node.ELEMENT_NODE) {
                if (node.matches && node.matches('.form-date-input, input[type="date"], input[type="datetime-local"]')) {
                  initAllDatePickers(node.parentElement || document);
                } else if (node.querySelectorAll) {
                  initAllDatePickers(node);
                }
              }
            });
          }
        }
      });
      observer.observe(document.body, { childList: true, subtree: true });
    }
  });

  window.initAllDatePickers = initAllDatePickers;

})(window, document);
