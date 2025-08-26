/**
 * Real-time Redis Logs Management
 * Enhanced logging interface with WebSocket streaming
 */

class RedisLogsManager {
    constructor() {
        this.ws = null;
        this.isConnected = false;
        this.logs = [];
        this.maxLogs = 1000;
        this.autoScroll = true;
        this.filters = {
            level: 'all',
            component: 'all',
            search: ''
        };
        
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.connectWebSocket();
        this.loadInitialData();
    }
    
    setupEventListeners() {
        // Filter controls
        document.getElementById('logLevel')?.addEventListener('change', (e) => {
            this.filters.level = e.target.value;
            this.applyFilters();
        });
        
        document.getElementById('logComponent')?.addEventListener('change', (e) => {
            this.filters.component = e.target.value;
            this.applyFilters();
        });
        
        document.getElementById('logSearch')?.addEventListener('input', (e) => {
            this.filters.search = e.target.value;
            this.debounceFilter();
        });
        
        // Control buttons
        document.getElementById('clearLogs')?.addEventListener('click', () => {
            this.clearLogs();
        });
        
        document.getElementById('pauseLogs')?.addEventListener('click', () => {
            this.togglePause();
        });
        
        document.getElementById('autoScrollToggle')?.addEventListener('change', (e) => {
            this.autoScroll = e.target.checked;
        });
        
        // Export logs
        document.getElementById('exportLogs')?.addEventListener('click', () => {
            this.exportLogs();
        });
    }
    
    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/logs`;
        
        try {
            this.ws = new WebSocket(wsUrl);
            
            this.ws.onopen = () => {
                console.log('✅ WebSocket connected for real-time logs');
                this.isConnected = true;
                this.updateConnectionStatus(true);
            };
            
            this.ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                this.handleWebSocketMessage(data);
            };
            
            this.ws.onclose = () => {
                console.log('❌ WebSocket disconnected');
                this.isConnected = false;
                this.updateConnectionStatus(false);
                
                // Attempt to reconnect after 5 seconds
                setTimeout(() => {
                    if (!this.isConnected) {
                        this.connectWebSocket();
                    }
                }, 5000);
            };
            
            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.updateConnectionStatus(false, 'WebSocket error');
            };
            
        } catch (error) {
            console.error('Failed to create WebSocket:', error);
            this.updateConnectionStatus(false, 'Connection failed');
        }
    }
    
    handleWebSocketMessage(data) {
        if (data.error) {
            console.error('WebSocket error:', data.error);
            this.updateConnectionStatus(false, data.error);
            return;
        }
        
        switch (data.type) {
            case 'initial_logs':
                this.logs = data.logs || [];
                this.renderLogs();
                break;
                
            case 'new_logs':
                if (data.logs && data.logs.length > 0) {
                    this.logs = [...data.logs, ...this.logs];
                    
                    // Limit log count
                    if (this.logs.length > this.maxLogs) {
                        this.logs = this.logs.slice(0, this.maxLogs);
                    }
                    
                    this.renderLogs();
                    this.highlightNewLogs(data.logs.length);
                }
                break;
        }
    }
    
    async loadInitialData() {
        try {
            // Load log stats
            const statsResponse = await fetch('/api/logs/stats');
            const statsData = await statsResponse.json();
            
            if (statsData.success) {
                this.updateLogStats(statsData.stats);
            }
            
            // Load categories for filter
            const categoriesResponse = await fetch('/api/logs/categories');
            const categoriesData = await categoriesResponse.json();
            
            if (categoriesData.categories) {
                this.populateComponentFilter(categoriesData.categories);
            }
            
        } catch (error) {
            console.error('Failed to load initial data:', error);
        }
    }
    
    applyFilters() {
        this.renderLogs();
    }
    
    debounceFilter() {
        clearTimeout(this.filterTimeout);
        this.filterTimeout = setTimeout(() => {
            this.applyFilters();
        }, 300);
    }
    
    getFilteredLogs() {
        return this.logs.filter(log => {
            // Level filter
            if (this.filters.level !== 'all' && 
                log.level?.toLowerCase() !== this.filters.level.toLowerCase()) {
                return false;
            }
            
            // Component filter
            if (this.filters.component !== 'all' && 
                log.component !== this.filters.component) {
                return false;
            }
            
            // Search filter
            if (this.filters.search && 
                !log.message?.toLowerCase().includes(this.filters.search.toLowerCase())) {
                return false;
            }
            
            return true;
        });
    }
    
    renderLogs() {
        const container = document.getElementById('logOutput');
        if (!container) return;
        
        const filteredLogs = this.getFilteredLogs();
        
        container.innerHTML = filteredLogs.map(log => {
            const timestamp = new Date(log.timestamp).toLocaleTimeString();
            const levelClass = this.getLevelClass(log.level);
            
            return `
                <div class="log-entry ${levelClass}" data-level="${log.level}" data-component="${log.component}">
                    <span class="log-timestamp">${timestamp}</span>
                    <span class="log-level">${log.level}</span>
                    <span class="log-component">${log.component}</span>
                    <span class="log-message">${this.escapeHtml(log.message)}</span>
                </div>
            `;
        }).join('');
        
        // Auto-scroll to bottom if enabled
        if (this.autoScroll) {
            container.scrollTop = container.scrollHeight;
        }
        
        // Update log count
        document.getElementById('logCount').textContent = filteredLogs.length;
    }
    
    highlightNewLogs(count) {
        const entries = document.querySelectorAll('.log-entry');
        for (let i = 0; i < Math.min(count, entries.length); i++) {
            entries[i].classList.add('new-log');
            setTimeout(() => {
                entries[i].classList.remove('new-log');
            }, 2000);
        }
    }
    
    getLevelClass(level) {
        const levelMap = {
            'ERROR': 'log-error',
            'WARNING': 'log-warning', 
            'WARN': 'log-warning',
            'INFO': 'log-info',
            'DEBUG': 'log-debug'
        };
        return levelMap[level?.toUpperCase()] || 'log-info';
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    updateConnectionStatus(connected, error = null) {
        const statusEl = document.getElementById('connectionStatus');
        if (!statusEl) return;
        
        if (connected) {
            statusEl.innerHTML = '<span class="status-connected">🟢 Connected</span>';
        } else {
            const errorMsg = error ? ` (${error})` : '';
            statusEl.innerHTML = `<span class="status-disconnected">🔴 Disconnected${errorMsg}</span>`;
        }
    }
    
    updateLogStats(stats) {
        const statsEl = document.getElementById('logStats');
        if (!statsEl || !stats) return;
        
        const totalLogs = stats.total_logs || 0;
        const redisDb = stats.redis_db || 'N/A';
        
        statsEl.innerHTML = `
            <div class="stat-item">
                <span class="stat-label">Total Logs:</span>
                <span class="stat-value">${totalLogs.toLocaleString()}</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">Redis DB:</span>
                <span class="stat-value">${redisDb}</span>
            </div>
        `;
        
        // Update level distribution
        if (stats.level_distribution) {
            this.updateLevelDistribution(stats.level_distribution);
        }
    }
    
    updateLevelDistribution(distribution) {
        const distEl = document.getElementById('levelDistribution');
        if (!distEl) return;
        
        const total = Object.values(distribution).reduce((sum, count) => sum + count, 0);
        
        distEl.innerHTML = Object.entries(distribution).map(([level, count]) => {
            const percentage = total > 0 ? ((count / total) * 100).toFixed(1) : 0;
            const levelClass = this.getLevelClass(level);
            
            return `
                <div class="level-stat ${levelClass}">
                    <span class="level-name">${level}</span>
                    <span class="level-count">${count}</span>
                    <span class="level-percentage">(${percentage}%)</span>
                </div>
            `;
        }).join('');
    }
    
    populateComponentFilter(categories) {
        const select = document.getElementById('logComponent');
        if (!select) return;
        
        select.innerHTML = categories.map(cat => 
            `<option value="${cat.value}">${cat.label}</option>`
        ).join('');
    }
    
    async clearLogs() {
        if (!confirm('Are you sure you want to clear all logs from Redis?')) {
            return;
        }
        
        try {
            const response = await fetch('/api/logs', { method: 'DELETE' });
            const data = await response.json();
            
            if (data.success) {
                this.logs = [];
                this.renderLogs();
                this.showNotification('Logs cleared successfully', 'success');
            } else {
                this.showNotification(`Failed to clear logs: ${data.error}`, 'error');
            }
        } catch (error) {
            this.showNotification(`Error clearing logs: ${error.message}`, 'error');
        }
    }
    
    togglePause() {
        const button = document.getElementById('pauseLogs');
        if (!button) return;
        
        if (this.isConnected) {
            this.ws.close();
            button.textContent = 'Resume';
            button.classList.add('paused');
        } else {
            this.connectWebSocket();
            button.textContent = 'Pause';
            button.classList.remove('paused');
        }
    }
    
    exportLogs() {
        const filteredLogs = this.getFilteredLogs();
        const csvContent = this.logsToCSV(filteredLogs);
        
        const blob = new Blob([csvContent], { type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = url;
        a.download = `pmcp-logs-${new Date().toISOString().split('T')[0]}.csv`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        
        window.URL.revokeObjectURL(url);
    }
    
    logsToCSV(logs) {
        const headers = ['Timestamp', 'Level', 'Component', 'Message'];
        const rows = logs.map(log => [
            log.timestamp,
            log.level,
            log.component,
            `"${log.message.replace(/"/g, '""')}"`
        ]);
        
        return [headers, ...rows].map(row => row.join(',')).join('\n');
    }
    
    showNotification(message, type = 'info') {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.textContent = message;
        
        // Add to page
        document.body.appendChild(notification);
        
        // Remove after 3 seconds
        setTimeout(() => {
            notification.remove();
        }, 3000);
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.redisLogsManager = new RedisLogsManager();
});
