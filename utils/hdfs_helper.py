import subprocess
import time
from config import Config

class HDFSHelper:
    """HDFS操作辅助类"""
    
    @staticmethod
    def upload_files_with_retry(local_logs_path, local_scores_path, hdfs_input_path):
        """带重试机制的文件上传"""
        try:
            # 创建HDFS目录
            subprocess.run(['hdfs', 'dfs', '-mkdir', '-p', hdfs_input_path], check=True)
            
            # 重试上传
            for attempt in range(Config.HDFS_MAX_RETRIES):
                try:
                    # 使用 -f 参数强制覆盖，避免 File exists 错误
                    subprocess.run([
                        'hdfs', 'dfs', '-put', '-f', local_logs_path, 
                        f"{hdfs_input_path}/action_logs.csv"
                    ], check=True, timeout=Config.HDFS_TIMEOUT)
                    
                    subprocess.run([
                        'hdfs', 'dfs', '-put', local_scores_path, 
                        f"{hdfs_input_path}/quiz_scores.csv"
                    ], check=True, timeout=Config.HDFS_TIMEOUT)
                    
                    print(f"成功上传文件到HDFS，尝试次数: {attempt + 1}")
                    return True
                    
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                    print(f"上传尝试 {attempt + 1} 失败: {e}")
                    if attempt == Config.HDFS_MAX_RETRIES - 1:
                        raise e
                    time.sleep(Config.HDFS_RETRY_DELAY)
                    
        except Exception as e:
            print(f"HDFS上传失败: {e}")
            raise e
    
    @staticmethod
    def clean_user_data(user_id):
        """清理用户的HDFS数据"""
        user_hdfs_path = f"{Config.HDFS_JOB_BASE_PATH}/{user_id}"
        try:
            result = subprocess.run(['hdfs', 'dfs', '-test', '-d', user_hdfs_path], 
                                  capture_output=True)
            if result.returncode == 0:
                print(f"清理用户 {user_id} 的HDFS数据")
                subprocess.run(['hdfs', 'dfs', '-rm', '-r', user_hdfs_path], check=True)
                return True
        except subprocess.CalledProcessError as e:
            print(f"警告: 无法清理HDFS数据: {e}")
            return False
        return True
    
    @staticmethod
    def check_hdfs_path_exists(hdfs_path):
        """检查HDFS路径是否存在"""
        try:
            result = subprocess.run(['hdfs', 'dfs', '-test', '-e', hdfs_path], 
                                  capture_output=True)
            return result.returncode == 0
        except Exception as e:
            print(f"检查HDFS路径失败: {e}")
            return False
