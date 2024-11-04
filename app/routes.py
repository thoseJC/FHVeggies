import requests
from flask import Blueprint, render_template, redirect, url_for, flash, request, session, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from .models import Item, PreMadeBox, Order, OrderLine, PrivateCustomer, CorporateCustomer, Staff, Customer, Payment
from .forms import LoginForm
from .extensions import db
from .models import Item, PreMadeBox
import uuid, math
from datetime import datetime, timedelta
from sqlalchemy import func, desc
import json


staff_bp = Blueprint('staff', __name__)

# Define the 'auth' blueprint for authentication-related routes
auth_bp = Blueprint('auth', __name__)
shop_bp = Blueprint('shop', __name__)

@auth_bp.route('/')
def home():
    # Redirect to the login page as the root route
    return redirect(url_for('auth.login'))

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = None
        if form.user_type.data == "customer":
            user = Customer.query.filter_by(username=form.username.data).first()
        elif form.user_type.data == "staff":
            user = Staff.query.filter_by(username=form.username.data).first()
        else:
            flash('Invalid user type selected.')
            return redirect(url_for('auth.login'))

        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password')
            return redirect(url_for('auth.login'))

        login_user(user)
        # Simplified redirection logic based on user type
        if isinstance(user, Customer):
            return redirect(url_for('auth.customer_dashboard'))
        elif isinstance(user, Staff):
            return redirect(url_for('staff.staff_dashboard'))
        else:
            flash('User type not recognized.')
            return redirect(url_for('auth.login'))

    return render_template('login.html', title='Sign In', form=form)


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash("You have been logged out.")
    return redirect(url_for('auth.login'))


@auth_bp.route('/customer/dashboard')
@login_required
def customer_dashboard():
    if current_user.role != 'customer':
        flash("Unauthorized access!")
        return redirect(url_for('auth.login'))

    # Get current order (pending payment)
    current_order = Order.query.filter_by(
        customer_id=current_user.id,
        payment_status='Pending'
    ).order_by(Order.created_at.desc()).first()

    # Get order history (excluding current pending order)
    previous_orders = Order.query.filter_by(
        customer_id=current_user.id
    ).filter(
        Order.payment_status != 'Pending'
    ).order_by(Order.created_at.desc()).limit(5).all()  # Limiting to last 5 orders

    return render_template(
        'customer_dashboard.html',
        current_order=current_order,
        previous_orders=previous_orders
    )


@shop_bp.route('/', methods=['GET', 'POST'])
def shop():
    # Get category and filter_type parameters from the query string
    category = request.args.get('category', 'all')
    filter_type = request.args.get('filter', 'all')

    # Determine which items to query based on category and filter_type
    if filter_type == 'premade_box':
        # Query only premade boxes with specified names
        items = Item.query.filter(Item.name.in_(['Box A', 'Box B', 'Box C', 'Custom Premade Box'])).all()
    else:
        # Query items by category and availability if a specific category is selected
        if category != 'all':
            items = Item.query.filter_by(category=category, available=True).all()
        else:
            items = Item.query.filter_by(available=True).all()

    # Query all premade boxes (if you want to display them separately)
    premade_boxes = PreMadeBox.query.all()

    # Pass items, premade boxes, category, and filter_type to the template
    return render_template(
        'shop.html',
        items=items,
        premade_boxes=premade_boxes,
        category=category,
        filter_type=filter_type
    )


@shop_bp.route('/customize_box/<int:box_id>', methods=['GET'])
@login_required
def customize_box(box_id):
    # Get all available items for selection
    available_items = Item.query.filter_by(available=True).all()

    return render_template(
        'customize_box.html',
        available_items=available_items,
        box_id=box_id
    )


@shop_bp.route('/add_to_cart', methods=['POST'])
@login_required
def add_to_cart():
    try:
        cart = session.get('cart', [])
        cart_item = None

        if request.form.get('item_type') == 'premade_box':
            cart_item = {
                'cart_item_id': str(uuid.uuid4()),
                'type': 'premade_box',
                'id': request.form.get('box_id'),
                'box_size': request.form.get('box_size'),
                'selected_items': request.form.get('selected_items'),
                'total_price': float(request.form.get('total_price', 0))
            }
        else:
            item_id = request.form.get('item_id')
            quantity = int(request.form.get('quantity', 1))
            cart_item = {
                'cart_item_id': str(uuid.uuid4()),
                'id': item_id,
                'type': 'regular',
                'quantity': quantity,
                'unit_type': request.form.get('unit_type')
            }

        if cart_item:
            cart.append(cart_item)
            session['cart'] = cart
            flash('Item added to cart successfully!', 'success')

        return redirect(url_for('shop.shop'))

    except Exception as e:
        flash(f'Error adding item to cart: {str(e)}', 'danger')
        return redirect(url_for('shop.shop'))


@shop_bp.route('/make_installment_payment/<int:order_id>', methods=['POST'])
@login_required
def make_installment_payment(order_id):  # Add order_id parameter here
    order = Order.query.get_or_404(order_id)
    installment_details = session.get('installment_details', {})

    if not installment_details:
        flash('No installment details found.', 'error')
        return redirect(url_for('shop.order_details', order_id=order_id))

    # Get the next installment number
    next_installment = Payment.query.filter_by(order_id=order.id).count() + 1
    total_installments = installment_details['installments']

    if next_installment > total_installments:
        flash('All installments have been paid.', 'info')
        return redirect(url_for('shop.order_details', order_id=order_id))

    payment = Payment(
        order=order,
        payment_method='account',
        amount=installment_details['amount_per_installment'],
        installment_number=next_installment
    )

    if payment.process_payment():
        try:
            db.session.add(payment)
            current_user.balance += payment.amount
            db.session.commit()

            if next_installment == total_installments:
                order.payment_status = 'Paid'
                db.session.commit()
                flash('Final installment paid successfully!', 'success')
            else:
                flash(f'Installment {next_installment} paid successfully!', 'success')

        except Exception as e:
            db.session.rollback()
            flash(f'Error processing payment: {str(e)}', 'error')
    else:
        flash('Payment processing failed.', 'error')

    return redirect(url_for('shop.order_details', order_id=order_id))


@shop_bp.route('/remove_from_cart/<cart_item_id>', methods=['GET'])
@login_required
def remove_from_cart(cart_item_id):
    if not cart_item_id:
        flash('Invalid request: missing item identifier.', 'danger')
        return redirect(url_for('shop.checkout'))

    # Retrieve the cart from the session
    cart = session.get('cart', [])

    # Filter out None values and ensure all items are dictionaries
    cart = [item for item in cart if item is not None and isinstance(item, dict)]

    # Remove the item with the matching cart_item_id
    updated_cart = []
    for item in cart:
        if isinstance(item, dict) and item.get('cart_item_id') != cart_item_id:
            updated_cart.append(item)

    # Update the session with the new cart
    session['cart'] = updated_cart

    flash('Item removed from your cart.', 'success')
    return redirect(url_for('shop.checkout'))


# View Current Order Details Route
@shop_bp.route('/current_order')
@login_required
def current_order():
    order = Order.query.filter_by(customer=current_user, payment_status='Pending').first()
    if not order:
        flash("No current order found.", "info")
        return redirect(url_for('shop.shop'))
    return render_template('current_order.html', order=order)


# Haversine function to calculate distance between two coordinates
def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Earth's radius in km
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    return R * c

# Function to get coordinates from an address using Nominatim
def get_coordinates(address):
    url = f"https://nominatim.openstreetmap.org/search?q={address}&format=json&limit=1"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if data:
            return float(data[0]['lat']), float(data[0]['lon'])
    return None, None


@shop_bp.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    cart = session.get('cart', [])
    if not cart:
        flash('Your cart is empty', 'warning')
        return redirect(url_for('shop.shop'))

    try:
        subtotal = 0

        # Get all item IDs from the cart (both regular items and premade box items)
        item_ids = []
        for cart_item in cart:
            if cart_item.get('type') != 'premade_box':
                item_ids.append(cart_item.get('id'))

        # Fetch all regular items at once and create a dictionary
        items = {}
        if item_ids:
            db_items = Item.query.filter(Item.id.in_(item_ids)).all()
            items = {str(item.id): item for item in db_items}  # Convert ID to string for comparison

        # Fetch all premade boxes at once if needed
        box_ids = [item.get('id') for item in cart if item.get('type') == 'premade_box']
        premade_boxes = {}
        if box_ids:
            db_boxes = PreMadeBox.query.filter(PreMadeBox.id.in_(box_ids)).all()
            premade_boxes = {str(box.id): box for box in db_boxes}  # Convert ID to string for comparison

        # Calculate subtotal
        for cart_item in cart:
            if isinstance(cart_item, dict):
                if cart_item.get('type') == 'premade_box':
                    box_size = cart_item.get('box_size')
                    box_fees = {'small': 1, 'medium': 2, 'large': 3}
                    box_fee = box_fees.get(box_size, 0)

                    # Calculate items total
                    selected_items = cart_item.get('selected_items', {})
                    if isinstance(selected_items, str):
                        selected_items = json.loads(selected_items)

                    items_total = sum(
                        float(item.get('price', 0)) * int(item.get('quantity', 0))
                        for item in selected_items.values()
                    )

                    subtotal += items_total + box_fee
                else:
                    item_id = str(cart_item.get('id'))  # Convert to string for dictionary lookup
                    quantity = int(cart_item.get('quantity', 0))

                    if item_id in items:
                        item = items[item_id]
                        subtotal += item.price_per_unit * quantity

        # Calculate discount
        discount = subtotal * 0.1 if isinstance(current_user, CorporateCustomer) else 0

        print("Session order_details:", session.get('order_details'))
        print("Cart contents:", session.get('cart'))

        return render_template(
            'checkout.html',
            cart=cart,
            items=items,
            premade_boxes=premade_boxes,
            subtotal=subtotal,
            discount=discount,
            delivery_fee=0,
            total=subtotal - discount
        )

    except Exception as e:
        print(f"Error in checkout: {str(e)}")  # For debugging
        flash('An error occurred during checkout. Please try again.', 'danger')
        return redirect(url_for('shop.shop'))


@shop_bp.route('/place_order', methods=['POST'])
@login_required
def place_order():
    cart = session.get('cart', [])
    if not cart:
        flash('Your cart is empty.', 'error')
        return redirect(url_for('shop.checkout'))

    # Extract delivery details from the form
    delivery_option = request.form.get('delivery_option')
    street_address = request.form.get('street_address') if delivery_option == 'delivery' else None
    city = request.form.get('city') if delivery_option == 'delivery' else None
    postal_code = request.form.get('postal_code') if delivery_option == 'delivery' else None
    delivery_address = f"{street_address}, {city}, {postal_code}" if street_address and city and postal_code else None

    # Calculate delivery distance if delivery option is selected
    if delivery_option == 'delivery':
        origin_lat, origin_lon = -43.6409, 172.4691  # Coordinates of Lincoln University
        dest_lat, dest_lon = get_coordinates(delivery_address)
        if dest_lat and dest_lon:
            distance = haversine(origin_lat, origin_lon, dest_lat, dest_lon)
            if distance > 20:
                flash('Delivery is only available within a 20 km radius.', 'danger')
                return redirect(url_for('shop.checkout'))
        else:
            flash('Unable to determine the distance for the provided address. Please check your address.', 'danger')
            return redirect(url_for('shop.checkout'))

    # Recalculate total from cart items
    calculated_subtotal = 0
    for cart_item in cart:
        if cart_item.get('type') == 'regular':
            item = Item.query.get(cart_item.get('id'))
            if item:
                quantity = cart_item.get('quantity', 1)
                calculated_subtotal += item.price_per_unit * quantity
        elif cart_item.get('type') == 'premade_box':
            box = PreMadeBox.query.get(cart_item.get('id'))
            if box:
                quantity = cart_item.get('quantity', 1)
                calculated_subtotal += box.calculate_price() * quantity

    # Use calculated values instead of form/session values
    subtotal = calculated_subtotal
    discount = float(request.form.get('discount', 0))
    delivery_fee = 10 if delivery_option == 'delivery' else 0
    box_fee = session.get('custom_box_details', {}).get('box_fee', 0)
    total = subtotal - discount + delivery_fee + box_fee

    order = Order(
        customer_id=current_user.id,
        subtotal=subtotal,
        discount=discount,
        delivery_fee=delivery_fee,
        total_price=total,
        delivery=True if delivery_option == 'delivery' else False,
        delivery_address=delivery_address,
        payment_status='Pending'
    )

    # Add items to order (including customized boxes)
    if 'custom_box_details' in session:
        custom_box_details = session.pop('custom_box_details')
        for item_id, quantity in custom_box_details['selected_items'].items():
            item = Item.query.get(item_id)
            if item:
                # Create OrderLine without total_price parameter
                order_line = OrderLine(
                    item_id=item.id,
                    quantity=quantity
                )
                order.items.append(order_line)

    for cart_item in cart:
        item_id = cart_item.get('id')
        quantity = cart_item.get('quantity', 1)
        if cart_item.get('type') == 'premade_box':
            box = PreMadeBox.query.get(item_id)
            if box:
                for box_item in box.items:
                    # Create OrderLine without total_price parameter
                    order_line = OrderLine(
                        item_id=box_item.item_id,
                        quantity=box_item.quantity * quantity
                    )
                    order.items.append(order_line)
        else:
            item = Item.query.get(item_id)
            if item:
                # Create OrderLine without total_price parameter
                order_line = OrderLine(
                    item_id=item.id,
                    quantity=quantity
                )
                order.items.append(order_line)

    try:
        db.session.add(order)
        db.session.commit()

        # Store the correct total in session before clearing cart
        session['order_details'] = {
            'subtotal': subtotal,
            'discount': discount,
            'delivery_fee': delivery_fee,
            'total': total
        }

        session.pop('cart', None)  # Clear cart after successful order placement

        flash('Order placed successfully! Please proceed to payment.', 'success')
        return redirect(url_for('shop.make_payment', order_id=order.id))

    except Exception as e:
        db.session.rollback()
        flash(f'Error saving order: {str(e)}', 'error')
        return redirect(url_for('shop.checkout'))


@shop_bp.route('/store_order_details', methods=['POST'])
@login_required
def store_order_details():
    data = request.get_json()
    print("Received order details:", data)  # Debug print

    # Verify the calculations
    cart = session.get('cart', [])
    calculated_total = 0
    for item in cart:
        if item.get('type') == 'regular':
            db_item = Item.query.get(item['id'])
            if db_item:
                calculated_total += db_item.price_per_unit * item['quantity']

    print("Calculated total from cart:", calculated_total)  # Debug print

    # Only store if the totals match
    if abs(calculated_total - float(data.get('total', 0))) < 0.01:
        session['order_details'] = data
    else:
        # Use calculated values instead
        data['subtotal'] = calculated_total
        data['total'] = calculated_total
        session['order_details'] = data

    return jsonify({'success': True})


# New Payment Route
@shop_bp.route('/make_payment/<int:order_id>', methods=['GET', 'POST'])
@login_required
def make_payment(order_id):
    order = Order.query.get_or_404(order_id)

    if not order:
        flash('Order not found.', 'error')
        return redirect(url_for('shop.shop'))

    if order.payment_status == 'Paid':
        flash('This order has already been paid for.', 'warning')
        return redirect(url_for('shop.customer_orders'))

    if request.method == 'POST':
        payment_method = request.form.get('payment_method')

        try:
            if payment_method in ['credit_card', 'debit_card']:
                # Handle card payment
                card_number = request.form.get('card_number')
                expiry_date = request.form.get('expiry_date')
                cvv = request.form.get('cvv')

                if not all([card_number, expiry_date, cvv]):
                    flash('Please fill out all card details.', 'danger')
                    return redirect(url_for('shop.make_payment', order_id=order.id))

                # Validate card number (remove spaces and check length)
                card_number = card_number.replace(' ', '')
                if len(card_number) != 16 or not card_number.isdigit():
                    flash('Invalid card number.', 'danger')
                    return redirect(url_for('shop.make_payment', order_id=order.id))

                # Create single card payment
                payment = Payment(
                    order_id=order.id,
                    payment_method=payment_method,
                    amount=order.total_price,
                    status='pending'
                )

                if payment.process_payment():
                    db.session.add(payment)
                    order.payment_status = 'Paid'
                    db.session.commit()
                    flash('Payment processed successfully!', 'success')
                    return redirect(url_for('shop.customer_orders'))

            elif payment_method == 'account':
                # Handle account payment with installments
                installments = int(request.form.get('installments', 1))
                amount_per_installment = order.total_price / installments

                # Validate against customer limits
                if isinstance(current_user, PrivateCustomer):
                    if (current_user.balance + amount_per_installment) > 100:
                        flash('This payment would exceed your account limit.', 'danger')
                        return redirect(url_for('shop.make_payment', order_id=order.id))
                elif isinstance(current_user, CorporateCustomer):
                    if (current_user.balance + amount_per_installment) > current_user.credit_limit:
                        flash('This payment would exceed your credit limit.', 'danger')
                        return redirect(url_for('shop.make_payment', order_id=order.id))

                # Create first installment payment
                payment = Payment(
                    order_id=order.id,
                    payment_method='account',
                    amount=amount_per_installment,
                    installment_number=1,
                    status='pending'
                )

                if payment.process_payment():
                    db.session.add(payment)
                    current_user.balance += amount_per_installment

                    if installments == 1:
                        order.payment_status = 'Paid'
                    else:
                        order.payment_status = 'Partial'
                        # Store installment details in session for future payments
                        session['installment_details'] = {
                            'installments': installments,
                            'amount_per_installment': amount_per_installment,
                            'paid_installments': 1
                        }

                    db.session.commit()
                    flash(f'First installment processed successfully!', 'success')
                    return redirect(url_for('shop.customer_orders'))

            else:
                flash('Invalid payment method selected.', 'danger')
                return redirect(url_for('shop.make_payment', order_id=order.id))

        except Exception as e:
            db.session.rollback()
            flash(f'Error processing payment: {str(e)}', 'danger')
            return redirect(url_for('shop.make_payment', order_id=order.id))

    return render_template(
        'make_payment.html',
        order=order,
        payment_successful=False
    )

@shop_bp.route('/customer_orders', methods=['GET'])
@login_required
def customer_orders():
    """Display all orders for the logged-in customer."""
    orders = Order.query.filter_by(customer_id=current_user.id).order_by(Order.created_at.desc()).all()

    if not orders:
        flash('You have no orders.', 'info')

    return render_template('customer_orders.html', orders=orders)


@shop_bp.route('/order_details/<int:order_id>')
@login_required
def order_details(order_id):
    """Display detailed information for a specific order."""
    order = Order.query.get_or_404(order_id)

    # Ensure the order belongs to the current user
    if order.customer_id != current_user.id:
        flash("Unauthorized access to order details", "danger")
        return redirect(url_for('shop.customer_orders'))

    order_lines = order.items  # Assuming `order.items` gives a list of related order lines

    return render_template('order_details.html', order=order, order_lines=order_lines)


@shop_bp.route('/cancel_order/<int:order_id>', methods=['POST'])
@login_required
def cancel_order(order_id):
    order = Order.query.get_or_404(order_id)

    # Check if the current user is authorized to cancel this order
    if order.customer_id != current_user.id:
        flash("Unauthorized action.", "danger")
        return redirect(url_for('shop.customer_orders'))

    # Check if the order can be canceled (only if it has not been fulfilled)
    if order.payment_status == 'Pending' or 'Paid':
        try:
            # Remove the order and its associated order lines
            OrderLine.query.filter_by(order_id=order.id).delete()
            db.session.delete(order)
            db.session.commit()
            flash("Order canceled successfully.", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Error canceling order: {str(e)}", "error")
    else:
        flash("Order cannot be canceled as it has already been fulfilled or paid.", "danger")

    return redirect(url_for('shop.customer_orders'))


@shop_bp.route('/profile', methods=['GET'])
@login_required
def profile():
    """Display the current logged-in customer's profile details."""
    if current_user.role != 'customer':
        flash("Unauthorized access!", "danger")
        return redirect(url_for('auth.login'))

    # Fetch customer-specific details
    customer_type = "Private Customer" if current_user.customer_type == 'private' else "Corporate Customer"

    return render_template('profile.html', customer=current_user, customer_type=customer_type)


@staff_bp.before_request
@login_required
def restrict_to_staff():
    if not isinstance(current_user, Staff):
        flash("Unauthorized access!")
        return redirect(url_for('auth.login'))


@staff_bp.route('/dashboard', methods=['GET'])
@login_required
def staff_dashboard():
    # Ensure the user is a staff member
    if not isinstance(current_user, Staff):
        flash("Unauthorized access!", "danger")
        return redirect(url_for('auth.login'))

    # View all vegetables and premade boxes
    items = Item.query.all()
    premade_boxes = PreMadeBox.query.all()

    # View all current and previous orders
    current_orders = Order.query.filter(Order.status == 'Pending').all()
    previous_orders = Order.query.filter(Order.status != 'Pending').all()

    # View all customers
    customers = Customer.query.all()

    # Most popular items with item name and order frequency
    popular_items = db.session.query(
        Item.id, Item.name, func.count(OrderLine.item_id).label('count')
    ).join(OrderLine).group_by(Item.id, Item.name).order_by(desc('count')).limit(5).all()

    # Aggregate sales for week, month, and year
    today = datetime.today()
    start_of_week = today - timedelta(days=today.weekday())
    start_of_month = today.replace(day=1)
    start_of_year = today.replace(month=1, day=1)

    weekly_sales = db.session.query(func.sum(Order.total_price)).filter(Order.created_at >= start_of_week).scalar() or 0
    monthly_sales = db.session.query(func.sum(Order.total_price)).filter(Order.created_at >= start_of_month).scalar() or 0
    yearly_sales = db.session.query(func.sum(Order.total_price)).filter(Order.created_at >= start_of_year).scalar() or 0

    return render_template(
        'staff_dashboard.html',
        items=items,
        premade_boxes=premade_boxes,
        current_orders=current_orders,
        previous_orders=previous_orders,
        customers=customers,
        popular_items=popular_items,
        weekly_sales=weekly_sales,
        monthly_sales=monthly_sales,
        yearly_sales=yearly_sales
    )


@staff_bp.route('/update_order_status/<int:order_id>', methods=['POST'])
def update_order_status(order_id):
    order = Order.query.get_or_404(order_id)
    new_status = request.form.get('status')
    if new_status:
        order.status = new_status
        db.session.commit()
        flash(f'Order {order_id} status updated to {new_status}.', 'success')
    else:
        flash('No status provided.', 'danger')
    return redirect(url_for('staff.staff_dashboard'))

@staff_bp.route('/generate_customer_list', methods=['GET'])
def generate_customer_list():
    customers = Customer.query.all()
    return jsonify([{
        'id': customer.id,
        'name': customer.name,
        'username': customer.username,
        'contact_info': customer.contact_info,
        'balance': customer.balance
    } for customer in customers])

@staff_bp.route('/popular_items', methods=['GET'])
def popular_items():
    popular_items = db.session.query(
        OrderLine.item_id, func.count(OrderLine.item_id).label('count')
    ).group_by(OrderLine.item_id).order_by(desc('count')).limit(5).all()

    return jsonify([{
        'item_id': item[0],
        'count': item[1]
    } for item in popular_items])


@staff_bp.route('/current_orders', methods=['GET'])
@login_required
def current_orders():
    # Fetch current orders (status is 'Pending')
    current_orders = Order.query.filter(Order.status == 'Pending').all()

    return render_template('current_orders.html', current_orders=current_orders)


@staff_bp.route('/previous_orders', methods=['GET'])
@login_required
def previous_orders():

    previous_orders = Order.query.filter(Order.status != 'Pending').all()
    return render_template('previous_orders.html', previous_orders=previous_orders)

@staff_bp.route('/available_items', methods=['GET'])
@login_required
def available_items():
    items = Item.query.all()
    premade_boxes = PreMadeBox.query.all()
    return render_template('available_items.html', items=items, premade_boxes=premade_boxes)

@staff_bp.route('/customer_list', methods=['GET'])
@login_required
def customer_list():

    customers = Customer.query.all()
    return render_template('customer_list.html', customers=customers)


@staff_bp.route('/place_customer_order', methods=['GET', 'POST'])
@login_required
def place_customer_order():
    # Get list of all customers for staff to select from
    customers = Customer.query.all()

    # Get available items and premade boxes
    items = Item.query.filter_by(available=True).all()
    premade_boxes = PreMadeBox.query.all()

    if request.method == 'POST':
        customer_id = request.form.get('customer_id')
        if not customer_id:
            flash('Please select a customer', 'danger')
            return redirect(url_for('staff.place_customer_order'))

        # Create a new session cart for this staff order
        session['staff_cart'] = []
        session['selected_customer_id'] = customer_id
        return redirect(url_for('staff.staff_shop'))

    return render_template(
        'staff/place_customer_order.html',
        customers=customers,
        items=items,
        premade_boxes=premade_boxes
    )


@staff_bp.route('/staff_shop', methods=['GET'])
@login_required
def staff_shop():
    if 'selected_customer_id' not in session:
        flash('Please select a customer first', 'warning')
        return redirect(url_for('staff.place_customer_order'))

    selected_customer = Customer.query.get(session['selected_customer_id'])
    items = Item.query.filter_by(available=True).all()
    premade_boxes = PreMadeBox.query.all()

    return render_template(
        'staff/staff_shop.html',
        customer=selected_customer,
        items=items,
        premade_boxes=premade_boxes
    )


@staff_bp.route('/staff_add_to_cart', methods=['POST'])
@login_required
def staff_add_to_cart():
    if not isinstance(current_user, Staff):
        flash("Unauthorized access!", "danger")
        return redirect(url_for('auth.login'))

    cart = session.get('staff_cart', [])

    try:
        item_id = request.form.get('item_id')
        quantity = int(request.form.get('quantity', 1))
        unit_type = request.form.get('unit_type')

        # Get the item from database
        item = Item.query.get_or_404(item_id)

        cart_item = {
            'cart_item_id': str(uuid.uuid4()),
            'id': item_id,
            'type': 'regular',
            'quantity': quantity,
            'unit_type': unit_type,
            'price_per_unit': item.price_per_unit  # Store the price
        }

        cart.append(cart_item)
        session['staff_cart'] = cart

        flash(f'Added {quantity} {unit_type} of {item.name} to cart.', 'success')

    except Exception as e:
        flash(f'Error adding item to cart: {str(e)}', 'danger')

    return redirect(url_for('staff.staff_shop'))


@staff_bp.route('/staff_remove_from_cart/<cart_item_id>')
@login_required
def staff_remove_from_cart(cart_item_id):
    if not isinstance(current_user, Staff):
        flash("Unauthorized access!", "danger")
        return redirect(url_for('auth.login'))

    cart = session.get('staff_cart', [])
    cart = [item for item in cart if item.get('cart_item_id') != cart_item_id]

    # Recalculate cart subtotal
    subtotal = 0
    for cart_item in cart:
        if cart_item['type'] == 'regular':
            item = Item.query.get(cart_item['id'])
            if item:
                subtotal += item.price_per_unit * cart_item['quantity']
        else:  # premade box
            subtotal += cart_item.get('total_price', 0)

    session['staff_cart'] = cart
    session['staff_cart_subtotal'] = subtotal

    flash('Item removed from cart.', 'success')
    return redirect(url_for('staff.staff_shop'))


def calculate_cart_total(cart):
    """Calculate total price for cart items"""
    subtotal = 0
    for cart_item in cart:
        if cart_item['type'] == 'regular':
            item = Item.query.get(cart_item['id'])
            if item:
                subtotal += item.price_per_unit * cart_item['quantity']
        elif cart_item['type'] == 'premade_box':
            box = PreMadeBox.query.get(cart_item['id'])
            if box:
                subtotal += box.calculate_price() * cart_item.get('quantity', 1)
    return subtotal


@staff_bp.route('/staff_checkout', methods=['GET', 'POST'])
@login_required
def staff_checkout():
    if 'selected_customer_id' not in session or 'staff_cart' not in session:
        flash('Invalid session. Please start over.', 'danger')
        return redirect(url_for('staff.place_customer_order'))

    customer = Customer.query.get(session['selected_customer_id'])
    cart = session['staff_cart']

    if not cart:
        flash('Cart is empty', 'warning')
        return redirect(url_for('staff.staff_shop'))

        # Get all items for the template
    item_ids = [item['id'] for item in cart if item['type'] == 'regular']
    items = Item.query.filter(Item.id.in_(item_ids)).all()

    # Calculate totals using helper function
    subtotal = calculate_cart_total(cart)
    discount = subtotal * 0.1 if isinstance(customer, CorporateCustomer) else 0
    total = subtotal - discount

    if request.method == 'POST':
        payment_method = request.form.get('payment_method')

        # Create order
        order = Order(
            customer_id=customer.id,
            subtotal=subtotal,
            discount=discount,
            total_price=total,
            payment_status='Pending',
            status='Processing'  # Set initial status
        )

        # Add order items
        for cart_item in cart:
            if cart_item['type'] == 'regular':
                item = Item.query.get(cart_item['id'])
                if item:
                    order_line = OrderLine(
                        item_id=item.id,
                        quantity=cart_item['quantity']
                    )
                    order.items.append(order_line)
            elif cart_item['type'] == 'premade_box':
                # Handle premade box items
                box = PreMadeBox.query.get(cart_item['id'])
                if box:
                    for box_item in box.items:
                        order_line = OrderLine(
                            item_id=box_item.item_id,
                            quantity=box_item.quantity * cart_item.get('quantity', 1)
                        )
                        order.items.append(order_line)

        try:
            db.session.add(order)
            db.session.commit()

            # Process payment
            payment = Payment(
                order_id=order.id,
                payment_method=payment_method,
                amount=total,
                status='completed'
            )

            if payment.process_payment():
                db.session.add(payment)
                order.payment_status = 'Paid'
                db.session.commit()

                # Clear staff session data
                session.pop('staff_cart', None)
                session.pop('selected_customer_id', None)

                flash(f'Order placed successfully for {customer.name}!', 'success')
                return redirect(url_for('staff.staff_dashboard'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error processing order: {str(e)}', 'danger')

    return render_template(
        'staff/staff_checkout.html',
        customer=customer,
        cart=cart,
        items=items,
        subtotal=subtotal,
        discount=discount,
        total=total
    )