/**
 * === Web Performance Analyzer ===
 * Author: Pruthvi x Cursor AI
 * 
 * Features:
 * - Measures DNS, TCP, TTFB, Response, DOM, and full page load times
 * - Lists individual resource timings
 * - Highlights slow assets (>300ms)
 * - Auto-prompts AI assistant to suggest optimization or missing data collection
 * - Real-time performance dashboard
 * - Export performance data
 */

class PerformanceAnalyzer {
    constructor() {
        this.metrics = {};
        this.resources = [];
        this.slowAssets = [];
        this.isVisible = false;
        this.init();
    }

    init() {
        // Wait for page load to ensure all resources are captured
        if (document.readyState === 'complete') {
            this.analyze().catch(console.error);
        } else {
            window.addEventListener('load', () => this.analyze().catch(console.error));
        }

        // Create performance dashboard
        this.createDashboard();

        // Add keyboard shortcut (Ctrl+Shift+P)
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.shiftKey && e.key === 'P') {
                e.preventDefault();
                this.toggleDashboard();
            }
        });
    }

    async analyze() {
        const navEntries = performance.getEntriesByType("navigation")[0];
        const resources = performance.getEntriesByType("resource");

        console.log("=== Page Performance Metrics ===");

        // Get Core Web Vitals asynchronously
        const [lcp, fid] = await Promise.all([
            this.getLCP(),
            this.getFID()
        ]);

        this.metrics = {
            dnsLookup: navEntries.domainLookupEnd - navEntries.domainLookupStart,
            tcpConnection: navEntries.connectEnd - navEntries.connectStart,
            ttfb: navEntries.responseStart - navEntries.requestStart,
            responseTime: navEntries.responseEnd - navEntries.responseStart,
            domLoad: navEntries.domContentLoadedEventEnd - navEntries.startTime,
            fullPageLoad: navEntries.loadEventEnd - navEntries.startTime,
            // Additional Core Web Vitals
            fcp: this.getFCP(),
            lcp: lcp,
            cls: this.getCLS(),
            fid: fid
        };

        // Log metrics to console
        for (const [key, value] of Object.entries(this.metrics)) {
            const displayValue = typeof value === 'number' ? value.toFixed(2) : value;
            console.log(`${key.replace(/([A-Z])/g, " $1")}:`, displayValue, "ms");
        }

        console.log("\n=== Resource Load Times ===");

        this.resources = resources.map(r => ({
            type: r.initiatorType.toUpperCase(),
            name: r.name,
            duration: r.duration,
            size: r.transferSize || 0
        }));

        this.resources.forEach((r) => {
            const duration = r.duration.toFixed(2);
            console.log(`${r.type} → ${r.name} : ${duration} ms`);

            // Track slow assets
            if (r.duration > 300) {
                this.slowAssets.push(r);
            }
        });

        // Detect potential issues
        this.detectIssues();

        // Generate AI prompt
        this.generateAIPrompt();

        // Calculate performance score
        this.calculatePerformanceScore();

        // Update dashboard if visible
        if (this.isVisible) {
            this.updateDashboard();
        }
    }

    detectIssues() {
        const missing = [];
        const warnings = [];

        // Critical issues
        if (this.metrics.fullPageLoad === 0) missing.push("Full page load time not captured");
        if (this.resources.length === 0) missing.push("No resource entries found (possible cache or CSP)");

        // Performance warnings
        if (this.metrics.ttfb > 200) warnings.push(`High TTFB (${this.metrics.ttfb.toFixed(2)}ms) - server response slow`);
        if (this.metrics.domLoad > 1000) warnings.push(`Slow DOM load (${this.metrics.domLoad.toFixed(2)}ms) - consider code splitting`);
        if (this.metrics.fcp > 1800) warnings.push(`Slow FCP (${this.metrics.fcp.toFixed(2)}ms) - first content paint delayed`);
        if (this.metrics.lcp > 2500) warnings.push(`Slow LCP (${this.metrics.lcp.toFixed(2)}ms) - largest content paint delayed`);
        if (this.metrics.cls > 0.1) warnings.push(`High CLS (${this.metrics.cls.toFixed(3)}) - layout shift detected`);
        if (this.metrics.fid > 100) warnings.push(`High FID (${this.metrics.fid.toFixed(2)}ms) - input delay detected`);
        if (this.slowAssets.length > 5) warnings.push("Multiple slow assets detected - optimization needed");

        // Check for specific bottlenecks
        const fontLoad = this.resources.find(r => r.name.includes('fonts.googleapis.com'));
        if (fontLoad && fontLoad.duration > 150) warnings.push(`Slow font loading (${fontLoad.duration.toFixed(2)}ms) - consider font optimization`);

        const chartLoad = this.resources.find(r => r.name.includes('chart'));
        if (chartLoad && chartLoad.duration > 200) warnings.push(`Heavy chart library (${chartLoad.duration.toFixed(2)}ms) - consider lazy loading`);

        if (missing.length > 0) {
            console.warn("\n⚠️ Critical Issues Detected:");
            missing.forEach((m) => console.warn(" -", m));
        }

        if (warnings.length > 0) {
            console.warn("\n⚠️ Performance Warnings:");
            warnings.forEach((w) => console.warn(" -", w));
        }

        return [...missing, ...warnings];
    }

    calculatePerformanceScore() {
        // Calculate overall performance score (0-100)
        let score = 100;

        // Deduct points for slow metrics
        if (this.metrics.lcp > 2500) score -= 30;
        else if (this.metrics.lcp > 2000) score -= 20;
        else if (this.metrics.lcp > 1500) score -= 10;

        if (this.metrics.fcp > 1800) score -= 25;
        else if (this.metrics.fcp > 1200) score -= 15;
        else if (this.metrics.fcp > 800) score -= 5;

        if (this.metrics.cls > 0.25) score -= 20;
        else if (this.metrics.cls > 0.1) score -= 10;

        if (this.metrics.fid > 300) score -= 15;
        else if (this.metrics.fid > 100) score -= 5;

        if (this.metrics.ttfb > 600) score -= 10;
        else if (this.metrics.ttfb > 200) score -= 5;

        // Deduct points for slow assets
        const slowAssetsCount = this.slowAssets.length;
        if (slowAssetsCount > 5) score -= 15;
        else if (slowAssetsCount > 3) score -= 10;
        else if (slowAssetsCount > 1) score -= 5;

        this.performanceScore = Math.max(0, Math.min(100, score));

        // Log performance grade
        let grade = 'F';
        if (this.performanceScore >= 90) grade = 'A+';
        else if (this.performanceScore >= 80) grade = 'A';
        else if (this.performanceScore >= 70) grade = 'B';
        else if (this.performanceScore >= 60) grade = 'C';
        else if (this.performanceScore >= 50) grade = 'D';

        console.log(`\n🎯 Performance Score: ${this.performanceScore}/100 (Grade: ${grade})`);

        return this.performanceScore;
    }

    generateAIPrompt() {
        const aiPrompt = `
The following page performance metrics were collected:
${Object.entries(this.metrics)
                .map(([k, v]) => `${k}: ${v.toFixed(2)} ms`)
                .join("\n")}

Resource load times:
${this.resources
                .map((r) => `${r.type} → ${r.name} : ${r.duration.toFixed(2)} ms`)
                .join("\n")}

Slow assets (>300ms):
${this.slowAssets
                .map((r) => `${r.type} → ${r.name} : ${r.duration.toFixed(2)} ms`)
                .join("\n")}

Now analyze this data and suggest:
1. Which assets should be optimized (slow >300ms)
2. What missing data should be captured (e.g., CLS, FCP, LCP, JS blocking)
3. Any code or configuration improvements for better performance
4. Specific recommendations for this Django billing application
`;

        console.log("\n\n=== 💡 AI Optimization Prompt ===\n", aiPrompt);
        console.log("\nCopy the above prompt and give it to Cursor AI to suggest optimization.\n");

        return aiPrompt;
    }

    // Core Web Vitals measurement methods
    getFCP() {
        try {
            const fcpEntry = performance.getEntriesByName('first-contentful-paint')[0];
            return fcpEntry ? fcpEntry.startTime : 0;
        } catch (e) {
            return 0;
        }
    }

    getLCP() {
        return new Promise((resolve) => {
            try {
                if (!('PerformanceObserver' in window)) {
                    resolve(0);
                    return;
                }

                const observer = new PerformanceObserver((list) => {
                    const entries = list.getEntries();
                    const lastEntry = entries[entries.length - 1];
                    resolve(lastEntry ? lastEntry.startTime : 0);
                });
                observer.observe({ entryTypes: ['largest-contentful-paint'] });

                // Timeout after 5 seconds
                setTimeout(() => resolve(0), 5000);
            } catch (e) {
                resolve(0);
            }
        });
    }

    getCLS() {
        try {
            if (!('PerformanceObserver' in window)) {
                return 0;
            }

            let clsValue = 0;
            const observer = new PerformanceObserver((list) => {
                for (const entry of list.getEntries()) {
                    if (!entry.hadRecentInput) {
                        clsValue += entry.value;
                    }
                }
            });
            observer.observe({ entryTypes: ['layout-shift'] });
            return clsValue;
        } catch (e) {
            return 0;
        }
    }

    getFID() {
        return new Promise((resolve) => {
            try {
                if (!('PerformanceObserver' in window)) {
                    resolve(0);
                    return;
                }

                const observer = new PerformanceObserver((list) => {
                    const entries = list.getEntries();
                    const firstEntry = entries[0];
                    resolve(firstEntry ? firstEntry.processingStart - firstEntry.startTime : 0);
                });
                observer.observe({ entryTypes: ['first-input'] });

                // Timeout after 5 seconds
                setTimeout(() => resolve(0), 5000);
            } catch (e) {
                resolve(0);
            }
        });
    }

    createDashboard() {
        const dashboard = document.createElement('div');
        dashboard.id = 'performance-dashboard';
        dashboard.className = 'perf-dashboard';
        dashboard.innerHTML = `
            <div class="perf-header">
                <h3>🚀 Performance Analyzer</h3>
                <div class="perf-controls">
                    <button class="perf-btn" id="perf-refresh">🔄</button>
                    <button class="perf-btn" id="perf-export">📊</button>
                    <button class="perf-btn" id="perf-close">✕</button>
                </div>
            </div>
            <div class="perf-content">
                <div class="perf-section">
                    <h4>📈 Core Metrics</h4>
                    <div class="perf-metrics" id="perf-metrics"></div>
                </div>
                <div class="perf-section">
                    <h4>📦 Resources</h4>
                    <div class="perf-resources" id="perf-resources"></div>
                </div>
                <div class="perf-section">
                    <h4>⚠️ Slow Assets</h4>
                    <div class="perf-slow" id="perf-slow"></div>
                </div>
                <div class="perf-section">
                    <h4>🤖 AI Prompt</h4>
                    <textarea class="perf-prompt" id="perf-prompt" readonly></textarea>
                    <button class="perf-btn perf-copy" id="perf-copy">📋 Copy</button>
                </div>
            </div>
        `;

        document.body.appendChild(dashboard);

        // Add event listeners
        document.getElementById('perf-refresh').addEventListener('click', () => this.refresh().catch(console.error));
        document.getElementById('perf-export').addEventListener('click', () => this.exportData());
        document.getElementById('perf-close').addEventListener('click', () => this.toggleDashboard());
        document.getElementById('perf-copy').addEventListener('click', () => this.copyPrompt());
    }

    updateDashboard() {
        // Update metrics
        const metricsEl = document.getElementById('perf-metrics');
        metricsEl.innerHTML = Object.entries(this.metrics)
            .map(([key, value]) => `
                <div class="perf-metric">
                    <span class="perf-label">${key.replace(/([A-Z])/g, " $1")}</span>
                    <span class="perf-value ${this.getMetricClass(key, value)}">${value.toFixed(2)} ms</span>
                </div>
            `).join('');

        // Update resources
        const resourcesEl = document.getElementById('perf-resources');
        resourcesEl.innerHTML = this.resources
            .slice(0, 10) // Show first 10 resources
            .map(r => `
                <div class="perf-resource ${r.duration > 300 ? 'slow' : ''}">
                    <span class="perf-resource-type">${r.type}</span>
                    <span class="perf-resource-name">${this.truncateUrl(r.name)}</span>
                    <span class="perf-resource-duration">${r.duration.toFixed(2)} ms</span>
                </div>
            `).join('');

        // Update slow assets
        const slowEl = document.getElementById('perf-slow');
        if (this.slowAssets.length > 0) {
            slowEl.innerHTML = this.slowAssets
                .map(r => `
                    <div class="perf-slow-asset">
                        <span class="perf-resource-type">${r.type}</span>
                        <span class="perf-resource-name">${this.truncateUrl(r.name)}</span>
                        <span class="perf-resource-duration slow">${r.duration.toFixed(2)} ms</span>
                    </div>
                `).join('');
        } else {
            slowEl.innerHTML = '<div class="perf-no-slow">✅ No slow assets detected</div>';
        }

        // Update AI prompt
        document.getElementById('perf-prompt').value = this.generateAIPrompt();
    }

    getMetricClass(key, value) {
        const thresholds = {
            dnsLookup: 100,
            tcpConnection: 200,
            ttfb: 1000,
            responseTime: 500,
            domLoad: 3000,
            fullPageLoad: 5000
        };

        if (value > thresholds[key]) return 'slow';
        if (value > thresholds[key] * 0.7) return 'warning';
        return 'good';
    }

    truncateUrl(url) {
        if (url.length > 50) {
            return url.substring(0, 47) + '...';
        }
        return url;
    }

    toggleDashboard() {
        const dashboard = document.getElementById('performance-dashboard');
        this.isVisible = !this.isVisible;

        if (this.isVisible) {
            dashboard.classList.add('visible');
            this.updateDashboard();
        } else {
            dashboard.classList.remove('visible');
        }
    }

    async refresh() {
        await this.analyze();
        this.updateDashboard();
    }

    exportData() {
        const data = {
            timestamp: new Date().toISOString(),
            url: window.location.href,
            metrics: this.metrics,
            resources: this.resources,
            slowAssets: this.slowAssets,
            userAgent: navigator.userAgent
        };

        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `performance-${Date.now()}.json`;
        a.click();
        URL.revokeObjectURL(url);
    }

    copyPrompt() {
        const prompt = document.getElementById('perf-prompt');
        prompt.select();
        document.execCommand('copy');

        // Show feedback
        const btn = document.getElementById('perf-copy');
        const originalText = btn.textContent;
        btn.textContent = '✅ Copied!';
        setTimeout(() => {
            btn.textContent = originalText;
        }, 2000);
    }
}

// Initialize performance analyzer
const perfAnalyzer = new PerformanceAnalyzer();

// Expose global function for manual analysis
window.analyzePerformance = () => perfAnalyzer.analyze().catch(console.error);
window.togglePerformanceDashboard = () => perfAnalyzer.toggleDashboard();
