from flask import Flask
from config_settings import Config
from .commands import seed_items, update_total_price
from .context_processors import init_cart_context
from .extensions import db, migrate, login_manager
from .commands import create_test_users, seed_items, create_staff_user
from .commands import seed_premade_boxes



# Import all models here to ensure they are registered with SQLAlchemy
from .models import (
    Customer,
    Staff,
    Item,
    PreMadeBox,
    PreMadeBoxItem,
    Order,
    OrderLine,
    Payment
)

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    from .commands import create_test_users
    app.cli.add_command(create_test_users)
    app.cli.add_command(seed_items)
    app.cli.add_command(seed_premade_boxes)
    app.cli.add_command(update_total_price)

    # Register blueprints
    from .routes import auth_bp, shop_bp, staff_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(shop_bp, url_prefix='/shop')
    app.register_blueprint(staff_bp, url_prefix='/staff')

    # Import commands and register them
    app.cli.add_command(create_staff_user)

    init_cart_context(app)

    return app


# User loader for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    user = Customer.query.get(int(user_id))
    if not user:
        user = Staff.query.get(int(user_id))
    return user