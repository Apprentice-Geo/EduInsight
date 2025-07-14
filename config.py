import os

class Config:
    """应用配置类"""
    
    # Flask配置
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-change-this-in-production'
    
    # Spark配置
    SPARK_DRIVER_HOST = "198.18.0.1"
    SPARK_APP_NAME = "EduInsight Academic Warning System"
    
    # 路径配置
    UPLOAD_FOLDER = '/tmp/spark_uploads'
    DB_PATH = "/home/spark/teaching_analysis.db"
    HDFS_JOB_BASE_PATH = "/user/spark/jobs"
    
    # 文件配置
    ALLOWED_EXTENSIONS = {'csv'}
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    
    # HDFS配置
    HDFS_TIMEOUT = 120
    HDFS_MAX_RETRIES = 3
    HDFS_RETRY_DELAY = 5
    
    # 机器学习配置
    KMEANS_CLUSTERS = 3
    PCA_COMPONENTS = 3
    ANOMALY_THRESHOLD = 2.0
    
    @staticmethod
    def init_app(app):
        """初始化应用配置"""
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
