import sqlite3
from config import Config

class AnalysisResult:
    """分析结果模型类"""
    
    def __init__(self, db_path=None):
        self.db_path = db_path or Config.DB_PATH
    
    def get_user_results(self, user_id):
        """获取用户的分析结果"""
        table_name = f"user_{user_id}"
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 检查表是否存在
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
            if not cursor.fetchone():
                conn.close()
                return None
            
            # 获取所有结果
            cursor.execute(f"SELECT * FROM {table_name}")
            columns = [description[0] for description in cursor.description]
            results = cursor.fetchall()
            
            conn.close()
            
            # 转换为字典列表
            return [dict(zip(columns, row)) for row in results]
            
        except Exception as e:
            print(f"Error getting user results: {e}")
            return None
    
    def get_risk_statistics(self, user_id):
        """获取风险统计信息"""
        table_name = f"user_{user_id}"
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(f"""
                SELECT 
                    comprehensive_warning,
                    COUNT(*) as count
                FROM {table_name} 
                GROUP BY comprehensive_warning
            """)
            
            risk_stats = cursor.fetchall()
            conn.close()
            
            stats = {}
            for warning_level, count in risk_stats:
                stats[warning_level] = count
            
            return stats
            
        except Exception as e:
            print(f"Error getting risk statistics: {e}")
            return {}
    
    def clear_user_results(self, user_id):
        """清理用户的分析结果"""
        table_name = f"user_{user_id}"
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error clearing user results: {e}")
            return False
    
    def table_exists(self, user_id):
        """检查用户结果表是否存在"""
        table_name = f"user_{user_id}"
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
            exists = cursor.fetchone() is not None
            conn.close()
            return exists
        except Exception as e:
            print(f"Error checking table existence: {e}")
            return False
    
    def get_cluster_mapping(self, user_id):
        """获取用户的动态聚类映射"""
        metadata_table = f"metadata_{user_id}"
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 检查元数据表是否存在
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (metadata_table,))
            if not cursor.fetchone():
                conn.close()
                # 返回默认映射
                return {0: "聚类0", 1: "聚类1", 2: "聚类2"}
            
            # 获取聚类映射
            cursor.execute(f"SELECT cluster_mapping FROM {metadata_table} LIMIT 1")
            result = cursor.fetchone()
            conn.close()
            
            if result:
                import json
                cluster_mapping = json.loads(result[0])
                # 确保键是整数类型
                converted_mapping = {}
                for key, value in cluster_mapping.items():
                    converted_mapping[int(key)] = value
                return converted_mapping
            else:
                # 返回默认映射
                return {0: "聚类0", 1: "聚类1", 2: "聚类2"}
                
        except Exception as e:
            print(f"Error getting cluster mapping: {e}")
            # 返回默认映射
            return {0: "聚类0", 1: "聚类1", 2: "聚类2"}
