import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import json
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DataCache:
    """数据缓存管理类"""
    
    def __init__(self, default_ttl=30):
        """
        初始化数据缓存
        :param default_ttl: 默认缓存时间（秒）
        """
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.default_ttl = default_ttl
        self.lock = threading.RLock()
        self.hit_count = 0
        self.miss_count = 0
    
    def get(self, key: str) -> Optional[Any]:
        """
        从缓存中获取数据
        :param key: 缓存键
        :return: 缓存数据或None
        """
        with self.lock:
            if key in self.cache:
                cache_item = self.cache[key]
                # 检查缓存是否过期
                if datetime.now() < cache_item['expires_at']:
                    self.hit_count += 1
                    return cache_item['data']
                else:
                    # 缓存已过期，移除
                    del self.cache[key]
            
            self.miss_count += 1
            return None
    
    def set(self, key: str, data: Any, ttl: Optional[int] = None):
        """
        设置缓存数据
        :param key: 缓存键
        :param data: 要缓存的数据
        :param ttl: 缓存时间（秒），None使用默认值
        """
        with self.lock:
            expires_at = datetime.now() + timedelta(seconds=ttl or self.default_ttl)
            self.cache[key] = {
                'data': data,
                'expires_at': expires_at,
                'created_at': datetime.now(),
                'ttl': ttl or self.default_ttl
            }
    
    def delete(self, key: str):
        """删除指定缓存"""
        with self.lock:
            if key in self.cache:
                del self.cache[key]
    
    def clear(self):
        """清空所有缓存"""
        with self.lock:
            self.cache.clear()
            self.hit_count = 0
            self.miss_count = 0
    
    def cleanup_expired(self):
        """清理过期的缓存"""
        with self.lock:
            current_time = datetime.now()
            keys_to_delete = []
            
            for key, item in self.cache.items():
                if current_time >= item['expires_at']:
                    keys_to_delete.append(key)
            
            for key in keys_to_delete:
                del self.cache[key]
            
            return len(keys_to_delete)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        with self.lock:
            return {
                'total_items': len(self.cache),
                'hit_count': self.hit_count,
                'miss_count': self.miss_count,
                'hit_rate': self.hit_count / (self.hit_count + self.miss_count) if (self.hit_count + self.miss_count) > 0 else 0,
                'default_ttl': self.default_ttl
            }
    
    def get_all_keys(self) -> list:
        """获取所有缓存键"""
        with self.lock:
            return list(self.cache.keys())

class BatchProcessor:
    """批量处理器"""
    
    def __init__(self, max_batch_size=10, max_batch_time=1.0):
        """
        初始化批量处理器
        :param max_batch_size: 最大批量大小
        :param max_batch_time: 最大批量处理时间（秒）
        """
        self.max_batch_size = max_batch_size
        self.max_batch_time = max_batch_time
        self.batch_queue = []
        self.last_process_time = datetime.now()
        self.lock = threading.RLock()
        self.processed_count = 0
    
    def add_to_batch(self, item: Any) -> bool:
        """
        添加项目到批量队列
        :param item: 要处理的项目
        :return: 是否触发了批量处理
        """
        with self.lock:
            self.batch_queue.append(item)
            
            # 检查是否达到批量处理条件
            current_time = datetime.now()
            time_since_last_process = (current_time - self.last_process_time).total_seconds()
            
            if (len(self.batch_queue) >= self.max_batch_size or 
                time_since_last_process >= self.max_batch_time):
                self._process_batch()
                return True
            
            return False
    
    def _process_batch(self):
        """处理当前批量队列"""
        with self.lock:
            if not self.batch_queue:
                return
            
            # 这里可以添加具体的批量处理逻辑
            # 例如：批量发送数据、批量更新数据库等
            batch_size = len(self.batch_queue)
            logger.info(f"处理批量数据，大小: {batch_size}")
            
            # 模拟批量处理
            processed_items = self.batch_queue.copy()
            self.batch_queue.clear()
            self.last_process_time = datetime.now()
            self.processed_count += batch_size
    
    def force_process(self):
        """强制处理当前批量队列"""
        with self.lock:
            self._process_batch()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取批量处理器统计信息"""
        with self.lock:
            return {
                'queue_size': len(self.batch_queue),
                'max_batch_size': self.max_batch_size,
                'max_batch_time': self.max_batch_time,
                'processed_count': self.processed_count,
                'time_since_last_process': (datetime.now() - self.last_process_time).total_seconds()
            }

class PerformanceOptimizer:
    """性能优化器"""
    
    def __init__(self):
        self.data_cache = DataCache(default_ttl=15)  # 15秒缓存时间
        self.batch_processor = BatchProcessor(max_batch_size=5, max_batch_time=2.0)
        self.optimization_enabled = True
    
    def get_cached_server_stats(self, server_key: str, fetch_func, *args, **kwargs) -> Dict[str, Any]:
        """
        获取缓存的服务器状态数据
        :param server_key: 服务器唯一标识
        :param fetch_func: 数据获取函数
        :return: 服务器状态数据
        """
        if not self.optimization_enabled:
            return fetch_func(*args, **kwargs)
        
        cache_key = f"server_stats:{server_key}"
        cached_data = self.data_cache.get(cache_key)
        
        if cached_data is not None:
            cached_data['from_cache'] = True
            cached_data['cache_timestamp'] = datetime.now().isoformat()
            return cached_data
        
        # 缓存未命中，获取新数据
        fresh_data = fetch_func(*args, **kwargs)
        if 'error' not in fresh_data:
            self.data_cache.set(cache_key, fresh_data, ttl=10)  # 10秒缓存
        
        fresh_data['from_cache'] = False
        fresh_data['cache_timestamp'] = datetime.now().isoformat()
        return fresh_data
    
    def add_monitoring_data_to_batch(self, data: Dict[str, Any]):
        """
        添加监控数据到批量队列
        :param data: 监控数据
        """
        if self.optimization_enabled:
            self.batch_processor.add_to_batch(data)
    
    def cleanup(self):
        """清理资源"""
        self.data_cache.clear()
        self.batch_processor.force_process()
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计信息"""
        return {
            'cache_stats': self.data_cache.get_stats(),
            'batch_stats': self.batch_processor.get_stats(),
            'optimization_enabled': self.optimization_enabled
        }
    
    def enable_optimization(self, enabled: bool = True):
        """启用或禁用性能优化"""
        self.optimization_enabled = enabled
        if not enabled:
            self.cleanup()

# 全局性能优化器实例
performance_optimizer = PerformanceOptimizer()

def cleanup_cache_periodically():
    """定期清理缓存（后台线程）"""
    while True:
        try:
            time.sleep(60)  # 每分钟清理一次
            expired_count = performance_optimizer.data_cache.cleanup_expired()
            if expired_count > 0:
                logger.info(f"清理了 {expired_count} 个过期缓存")
        except Exception as e:
            logger.error(f"缓存清理线程异常: {e}")

# 启动缓存清理线程
cache_cleanup_thread = threading.Thread(target=cleanup_cache_periodically, daemon=True)
cache_cleanup_thread.start()