from functools import wraps
from flask import session, redirect, url_for, flash
from models.user import User

class AuthManager:
    """认证管理器"""
    
    def __init__(self, db_path=None):
        self.user_model = User(db_path)
    
    def login_user(self, username, password):
        """用户登录"""
        user = self.user_model.authenticate_user(username, password)
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            return True, user
        return False, None
    
    def logout_user(self):
        """用户登出"""
        session.clear()
    
    def register_user(self, username, email, password):
        """用户注册"""
        try:
            user_id = self.user_model.create_user(username, email, password)
            return True, user_id
        except ValueError as e:
            return False, str(e)
    
    def get_current_user(self):
        """获取当前登录用户"""
        if 'user_id' in session:
            return self.user_model.get_user_by_id(session['user_id'])
        return None
    
    def is_authenticated(self):
        """检查用户是否已登录"""
        return 'user_id' in session

def login_required(f):
    """登录装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('请先登录', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function
