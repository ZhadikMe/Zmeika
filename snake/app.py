from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash
from prometheus_client import Counter, generate_latest, CollectorRegistry, Gauge
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import os
from datetime import timedelta, datetime
import time
import threading
from functools import wraps

app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.config['SESSION_COOKIE_SECURE'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)

db = SQLAlchemy(app)
csrf = CSRFProtect(app)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            if request.path.startswith('/api/') or request.is_json:
                return jsonify({'status': 'error', 'message': 'Authentication required'}), 401
            flash('Для доступа к этой странице необходимо войти в систему', 'warning')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

ip_attempts = {}
ip_lock = threading.Lock()

def get_block_time(ip_address):
    with ip_lock:
        attempts = ip_attempts.get(ip_address, 0)
        
        if attempts == 0:
            block_time = 60
        elif attempts == 1:
            block_time = 300
        elif attempts == 2:
            block_time = 900
        else:
            block_time = 1800
        
        ip_attempts[ip_address] = attempts + 1
        threading.Timer(86400, lambda: reset_ip_attempts(ip_address)).start()
        return block_time

def reset_ip_attempts(ip_address):
    with ip_lock:
        if ip_address in ip_attempts:
            del ip_attempts[ip_address]

def get_dynamic_rate_limit():
    ip_address = request.remote_addr
    attempts = ip_attempts.get(ip_address, 0)
    
    if attempts == 0:
        return "10 per minute"
    elif attempts == 1:
        return "5 per 5 minutes"
    else:
        return "3 per 15 minutes"

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
    strategy="fixed-window"
)

registry = CollectorRegistry()
failed_logins = Counter('failed_logins_total', 'Total failed login attempts', ['username', 'ip_address'], registry=registry)
successful_logins = Counter('successful_logins_total', 'Total successful logins', ['username'], registry=registry)
score_saves = Counter('score_saves_total', 'Total score saves', ['username'], registry=registry)
invalid_scores = Counter('invalid_scores_total', 'Total invalid score attempts', registry=registry)
blocked_ips = Gauge('blocked_ips_total', 'Currently blocked IP addresses', registry=registry)
login_attempts_blocked = Counter('login_attempts_blocked_total', 'Total blocked login attempts', ['ip_address'], registry=registry)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    scores = db.relationship('Score', backref='user', lazy=True)
    is_blocked = db.Column(db.Boolean, default=False)
    blocked_until = db.Column(db.DateTime, nullable=True)
    failed_attempts = db.Column(db.Integer, default=0)
    last_failed_attempt = db.Column(db.DateTime, nullable=True)

class Score(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    value = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

with app.app_context():
    db.create_all()

@app.route('/health')
@limiter.exempt
def health_check():
    return {'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()}, 200

@app.route('/')
@limiter.exempt
def index():
    if 'username' in session:
        return render_template('index.html', username=session['username'])
    return redirect(url_for('login'))

def check_user_blocked(username):
    user = User.query.filter_by(username=username).first()
    if not user:
        return None
    
    if user.is_blocked and user.blocked_until:
        if datetime.utcnow() < user.blocked_until:
            remaining_seconds = (user.blocked_until - datetime.utcnow()).seconds
            return remaining_seconds
        else:
            user.is_blocked = False
            user.blocked_until = None
            user.failed_attempts = 0
            db.session.commit()
    
    return None

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit(get_dynamic_rate_limit)
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        ip_address = request.remote_addr

        user_block_seconds = check_user_blocked(username)
        if user_block_seconds:
            minutes = user_block_seconds // 60
            seconds = user_block_seconds % 60
            
            if minutes > 0:
                time_str = f"{minutes} минут"
                if seconds > 0:
                    time_str = f"{minutes} минут {seconds} секунд"
            else:
                time_str = f"{seconds} секунд"
            
            message = f'Аккаунт заблокирован. Попробуйте через {time_str}.'
            flash(message, 'danger')
            failed_logins.labels(username=username, ip_address=ip_address).inc()
            return render_template('login.html')

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password_hash, password):
            if user.failed_attempts > 0:
                user.failed_attempts = 0
                user.last_failed_attempt = None
                db.session.commit()
            
            session.permanent = True
            session['username'] = username
            successful_logins.labels(username=username).inc()
            flash('Вы успешно вошли в систему!', 'success')
            return redirect(url_for('index'))
        else:
            if user:
                user.failed_attempts += 1
                user.last_failed_attempt = datetime.utcnow()
                
                if user.failed_attempts >= 3:
                    time_window = 300
                    
                    if user.last_failed_attempt and \
                       (datetime.utcnow() - user.last_failed_attempt).seconds < time_window:
                        
                        if user.failed_attempts == 3:
                            block_minutes = 5
                        elif user.failed_attempts == 4:
                            block_minutes = 15
                        elif user.failed_attempts == 5:
                            block_minutes = 30
                        elif user.failed_attempts == 6:
                            block_minutes = 60
                        else:
                            block_minutes = 120
                        
                        user.is_blocked = True
                        user.blocked_until = datetime.utcnow() + timedelta(minutes=block_minutes)
                        flash(f'Аккаунт заблокирован на {block_minutes} минут из-за множества неудачных попыток входа.', 'danger')
                    else:
                        user.failed_attempts = 1
                
                db.session.commit()
            
            failed_logins.labels(username=username, ip_address=ip_address).inc()
            flash('Неверное имя пользователя или пароль', 'danger')

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
@limiter.limit(get_dynamic_rate_limit)
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        ip_address = request.remote_addr

        if len(username) < 3 or len(username) > 80:
            flash('Имя должно быть от 3 до 80 символов', 'danger')
            return redirect(url_for('register'))

        if len(password) < 6:
            flash('Пароль должен быть не менее 6 символов', 'danger')
            return redirect(url_for('register'))

        if User.query.filter_by(username=username).first():
            flash('Это имя уже занято', 'danger')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)
        new_user = User(username=username, password_hash=hashed_password)

        db.session.add(new_user)
        db.session.commit()

        flash('Регистрация прошла успешно!', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('login'))

@app.route('/save_score', methods=['POST'])
@csrf.exempt
@login_required 
def save_score():
    if 'username' not in session:
        return {'status': 'error', 'message': 'Not logged in'}, 401

    username = session['username']
    user = User.query.filter_by(username=username).first()

    if not user:
        return {'status': 'error', 'message': 'User not found'}, 404

    score_value = request.json.get('score')

    if not score_value or not isinstance(score_value, int):
        invalid_scores.inc()
        return {'status': 'error', 'message': 'Invalid score'}, 400

    if score_value < 0 or score_value > 999999:
        invalid_scores.inc()
        return {'status': 'error', 'message': 'Score out of range'}, 400

    new_score = Score(value=score_value, user_id=user.id)
    db.session.add(new_score)
    db.session.commit()

    score_saves.labels(username=username).inc()

    return {'status': 'success'}

@app.route('/leaderboard')
@login_required 
def leaderboard():
    top_scores = db.session.query(
        User.username,
        db.func.max(Score.value).label('max_score')
    ).join(Score).group_by(User.username).order_by(db.desc('max_score')).limit(10).all()

    ranked_scores = []
    for rank, (username, max_score) in enumerate(top_scores, start=1):
        ranked_scores.append({
            'rank': rank,
            'username': username,
            'max_score': max_score
        })

    return render_template('leaderboard.html', scores=ranked_scores)

@app.route('/metrics')
@limiter.exempt
def metrics():
    return generate_latest(registry), 200, {'Content-Type': 'text/plain'}

@app.errorhandler(400)
def handle_csrf_error(e):
    return {'status': 'error', 'message': 'CSRF token invalid'}, 400

@app.errorhandler(429)
def ratelimit_handler(e):
    ip_address = request.remote_addr
    login_attempts_blocked.labels(ip_address=ip_address).inc()
    
    block_time = get_block_time(ip_address)
    minutes = block_time // 60
    seconds = block_time % 60
    
    if minutes > 0:
        if seconds > 0:
            time_str = f"{minutes} минут {seconds} секунд"
        else:
            time_str = f"{minutes} минут"
    else:
        time_str = f"{seconds} секунд"
    
    flash(f'Слишком много попыток. Подождите {time_str}.', 'danger')
    
    if request.path == '/login':
        return render_template('login.html'), 429
    elif request.path == '/register':
        return render_template('register.html'), 429
    else:
        return redirect(url_for('login'))

if __name__ == '__main__':
    import os

    ssl_context = None
    if os.path.exists('localhost+2.pem') and os.path.exists('localhost+2-key.pem'):
        ssl_context = ('localhost+2.pem', 'localhost+2-key.pem')

    app.run(
        debug=False,
        host='0.0.0.0',
        port=5000,
        ssl_context=ssl_context,
        use_reloader=False
    )
