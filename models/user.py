import sqlite3
import hashlib
import secrets
from config import Config
from utils.db_helper import db_helper

class User:
    """用户模型类"""
    
    def __init__(self, db_path=None):
        self.db_path = db_path or Config.DB_PATH
        self.init_database()
    
    def init_database(self):
        """初始化用户相关的数据库表"""
        conn = db_helper.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'teacher',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_sessions (
                session_id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def hash_password(self, password):
        """密码哈希"""
        salt = secrets.token_hex(16)
        password_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
        return salt + password_hash.hex()
    
    def verify_password(self, password, stored_hash):
        """验证密码"""
        salt = stored_hash[:32]
        stored_password_hash = stored_hash[32:]
        password_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
        return password_hash.hex() == stored_password_hash
    
    def create_user(self, username, email, password, role='teacher'):
        """创建新用户"""
        try:
            password_hash = self.hash_password(password)
            result = db_helper.execute_query(
                "INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
                (username, email, password_hash, role)
            )
            
            # 获取新创建用户的ID
            user_id = db_helper.execute_query(
                "SELECT last_insert_rowid();",
                fetch_one=True
            )[0]
            
            return user_id
        except sqlite3.IntegrityError as e:
            if "username" in str(e):
                raise ValueError("用户名已存在")
            elif "email" in str(e):
                raise ValueError("邮箱已存在")
            else:
                raise ValueError("创建用户失败")
        except Exception as e:
            raise ValueError(f"创建用户时发生错误: {e}")
    
    def authenticate_user(self, username, password):
        """用户认证"""
        user = db_helper.execute_query(
            "SELECT id, username, email, password_hash, role FROM users WHERE username = ? AND is_active = 1",
            (username,),
            fetch_one=True
        )
        
        if user and self.verify_password(password, user[3]):
            return {
                'id': user[0],
                'username': user[1],
                'email': user[2],
                'role': user[4]
            }
        return None
    
    def get_user_by_id(self, user_id):
        """根据ID获取用户信息"""
        user = db_helper.execute_query(
            "SELECT id, username, email, role FROM users WHERE id = ? AND is_active = 1",
            (user_id,),
            fetch_one=True
        )
        
        if user:
            return {
                'id': user[0],
                'username': user[1],
                'email': user[2],
                'role': user[3]
            }
        return None
