from flask import Flask, render_template, jsonify, request
import psutil
import paramiko
import json
from datetime import datetime
import time
import threading
import os

app = Flask(__name__)

class ServerMonitor:
    def __init__(self):
        self.ssh_client = None
        self.ssh_config = {
            'enabled': False,
            'hostname': '',
            'username': '',
            'password': '',
            'port': 22
        }
        self.ssh_connections = []  # 存储多个SSH连接配置
        self.connection_status = 'disconnected'
        self.load_ssh_connections()
    
    def load_ssh_connections(self):
        """加载保存的SSH连接配置"""
        try:
            if os.path.exists('ssh_connections.json'):
                with open('ssh_connections.json', 'r', encoding='utf-8') as f:
                    self.ssh_connections = json.load(f)
        except Exception as e:
            print(f"加载SSH连接配置失败: {e}")
            self.ssh_connections = []
    
    def save_ssh_connections(self):
        """保存SSH连接配置"""
        try:
            with open('ssh_connections.json', 'w', encoding='utf-8') as f:
                json.dump(self.ssh_connections, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存SSH连接配置失败: {e}")
    
    def add_ssh_connection(self, config):
        """添加新的SSH连接配置"""
        # 检查是否已存在相同配置
        for conn in self.ssh_connections:
            if (conn['hostname'] == config['hostname'] and 
                conn['username'] == config['username'] and
                conn['port'] == config.get('port', 22)):
                # 更新现有配置
                conn.update(config)
                self.save_ssh_connections()
                return
        
        # 添加新配置
        self.ssh_connections.append(config)
        self.save_ssh_connections()
    
    def remove_ssh_connection(self, hostname, username, port=22):
        """移除SSH连接配置"""
        self.ssh_connections = [
            conn for conn in self.ssh_connections 
            if not (conn['hostname'] == hostname and 
                   conn['username'] == username and
                   conn.get('port', 22) == port)
        ]
        self.save_ssh_connections()
    
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
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # 添加超时和极连接测试
            self.ssh_client.connect(
                self.ssh_config['hostname'],
                port=self.ssh_config['port'],
                username=self.ssh_config['username'],
                password=self.ssh_config['password'],
                timeout=15,
                banner_timeout=30
            )
            
            # 测试连接是否真正有效
            stdin, stdout, stderr = self.ssh_client.exec_command('echo "连接测试成功"', timeout=10)
            test_output = stdout.read().decode().strip()
            
            if test_output == "连接测试成功":
                self.connection_status = 'connected'
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
                
        except paramiko.AuthenticationException:
            self.connection_status = 'error: 认证失败 - 用户名或密码错误'
            print("✗ SSH认证失败")
            return False
        except paramiko.SSHException as e:
            self.connection_status = f'error: SSH协议错误 - {str(e)}'
            print(f"✗ SSH协议错误: {e}")
            return False
        except Exception as e:
            self.connection_status = f'error: 连接失败 - {str(e)}'
            print(f"✗ SSH连接失败: {e}")
            return False

    def disconnect_ssh(self):
        """断开SSH连接"""
        if self.ssh_client:
            self.ssh_client.close()
            self.ssh_client = None
        self.connection_status = 'disconnected'
        return True
    
    def get_remote_stats(self):
        """获取远程服务器状态（通过SSH）"""
        if not self.ssh_client or self.connection_status != 'connected':
            return {'error': 'SSH连接未建立', 'connection_status': self.connection_status}
        
        try:
            # 更通用的命令，兼容不同Linux发行版
            commands = {
                'cpu_usage': "cat /proc/stat | grep '^cpu ' | awk '{usage=($2+$4)*100/($2+$4+$5)} END {printf \"%.1f\", usage}'",
                'memory_info': "free -b | grep 'Mem:' | awk '{printf \"%d|%d|%.1f\", $2, $3, $3/$2*100}'",
                'process_list': "ps -eo pid,comm,%cpu,%mem,stat --sort=-%cpu | head -11 | awk '{print $1, $2, $3, $4, $5}'",
                'uptime_info': "cat /proc/uptime | awk '{printf \"%d天%d小时%d分钟\", $1/86400, ($1%86400)/3600, ($1%3600)/60}'",
                'network_connections': "ss -tun | wc -l",
                'hostname': "hostname"
            }
            
            stats = {'connection_status': 'connected'}
            for key, cmd in commands.items():
                try:
                    stdin, stdout, stderr = self.ssh_client.exec_command(cmd, timeout=10)
                    output = stdout.read().decode().strip()
                    error = stderr.read().decode().strip()
                    
                    if error and 'Warning' not in error:  # 忽略警告信息
                        stats[key] = f'error: {error}'
                    else:
                        stats[key] = output
                except Exception as e:
                    stats[key] = f'极error: {str(e)}'
            
            # 解析内存信息
            if 'memory_info' in stats and not stats['memory_info'].startswith('error'):
                try:
                    mem_total, mem_used, mem_percent = stats['memory_info'].split('|')
                    stats['memory'] = {
                        'total': round(int(mem_total) / (1024**3), 2),
                        'used': round(int(mem_used) / (1024**3), 2),
                        'percent': float(mem_percent)
                    }
                except:
                    stats['memory'] = {'total': 0, 'used': 0, 'percent': 0}
            
            # 解析CPU信息
            if 'cpu_usage' in stats and not stats['cpu_usage'].startswith('error'):
                try:
                    stats['cpu'] = float(stats['cpu_usage'])
                except:
                    stats['cpu'] = 0
            
            # 解析进程信息
            if 'process_list' in stats and not stats['process_list'].startswith('error'):
                processes = []
                lines = stats['process_list'].split('\n')
                for line in lines[1:]:  # 跳过标题行
                    parts = line.split()
                    if len(parts) >= 5:
                        processes.append({
                            'pid': parts[0],
                            'name': parts[1],
                            'cpu': parts[2],
                            'memory': parts[3],
                            'status': parts[4] if len(parts) > 4 else 'unknown'
                        })
                stats['processes'] = processes[:10]  # 只返回前10个进程
            
            # 添加其他信息
            stats['network'] = {'connections': stats.get('network_connections', 0)}
            stats['uptime'] = stats.get('uptime_info', '未知')
            stats['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            return stats
            
        except Exception as e:
            self.connection_status = f'error: {str(e)}'
            return {'error': str(e), 'connection_status': self.connection_status}

monitor = ServerMonitor()

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
        'connections': monitor.ssh_connections
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
            'error': 'SS极H连接未建立',
            'connection_status': monitor.connection_status
        }), 400

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)