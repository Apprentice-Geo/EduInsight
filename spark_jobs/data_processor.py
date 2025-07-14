from pyspark.sql.functions import col, count, when, lit, avg, stddev, input_file_name, regexp_extract
from pyspark.sql.window import Window
from pyspark.sql.functions import avg as spark_avg, row_number

class DataProcessor:
    """数据处理类"""
    
    @staticmethod
    def load_data(spark, input_path):
        """加载HDFS数据"""
        logs_df = spark.read.option("header", "true").csv(f"{input_path}/action_logs.csv")
        scores_df = spark.read.option("header", "true").option("inferSchema", "true").csv(f"{input_path}/quiz_scores.csv")

        # 从文件路径中提取时间戳作为特征
        logs_df = logs_df.withColumn("upload_timestamp", regexp_extract(input_file_name(), r'input/(\d+\.\d+)/', 1))
        scores_df = scores_df.withColumn("upload_timestamp", regexp_extract(input_file_name(), r'input/(\d+\.\d+)/', 1))
        
        return logs_df, scores_df
    
    @staticmethod
    def extract_activity_features(logs_df):
        """提取活动特征"""
        # 基础活动统计
        activity_counts = logs_df.groupBy("student_id").agg(count("*").alias("total_actions"))
        
        # 不同行为类型的统计
        action_type_stats = logs_df.groupBy("student_id", "action_type").count().groupBy("student_id").pivot("action_type").sum("count").na.fill(0)
        
        # 学习时间分布特征
        time_features = logs_df.groupBy("student_id").agg(
            count("*").alias("session_count"),
        )
        
        return activity_counts, action_type_stats, time_features
    
    @staticmethod
    def identify_procrastinators(logs_df):
        """识别拖延者"""
        late_submissions = logs_df.filter(
            (col("action_type") == "submit_quiz") & (col("action_timestamp") > "2025-07-10")
        ).select("student_id").distinct().withColumn("is_procrastinator", lit(1))
        
        return late_submissions
    
    @staticmethod
    def extract_temporal_features(scores_df):
        """提取时序特征"""
        # 定义窗口，按学生ID分区，按时间戳排序
        student_window = Window.partitionBy("student_id").orderBy("upload_timestamp")

        # 计算历史平均分和最近一次的分数
        scores_with_history = scores_df.withColumn(
            "historical_avg_score", 
            spark_avg("score").over(student_window.rowsBetween(Window.unboundedPreceding, Window.currentRow - 1))
        ).withColumn(
            "latest_score",
            col("score")
        )

        # 获取每个学生的最新记录
        latest_scores = scores_with_history.withColumn(
            "row", 
            row_number().over(student_window.orderBy(col("upload_timestamp").desc()))
        ).filter(col("row") == 1).drop("row")

        # 计算分数趋势
        scores_with_trend = latest_scores.withColumn(
            "score_trend", 
            when(col("historical_avg_score").isNotNull(), col("latest_score") - col("historical_avg_score")).otherwise(0)
        )
        
        return scores_with_trend
    
    @staticmethod
    def merge_features(activity_counts, action_type_stats, time_features, late_submissions, scores_with_trend):
        """合并所有特征"""
        features_df = activity_counts.join(action_type_stats, "student_id", "left_outer")
        features_df = features_df.join(time_features, "student_id", "left_outer")
        features_df = features_df.join(late_submissions, "student_id", "left_outer").na.fill({"is_procrastinator": 0})
        final_data_df = features_df.join(scores_with_trend, "student_id").na.fill(0)
        
        return final_data_df
