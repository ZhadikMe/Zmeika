import pytest
from snake.app import app as flask_app
from snake.app import db

@pytest.fixture
def client():
    # Настраиваем тестовую базу данных
    flask_app.config['TESTING'] = True
    flask_app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    flask_app.config['WTF_CSRF_ENABLED'] = False
    
    with flask_app.test_client() as client:
        with flask_app.app_context():
            db.create_all()
        yield client
        with flask_app.app_context():
            db.drop_all()

def test_homepage_redirect(client):
    """Тест редиректа на login для неавторизованных пользователей"""
    rv = client.get('/')
    assert rv.status_code == 302
    assert '/login' in rv.location

def test_homepage_authenticated(client):
    """Тест главной страницы для авторизованного пользователя"""
    # Регистрация тестового пользователя
    client.post('/register', data={
        'username': 'testuser',
        'password': 'testpass'
    })
    
    # Аутентификация
    client.post('/login', data={
        'username': 'testuser',
        'password': 'testpass'
    })
    
    # Проверка главной страницы
    rv = client.get('/')
    assert rv.status_code == 200
    assert b'testuser' in rv.data
