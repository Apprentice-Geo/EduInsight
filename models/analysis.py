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
        """基于用户数据动态生成聚类映射"""
        table_name = f"user_{user_id}"
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 检查用户表是否存在
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
            if not cursor.fetchone():
                conn.close()
                # 返回默认映射
                return {0: "聚类0", 1: "聚类1", 2: "聚类2"}
            
            # 获取聚类统计信息
            cursor.execute(f"""
                SELECT 
                    cluster,
                    COUNT(*) as cluster_size,
                    AVG(latest_score) as avg_score,
                    AVG(total_actions) as avg_actions,
                    AVG(is_procrastinator) as procrastination_rate
                FROM {table_name} 
                GROUP BY cluster
            """)
            
            cluster_stats = cursor.fetchall()
            conn.close()
            
            if not cluster_stats:
                return {0: "聚类0", 1: "聚类1", 2: "聚类2"}
            
            # 动态分配聚类标签（复用MLAnalyzer的逻辑）
            cluster_scores = []
            for row in cluster_stats:
                cluster_id, cluster_size, avg_score, avg_actions, procrastination_rate = row
                avg_score = avg_score or 0
                avg_actions = avg_actions or 0
                procrastination_rate = procrastination_rate or 0
                
                # 标准化分数
                normalized_score = avg_score / 100.0
                normalized_actions = min(avg_actions / 30.0, 1.0)
                
                # 综合评分
                composite_score = (normalized_score * 0.6 + 
                                 normalized_actions * 0.3 - 
                                 procrastination_rate * 0.1)
                
                cluster_scores.append((cluster_id, composite_score))
            
            # 按综合评分排序
            cluster_scores.sort(key=lambda x: x[1], reverse=True)
            
            # 分配标签
            cluster_mapping = {}
            labels = ["优秀学习者", "普通学习者", "需要关注学习者"]
            
            for i, (cluster_id, score) in enumerate(cluster_scores):
                if i < len(labels):
                    cluster_mapping[cluster_id] = labels[i]
                else:
                    cluster_mapping[cluster_id] = f"聚类{cluster_id}"
            
            return cluster_mapping
                
        except Exception as e:
            print(f"Error generating dynamic cluster mapping: {e}")
            # 返回默认映射
            return {0: "聚类0", 1: "聚类1", 2: "聚类2"}
