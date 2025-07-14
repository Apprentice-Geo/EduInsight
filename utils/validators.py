from functools import wraps
from flask import session, redirect, url_for, flash

def login_required(f):
    """登录装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('请先登录', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def validate_file_extension(filename, allowed_extensions=None):
    """验证文件扩展名"""
    if allowed_extensions is None:
        allowed_extensions = {'csv'}
    
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

def validate_user_id(user_id):
    """验证用户ID格式"""
    if not user_id:
        return False, "用户ID不能为空"
    
    # 检查用户ID是否为数字
    try:
        int(user_id)
        return True, ""
    except ValueError:
        return False, "用户ID必须为数字"

def validate_upload_files(files):
    """验证上传的文件"""
    required_files = ['logs_file', 'scores_file']
    
    for file_key in required_files:
        if file_key not in files:
            return False, f"缺少文件: {file_key}"
        
        file = files[file_key]
        if file.filename == '':
            return False, f"未选择文件: {file_key}"
        
        if not validate_file_extension(file.filename):
            return False, f"文件格式错误，只支持CSV格式: {file.filename}"
    
    return True, ""
