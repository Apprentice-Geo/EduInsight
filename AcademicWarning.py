import sys
import sqlite3
from pyspark.sql import SparkSession
from spark_jobs.data_processor import DataProcessor
from spark_jobs.feature_engineering import FeatureEngineer
from spark_jobs.ml_analysis import MLAnalyzer
from config import Config
from utils.db_helper import db_helper

def analyze(user_id, db_path):
    """
    Spark核心分析逻辑
    :param user_id: 用户ID
    :param db_path: SQLite数据库文件的绝对路径
    """
    spark = SparkSession.builder.appName(f"{Config.SPARK_APP_NAME} - {user_id}").getOrCreate()

    try:
        # 构建HDFS输入路径
        input_path = f"hdfs://mycluster{Config.HDFS_JOB_BASE_PATH}/{user_id}/input/*"
        
        # 1. 数据加载
        print("加载数据...")
        logs_df, scores_df = DataProcessor.load_data(spark, input_path)
        
        # 2. 特征提取
        print("提取特征...")
        activity_counts, action_type_stats, time_features = DataProcessor.extract_activity_features(logs_df)
        late_submissions = DataProcessor.identify_procrastinators(logs_df)
        scores_with_trend = DataProcessor.extract_temporal_features(scores_df)
        
        # 3. 特征合并
        print("合并特征...")
        final_data_df = DataProcessor.merge_features(
            activity_counts, action_type_stats, time_features, late_submissions, scores_with_trend
        )
        
        # 4. 特征工程
        print("特征工程...")
        feature_vector_df, numeric_cols = FeatureEngineer.prepare_ml_features(final_data_df)
        scaled_df, scaler_model = FeatureEngineer.scale_features(feature_vector_df)
        
        # 5. 机器学习分析
        print("机器学习分析...")
        clustered_df, kmeans_model, cluster_mapping = MLAnalyzer.perform_kmeans_clustering(scaled_df)
        pca_df, pca_model = MLAnalyzer.perform_pca_analysis(scaled_df)
        anomaly_students = MLAnalyzer.detect_anomalies(final_data_df, numeric_cols)
        
        # 6. 生成预警
        print("生成预警...")
        final_analysis_df = clustered_df.select(
            "student_id", "latest_score", "historical_avg_score", "score_trend", 
            "total_actions", "is_procrastinator", "cluster"
        )
        
        final_warning_df = MLAnalyzer.generate_warnings(final_analysis_df)
        
        # 7. 显示分析结果
        print("=== 增强分析结果 ===")
        final_warning_df.show()
        
        # 显示统计信息
        risk_distribution = final_warning_df.groupBy("comprehensive_warning").count()
        print("综合风险等级分布:")
        risk_distribution.show()
        
        cluster_risk_analysis = final_warning_df.groupBy("cluster", "comprehensive_warning").count()
        print("聚类与风险等级关联分析:")
        cluster_risk_analysis.show()

        # 8. 保存结果到SQLite (使用WAL模式)
        print(f"保存结果到SQLite数据库: {db_path}")
        result_df = final_warning_df.select(
            "student_id", "latest_score", "historical_avg_score", "score_trend", 
            "total_actions", "is_procrastinator", "cluster", "warning_level", 
            "cluster_risk_level", "comprehensive_warning"
        )
        
        pandas_df = result_df.toPandas()
        
        # 使用WAL模式的数据库连接
        conn = db_helper.get_connection()
        table_name = f"user_{user_id}"
        pandas_df.to_sql(name=table_name, con=conn, if_exists="replace", index=False)
        
        # 注意：聚类映射不再保存到数据库，而是在需要时动态生成
        
        conn.close()
        
        print("分析完成，结果已保存到数据库。")

    except Exception as e:
        print(f"用户 {user_id} 的Spark任务发生错误: {e}")
        raise e
    finally:
        spark.stop()

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: AcademicWarning.py <user_id> <db_path>")
        sys.exit(-1)
    
    user_id_arg = sys.argv[1]
    db_path_arg = sys.argv[2]
    analyze(user_id_arg, db_path_arg)
