from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import time
import logging
import socket
from datetime import datetime, timedelta

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MonitorScheduler:
    def __init__(self, app, monitor_instance):
        self.app = app
        self.monitor = monitor_instance
        self.scheduler = BackgroundScheduler()
        self.refresh_interval = 5  # 默认5秒刷新间隔
        self.is_running = False
        self.last_refresh_time = None
        self.next_refresh_time = None
        
    def refresh_server_data(self):
        """定时刷新服务器数据的回调函数"""
        try:
            with self.app.app_context():
                self.last_refresh_time = datetime.now()
                self.next_refresh_time = self.last_refresh_time + timedelta(seconds=self.refresh_interval)
                
                # 获取服务器数据
                if self.monitor.ssh_config['enabled'] and self.monitor.connection_status == 'connected':
                    stats = self.monitor.get_remote_stats()
                else:
                    stats = self.monitor.get_local_stats()
                
                # 记录刷新日志
                logger.info(f"定时刷新完成 - 时间: {self.last_refresh_time.strftime('%Y-%m-%d %H:%M:%S')}")
                if 'error' in stats:
                    logger.warning(f"数据获取错误: {stats['error']}")
                else:
                    logger.info(f"CPU使用率: {stats.get('cpu', 0)}%, 内存使用率: {stats.get('memory', {}).get('percent', 0)}%")
                
                return stats
                
        except paramiko.SSHException as e:
            error_msg = f"SSH连接异常: {str(e)}"
            logger.error(f"定时刷新任务执行失败 - {error_msg}")
            return {'error': error_msg, 'error_type': 'ssh_exception'}
        except socket.timeout:
            error_msg = "网络连接超时，请检查网络连接"
            logger.error(f"定时刷新任务执行失败 - {error_msg}")
            return {'error': error_msg, 'error_type': 'timeout'}
        except socket.error as e:
            error_msg = f"网络连接错误: {str(e)}"
            logger.error(f"定时刷新任务执行失败 - {error_msg}")
            return {'error': error_msg, 'error_type': 'network_error'}
        except Exception as e:
            error_type = type(e).__name__
            error_msg = f"定时刷新任务执行失败: {error_type}: {str(e)}"
            logger.error(error_msg)
            return {'error': error_msg, 'error_type': error_type.lower()}
    
    def start_scheduler(self, interval_seconds=5):
        """启动定时调度器"""
        if self.is_running:
            logger.warning("调度器已经在运行中")
            return False
            
        try:
            self.refresh_interval = interval_seconds
            
            # 添加定时任务
            self.scheduler.add_job(
                func=self.refresh_server_data,
                trigger=IntervalTrigger(seconds=interval_seconds),
                id='server_monitor_refresh',
                name='服务器监控数据刷新任务',
                replace_existing=True
            )
            
            # 启动调度器
            self.scheduler.start()
            self.is_running = True
            
            # 立即执行一次初始刷新
            self.refresh_server_data()
            
            logger.info(f"定时调度器已启动，刷新间隔: {interval_seconds}秒")
            return True
            
        except Exception as e:
            logger.error(f"启动调度器失败: {str(e)}")
            return False
    
    def stop_scheduler(self):
        """停止定时调度器"""
        if self.is_running:
            try:
                self.scheduler.shutdown()
                self.is_running = False
                logger.info("定时调度器已停止")
                return True
            except Exception as e:
                logger.error(f"停止调度器失败: {str(e)}")
                return False
        return True
    
    def update_interval(self, new_interval_seconds):
        """更新刷新间隔"""
        if not self.is_running:
            return self.start_scheduler(new_interval_seconds)
            
        try:
            # 先停止当前任务
            self.scheduler.remove_job('server_monitor_refresh')
            
            # 重新添加任务
            self.scheduler.add_job(
                func=self.refresh_server_data,
                trigger=IntervalTrigger(seconds=new_interval_seconds),
                id='server_monitor_refresh',
                name='服务器监控数据刷新任务',
                replace_existing=True
            )
            
            self.refresh_interval = new_interval_seconds
            logger.info(f"刷新间隔已更新为: {new_interval_seconds}秒")
            return True
            
        except Exception as e:
            logger.error(f"更新刷新间隔失败: {str(e)}")
            return False
    
    def get_scheduler_status(self):
        """获取调度器状态"""
        jobs = self.scheduler.get_jobs()
        job_status = []
        
        for job in jobs:
            job_status.append({
                'id': job.id,
                'name': job.name,
                'next_run_time': job.next_run_time.strftime('%Y-%m-%d %H:%M:%S') if job.next_run_time else None,
                'trigger': str(job.trigger)
            })
        
        return {
            'is_running': self.is_running,
            'refresh_interval': self.refresh_interval,
            'last_refresh_time': self.last_refresh_time.strftime('%Y-%m-%d %H:%M:%S') if self.last_refresh_time else None,
            'next_refresh_time': self.next_refresh_time.strftime('%Y-%m-%d %H:%M:%S') if self.next_refresh_time else None,
            'jobs': job_status
        }
    
    def __del__(self):
        """析构函数，确保调度器正确关闭"""
        if self.is_running:
            self.stop_scheduler()