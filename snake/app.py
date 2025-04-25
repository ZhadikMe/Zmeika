from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Модели базы данных
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    scores = db.relationship('Score', backref='user', lazy=True)

class Score(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    value = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# Создаем таблицы при первом запуске
with app.app_context():
    db.create_all()

@app.route('/')
def index():
    if 'username' in session:
        return render_template('index.html', username=session['username'])
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            session['username'] = username
            flash('Вы успешно вошли в систему!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Неверное имя пользователя или пароль', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if User.query.filter_by(username=username).first():
            flash('Это имя пользователя уже занято', 'danger')
            return redirect(url_for('register'))
        
        hashed_password = generate_password_hash(password)
        new_user = User(username=username, password_hash=hashed_password)
        
        db.session.add(new_user)
        db.session.commit()
        
        flash('Регистрация прошла успешно! Теперь вы можете войти.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('login'))

@app.route('/save_score', methods=['POST'])
def save_score():
    if 'username' not in session:
        return {'status': 'error', 'message': 'Not logged in'}, 401
    
    username = session['username']
    user = User.query.filter_by(username=username).first()
    
    if not user:
        return {'status': 'error', 'message': 'User not found'}, 404
    
    score_value = request.json.get('score')
    if not score_value:
        return {'status': 'error', 'message': 'Score is required'}, 400
    
    new_score = Score(value=score_value, user_id=user.id)
    db.session.add(new_score)
    db.session.commit()
    
    return {'status': 'success'}

@app.route('/leaderboard')
def leaderboard():
    top_scores = db.session.query(
        User.username, 
        db.func.max(Score.value).label('max_score')
    ).join(Score).group_by(User.username).order_by(db.desc('max_score')).limit(10).all()
    
    # Добавляем ранги
    ranked_scores = []
    for rank, (username, max_score) in enumerate(top_scores, start=1):
        ranked_scores.append({
            'rank': rank,
            'username': username,
            'max_score': max_score
        })
    
    return render_template('leaderboard.html', scores=ranked_scores)

if __name__ == '__main__':
    app.run(debug=True)