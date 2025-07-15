import sqlite3
import threading
from config import Config

class DatabaseHelper:
    """数据库助手类，支持WAL模式的SQLite连接"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, db_path=None):
        """单例模式确保数据库连接的一致性"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(DatabaseHelper, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, db_path=None):
        if not self._initialized:
            self.db_path = db_path or Config.DB_PATH
            self._setup_wal_mode()
            self._initialized = True
    
    def _setup_wal_mode(self):
        """设置WAL模式"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 启用WAL模式
            cursor.execute("PRAGMA journal_mode=WAL;")
            wal_result = cursor.fetchone()
            
            # 优化WAL模式的相关设置
            cursor.execute("PRAGMA synchronous=NORMAL;")  # 平衡性能和安全性
            cursor.execute("PRAGMA cache_size=10000;")    # 增加缓存大小
            cursor.execute("PRAGMA temp_store=memory;")    # 临时表存储在内存中
            cursor.execute("PRAGMA mmap_size=268435456;")  # 启用内存映射(256MB)
            
            if wal_result and wal_result[0] == 'wal':
                print(f"SQLite WAL模式已启用: {self.db_path}")
            else:
                print(f"警告: WAL模式启用失败，当前模式: {wal_result}")
            
            conn.close()
        except Exception as e:
            print(f"设置WAL模式时出错: {e}")
    
    def get_connection(self):
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        
        # 为每个连接设置优化参数
        cursor = conn.cursor()
        cursor.execute("PRAGMA busy_timeout=30000;")  # 30秒超时
        cursor.execute("PRAGMA foreign_keys=ON;")     # 启用外键约束
        
        return conn
    
    def execute_query(self, query, params=None, fetch_one=False, fetch_all=False):
        """执行查询操作"""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            if fetch_one:
                return cursor.fetchone()
            elif fetch_all:
                return cursor.fetchall()
            else:
                conn.commit()
                return cursor.rowcount
                
        except Exception as e:
            if conn:
                conn.rollback()
            raise e
        finally:
            if conn:
                conn.close()
    
    def execute_transaction(self, operations):
        """执行事务操作
        
        Args:
            operations: 操作列表，每个操作是(query, params)的元组
        """
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # 开始事务
            cursor.execute("BEGIN IMMEDIATE;")
            
            for query, params in operations:
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
            
            conn.commit()
            return True
            
        except Exception as e:
            if conn:
                conn.rollback()
            raise e
        finally:
            if conn:
                conn.close()
    
    def check_wal_status(self):
        """检查WAL模式状态"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode;")
            mode = cursor.fetchone()[0]
            conn.close()
            return mode
        except Exception as e:
            print(f"检查WAL状态时出错: {e}")
            return None

# 全局数据库助手实例
db_helper = DatabaseHelper()