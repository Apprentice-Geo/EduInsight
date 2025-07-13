import sys
import sqlite3
import pandas
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, count, when, lit, avg, stddev, max as spark_max, min as spark_min, sum, abs
from pyspark.ml.feature import VectorAssembler, StandardScaler
from pyspark.ml.clustering import KMeans
from pyspark.ml.feature import PCA
from pyspark.ml.stat import Correlation
import numpy as np

def analyze(job_id, db_path):
    """
    Spark核心分析逻辑
    :param job_id: 本次任务的唯一ID
    :param db_path: SQLite数据库文件的绝对路径
    """
    spark = SparkSession.builder.appName(f"Academic Warning - {job_id}").getOrCreate()

    try:
        # 根据job_id构建HDFS输入路径
        input_path = f"hdfs://mycluster/user/spark/jobs/{job_id}/input"
        
        logs_df = spark.read.option("header", "true").csv(f"{input_path}/action_logs.csv")
        scores_df = spark.read.option("header", "true").option("inferSchema", "true").csv(f"{input_path}/quiz_scores.csv")

        # --- 增强特征工程 ---
        # 基础活动统计
        activity_counts = logs_df.groupBy("student_id").agg(count("*").alias("total_actions"))
        
        # 不同行为类型的统计
        action_type_stats = logs_df.groupBy("student_id", "action_type").count().groupBy("student_id").pivot("action_type").sum("count").na.fill(0)
        
        # 学习时间分布特征（假设有时间戳）
        time_features = logs_df.groupBy("student_id").agg(
            count("*").alias("session_count"),
            # 可以根据实际数据格式调整时间特征提取
        )
        
        # 拖延行为识别
        late_submissions = logs_df.filter(
            (col("action_type") == "submit_quiz") & (col("action_timestamp") > "2025-07-10")
        ).select("student_id").distinct().withColumn("is_procrastinator", lit(1))

        # --- 连接数据 ---
        # 逐步连接所有特征
        features_df = activity_counts.join(action_type_stats, "student_id", "left_outer")
        features_df = features_df.join(time_features, "student_id", "left_outer")
        features_df = features_df.join(late_submissions, "student_id", "left_outer").na.fill({"is_procrastinator": 0})
        final_data_df = features_df.join(scores_df, "student_id").na.fill(0)
        
        # --- 无监督学习分析 ---
        
        # 准备机器学习特征向量
        numeric_cols = [col_name for col_name, col_type in final_data_df.dtypes 
                       if col_type in ['int', 'bigint', 'float', 'double'] and col_name != 'student_id']
        
        # 特征向量化
        assembler = VectorAssembler(inputCols=numeric_cols, outputCol="features")
        feature_vector_df = assembler.transform(final_data_df)
        
        # 特征标准化
        scaler = StandardScaler(inputCol="features", outputCol="scaled_features", withStd=True, withMean=True)
        scaler_model = scaler.fit(feature_vector_df)
        scaled_df = scaler_model.transform(feature_vector_df)
        
        # 1. K-means聚类分析
        print("执行K-means聚类分析...")
        kmeans = KMeans(featuresCol="scaled_features", predictionCol="cluster", k=3, seed=42)
        kmeans_model = kmeans.fit(scaled_df)
        clustered_df = kmeans_model.transform(scaled_df)
        
        # 分析聚类结果
        cluster_summary = clustered_df.groupBy("cluster").agg(
            count("*").alias("cluster_size"),
            avg("score").alias("avg_score"),
            avg("total_actions").alias("avg_actions"),
            avg("is_procrastinator").alias("procrastination_rate")
        )
        print("聚类分析结果:")
        cluster_summary.show()
        
        # 2. PCA降维分析
        print("执行PCA主成分分析...")
        pca = PCA(k=3, inputCol="scaled_features", outputCol="pca_features")
        pca_model = pca.fit(scaled_df)
        pca_df = pca_model.transform(scaled_df)
        
        print(f"PCA解释方差比: {pca_model.explainedVariance.toArray()}")
        
        # 3. 异常检测（基于统计方法）
        print("执行异常检测...")
        # 计算每个特征的统计信息
        stats_df = final_data_df.select([col(c) for c in numeric_cols]).describe()
        
        # 使用Z-score方法检测异常
        anomaly_conditions = []
        for col_name in numeric_cols:
            if col_name in ['score', 'total_actions']:  # 主要关注这些特征
                mean_val = final_data_df.select(avg(col_name)).collect()[0][0]
                std_val = final_data_df.select(stddev(col_name)).collect()[0][0]
                if std_val and std_val > 0:
                    # Z-score > 2 视为异常
                    anomaly_conditions.append(
                        (abs(col(col_name) - mean_val) / std_val > 2).alias(f"{col_name}_anomaly")
                    )
        
        if anomaly_conditions:
            anomaly_df = final_data_df.select("student_id", *anomaly_conditions)
            # 统计每个学生的异常特征数量
            anomaly_col_names = [f"{col_name}_anomaly" for col_name in numeric_cols if col_name in ['score', 'total_actions']]
            # 使用reduce来正确组合多个when表达式
            from functools import reduce
            from operator import add
            anomaly_expressions = [when(col(col_name), 1).otherwise(0) for col_name in anomaly_col_names]
            anomaly_count_expr = reduce(add, anomaly_expressions) if anomaly_expressions else lit(0)
            anomaly_summary = anomaly_df.withColumn("anomaly_count", anomaly_count_expr)
            
            # 标记异常学生（有2个或以上异常特征）
            anomaly_students = anomaly_summary.filter(col("anomaly_count") >= 2)
            print(f"检测到 {anomaly_students.count()} 名异常学生")
        
        # 将聚类结果合并到最终数据
        final_analysis_df = clustered_df.select(
            "student_id", "score", "total_actions", "is_procrastinator", "cluster"
        )
        
        # --- 传统预警模型（增强版） ---
        # 结合聚类结果的智能预警
        enhanced_warning_df = final_analysis_df.withColumn(
            "warning_level",
            when((col("score") < 60) | (col("total_actions") < 2) | (col("is_procrastinator") == 1), "High Risk")
            .otherwise("Normal")
        ).withColumn(
            "cluster_risk_level",
            when(col("cluster") == 0, "Low Risk Cluster")
            .when(col("cluster") == 1, "Medium Risk Cluster")
            .otherwise("High Risk Cluster")
        )
        
        # 综合预警等级（结合传统规则和聚类结果）
        final_warning_df = enhanced_warning_df.withColumn(
            "comprehensive_warning",
            when(
                (col("warning_level") == "High Risk") | 
                (col("cluster_risk_level") == "High Risk Cluster"), 
                "High Risk"
            ).when(
                col("cluster_risk_level") == "Medium Risk Cluster", 
                "Medium Risk"
            ).otherwise("Low Risk")
        )
        
        print("=== 增强分析结果 ===")
        final_warning_df.show()
        
        # 显示各风险等级的学生分布
        risk_distribution = final_warning_df.groupBy("comprehensive_warning").count()
        print("综合风险等级分布:")
        risk_distribution.show()
        
        # 显示聚类与风险的关联
        cluster_risk_analysis = final_warning_df.groupBy("cluster", "comprehensive_warning").count()
        print("聚类与风险等级关联分析:")
        cluster_risk_analysis.show()

        # --- 将结果写入SQLite ---
        print(f"Writing enhanced results to SQLite DB at {db_path}")
        # 选择要保存的关键字段
        result_df = final_warning_df.select(
            "student_id", "score", "total_actions", "is_procrastinator", 
            "cluster", "warning_level", "cluster_risk_level", "comprehensive_warning"
        )
        # 使用Pandas作为桥梁将Spark DataFrame写入SQLite
        pandas_df = result_df.toPandas()
        
        conn = sqlite3.connect(db_path)
        table_name = f"job_{job_id.replace('-', '_')}"
        pandas_df.to_sql(name=table_name, con=conn, if_exists="replace", index=False)
        conn.close()
        
        print("Write to SQLite complete.")

    except Exception as e:
        print(f"An error occurred in Spark job {job_id}: {e}")
        # 实际项目中可以在这里记录错误日志
    finally:
        spark.stop()

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: AcademicWarning.py <job_id> <db_path>")
        sys.exit(-1)
    
    job_id_arg = sys.argv[1]
    db_path_arg = sys.argv[2]
    analyze(job_id_arg, db_path_arg)
