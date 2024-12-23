import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config_settings import Config
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text

def test_connection():
    app = Flask(__name__)
    app.config.from_object(Config)

    db = SQLAlchemy(app)

    with app.app_context():
        try:
            db.engine.connect()
            print("Database connection successful!")
            # Use text() for the query
            result = db.session.execute(text('SELECT 1'))
            print("Query executed successfully!")

            # Check if alembic_version table exists
            result = db.session.execute(text("""
                SELECT TABLE_NAME
                FROM information_schema.TABLES
                WHERE TABLE_SCHEMA = 'JennyJC$FHVeggies'
                AND TABLE_NAME = 'alembic_version'
            """))
            if result.fetchone():
                print("alembic_version table exists")
                # Check content of alembic_version table
                version = db.session.execute(text('SELECT * FROM alembic_version')).fetchall()
                print(f"Current versions: {version}")
            else:
                print("alembic_version table does not exist")

        except Exception as e:
            print(f"Error occurred: {str(e)}")
        finally:
            db.session.close()

if __name__ == "__main__":
    test_connection()