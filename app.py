from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash
import os
import subprocess
import time
from pyecharts import options as opts
from pyecharts.charts import Bar, Pie, Page, Scatter
from pyecharts.commons.utils import JsCode

# 导入新的模块
from config import Config
from auth import AuthManager, login_required
from models.analysis import AnalysisResult
from utils.hdfs_helper import HDFSHelper
from utils.validators import validate_upload_files

# --- Flask应用初始化 ---
app = Flask(__name__)
app.secret_key = Config.SECRET_KEY
Config.init_app(app)

# 初始化管理器
auth_manager = AuthManager()
analysis_model = AnalysisResult()

# --- 路由定义 ---

@app.route('/')
@login_required
def index():
    """主页，提供文件上传表单"""
    current_user = auth_manager.get_current_user()
    return render_template('index.html', username=current_user['username'])

@app.route('/upload', methods=['POST'])
@login_required
def upload_and_run_spark():
    """处理文件上传并异步启动Spark任务"""
    # 验证上传的文件
    is_valid, error_message = validate_upload_files(request.files)
    if not is_valid:
        flash(error_message, 'error')
        return redirect(url_for('index'))

    logs_file = request.files['logs_file']
    scores_file = request.files['scores_file']

    # 使用当前登录用户的ID
    user_id = str(session['user_id'])
    username = session['username']
    
    # 清理该用户之前的分析结果（仅清理SQLite结果，保留HDFS历史数据）
    analysis_model.clear_user_results(user_id)
    print(f"Cleared previous analysis results for user {user_id} ({username}), keeping HDFS historical data")

    # 1. 保存上传的文件到本地临时目录
    local_logs_path = os.path.join(Config.UPLOAD_FOLDER, f"{user_id}_logs.csv")
    local_scores_path = os.path.join(Config.UPLOAD_FOLDER, f"{user_id}_scores.csv")
    logs_file.save(local_logs_path)
    scores_file.save(local_scores_path)

    # 2. 上传文件到HDFS（保留历史数据）
    hdfs_input_path = f"{Config.HDFS_JOB_BASE_PATH}/{user_id}/input/{time.time()}"
    try:
        HDFSHelper.upload_files_with_retry(local_logs_path, local_scores_path, hdfs_input_path)
        print(f"Successfully uploaded files to HDFS: {hdfs_input_path} (historical data preserved)")
    except Exception as e:
        flash(f"上传文件到HDFS失败: {e}。请联系管理员。", 'error')
        return redirect(url_for('index'))

    # 3. 启动Spark任务
    spark_submit_cmd = [
        "spark-submit", "--master", "yarn", "--deploy-mode", "client",
        "--conf", f"spark.driver.host={Config.SPARK_DRIVER_HOST}",
        "AcademicWarning.py", user_id, Config.DB_PATH
    ]
    print(f"Executing Spark command for user {username} (ID: {user_id}): {' '.join(spark_submit_cmd)}")
    subprocess.Popen(spark_submit_cmd)

    return redirect(url_for('waiting_page', user_id=user_id))

@app.route('/waiting/<user_id>')
@login_required
def waiting_page(user_id):
    """显示等待页面"""
    # 验证用户权限
    if str(session['user_id']) != user_id:
        flash('您只能查看自己的分析结果', 'error')
        return redirect(url_for('index'))
    
    current_user = auth_manager.get_current_user()
    return render_template('waiting.html', user_id=user_id, username=current_user['username'])

@app.route('/api/status/<user_id>')
@login_required
def check_status(user_id):
    """检查任务状态"""
    # 验证用户权限
    if str(session['user_id']) != user_id:
        return jsonify({"status": "error", "message": "权限不足"})
    
    if analysis_model.table_exists(user_id):
        return jsonify({"status": "completed"})
    else:
        return jsonify({"status": "processing"})

@app.route('/results/<user_id>')
@login_required
def show_results(user_id):
    """显示分析结果"""
    # 验证用户权限
    if str(session['user_id']) != user_id:
        flash('您只能查看自己的分析结果', 'error')
        return redirect(url_for('index'))
    
    # 获取分析结果
    results = analysis_model.get_user_results(user_id)
    if not results:
        flash('分析结果不存在，请重新上传文件进行分析', 'error')
        return redirect(url_for('index'))
    
    # 获取风险统计
    risk_stats = analysis_model.get_risk_statistics(user_id)

    # --- 数据准备（保留两位小数）---
    student_ids = [item['student_id'] for item in results]
    latest_scores = [round(float(item['latest_score']), 2) if item['latest_score'] is not None else 0.00 for item in results]
    historical_avg_scores = [round(float(item['historical_avg_score']), 2) if item['historical_avg_score'] is not None else 0.00 for item in results]
    score_trends = [round(float(item['score_trend']), 2) if item['score_trend'] is not None else 0.00 for item in results]
    clusters = [item['cluster'] for item in results]
    comprehensive_warnings = [item['comprehensive_warning'] for item in results]
    
    # 高风险学生（基于综合预警）
    high_risk_students = [item for item in results if item['comprehensive_warning'] == 'High Risk']
    medium_risk_students = [item for item in results if item['comprehensive_warning'] == 'Medium Risk']
    
    # --- Pyecharts 绘图 ---
    
    # 1. 成绩与趋势对比图
    bar = Bar({"width": "100%", "height": "400px"})
    bar.add_xaxis(student_ids)
    bar.add_yaxis("最近分数", latest_scores)
    bar.add_yaxis("历史平均分", historical_avg_scores)
    bar.set_global_opts(
        title_opts=opts.TitleOpts(title="学生分数与历史趋势对比"),
        datazoom_opts=opts.DataZoomOpts(type_="inside"),
        tooltip_opts=opts.TooltipOpts(
            trigger="axis",
            axis_pointer_type="cross",
            formatter="{b}<br/>{a0}: {c0}<br/>{a1}: {c1}"
        )
    )
    bar.set_series_opts(
        label_opts=opts.LabelOpts(
            is_show=True,
            position="top",
            formatter="{c}"
        )
    )

    # 2. 综合风险等级分布饼图
    pie_data = [(k, v) for k, v in risk_stats.items() if v > 0]
    pie = (
        Pie({"width": "100%", "height": "400px"})
        .add("", pie_data)
        .set_global_opts(title_opts=opts.TitleOpts(title="学生综合风险等级分布"))
        .set_series_opts(label_opts=opts.LabelOpts(formatter="{b}: {c}"))
    )
    
    # 3. 聚类散点图
    # 获取动态聚类映射
    cluster_names = analysis_model.get_cluster_mapping(user_id)
    
    # 准备散点图数据
    scatter_data = []
    for i, (score, actions, cluster) in enumerate(zip(latest_scores, [item['total_actions'] for item in results], clusters)):
        cluster_name = cluster_names.get(cluster, f"聚类{cluster}")
        scatter_data.append([score, actions, cluster_name, student_ids[i]])
    
    # 按聚类分组数据
    cluster_scatter_data = {}
    for data_point in scatter_data:
        cluster_name = data_point[2]
        if cluster_name not in cluster_scatter_data:
            cluster_scatter_data[cluster_name] = []
        cluster_scatter_data[cluster_name].append([data_point[0], data_point[1], data_point[3]])  # [score, actions, student_id]
    
    # 创建散点图
    scatter = Scatter({"width": "100%", "height": "400px"})
    
    # 为每个聚类添加数据系列
    colors = ["#2ca02c", "#ff7f0e", "#d62728"]  # 绿色、橙色、红色
    
    # 添加空的x轴数据以初始化散点图
    scatter.add_xaxis([])
    
    for i, (cluster_name, data) in enumerate(cluster_scatter_data.items()):
        scatter.add_yaxis(
            cluster_name,
            data,  # 直接传入[x, y]坐标点列表
            symbol_size=10,
            label_opts=opts.LabelOpts(is_show=False),  # 隐藏点旁边的数字标签
            itemstyle_opts=opts.ItemStyleOpts(color=colors[i % len(colors)])
        )
    
    scatter.set_global_opts(
        title_opts=opts.TitleOpts(title="学生学习行为聚类分析"),
        xaxis_opts=opts.AxisOpts(
            name="最近分数",
            name_location="middle",
            name_gap=30,
            type_="value"  # 设置为数值轴
        ),
        yaxis_opts=opts.AxisOpts(
            name="学习活动次数",
            name_location="middle",
            name_gap=40,
            type_="value"  # 设置为数值轴
        ),
        tooltip_opts=opts.TooltipOpts(
            formatter=JsCode("""
                function(params){
                    return params.seriesName + '<br/>' + '学生ID: ' + params.data[2] + '<br/>最近分数: ' + params.data[0] + '<br/>活动次数: ' + params.data[1];
                }
            """)
        ),
        legend_opts=opts.LegendOpts(pos_top="5%")
    )

    # 使用Page布局来组合图表
    page = Page(layout=Page.SimplePageLayout)
    page.add(bar, pie, scatter)
    
    current_user = auth_manager.get_current_user()
    return render_template(
        'results.html', 
        charts_html=page.render_embed(),
        high_risk_students=high_risk_students,
        medium_risk_students=medium_risk_students,
        all_students_data=results,
        total_students=len(results),
        user_id=user_id,
        username=current_user['username']
    )

@app.route('/student_details/<user_id>')
@login_required
def student_details(user_id):
    """显示学生详细信息页面"""
    # 验证用户权限
    if str(session['user_id']) != user_id:
        flash('您只能查看自己的分析结果', 'error')
        return redirect(url_for('index'))
    
    # 获取分析结果
    results = analysis_model.get_user_results(user_id)
    if not results:
        flash('分析结果不存在，请重新上传文件进行分析', 'error')
        return redirect(url_for('index'))
    
    # 分类学生
    high_risk_students = [item for item in results if item['comprehensive_warning'] == 'High Risk']
    medium_risk_students = [item for item in results if item['comprehensive_warning'] == 'Medium Risk']
    
    # 获取动态聚类映射
    cluster_names = analysis_model.get_cluster_mapping(user_id)
    
    current_user = auth_manager.get_current_user()
    return render_template(
        'student_details.html',
        high_risk_students=high_risk_students,
        medium_risk_students=medium_risk_students,
        all_students_data=results,
        total_students=len(results),
        user_id=user_id,
        username=current_user['username'],
        cluster_names=cluster_names
    )

# --- 认证相关路由 ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    """用户登录"""
    # 如果已经登录，直接跳转到主页
    if auth_manager.is_authenticated():
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('请输入用户名和密码', 'error')
            return render_template('login.html')
        
        success, user = auth_manager.login_user(username, password)
        if success:
            flash(f'欢迎回来，{user["username"]}！', 'success')
            return redirect(url_for('index'))
        else:
            flash('用户名或密码错误', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """用户注册"""
    # 如果已经登录，直接跳转到主页
    if auth_manager.is_authenticated():
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if not all([username, email, password, confirm_password]):
            flash('请填写所有字段', 'error')
            return render_template('register.html')
        
        if password != confirm_password:
            flash('两次输入的密码不一致', 'error')
            return render_template('register.html')
        
        success, result = auth_manager.register_user(username, email, password)
        if success:
            flash('注册成功！请登录', 'success')
            return redirect(url_for('login'))
        else:
            flash(result, 'error')
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    """用户登出"""
    auth_manager.logout_user()
    flash('已成功登出', 'info')
    return redirect(url_for('login'))

if __name__ == '__main__':
    # 确保在局域网内可访问
    app.run(host='0.0.0.0', port=5000, debug=True)
