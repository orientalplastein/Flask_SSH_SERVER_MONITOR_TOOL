// 全局变量
let cpuChart = null;
let memoryChart = null;
let cpuData = [];
let memoryData = [];
const MAX_DATA_POINTS = 30;
let isRemoteMode = false;
let connectionStatus = 'local';

// 初始化函数
document.addEventListener('DOMContentLoaded', function() {
    updateCurrentTime();
    initializeCharts();
    // 页面加载时检查SSH连接状态
    checkSSHStatus();
    setInterval(updateCurrentTime, 1000);
    setInterval(loadData, 1000);
    
});

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

// 加载数据
function loadData() {
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

// 手动刷新数据
function refreshData() {
    loadData();
}

// 更新概览数据
function updateOverview(data) {
    const cpuUsage = document.getElementById('cpu-usage');
    const memoryUsage = document.getElementById('memory-usage');
    const networkConnections = document.getElementById('network-connections');
    const uptime = document.getElementById('uptime');
    
    if (cpuUsage) cpuUsage.textContent = data.cpu + '%';
    if (memoryUsage) memoryUsage.textContent = data.memory.percent + '%';
    if (networkConnections) networkConnections.textContent = data.network.connections;
    if (uptime) uptime.textContent = data.uptime;
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

// 更新进程列表
function updateProcesses(processes) {
    const tableBody = document.getElementById('processList');
    if (!tableBody) return;
    
    tableBody.innerHTML = '';
    
    processes.forEach(proc => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${proc.pid}</td>
            <td>${proc.name}</td>
            <td>${proc.cpu}%</td>
            <td>${proc.memory} MB</td>
            <td>${proc.status}</td>
        `;
        tableBody.appendChild(row);
    });
}




// 检查SSH连接状态
function checkSSHStatus() {
    fetch('/api/ssh/status')
    .then(response => response.json())
    .then(data => {
        if (data.connection_status === 'connected') {
            updateConnectionStatus('connected');
            // 如果是远程连接状态，立即加载数据
            loadData();
        }
    })
    .catch(error => {
        console.error('检查SSH状态错误:', error);
    });
}

// SSH连接相关函数
function testSSHConnection() {
    const hostname = document.getElementById('ssh-hostname').value;
    const username = document.getElementById('ssh-username').value;
    const password = document.getElementById('ssh-password').value;
    const port = document.getElementById('ssh-port').value || 22;
    
    if (!hostname || !username || !password) {
        alert('请填写完整的SSH连接信息');
        return;
    }
    
    // 先保存配置
    fetch('/api/ssh/configure', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ hostname, username, password, port })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // 配置保存成功后，立即测试连接
            fetch('/api/ssh/connect', { method: 'POST' })
            .then(response => response.json())
            .then(connectData => {
                if (connectData.success) {
                    alert('SSH连接测试成功！');
                    // 测试完成后断开连接
                    fetch('/api/ssh/disconnect', { method: 'POST' });
                } else {
                    alert('连接测试失败: ' + connectData.connection_status);
                }
            })
            .catch(error => {
                console.error('连接测试错误:', error);
                alert('连接测试失败: ' + error.message);
            });
        } else {
            alert('配置失败: ' + data.connection_status);
        }
    })
    .catch(error => {
        console.error('配置错误:', error);
        alert('配置失败: ' + error.message);
    });
}

function connectSSH() {
    fetch('/api/ssh/connect', { method: 'POST' })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('SSH连接成功！');
            updateConnectionStatus('connected');
            $('#sshConfigModal').modal('hide');
            // 连接成功后立即刷新数据
            loadData();
        } else {
            alert('连接失败: ' + data.connection_status);
        }
    })
    .catch(error => {
        console.error('连接错误:', error);
        alert('连接失败: ' + error.message);
    });
}

function disconnectSSH() {
    fetch('/api/ssh/disconnect', { method: 'POST' })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('SSH连接已断开');
            updateConnectionStatus('local');
        } else {
            alert('断开失败: ' + data.connection_status);
        }
    })
    .catch(error => {
        console.error('断开错误:', error);
        alert('断开失败: ' + error.message);
    });
}
