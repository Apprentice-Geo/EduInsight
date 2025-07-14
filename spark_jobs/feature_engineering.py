from pyspark.ml.feature import VectorAssembler, StandardScaler

class FeatureEngineer:
    """特征工程类"""
    
    @staticmethod
    def prepare_ml_features(df):
        """准备机器学习特征"""
        # 选择数值型特征
        numeric_cols = [col_name for col_name, col_type in df.dtypes 
                       if col_type in ['int', 'bigint', 'float', 'double'] and col_name != 'student_id']
        
        # 特征向量化
        assembler = VectorAssembler(inputCols=numeric_cols, outputCol="features")
        feature_vector_df = assembler.transform(df)
        
        return feature_vector_df, numeric_cols
    
    @staticmethod
    def scale_features(df):
        """特征标准化"""
        scaler = StandardScaler(inputCol="features", outputCol="scaled_features", withStd=True, withMean=True)
        scaler_model = scaler.fit(df)
        scaled_df = scaler_model.transform(df)
        
        return scaled_df, scaler_model
