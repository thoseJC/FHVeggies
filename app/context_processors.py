from flask import session, g


def init_cart_context(app):
    @app.before_request
    def cart_context():
        # Get the cart from session, default to empty list
        cart = session.get('cart', [])

        # Calculate total items count from cart
        total_count = 0

        # Filter out any None or invalid items and count valid ones
        for item in cart:
            if item and isinstance(item, dict):  # Verify item is a valid dictionary
                quantity = item.get('quantity', 1)
                # Ensure quantity is a valid number
                try:
                    total_count += int(quantity)
                except (TypeError, ValueError):
                    continue

        # Set the count in Flask's g object for global template access
        g.cart_items_count = total_count


# Add this to your app initialization
def register_context_processors(app):
    init_cart_context(app)