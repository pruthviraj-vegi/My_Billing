/**
 * Form Submit Guard - Prevents duplicate form submissions
 * Works with both regular forms and AJAX forms
 * 
 * Usage:
 * 1. Add data-prevent-double-submit attribute to form or button
 * 2. Or call FormSubmitGuard.init() to auto-protect all forms
 */

(function(window) {
    'use strict';

    const FormSubmitGuard = {
        // Track active submissions
        activeSubmissions: new Set(),
        
        // Default options
        defaults: {
            disableButton: true,
            showSpinner: true,
            restoreOnError: true,
            restoreDelay: 3000, // Auto-restore after 3s if no response
            buttonText: {
                submitting: 'Submitting...',
                submitted: 'Submitted'
            }
        },

        /**
         * Initialize - Auto-protect all forms with data-prevent-double-submit
         */
        init: function(options = {}) {
            const config = { ...this.defaults, ...options };
            
            // Protect forms with data attribute
            document.querySelectorAll('form[data-prevent-double-submit]').forEach(form => {
                this.protectForm(form, config);
            });

            // Protect buttons with data attribute
            document.querySelectorAll('button[data-prevent-double-submit], input[type="submit"][data-prevent-double-submit]').forEach(button => {
                this.protectButton(button, config);
            });

            // Auto-protect all submit buttons if autoProtect is enabled
            if (config.autoProtect) {
                document.querySelectorAll('form').forEach(form => {
                    if (!form.hasAttribute('data-prevent-double-submit')) {
                        this.protectForm(form, config);
                    }
                });
            }
        },

        /**
         * Protect a form from double submission
         */
        protectForm: function(form, options = {}) {
            const config = { ...this.defaults, ...options };
            const formId = form.id || `form_${Date.now()}_${Math.random()}`;
            
            form.addEventListener('submit', function(e) {
                // Check if already submitting
                if (FormSubmitGuard.activeSubmissions.has(formId)) {
                    e.preventDefault();
                    e.stopPropagation();
                    return false;
                }

                // Mark as submitting
                FormSubmitGuard.activeSubmissions.add(formId);
                
                // Get submit button
                const submitButton = form.querySelector('button[type="submit"], input[type="submit"]') 
                    || form.querySelector('button:not([type]), input:not([type])');

                // Store original state
                const originalState = {
                    button: submitButton,
                    disabled: submitButton ? submitButton.disabled : false,
                    text: submitButton ? submitButton.textContent || submitButton.value : '',
                    innerHTML: submitButton ? submitButton.innerHTML : ''
                };

                // Disable button and show loading state
                if (submitButton && config.disableButton) {
                    FormSubmitGuard.setSubmittingState(submitButton, config);
                }

                // Handle form submission completion
                const handleComplete = function() {
                    FormSubmitGuard.activeSubmissions.delete(formId);
                    
                    if (submitButton && config.disableButton) {
                        if (config.restoreOnError) {
                            // Auto-restore after delay (in case of network issues)
                            setTimeout(() => {
                                if (FormSubmitGuard.activeSubmissions.has(formId)) {
                                    FormSubmitGuard.restoreButtonState(submitButton, originalState);
                                }
                            }, config.restoreDelay);
                        }
                    }
                };

                // For AJAX forms, listen for custom events
                form.addEventListener('ajax:success', handleComplete, { once: true });
                form.addEventListener('ajax:error', handleComplete, { once: true });
                form.addEventListener('ajax:complete', handleComplete, { once: true });

                // For regular forms, restore on page unload or after timeout
                if (!form.hasAttribute('data-ajax-form')) {
                    // If form submits normally (page reload), browser will handle it
                    // But if it's prevented, restore after timeout
                    setTimeout(handleComplete, config.restoreDelay);
                }
            });
        },

        /**
         * Protect a button from double clicks
         */
        protectButton: function(button, options = {}) {
            const config = { ...this.defaults, ...options };
            const buttonId = button.id || `btn_${Date.now()}_${Math.random()}`;
            
            button.addEventListener('click', function(e) {
                // Check if already submitting
                if (FormSubmitGuard.activeSubmissions.has(buttonId)) {
                    e.preventDefault();
                    e.stopPropagation();
                    return false;
                }

                // Only protect if it's a submit button or has submit behavior
                if (button.type !== 'submit' && !button.closest('form')) {
                    return;
                }

                // Mark as submitting
                FormSubmitGuard.activeSubmissions.add(buttonId);
                
                // Store original state
                const originalState = {
                    disabled: button.disabled,
                    text: button.textContent || button.value,
                    innerHTML: button.innerHTML
                };

                // Set submitting state
                if (config.disableButton) {
                    FormSubmitGuard.setSubmittingState(button, config);
                }

                // Restore after delay or on completion
                const handleComplete = function() {
                    FormSubmitGuard.activeSubmissions.delete(buttonId);
                    if (config.restoreOnError) {
                        setTimeout(() => {
                            if (FormSubmitGuard.activeSubmissions.has(buttonId)) {
                                FormSubmitGuard.restoreButtonState(button, originalState);
                            }
                        }, config.restoreDelay);
                    }
                };

                // Listen for custom events (for AJAX)
                button.addEventListener('ajax:success', handleComplete, { once: true });
                button.addEventListener('ajax:error', handleComplete, { once: true });
                button.addEventListener('ajax:complete', handleComplete, { once: true });

                // Auto-restore after timeout
                setTimeout(handleComplete, config.restoreDelay);
            });
        },

        /**
         * Set button to submitting state
         */
        setSubmittingState: function(button, config) {
            button.disabled = true;
            button.classList.add('submitting');
            
            if (config.showSpinner) {
                const spinner = '<i class="fas fa-spinner fa-spin"></i> ';
                if (button.tagName === 'INPUT') {
                    button.value = spinner + (config.buttonText.submitting || 'Submitting...');
                } else {
                    const originalText = button.textContent.trim();
                    button.dataset.originalText = originalText;
                    button.innerHTML = spinner + (config.buttonText.submitting || originalText);
                }
            }
        },

        /**
         * Restore button to original state
         */
        restoreButtonState: function(button, originalState) {
            if (!button) return;
            
            button.disabled = originalState.disabled;
            button.classList.remove('submitting');
            
            if (button.tagName === 'INPUT') {
                button.value = originalState.text;
            } else {
                button.innerHTML = originalState.innerHTML;
            }
        },

        /**
         * Manually mark submission as complete (for custom AJAX handlers)
         */
        complete: function(formOrButton) {
            const element = typeof formOrButton === 'string' 
                ? document.getElementById(formOrButton) 
                : formOrButton;
            
            if (element) {
                const id = element.id || `element_${Date.now()}`;
                this.activeSubmissions.delete(id);
                
                // Restore button if exists
                const button = element.querySelector('button[type="submit"], input[type="submit"]') 
                    || element;
                
                if (button && button.classList.contains('submitting')) {
                    const originalText = button.dataset.originalText || button.textContent;
                    button.disabled = false;
                    button.classList.remove('submitting');
                    if (button.tagName !== 'INPUT') {
                        button.innerHTML = originalText;
                    }
                }
            }
        },

        /**
         * Check if form/button is currently submitting
         */
        isSubmitting: function(formOrButton) {
            const element = typeof formOrButton === 'string' 
                ? document.getElementById(formOrButton) 
                : formOrButton;
            
            if (!element) return false;
            
            const id = element.id || 'unknown';
            return this.activeSubmissions.has(id);
        }
    };

    // Auto-initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => FormSubmitGuard.init());
    } else {
        FormSubmitGuard.init();
    }

    // Expose globally
    window.FormSubmitGuard = FormSubmitGuard;

})(window);

