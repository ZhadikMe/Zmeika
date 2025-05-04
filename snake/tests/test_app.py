import pytest
from snake.app import app as flask_app
from snake.app import db

@pytest.fixture
def client():
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
    rv = client.get('/')
    assert rv.status_code == 302
    assert '/login' in rv.location

def test_homepage_authenticated(client):
    client.post('/register', data={
        'username': 'testuser',
        'password': 'testpass'
    })
    
    client.post('/login', data={
        'username': 'testuser',
        'password': 'testpass'
    })
    
    rv = client.get('/')
    assert rv.status_code == 200
    assert b'testuser' in rv.data


