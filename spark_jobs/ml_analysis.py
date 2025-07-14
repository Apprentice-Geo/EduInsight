from pyspark.ml.clustering import KMeans
from pyspark.ml.feature import PCA
from pyspark.sql.functions import col, count, avg, stddev, abs, when, lit
from functools import reduce
from operator import add
from config import Config

class MLAnalyzer:
    """机器学习分析器"""
    
    @staticmethod
    def perform_kmeans_clustering(df, k=None):
        """执行K-means聚类"""
        k = k or Config.KMEANS_CLUSTERS
        
        print("执行K-means聚类分析...")
        kmeans = KMeans(featuresCol="scaled_features", predictionCol="cluster", k=k, seed=42)
        kmeans_model = kmeans.fit(df)
        clustered_df = kmeans_model.transform(df)
        
        # 分析聚类结果
        cluster_summary = clustered_df.groupBy("cluster").agg(
            count("*").alias("cluster_size"),
            avg("latest_score").alias("avg_score"),
            avg("total_actions").alias("avg_actions"),
            avg("is_procrastinator").alias("procrastination_rate")
        )
        print("聚类分析结果:")
        cluster_summary.show()
        
        # 动态分配聚类标签
        cluster_mapping = MLAnalyzer._assign_cluster_labels(cluster_summary)
        print(f"动态聚类标签映射: {cluster_mapping}")
        
        return clustered_df, kmeans_model, cluster_mapping
    
    @staticmethod
    def perform_pca_analysis(df, components=None):
        """执行PCA主成分分析"""
        components = components or Config.PCA_COMPONENTS
        
        print("执行PCA主成分分析...")
        pca = PCA(k=components, inputCol="scaled_features", outputCol="pca_features")
        pca_model = pca.fit(df)
        pca_df = pca_model.transform(df)
        
        print(f"PCA解释方差比: {pca_model.explainedVariance.toArray()}")
        
        return pca_df, pca_model
    
    @staticmethod
    def detect_anomalies(df, numeric_cols, threshold=None):
        """异常检测"""
        threshold = threshold or Config.ANOMALY_THRESHOLD
        
        print("执行异常检测...")
        
        # 使用Z-score方法检测异常
        anomaly_conditions = []
        for col_name in numeric_cols:
            if col_name in ['latest_score', 'total_actions']:  # 主要关注这些特征
                mean_val = df.select(avg(col_name)).collect()[0][0]
                std_val = df.select(stddev(col_name)).collect()[0][0]
                if std_val and std_val > 0:
                    # Z-score > threshold 视为异常
                    anomaly_conditions.append(
                        (abs(col(col_name) - mean_val) / std_val > threshold).alias(f"{col_name}_anomaly")
                    )
        
        if anomaly_conditions:
            anomaly_df = df.select("student_id", *anomaly_conditions)
            # 统计每个学生的异常特征数量
            anomaly_col_names = [f"{col_name}_anomaly" for col_name in numeric_cols if col_name in ['latest_score', 'total_actions']]
            
            anomaly_expressions = [when(col(col_name), 1).otherwise(0) for col_name in anomaly_col_names]
            anomaly_count_expr = reduce(add, anomaly_expressions) if anomaly_expressions else lit(0)
            anomaly_summary = anomaly_df.withColumn("anomaly_count", anomaly_count_expr)
            
            # 标记异常学生（有2个或以上异常特征）
            anomaly_students = anomaly_summary.filter(col("anomaly_count") >= 2)
            print(f"检测到 {anomaly_students.count()} 名异常学生")
            
            return anomaly_students
        
        return None
    
    @staticmethod
    def generate_warnings(df):
        """生成预警信息"""
        # 传统预警模型
        enhanced_warning_df = df.withColumn(
            "warning_level",
            when((col("latest_score") < 60) | (col("total_actions") < 2) | (col("is_procrastinator") == 1) | (col("score_trend") < -10), "High Risk")
            .when((col("score_trend") < -5), "Medium Risk")
            .otherwise("Normal")
        ).withColumn(
            "cluster_risk_level",
            when(col("cluster") == 0, "Low Risk Cluster")
            .when(col("cluster") == 1, "Medium Risk Cluster")
            .otherwise("High Risk Cluster")
        )
        
        # 综合预警等级
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
        
        return final_warning_df
    
    @staticmethod
    def _assign_cluster_labels(cluster_summary):
        """根据聚类特征动态分配有意义的标签"""
        # 收集聚类统计数据
        cluster_stats = cluster_summary.collect()
        
        # 计算综合评分：平均分数权重0.6 + 活动次数权重0.3 - 拖延率权重0.1
        cluster_scores = []
        for row in cluster_stats:
            cluster_id = row['cluster']
            avg_score = row['avg_score'] or 0
            avg_actions = row['avg_actions'] or 0
            procrastination_rate = row['procrastination_rate'] or 0
            
            # 标准化分数（假设分数0-100，活动次数0-30）
            normalized_score = avg_score / 100.0
            normalized_actions = min(avg_actions / 30.0, 1.0)
            
            # 综合评分
            composite_score = (normalized_score * 0.6 + 
                             normalized_actions * 0.3 - 
                             procrastination_rate * 0.1)
            
            cluster_scores.append((cluster_id, composite_score, avg_score, avg_actions))
        
        # 按综合评分排序
        cluster_scores.sort(key=lambda x: x[1], reverse=True)
        
        # 分配标签
        cluster_mapping = {}
        labels = ["优秀学习者", "普通学习者", "需要关注学习者"]
        
        for i, (cluster_id, score, avg_score, avg_actions) in enumerate(cluster_scores):
            if i < len(labels):
                cluster_mapping[cluster_id] = labels[i]
                print(f"聚类 {cluster_id}: {labels[i]} (综合评分: {score:.3f}, 平均分: {avg_score:.1f}, 平均活动: {avg_actions:.1f})")
            else:
                cluster_mapping[cluster_id] = f"聚类{cluster_id}"
        
        return cluster_mapping
