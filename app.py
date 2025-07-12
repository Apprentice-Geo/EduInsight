from flask import Flask, render_template, request, redirect, url_for, jsonify
import os
import subprocess
import uuid
import sqlite3
from pyecharts import options as opts
from pyecharts.charts import Bar, Pie, Page
import time

# --- 配置 ---
# 填入Spark Driver的IP地址
SPARK_DRIVER_HOST = "192.168.30.93" 

# 确保这些路径存在
UPLOAD_FOLDER = '/tmp/spark_uploads'
DB_PATH = "/home/spark/teaching_analysis.db" # SQLite数据库文件路径
HDFS_JOB_BASE_PATH = "/user/spark/jobs"

# --- Flask应用初始化 ---
app = Flask(__name__)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- 路由定义 ---

@app.route('/')
def index():
    """主页，提供文件上传表单。"""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_and_run_spark():
    """处理文件上传并异步启动Spark任务。"""
    if 'logs_file' not in request.files or 'scores_file' not in request.files:
        return "错误：请确保两个文件都已选择！", 400

    logs_file = request.files['logs_file']
    scores_file = request.files['scores_file']
    
    job_id = str(uuid.uuid4())
    
    # 1. 保存上传的文件到本地临时目录
    local_logs_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{job_id}_logs.csv")
    local_scores_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{job_id}_scores.csv")
    logs_file.save(local_logs_path)
    scores_file.save(local_scores_path)

    # 2. 将本地文件上传到HDFS的专属任务目录
    hdfs_input_path = f"{HDFS_JOB_BASE_PATH}/{job_id}/input"
    try:
        subprocess.run(['hdfs', 'dfs', '-mkdir', '-p', hdfs_input_path], check=True)
        subprocess.run(['hdfs', 'dfs', '-put', local_logs_path, f"{hdfs_input_path}/action_logs.csv"], check=True)
        subprocess.run(['hdfs', 'dfs', '-put', local_scores_path, f"{hdfs_input_path}/quiz_scores.csv"], check=True)
    except subprocess.CalledProcessError as e:
        return f"上传文件到HDFS失败: {e}", 500

    # 3. 准备并异步启动spark-submit命令
    spark_submit_cmd = [
        "spark-submit", "--master", "yarn", "--deploy-mode", "client",
        "--conf", f"spark.driver.host={SPARK_DRIVER_HOST}",
        "AcademicWarning.py", job_id, DB_PATH
    ]
    print(f"Executing Spark command: {' '.join(spark_submit_cmd)}")
    subprocess.Popen(spark_submit_cmd)

    # 4. 重定向到等待页面
    return redirect(url_for('waiting_page', job_id=job_id))

@app.route('/waiting/<job_id>')
def waiting_page(job_id):
    """显示一个等待页面，它会用JavaScript轮询检查结果。"""
    return render_template('waiting.html', job_id=job_id)

@app.route('/api/status/<job_id>')
def check_status(job_id):
    """一个API端点，用于检查任务是否完成。"""
    table_name = f"job_{job_id.replace('-', '_')}"
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        # 检查对应的表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
        if cursor.fetchone():
            conn.close()
            return jsonify({"status": "completed"})
        else:
            conn.close()
            return jsonify({"status": "processing"})
    except Exception:
        return jsonify({"status": "processing"})


@app.route('/results/<job_id>')
def show_results(job_id):
    """查询结果并用Pyecharts渲染图表。"""
    table_name = f"job_{job_id.replace('-', '_')}"
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(f"SELECT student_id, score, warning_level, total_actions, is_procrastinator FROM {table_name} ORDER BY score DESC")
        rows = cursor.fetchall()
        conn.close()
    except Exception as e:
        return f"查询结果失败，任务可能仍在运行或已失败。错误: {e}"

    # --- 数据准备 ---
    student_ids = [row[0] for row in rows]
    scores = [row[1] for row in rows]
    warning_levels = [row[2] for row in rows]
    high_risk_students = [row for row in rows if row[2] == 'High Risk']
    
    # --- Pyecharts 绘图 ---
    
    # 1. 成绩分布柱状图
    bar = (
        Bar({"width": "100%", "height": "400px"})
        .add_xaxis(student_ids)
        .add_yaxis("学生成绩", scores)
        .set_global_opts(
            title_opts=opts.TitleOpts(title="学生成绩分布"),
            datazoom_opts=opts.DataZoomOpts(type_="inside"),
        )
    )

    # 2. 风险等级分布饼图
    level_counts = {"High Risk": 0, "Normal": 0}
    for level in warning_levels:
        level_counts[level] += 1
    
    pie_data = list(level_counts.items())
    pie = (
        Pie({"width": "100%", "height": "400px"})
        .add("", pie_data)
        .set_global_opts(title_opts=opts.TitleOpts(title="学生风险等级分布"))
        .set_series_opts(label_opts=opts.LabelOpts(formatter="{b}: {c}"))
    )

    # 使用Page布局来组合图表
    page = Page(layout=Page.SimplePageLayout)
    page.add(bar, pie)
    
    return render_template(
        'results.html', 
        charts_html=page.render_embed(),
        high_risk_students=high_risk_students,
        job_id=job_id
    )

if __name__ == '__main__':
    # 确保在局域网内可访问
    app.run(host='0.0.0.0', port=5000, debug=True)
