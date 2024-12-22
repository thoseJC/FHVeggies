import os

class Config:
    # General Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess'  # Set a strong secret key for security

    # SQLAlchemy database configuration for MySQL
    DB_USERNAME = os.environ.get('DB_USERNAME') or 'root'
    DB_PASSWORD = os.environ.get('DB_PASSWORD') or ''
    DB_HOST = os.environ.get('DB_HOST') or 'localhost'
    DB_PORT = os.environ.get('DB_PORT') or '3306'
    DB_NAME = os.environ.get('DB_NAME') or 'fhv'

    # Construct the database URI for SQLAlchemy
    SQLALCHEMY_DATABASE_URI = f'mysql+pymysql://{DB_USERNAME}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False  # Disable track modifications to improve performance

    # Additional configuration options for Flask extensions
    WTF_CSRF_ENABLED = True  # Enable CSRF protection for forms

    # Logging or Debug mode (useful during development)
    DEBUG = True  # Set to False in production

# Optionally, you can define different configurations for development, testing, and production environments

class DevelopmentConfig(Config):
    DEBUG = True

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'  # Use in-memory SQLite for faster tests

class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
