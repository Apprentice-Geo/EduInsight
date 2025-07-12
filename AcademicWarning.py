import sys
import sqlite3
import pandas
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, count, when, lit

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

        # --- 特征工程 ---
        activity_counts = logs_df.groupBy("student_id").agg(count("*").alias("total_actions"))

        late_submissions = logs_df.filter(
            (col("action_type") == "submit_quiz") & (col("action_timestamp") > "2025-07-10")
        ).select("student_id").distinct().withColumn("is_procrastinator", lit(1))

        # --- 连接数据 ---
        features_df = activity_counts.join(late_submissions, "student_id", "left_outer").na.fill({"is_procrastinator": 0})
        final_data_df = features_df.join(scores_df, "student_id")
        
        # --- 预警模型 ---
        warning_df = final_data_df.withColumn(
            "warning_level",
            when((col("score") < 60) | (col("total_actions") < 2) | (col("is_procrastinator") == 1), "High Risk")
            .otherwise("Normal")
        )
        
        print("--- Analysis Result ---")
        warning_df.show()

        # --- 将结果写入SQLite ---
        print(f"Writing results to SQLite DB at {db_path}")
        # 使用Pandas作为桥梁将Spark DataFrame写入SQLite
        pandas_df = warning_df.toPandas()
        
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
