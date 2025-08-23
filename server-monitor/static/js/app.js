// 全局变量
let cpuChart = null;
let memoryChart = null;
let cpuData = [];
let memoryData = [];
const MAX_DATA_POINTS = 30;
let isRemoteMode = false;
let connectionStatus = 'local';
let socket = null;
let realtimeUpdatesEnabled = false;

// 初始化函数
document.addEventListener('DOMContentLoaded', function() {
    updateCurrentTime();
    initializeCharts();
    initializeWebSocket();
    checkSSHStatus();
    setInterval(updateCurrentTime, 1000);
    // 页面加载后自动启动刷新
    setTimeout(initializeAutoRefresh, 1000);
});

// 初始化WebSocket连接
function initializeWebSocket() {
    socket = io();
    
    socket.on('connect', function() {
        console.log('WebSocket连接已建立');
        updateConnectionStatus(connectionStatus);
        // 连接成功后立即请求当前状态
        requestCurrentStats();
        // 启动5秒自动刷新
        startAutoRefresh();
    });
    
    socket.on('disconnect', function() {
        console.log('WebSocket连接已断开');
        // WebSocket断开时回退到HTTP轮询
        if (realtimeUpdatesEnabled) {
            console.log('WebSocket断开，启用HTTP轮询作为备用');
            setInterval(loadDataViaHTTP, 5000);
        }
    });
    
    socket.on('stats_update', function(data) {
        // 根据实际的连接状态更新模式
        if (data.connection_status === 'connected') {
            isRemoteMode = true;
            connectionStatus = 'connected';
        } else {
            isRemoteMode = false;
            connectionStatus = data.connection_status || 'local';
        }
        updateOverview(data);
        updateCharts(data);
        // 处理本地和远程不同的进程列表字段名
        const processes = data.processes || data.process_list || [];
        updateProcesses(processes);
    });
    
socket.on('ssh_status_update', function(data) {
    updateSSHStatusUI(data);
    // SSH状态更新后重新请求数据并重启实时更新
    if (realtimeUpdatesEnabled) {
        stopRealtimeUpdates();
        setTimeout(() => {
            startRealtimeUpdates(5);
            // 强制刷新一次数据
            requestCurrentStats();
        }, 1000);
    } else {
        requestCurrentStats();
    }
});
    
    socket.on('error', function(data) {
        console.error('WebSocket错误:', data.message);
        showNotification(data.message, 'error');
    });
    
    socket.on('connection_status', function(data) {
        console.log('连接状态:', data.status);
    });
}

// 启动实时数据更新
function startRealtimeUpdates(interval = 5) {
    if (socket && socket.connected) {
        socket.emit('start_realtime_updates', { interval: interval });
        realtimeUpdatesEnabled = true;
        console.log('实时数据更新已启动，间隔:', interval, '秒');
        showNotification('实时数据更新已启动', 'success');
    } else {
        console.error('WebSocket未连接，无法启动实时更新');
        showNotification('WebSocket连接未建立', 'error');
    }
}

// 停止实时数据更新
function stopRealtimeUpdates() {
    if (socket) {
        socket.emit('stop_realtime_updates');
        realtimeUpdatesEnabled = false;
        console.log('实时数据更新已停止');
        showNotification('实时数据更新已停止', 'info');
    }
}

// 请求当前状态数据
function requestCurrentStats() {
    if (socket && socket.connected) {
        socket.emit('request_stats');
    } else {
        console.error('WebSocket未连接，无法请求数据');
        // 回退到HTTP请求
        loadDataViaHTTP();
    }
}

// HTTP回退机制
function loadDataViaHTTP() {
    const apiUrl = isRemoteMode ? '/api/remote/stats' : '/api/stats';
    
    fetch(apiUrl)
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                console.error('Error:', data.error);
                return;
            }
            
            updateOverview(data);
            updateCharts(data);
            updateProcesses(data.processes || []);
        })
        .catch(error => {
            console.error('Fetch error:', error);
        });
}

// 更新当前时间
function updateCurrentTime() {
    const now = new Date();
    const timeElement = document.getElementById('current-time');
    if (timeElement) {
        timeElement.textContent = now.toLocaleString('zh-CN');
    }
}

// 初始化图表
function initializeCharts() {
    const cpuCtx = document.getElementById('cpuChart');
    const memoryCtx = document.getElementById('memoryChart');
    
    if (!cpuCtx || !memoryCtx) return;
    
    // 添加空指针检查
    if (!cpuCtx.getContext || !memoryCtx.getContext) {
        console.warn('Canvas上下文不可用，跳过图表初始化');
        return;
    }
    
    cpuChart = new Chart(cpuCtx.getContext('2d'), {
        type: 'line',
        data: {
            labels: Array(MAX_DATA_POINTS).fill(''),
            datasets: [{
                label: 'CPU使用率 (%)',
                data: cpuData,
                borderColor: '#007BFF',
                backgroundColor: 'rgba(0, 123, 255, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 0 },
            scales: {
                y: { beginAtZero: true, max: 100 },
                x: { grid: { display: false } }
            }
        }
    });
    
    memoryChart = new Chart(memoryCtx.getContext('2d'), {
        type: 'line',
        data: {
            labels: Array(MAX_DATA_POINTS).fill(''),
            datasets: [{
                label: '内存使用率 (%)',
                data: memoryData,
                borderColor: '#17A2B8',
                backgroundColor: 'rgba(23, 162, 184, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 0 },
            scales: {
                y: { beginAtZero: true, max: 100 },
                x: { grid: { display: false } }
            }
        }
    });
}

// 更新连接状态显示
function updateConnectionStatus(status) {
    const statusElement = document.getElementById('connection-status');
    connectionStatus = status;
    
    if (!statusElement) return;
    
    switch(status) {
        case 'connected':
            statusElement.className = 'badge bg-success me-2';
            statusElement.textContent = '远程连接';
            isRemoteMode = true;
            break;
        case 'error':
            statusElement.className = 'badge bg-danger me-2';
            statusElement.textContent = '连接错误';
            isRemoteMode = false;
            break;
        default:
            statusElement.className = 'badge bg-secondary me-2';
            statusElement.textContent = '本地模式';
            isRemoteMode = false;
    }
}

// 更新SSH状态UI
function updateSSHStatusUI(data) {
    updateConnectionStatus(data.connection_status);
    
    // 更新连接历史列表
    const connectionsList = document.getElementById('ssh-connections-list');
    if (connectionsList && data.connections) {
        connectionsList.innerHTML = '';
        data.connections.forEach(conn => {
            const li = document.createElement('li');
            li.className = 'list-group-item';
            li.innerHTML = `
                <div class="d-flex justify-content-between align-items-center">
                    <span>${conn.name}</span>
                    <button class="btn btn-sm btn-outline-primary" onclick="switchToConnection('${conn.hostname}', '${conn.username}', ${conn.port}, '${conn.password}')">
                        切换
                    </button>
                </div>
            `;
            connectionsList.appendChild(li);
        });
    }
}

// 更新概览数据
function updateOverview(data) {
    const cpuUsage = document.getElementById('cpu-usage');
    const memoryUsage = document.getElementById('memory-usage');
    const networkConnections = document.getElementById('network-connections');
    const diskUsage = document.getElementById('disk-usage');
    const loadAverage = document.getElementById('load-average');
    const uptime = document.getElementById('uptime');
    const timestamp = document.getElementById('data-timestamp');
    
    if (cpuUsage) cpuUsage.textContent = (data.cpu || 0) + '%';
    if (memoryUsage) memoryUsage.textContent = (data.memory?.percent || 0) + '%';
    // 处理本地和远程不同的网络连接数据结构
    const networkCount = data.network?.connections || data.network_connections || 0;
    if (networkConnections) networkConnections.textContent = networkCount;
    // 更新磁盘使用率
    if (diskUsage) diskUsage.textContent = (data.disk_usage || data.disk || 0) + '%';
    // 更新系统负载
    if (loadAverage) {
        // 优先使用load_average字段，如果没有则从load对象构建
        let loadText = data.load_average;
        if (!loadText && data.load) {
            loadText = `${data.load['1min'] || 0.00} ${data.load['5min'] || 0.00} ${data.load['15min'] || 0.00}`;
        }
        loadAverage.textContent = loadText || '0.00 0.00 0.00';
    }
    if (uptime) uptime.textContent = data.uptime || '00:00:00';
    if (timestamp) timestamp.textContent = data.timestamp || new Date().toLocaleString('zh-CN');
    
    // 更新服务状态监控
    updateServiceStatus(data.service_status);
    
    // 更新网络流量
    updateNetworkTraffic(data.network_traffic);
}

// 更新图表数据
function updateCharts(data) {
    cpuData.push(data.cpu);
    memoryData.push(data.memory.percent);
    
    if (cpuData.length > MAX_DATA_POINTS) {
        cpuData.shift();
        memoryData.shift();
    }
    
    if (cpuChart) {
        cpuChart.data.datasets[0].data = cpuData;
        cpuChart.update('none');
    }
    if (memoryChart) {
        memoryChart.data.datasets[0].data = memoryData;
        memoryChart.update('none');
    }
}

// 更新网络流量
function updateNetworkTraffic(networkTraffic) {
    const networkTrafficElement = document.getElementById('network-traffic');
    
    if (!networkTrafficElement || !networkTraffic) return;
    
    // 计算所有接口的总流量（接收 + 发送）
    let totalRx = 0;
    let totalTx = 0;
    
    // 遍历所有网络接口
    for (const [interfaceName, interfaceData] of Object.entries(networkTraffic)) {
        if (interfaceName !== 'connections' && typeof interfaceData === 'object') {
            totalRx += interfaceData.rx_bytes || 0;
            totalTx += interfaceData.tx_bytes || 0;
        }
    }
    
    const totalTraffic = totalRx + totalTx;
    
    // 转换为合适的单位（KB/s, MB/s）
    let displayValue;
    if (totalTraffic >= 1024 * 1024) {
        displayValue = (totalTraffic / (1024 * 1024)).toFixed(1) + ' MB/s';
    } else if (totalTraffic >= 1024) {
        displayValue = (totalTraffic / 1024).toFixed(1) + ' KB/s';
    } else {
        displayValue = totalTraffic + ' B/s';
    }
    
    networkTrafficElement.textContent = displayValue;
    
    // 添加详细流量信息的提示
    const rxFormatted = formatBytes(totalRx);
    const txFormatted = formatBytes(totalTx);
    networkTrafficElement.title = `接收: ${rxFormatted}/s\n发送: ${txFormatted}/s`;
}

// 格式化字节数为易读格式
function formatBytes(bytes) {
    if (bytes >= 1024 * 1024) {
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    } else if (bytes >= 1024) {
        return (bytes / 1024).toFixed(1) + ' KB';
    } else {
        return bytes + ' B';
    }
}

// 更新服务状态监控
function updateServiceStatus(serviceStatus) {
    const serviceStatusElement = document.getElementById('service-status');
    const serviceStatusContainer = document.getElementById('service-status-container');
    
    if (!serviceStatusElement || !serviceStatusContainer) return;
    
    if (!serviceStatus || Object.keys(serviceStatus).length === 0) {
        serviceStatusElement.textContent = '未监控';
        serviceStatusElement.className = 'badge bg-secondary';
        return;
    }
    
    // 计算正常运行的服务数量
    let runningCount = 0;
    let totalCount = 0;
    
    for (const [service, status] of Object.entries(serviceStatus)) {
        totalCount++;
        if (status === 'running' || status === 'active') {
            runningCount++;
        }
    }
    
    // 更新显示
    serviceStatusElement.textContent = `${runningCount}/${totalCount} 运行中`;
    
    // 根据运行比例设置颜色
    if (totalCount === 0) {
        serviceStatusElement.className = 'badge bg-secondary';
    } else if (runningCount === totalCount) {
        serviceStatusElement.className = 'badge bg-success';
    } else if (runningCount > 0) {
        serviceStatusElement.className = 'badge bg-warning';
    } else {
        serviceStatusElement.className = 'badge bg-danger';
    }
    
    // 添加详细服务状态提示
    let tooltipContent = '';
    for (const [service, status] of Object.entries(serviceStatus)) {
        const statusText = status === 'running' || status === 'active' ? '✅ 运行中' : '❌ 停止';
        tooltipContent += `${service}: ${statusText}\n`;
    }
    
    serviceStatusContainer.title = tooltipContent.trim();
}

// 更新进程列表
function updateProcesses(processes) {
    const tableBody = document.getElementById('processList');
    if (!tableBody) return;
    
    tableBody.innerHTML = '';
    
    processes.forEach(proc => {
        const row = document.createElement('tr');
        
        // 处理本地和远程不同的数据结构
        const pid = proc.pid || '';
        const name = proc.name || proc.command || '';
        const cpu = proc.cpu || '0';
        // 本地是memory（MB），远程是mem（百分比），需要转换为MB
        let memoryValue = proc.memory || proc.mem || '0';
        // 如果是百分比格式（远程数据），转换为MB显示（基于2GB总内存）
        if (memoryValue && parseFloat(memoryValue) < 100) {
            // 0.6% * 2048MB * 0.01 = 12.288MB
            memoryValue = (parseFloat(memoryValue) * 20.48).toFixed(1);
        }
        const status = proc.status || '';
        const user = proc.user || '';
        
        row.innerHTML = `
            <td>${pid}</td>
            <td>${user}</td>
            <td>${name}</td>
            <td>${cpu}%</td>
            <td>${memoryValue} MB</td>
            <td>${status}</td>
        `;
        tableBody.appendChild(row);
    });
}

// 显示通知
function showNotification(message, type = 'info') {
    // 简单的控制台通知，可以扩展为UI通知
    console.log(`[${type.toUpperCase()}] ${message}`);
}

// 统一的fetch错误处理函数
function handleFetchError(error, operation) {
    console.error(`${operation}错误:`, error);
    return `${operation}失败: ${error.message}`;
}

// 更新SSH连接状态
function updateSSHConnectionStatus(status) {
    updateConnectionStatus(status);
    if (socket) socket.emit('request_ssh_status');
}

// 检查SSH连接状态
function checkSSHStatus() {
    if (socket?.connected) {
        socket.emit('request_ssh_status');
    } else {
        fetch('/api/ssh/status')
            .then(response => response.json())
            .then(data => {
                isRemoteMode = data.connection_status === 'connected';
                updateConnectionStatus(data.connection_status || 'local');
            })
            .catch(error => {
                console.error('检查SSH状态错误:', error);
                isRemoteMode = false;
                updateConnectionStatus('local');
            });
    }
}

// SSH连接测试
function testSSHConnection() {
    const hostname = document.getElementById('ssh-hostname').value;
    const username = document.getElementById('ssh-username').value;
    const password = document.getElementById('ssh-password').value;
    const port = document.getElementById('ssh-port').value || 22;
    
    if (!hostname || !username || !password) {
        alert('请填写完整的SSH连接信息');
        return;
    }
    
    fetch('/api/ssh/configure', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ hostname, username, password, port })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            return fetch('/api/ssh/connect', { method: 'POST' });
        }
        throw new Error(data.connection_status || '配置失败');
    })
    .then(response => response.json())
    .then(connectData => {
        if (connectData.success) {
            alert('SSH连接测试成功！');
            fetch('/api/ssh/disconnect', { method: 'POST' });
        } else {
            alert('连接测试失败: ' + connectData.connection_status);
        }
    })
    .catch(error => alert(error.message));
}

// SSH连接操作函数
function sshOperation(url, successMessage, errorPrefix = '操作') {
    fetch(url, { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert(successMessage);
                updateSSHConnectionStatus(data.connection_status || 'connected');
                if (url.includes('connect')) $('#sshConfigModal').modal('hide');
            } else {
                alert(`${errorPrefix}失败: ${data.connection_status}`);
            }
        })
        .catch(error => alert(handleFetchError(error, errorPrefix)));
}

// SSH连接函数
function connectSSH() {
    sshOperation('/api/ssh/connect', 'SSH连接成功！', '连接');
}

function disconnectSSH() {
    sshOperation('/api/ssh/disconnect', 'SSH连接已断开', '断开');
}

// 切换到指定连接
function switchToConnection(hostname, username, port, password) {
    fetch('/api/ssh/switch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ hostname, username, port, password })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('已切换到指定连接');
            updateSSHConnectionStatus(data.connection_status);
        } else {
            alert('切换失败: ' + data.connection_status);
        }
    })
    .catch(error => alert(handleFetchError(error, '切换')));
}

// 手动刷新数据
function refreshData() {
    requestCurrentStats();
}

// 启动5秒定时刷新
function startAutoRefresh() {
    startRealtimeUpdates(5);
    // 更新按钮状态
    document.getElementById('startRefreshBtn').style.display = 'none';
    document.getElementById('stopRefreshBtn').style.display = 'inline-block';
    showNotification('自动刷新已启动（5秒间隔）', 'success');
}

// 停止自动刷新
function stopAutoRefresh() {
    stopRealtimeUpdates();
    // 更新按钮状态
    document.getElementById('startRefreshBtn').style.display = 'inline-block';
    document.getElementById('stopRefreshBtn').style.display = 'none';
    showNotification('自动刷新已停止', 'info');
}

// 页面加载时自动启动刷新
function initializeAutoRefresh() {
    // 检查WebSocket连接状态，如果已连接则自动启动
    if (socket && socket.connected) {
        startAutoRefresh();
    } else {
        // WebSocket未连接时，3秒后重试
        setTimeout(initializeAutoRefresh, 3000);
    }
}
