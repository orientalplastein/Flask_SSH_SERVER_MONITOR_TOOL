from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
import psutil
import paramiko
import json
from datetime import datetime, timedelta
import os
from scheduler import MonitorScheduler
from ssh_manager import ssh_manager
from cache_manager import performance_optimizer

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

class ServerMonitor:
    def __init__(self):
        self.ssh_config = {
            'enabled': False,
            'hostname': '',
            'username': '',
            'password': '',
            'port': 22
        }
        self.connection_status = 'disconnected'
        self.current_connection_key = None
        
        # 自动加载第一个SSH连接配置（如果有）
        self._auto_load_ssh_config()
    
    def _auto_load_ssh_config(self):
        """自动加载SSH连接配置"""
        try:
            connections = ssh_manager.get_connection_configs()
            if connections:
                # 使用第一个可用的连接配置
                first_config = connections[0]
                self.ssh_config.update({
                    'enabled': True,
                    'hostname': first_config['hostname'],
                    'username': first_config['username'],
                    'password': first_config['password'],
                    'port': int(first_config['port'])
                })
                # 自动建立连接
                self.connect_ssh()
        except Exception as e:
            self.connection_status = 'disconnected'
            self.current_connection_key = None
    
    def get_ssh_connections(self):
        """获取SSH连接配置"""
        return ssh_manager.connection_configs
    
    def add_ssh_connection(self, config):
        """添加新的SSH连接配置"""
        ssh_manager.add_connection_config(config)
    
    def remove_ssh_connection(self, hostname, username, port=22):
        """移除SSH连接配置"""
        ssh_manager.remove_connection_config(hostname, username, port)
    
    def get_local_stats(self):
        """获取本地服务器状态"""
        try:
            # CPU使用率 - 使用非阻塞方式
            cpu_percent = psutil.cpu_percent(interval=None)
            
            # 内存使用情况
            memory = psutil.virtual_memory()
            memory_total = round(memory.total / (1024 ** 2), 2)  # MB
            memory_used = round(memory.used / (1024 ** 2), 2)    # MB
            memory_percent = memory.percent
            
            # 进程列表 - 使用更高效的方式获取进程信息
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'memory_percent', 'status']):
                try:
                    # 获取进程CPU使用率（相对于单个CPU核心）
                    cpu_usage = proc.cpu_percent(interval=0) / psutil.cpu_count()
                    # 对于System Idle Process，显示为0% (它实际上是系统空闲时间)
                    if proc.info['name'].lower() == 'system idle process':
                        cpu_usage = 0.0
                    
                    processes.append({
                        'pid': proc.info['pid'],
                        'name': proc.info['name'],
                        'cpu': round(cpu_usage, 1),
                        'memory': round(proc.memory_info().rss / (1024 ** 2), 2),  # MB
                        'status': proc.info['status']
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
            
            # 按CPU使用率降序排序，过滤掉异常值
            processes = sorted(processes, key=lambda x: x['cpu'], reverse=True)
            processes = [p for p in processes if p['cpu'] <= 100 and p['cpu'] >= 0]  # 过滤掉异常CPU值
            
            # 网络连接
            net_connections = len(psutil.net_connections())
            
            # 系统运行时间
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime = datetime.now() - boot_time
            
            return {
                'cpu': cpu_percent,
                'memory': {
                    'total': memory_total,
                    'used': memory_used,
                    'percent': memory_percent
                },
                'processes': processes[:50],  # 只返回前50个进程
                'network': {
                    'connections': net_connections
                },
                'uptime': str(uptime).split('.')[0],
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def configure_ssh(self, hostname, username, password, port=22):
        """配置SSH连接参数"""
        self.ssh_config = {
            'enabled': True,
            'hostname': hostname,
            'username': username,
            'password': password,
            'port': port
        }
        
        # 保存到连接历史
        self.add_ssh_connection({
            'hostname': hostname,
            'username': username,
            'password': password,
            'port': port,
            'name': f"{username}@{hostname}:{port}"
        })
        
        self.connection_status = 'configured'
        return True  # 配置保存成功，但不代表连接成功

    def connect_ssh(self):
        """连接到远程服务器"""
        if not self.ssh_config['enabled']:
            self.connection_status = 'not_configured'
            return False
        
        try:
            print(f"尝试SSH连接到 {self.ssh_config['hostname']}:{self.ssh_config['port']}")
            
            # 使用SSH管理器创建连接
            success = ssh_manager.connect_with_config(self.ssh_config)
            
            if success:
                self.connection_status = 'connected'
                self.current_connection_key = ssh_manager.get_connection_key(
                    self.ssh_config['hostname'],
                    self.ssh_config['username'],
                    self.ssh_config['port']
                )
                print("✓ SSH连接测试成功")
                
                # 连接成功后，将当前配置添加到历史记录
                self.add_ssh_connection({
                    'hostname': self.ssh_config['hostname'],
                    'username': self.ssh_config['username'],
                    'password': self.ssh_config['password'],
                    'port': self.ssh_config['port'],
                    'name': f"{self.ssh_config['username']}@{self.ssh_config['hostname']}:{self.ssh_config['port']}"
                })
                
                return True
            else:
                self.connection_status = 'error: 连接测试失败'
                print("✗ SSH连接测试失败")
                return False
                
        except Exception as e:
            self.connection_status = f'error: 连接失败 - {str(e)}'
            print(f"✗ SSH连接失败: {e}")
            return False

    def disconnect_ssh(self):
        """断开SSH连接"""
        if self.current_connection_key:
            ssh_manager.disconnect_from_server(self.current_connection_key)
            self.current_connection_key = None
        self.connection_status = 'disconnected'
        return True
    
    def get_remote_stats(self, use_cache=True):
        """获取远程服务器状态（通过SSH）"""
        if not self.current_connection_key or self.connection_status != 'connected':
            return {'error': 'SSH连接未建立', 'connection_status': self.connection_status}
        
        # 生成服务器唯一标识
        server_key = self.current_connection_key
        
        def _fetch_remote_stats():
            """实际获取服务器状态的内部函数"""
            try:
                # 使用SSH管理器获取服务器状态
                stats = ssh_manager.get_server_stats_by_key(self.current_connection_key)
                
                if stats:
                    # 解析负载平均值（格式为"1min 5min 15min"）
                    load_avg = stats.get('load_avg', '0.00 0.00 0.00')
                    load_parts = load_avg.split()
                    load_1min = float(load_parts[0]) if len(load_parts) > 0 else 0.00
                    load_5min = float(load_parts[1]) if len(load_parts) > 1 else 0.00
                    load_15min = float(load_parts[2]) if len(load_parts) > 2 else 0.00
                    
                    # 转换为我们需要的格式
                    result = {
                        'cpu': stats.get('cpu_usage', 0),
                        'memory': {
                            'percent': stats.get('memory_usage', 0),
                            'total': 0,  # 这些信息需要从其他命令获取
                            '极速4': 0
                        },
                        'disk': stats.get('disk_usage', 0),
                        'load': {
                            '1min': load_1min,
                            '5min': load_5min,
                            '15min': load_15min
                        },
                        'processes': stats.get('processes', []),
                        'network': {
                            'connections': stats.get('network_connections', 0)
                        },
                        'uptime': self._get_remote_uptime(),  # 获取远程运行时间
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'connection_status': 'connected'
                    }
                    
                    # 添加网络流量统计
                    try:
                        client = ssh_manager.connection_pool.get(self.current_connection_key)
                        if client:
                            network_traffic = ssh_manager._get_network_traffic(client)
                            result['network_traffic'] = network_traffic
                    except Exception as e:
                        result['network_traffic'] = {}
                    
                    # 添加服务状态监控
                    try:
                        client = ssh_manager.connection_pool.get(self.current_connection_key)
                        if client:
                            service_status = ssh_manager._get_service_status(client)
                            result['service_status'] = service_status
                    except Exception as e:
                        result['service_status'] = {}
                    
                    return result
                else:
                    return {'error': '获取远程数据失败', 'connection_status': self.connection_status}
                
            except Exception as e:
                self.connection_status = f'error: {str(e)}'
                return {'error': str(e), 'connection_status': self.connection_status}
        
        # 使用缓存获取数据
        if use_cache:
            return performance_optimizer.get_cached_server_stats(server_key, _fetch_remote_stats)
        else:
            return _fetch_remote_stats()

    def _get_remote_uptime(self):
        """获取远程服务器的运行时间"""
        if not self.current_connection_key or self.connection_status != 'connected':
            return "0:00:00"
        
        try:
            # 获取SSH客户端
            client = ssh_manager.connection_pool.get(self.current_connection_key)
            if client:
                # 直接调用SSH管理器的uptime方法
                return ssh_manager._get_uptime(client)
        except Exception as e:
            print(f"获取远程运行时间失败: {e}")
        
        return "0:00:00"

monitor = ServerMonitor()
scheduler = MonitorScheduler(app, monitor)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/stats')
def get_stats():
    if monitor.ssh_config['enabled'] and monitor.connection_status == 'connected':
        stats = monitor.get_remote_stats()
    else:
        stats = monitor.get_local_stats()
    return jsonify(stats)

@app.route('/api/processes')
def get_processes():
    if monitor.ssh_config['enabled'] and monitor.connection_status == 'connected':
        stats = monitor.get_remote_stats()
    else:
        stats = monitor.get_local_stats()
    return jsonify(stats.get('processes', []))

@app.route('/api/ssh/configure', methods=['POST'])
def configure_ssh():
    data = request.get_json()
    if not data:
        return jsonify({'error': '无效的JSON数据'}), 400
    
    required_fields = ['hostname', 'username', 'password']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'缺少必要字段: {field}'}), 400
    
    success = monitor.configure_ssh(
        data['hostname'],
        data['username'],
        data['password'],
        data.get('port', 22)
    )
    
    return jsonify({
        'success': success,
        'connection_status': monitor.connection_status
    })

@app.route('/api/ssh/connect', methods=['POST'])
def connect_ssh():
    success = monitor.connect_ssh()
    return jsonify({
        'success': success,
        'connection_status': monitor.connection_status
    })

@app.route('/api/ssh/disconnect', methods=['POST'])
def disconnect_ssh():
    success = monitor.disconnect_ssh()
    return jsonify({
        'success': success,
        'connection_status': monitor.connection_status
    })

@app.route('/api/ssh/status')
def ssh_status():
    return jsonify({
        'connection_status': monitor.connection_status,
        'config': monitor.ssh_config,
        'connections': monitor.get_ssh_connections()
    })

@app.route('/api/ssh/connections', methods=['GET'])
def get_ssh_connections():
    return jsonify(monitor.ssh_connections)

@app.route('/api/ssh/connections', methods=['POST'])
def add_ssh_connection():
    data = request.get_json()
    if not data:
        return jsonify({'error': '无效的JSON数据'}), 400
    
    required_fields = ['hostname', 'username', 'password']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'缺少必要字段: {field}'}), 400
    
    monitor.add_ssh_connection({
        'hostname': data['hostname'],
        'username': data['username'],
        'password': data['password'],
        'port': data.get('port', 22),
        'name': data.get('name', f"{data['username']}@{data['hostname']}:{data.get('port', 22)}")
    })
    
    return jsonify({'success': True})

@app.route('/api/ssh/connections', methods=['DELETE'])
def remove_ssh_connection():
    data = request.get_json()
    if not data:
        return jsonify({'error': '无效的JSON数据'}), 400
    
    required_fields = ['hostname', 'username']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'缺少必要字段: {field}'}), 400
    
    monitor.remove_ssh_connection(
        data['hostname'],
        data['username'],
        data.get('port', 22)
    )
    
    return jsonify({'success': True})

@app.route('/api/ssh/switch', methods=['POST'])
def switch_ssh_connection():
    data = request.get_json()
    if not data:
        return jsonify({'error': '无效的JSON数据'}), 400
    
    required_fields = ['hostname', 'username']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'缺少必要字段: {field}'}), 400
    
    # 断开当前连接
    if monitor.connection_status == 'connected':
        monitor.disconnect_ssh()
    
    # 配置新的连接
    port = data.get('port', 22)
    success = monitor.configure_ssh(
        data['hostname'],
        data['username'],
        data['password'],
        port
    )
    
    if success:
        # 尝试连接
        success = monitor.connect_ssh()
    
    return jsonify({
        'success': success,
        'connection_status': monitor.connection_status
    })

@app.route('/api/remote/stats')
def get_remote_stats():
    if monitor.connection_status == 'connected':
        stats = monitor.get_remote_stats()
        return jsonify(stats)
    else:
        return jsonify({
            'error': 'SSH连接未建立',
            'connection_status': monitor.connection_status
        }), 400

@app.route('/api/scheduler/start', methods=['POST'])
def start_scheduler():
    """启动定时调度器"""
    try:
        data = request.get_json() or {}
        interval = data.get('interval', 5)
        
        success = scheduler.start_scheduler(interval)
        return jsonify({
            'success': success,
            'interval': interval,
            'status': scheduler.get_scheduler_status()
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/performance/stats')
def get_performance_stats():
    """获取性能优化统计信息"""
    try:
        stats = performance_optimizer.get_performance_stats()
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/performance/cache/clear', methods=['POST'])
def clear_cache():
    """清空缓存"""
    try:
        performance_optimizer.data_cache.clear()
        return jsonify({'success': True, 'message': '缓存已清空'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/performance/optimization', methods=['POST'])
def toggle_optimization():
    """启用或禁用性能优化"""
    try:
        data = request.get_json()
        if not data or 'enabled' not in data:
            return jsonify({'error': '缺少enabled参数'}), 400
        
        enabled = data['enabled']
        performance_optimizer.enable_optimization(enabled)
        
        return jsonify({
            'success': True,
            'optimization_enabled': enabled,
            'message': f'性能优化已{"启用" if enabled else "禁用"}'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/performance/cache/cleanup', methods=['POST'])
def cleanup_expired_cache():
    """清理过期缓存"""
    try:
        expired_count = performance_optimizer.data_cache.cleanup_expired()
        return jsonify({
            'success': True,
            'expired_count': expired_count,
            'message': f'清理了 {expired_count} 个过期缓存'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/scheduler/stop', methods=['POST'])
def stop_scheduler():
    """停止定时调度器"""
    try:
        success = scheduler.stop_scheduler()
        return jsonify({
            'success': success,
            'status': scheduler.get_scheduler_status()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/scheduler/status')
def get_scheduler_status():
    """获取调度器状态"""
    try:
        status = scheduler.get_scheduler_status()
        return jsonify(status)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/scheduler/interval', methods=['POST'])
def update_scheduler_interval():
    """更新刷新间隔"""
    try:
        data = request.get_json()
        if not data or 'interval' not in data:
            return jsonify({'error': '缺少interval参数'}), 400
        
        interval = data['interval']
        if interval < 1:
            return jsonify({'error': '刷新间隔不能小于1秒'}), 400
        
        success = scheduler.update_interval(interval)
        return jsonify({
            'success': success,
            'interval': interval,
            'status': scheduler.get_scheduler_status()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@socketio.on('connect')
def handle_connect():
    """处理WebSocket连接"""
    print('客户端已连接')
    emit('connection_status', {'status': 'connected'})

@socketio.on('disconnect')
def handle_disconnect():
    """处理WebSocket断开连接"""
    print('客户端已断开连接')

@socketio.on('request_stats')
def handle_request_stats():
    """处理实时数据请求"""
    try:
        if monitor.ssh_config['enabled'] and monitor.connection_status == 'connected':
            stats = monitor.get_remote_stats()
        else:
            stats = monitor.get_local_stats()
        
        emit('stats_update', stats)
    except Exception as e:
        emit('error', {'message': f'获取数据失败: {str(e)}'})

@socketio.on('request_ssh_status')
def handle_request_ssh_status():
    """处理SSH状态请求"""
    emit('ssh_status_update', {
        'connection_status': monitor.connection_status,
        'config': monitor.ssh_config,
        'connections': monitor.get_ssh_connections()
    })

# 全局变量跟踪实时更新状态
realtime_update_active = False
realtime_update_task = None

@socketio.on('start_realtime_updates')
def handle_start_realtime_updates(data):
    """开始实时数据更新"""
    global realtime_update_active, realtime_update_task
    
    if realtime_update_active:
        return
    
    interval = data.get('interval', 5)
    realtime_update_active = True
    
    def send_realtime_stats():
        while realtime_update_active:
            try:
                # 检查连接状态并获取相应数据
                if monitor.ssh_config['enabled'] and monitor.connection_status == 'connected':
                    stats = monitor.get_remote_stats()
                else:
                    stats = monitor.get_local_stats()
                
                # 发送数据到所有客户端
                socketio.emit('stats_update', stats)
                socketio.sleep(interval)
            except Exception as e:
                socketio.emit('error', {'message': f'实时更新失败: {str(e)}'})
                socketio.sleep(interval)
    
    # 启动定时器
    realtime_update_task = socketio.start_background_task(send_realtime_stats)

@socketio.on('stop_realtime_updates')
def handle_stop_realtime_updates():
    """停止实时数据更新"""
    global realtime_update_active, realtime_update_task
    
    if realtime_update_active:
        realtime_update_active = False
        if realtime_update_task:
            realtime_update_task.join()
            realtime_update_task = None

if __name__ == '__main__':
    socketio.run(app, debug=False, host='0.0.0.0', port=5000)
