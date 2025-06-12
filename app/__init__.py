from flask import Flask
from app.auth import auth_bp
from app.user import user_bp
from app.admin import admin_bp

def create_app():
    app = Flask(__name__)
    app.secret_key = 'your-secret-key'

    app.register_blueprint(auth_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(admin_bp)

    return app
