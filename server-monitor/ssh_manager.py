import paramiko
import logging
import json
import time
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from cache_manager import DataCache


@dataclass
class ServerStats:
    """服务器统计数据类"""
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    load_avg: float
    network_traffic: Dict[str, float]
    processes: List[Dict[str, Any]]
    timestamp: float


class SSHManager:
    """SSH连接管理器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.cache = DataCache()
        self.connection_configs = []
        self.connection_pool = {}
        
    def connect_to_server(self, hostname: str, username: str, password: str, 
                         port: int = 22, timeout: int = 10) -> Optional[paramiko.SSHClient]:
        """建立SSH连接"""
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(hostname, port=port, username=username, 
                          password=password, timeout=timeout)
            self.logger.info(f"成功连接到服务器 {hostname}")
            return client
        except paramiko.AuthenticationException:
            self.logger.error(f"认证失败: {hostname}")
        except paramiko.SSHException as e:
            self.logger.error(f"SSH连接错误 {hostname}: {str(e)}")
        except Exception as e:
            self.logger.error(f"连接服务器 {hostname} 失败: {str(e)}")
        return None

    def execute_command(self, client: paramiko.SSHClient, command: str) -> Optional[str]:
        """执行远程命令"""
        try:
            stdin, stdout, stderr = client.exec_command(command)
            output = stdout.read().decode().strip()
            error = stderr.read().decode().strip()
            
            if error:
                self.logger.warning(f"命令执行警告: {command}, 错误: {error}")
            
            return output
        except Exception as e:
            self.logger.error(f"执行命令失败: {command}, 错误: {str(e)}")
            return None

    def get_server_stats(self, client: paramiko.SSHClient) -> Optional[ServerStats]:
        """获取服务器性能统计数据"""
        try:
            # 获取CPU使用率
            cpu_usage = self._get_cpu_usage(client)
            
            # 获取内存使用率
            memory_usage = self._get_memory_usage(client)
            
            # 获取磁盘使用率
            disk_usage = self._get_disk_usage(client)
            
            # 获取系统负载
            load_avg = self._get_load_average(client)
            
            # 获取网络流量
            network_traffic = self._get_network_traffic(client)
            
            # 获取进程列表
            processes = self._get_process_list(client)
            
            stats = ServerStats(
                cpu_usage=cpu_usage,
                memory_usage=memory_usage,
                disk_usage=disk_usage,
                load_avg=load_avg,
                network_traffic=network_traffic,
                processes=processes,
                timestamp=time.time()
            )
            
            return stats
            
        except Exception as e:
            self.logger.error(f"获取服务器统计信息失败: {str(e)}")
            return None

    def _get_cpu_usage(self, client: paramiko.SSHClient) -> float:
        """获取CPU使用率"""
        try:
            # 使用更可靠的CPU使用率获取方式
            command = "grep 'cpu ' /proc/stat | awk '{usage=($2+$4)*100/($2+$4+$5)} END {print usage}'"
            output = self.execute_command(client, command)
            
            if output:
                try:
                    return round(float(output.strip()), 2)
                except ValueError:
                    pass
            
            # 备用方法：使用mpstat命令
            command = "mpstat 1 1 | awk 'END {print 100 - $NF}'"
            output = self.execute_command(client, command)
            
            if output:
                try:
                    return round(float(output.strip()), 2)
                except ValueError:
                    pass
            
            # 最后尝试使用top命令
            command = "top -bn1 | grep 'Cpu(s)' | awk '{print $2}' | cut -d'%' -f1"
            output = self.execute_command(client, command)
            
            if output:
                try:
                    return round(float(output.strip()), 2)
                except ValueError:
                    pass
            
            return 0.0
        except Exception as e:
            self.logger.error(f"获取CPU使用率失败: {str(e)}")
            return 0.0

    def _get_memory_usage(self, client: paramiko.SSHClient) -> float:
        """获取内存使用率"""
        try:
            command = "free | grep Mem"
            output = self.execute_command(client, command)
            
            if output:
                parts = output.split()
                total_mem = int(parts[1])
                used_mem = int(parts[2])
                usage = 100.0 * used_mem / total_mem if total_mem > 0 else 0.0
                return round(usage, 2)
            
            return 0.0
        except Exception as e:
            self.logger.error(f"获取内存使用率失败: {str(e)}")
            return 0.0

    def _get_disk_usage(self, client: paramiko.SSHClient) -> float:
        """获取磁盘使用率"""
        try:
            command = "df / | tail -1"
            output = self.execute_command(client, command)
            
            if output:
                parts = output.split()
                if len(parts) >= 5:
                    usage_str = parts[4].replace('%', '')
                    return float(usage_str)
            
            return 0.0
        except Exception as e:
            self.logger.error(f"获取磁盘使用率失败: {str(e)}")
            return 0.0

    def _get_load_average(self, client: paramiko.SSHClient) -> float:
        """获取系统负载平均值（1min）"""
        try:
            command = "cat /proc/loadavg"
            output = self.execute_command(client, command)
            
            if output:
                # 提取1分钟负载平均值
                parts = output.strip().split()
                if len(parts) >= 1:
                    return float(parts[0])
            
            return 0.0
        except Exception as e:
            self.logger.error(f"获取系统负载失败: {str(e)}")
            return 0.0

    def _get_uptime(self, client: paramiko.SSHClient) -> str:
        """获取系统运行时间"""
        try:
            # 主要方法：使用/proc/uptime
            command = "cat /proc/uptime | awk '{print $1}'"
            output = self.execute_command(client, command)
            
            if output:
                uptime_seconds = float(output.strip())
                # 转换为小时:分钟:秒格式
                hours = int(uptime_seconds // 3600)
                minutes = int((uptime_seconds % 3600) // 60)
                seconds = int(uptime_seconds % 60)
                return f"{hours}:{minutes:02d}:{seconds:02d}"
            
            # 备用方法：使用uptime命令
            command = "uptime -p | sed 's/up //' | sed 's/ minutes/m/' | sed 's/ hours/h/' | sed 's/ days/d/'"
            output = self.execute_command(client, command)
            
            if output:
                return output.strip()
            
            # 最后备用方法：使用简单的uptime
            command = "uptime | awk -F'up' '{print $2}' | awk -F',' '{print $1}' | sed 's/^[[:space:]]*//'"
            output = self.execute_command(client, command)
            
            if output:
                return output.strip()
            
            return "0:00:00"
        except Exception as e:
            self.logger.error(f"获取运行时间失败: {str(e)}")
            return "0:00:00"

    def _get_network_traffic(self, client: paramiko.SSHClient) -> Dict[str, Any]:
        """获取网络流量统计"""
        try:
            # 获取网络接口统计信息
            stdin, stdout, stderr = client.exec_command('cat /proc/net/dev | grep -E "(eth|ens|wlan)[0-9]:" | head -5')
            net_dev_output = stdout.read().decode().strip()
            
            traffic_stats = {'rx_bytes': 0, 'tx_bytes': 0, 'connections': 0}
            
            if net_dev_output:
                lines = net_dev_output.split('\n')
                for line in lines:
                    parts = line.split()
                    if len(parts) >= 10:
                        # 接收字节数在第2列，发送字节数在第10列
                        rx_bytes = int(parts[1])
                        tx_bytes = int(parts[9])
                        traffic_stats['rx_bytes'] += rx_bytes
                        traffic_stats['tx_bytes'] += tx_bytes
            
            # 获取网络连接数 - 使用更全面的方法
            try:
                # 方法1: 使用ss命令获取所有TCP连接（包括监听和已建立）
                conn_output = self.execute_command(client, "ss -t | wc -l")
                if conn_output:
                    # 减去标题行（通常有1-2行标题）
                    conn_count = max(0, int(conn_output.strip()) - 1)
                    traffic_stats['connections'] = conn_count
                    self.logger.info(f"ss命令获取到连接数: {conn_count}")
                else:
                    # 方法2: 使用netstat获取所有TCP连接
                    conn_output = self.execute_command(client, "netstat -t | wc -l")
                    if conn_output:
                        # 减去标题行
                        conn_count = max(0, int(conn_output.strip()) - 2)
                        traffic_stats['connections'] = conn_count
                        self.logger.info(f"netstat命令获取到连接数: {conn_count}")
                    else:
                        # 方法3: 使用更简单的方法直接计算连接数
                        conn_output = self.execute_command(client, "netstat -t | grep -c ESTABLISHED")
                        if conn_output:
                            traffic_stats['connections'] = int(conn_output.strip())
                            self.logger.info(f"ESTABLISHED连接数: {traffic_stats['connections']}")
                        else:
                            traffic_stats['connections'] = 0
                            self.logger.info("无法获取网络连接数，使用默认值0")
            except Exception as e:
                traffic_stats['connections'] = 0
                self.logger.error(f"获取网络连接数失败: {str(e)}")
            
            return traffic_stats
            
        except Exception as e:
            self.logger.error(f"获取网络流量失败: {str(e)}")
            return {'rx_bytes': 0, 'tx_bytes': 0, 'connections': 0}

    def _get_process_list(self, client: paramiko.SSHClient) -> List[Dict[str, Any]]:
        """获取进程列表"""
        try:
            command = "ps aux --sort=-%cpu | head -10"
            output = self.execute_command(client, command)
            
            processes = []
            if output:
                lines = output.strip().split('\n')[1:]  # 跳过标题行
                for line in lines:
                    parts = line.split(maxsplit=10)
                    if len(parts) >= 11:
                        process_info = {
                            'user': parts[0],
                            'pid': parts[1],
                            'cpu': float(parts[2]),
                            'mem': float(parts[3]),
                            'command': parts[10][:50]  # 限制命令长度
                        }
                        processes.append(process_info)
            
            return processes
            
        except Exception as e:
            self.logger.error(f"获取进程列表失败: {str(e)}")
            return []

    def close_connection(self, client: paramiko.SSHClient):
        """关闭SSH连接"""
        try:
            if client:
                client.close()
                self.logger.info("SSH连接已关闭")
        except Exception as e:
            self.logger.error(f"关闭连接失败: {str(e)}")

    def test_connection(self, hostname: str, username: str, password: str) -> bool:
        """测试连接是否可用"""
        client = self.connect_to_server(hostname, username, password)
        if client:
            self.close_connection(client)
            return True
        return False

    def get_cached_stats(self, server_id: str) -> Optional[ServerStats]:
        """获取缓存的服务器统计数据"""
        return self.cache.get(server_id)

    def update_server_stats(self, server_id: str, stats: ServerStats):
        """更新服务器统计数据到缓存"""
        self.cache.set(server_id, stats)

    def add_connection_config(self, config: Dict[str, Any]):
        """添加SSH连接配置"""
        self.connection_configs.append(config)
        self._save_connection_configs()

    def remove_connection_config(self, hostname: str, username: str, port: int = 22):
        """移除SSH连接配置"""
        self.connection_configs = [
            config for config in self.connection_configs
            if not (config['hostname'] == hostname and 
                   config['username'] == username and 
                   config.get('port', 22) == port)
        ]
        self._save_connection_configs()

    def _save_connection_configs(self):
        """保存连接配置到文件"""
        try:
            with open('ssh_connections.json', 'w', encoding='utf-8') as f:
                json.dump(self.connection_configs, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"保存连接配置失败: {str(e)}")

    def _load_connection_configs(self):
        """从文件加载连接配置"""
        try:
            if os.path.exists('ssh_connections.json'):
                with open('ssh_connections.json', 'r', encoding='utf-8') as f:
                    self.connection_configs = json.load(f)
        except Exception as e:
            self.logger.error(f"加载连接配置失败: {str(e)}")
            self.connection_configs = []

    def connect_with_config(self, config: Dict[str, Any]) -> bool:
        """使用配置连接到服务器（兼容app.py接口）"""
        try:
            client = self.connect_to_server(
                config['hostname'],
                config['username'],
                config['password'],
                config.get('port', 22),
                config.get('timeout', 10)
            )
            if client:
                connection_key = f"{config['hostname']}_{config['username']}_{config.get('port', 22)}"
                self.connection_pool[connection_key] = client
                return True
            return False
        except Exception as e:
            self.logger.error(f"连接服务器失败: {str(e)}")
            return False

    def disconnect_from_server(self, connection_key: str):
        """断开服务器连接"""
        if connection_key in self.connection_pool:
            client = self.connection_pool[connection_key]
            self.close_connection(client)
            del self.connection_pool[connection_key]

    def get_server_stats_by_key(self, connection_key: str) -> Optional[Dict[str, Any]]:
        """通过连接键获取服务器状态（兼容app.py接口）"""
        if connection_key not in self.connection_pool:
            return None
        
        client = self.connection_pool[connection_key]
        stats = self.get_server_stats(client)
        
        if stats:
            # 从网络流量数据中提取连接数
            network_connections = 0
            if hasattr(stats.network_traffic, 'get'):
                network_connections = stats.network_traffic.get('connections', 0)
            
            return {
                'cpu_usage': stats.cpu_usage,
                'memory_usage': stats.memory_usage,
                'disk_usage': stats.disk_usage,
                'load_average': stats.load_avg,
                'network_traffic': stats.network_traffic,
                'network_connections': network_connections,
                'processes': stats.processes,
                'timestamp': stats.timestamp
            }
        return None

    def get_connection_key(self, hostname: str, username: str, port: int = 22) -> str:
        """生成连接键"""
        return f"{hostname}_{username}_{port}"
    
    def get_connection_configs(self) -> List[Dict]:
        """获取所有连接配置"""
        return self.connection_configs

    def _get_network_traffic(self, client: paramiko.SSHClient) -> Dict[str, Any]:
        """获取网络流量统计和连接数"""
        try:
            # 获取网络接口统计信息
            command = "cat /proc/net/dev | grep -E '^(eth|ens|enp|wlan|wlp|lo):' | head -5"
            output = self.execute_command(client, command)
            
            traffic_stats = {'connections': 0}
            if output:
                lines = output.strip().split('\n')
                for line in lines:
                    if ':' in line:
                        parts = line.split()
                        if len(parts) >= 10:
                            interface = parts[0].replace(':', '')
                            rx_bytes = int(parts[1])
                            tx_bytes = int(parts[9])
                            traffic_stats[interface] = {
                                'rx_bytes': rx_bytes,
                                'tx_bytes': tx_bytes,
                                'rx_mbps': round(rx_bytes / 1024 / 1024, 2),
                                'tx_mbps': round(tx_bytes / 1024 / 1024, 2)
                            }
            
            # 获取网络连接数 - 使用更可靠的方法
            try:
                # 方法1: 使用ss命令获取所有TCP连接（包括监听和已建立）
                conn_output = self.execute_command(client, "ss -t | wc -l")
                if conn_output:
                    # 减去标题行（通常有1-2行标题）
                    conn_count = max(0, int(conn_output.strip()) - 1)
                    traffic_stats['connections'] = conn_count
                    self.logger.info(f"ss命令获取到连接数: {conn_count}")
                else:
                    # 方法2: 使用netstat获取所有TCP连接
                    conn_output = self.execute_command(client, "netstat -t | wc -l")
                    if conn_output:
                        # 减去标题行
                        conn_count = max(0, int(conn_output.strip()) - 2)
                        traffic_stats['connections'] = conn_count
                        self.logger.info(f"netstat命令获取到连接数: {conn_count}")
                    else:
                        # 方法3: 使用更简单的方法直接计算连接数
                        conn_output = self.execute_command(client, "netstat -t | grep -c ESTABLISHED")
                        if conn_output:
                            traffic_stats['connections'] = int(conn_output.strip())
                            self.logger.info(f"ESTABLISHED连接数: {traffic_stats['connections']}")
                        else:
                            traffic_stats['connections'] = 0
                            self.logger.info("无法获取网络连接数，使用默认值0")
            except Exception as e:
                traffic_stats['connections'] = 0
                self.logger.error(f"获取网络连接数失败: {str(e)}")
            
            return traffic_stats
            
        except Exception as e:
            self.logger.error(f"获取网络流量失败: {str(e)}")
            return {'connections': 0}

    def _get_service_status(self, client: paramiko.SSHClient) -> Dict[str, Any]:
        """获取服务状态监控"""
        services_to_check = [
            'ssh', 'nginx', 'mysql', 'apache2', 'postgresql', 
            'redis', 'mongodb', 'docker', 'cron', 'systemd'
        ]
        
        service_status = {}
        
        try:
            # 检查systemd服务状态
            for service in services_to_check:
                try:
                    # 尝试使用systemctl检查服务状态
                    command = f"systemctl is-active {service} 2>/dev/null || echo 'unknown'"
                    output = self.execute_command(client, command)
                    
                    if output:
                        status = output.strip().lower()
                        if status in ['active', 'inactive', 'failed', 'unknown']:
                            service_status[service] = status
                        else:
                            service_status[service] = 'unknown'
                    else:
                        service_status[service] = 'unknown'
                        
                except Exception:
                    service_status[service] = 'unknown'
            
            # 检查进程是否存在（备用方法）
            for service in services_to_check:
                if service_status.get(service) == 'unknown':
                    try:
                        command = f"pgrep -x {service} >/dev/null && echo 'running' || echo 'stopped'"
                        output = self.execute_command(client, command)
                        if output and output.strip() == 'running':
                            service_status[service] = 'active'
                    except Exception:
                        pass
            
            return service_status
            
        except Exception as e:
            self.logger.error(f"获取服务状态失败: {str(e)}")
            return {}

# 创建全局SSH管理器实例
ssh_manager = SSHManager()
# 加载保存的连接配置
ssh_manager._load_connection_configs()
