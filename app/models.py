from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from .extensions import db


# models.py

class Staff(UserMixin, db.Model):
    """Represents a staff member who can manage orders and customers."""

    __tablename__ = 'staff'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    # Remove the role field from the database model if it's not in your schema
    # role = db.Column(db.String(10), default='staff')  # You can comment this out

    def set_password(self, password):
        """Hashes the password using SHA256 and stores it in the database."""
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')

    def check_password(self, password):
        """Checks if the provided password matches the stored hash."""
        return check_password_hash(self.password_hash, password)

    @property
    def role(self):
        return 'staff'


class Customer(UserMixin, db.Model):
    """Base class for all customers."""
    __tablename__ = 'customers'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    contact_info = db.Column(db.String(100))
    balance = db.Column(db.Float, default=0.0)
    customer_type = db.Column(db.String(20), nullable=False)  # 'private' or 'corporate'
    credit_limit = db.Column(db.Float)  # Only for corporate customers
    role = db.Column(db.String(10), default='customer')

    orders = db.relationship('Order', back_populates='customer')

    __mapper_args__ = {
        'polymorphic_identity': 'customer',
        'polymorphic_on': customer_type
    }

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class PrivateCustomer(Customer):
    """Private customer with $100 balance limit."""
    __mapper_args__ = {
        'polymorphic_identity': 'private'
    }

    def can_place_order(self, order_amount):
        """Checks if private customer can place an order based on current balance."""
        return (self.balance + order_amount) <= 100.0


class CorporateCustomer(Customer):
    """Corporate customer with credit limit and 10% discount."""
    __mapper_args__ = {
        'polymorphic_identity': 'corporate'
    }

    def can_place_order(self, order_amount):
        """Checks if corporate customer can place an order based on credit limit."""
        return self.balance <= self.credit_limit

    def apply_discount(self, amount):
        """Applies 10% corporate discount."""
        return amount * 0.9

        @property
        def role(self):
            return 'customer'


class Item(db.Model):
    """Represents vegetables available for sale."""
    __tablename__ = 'items'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    category = db.Column(db.String(50))  # leafy_greens, root_vegetables, seasonal, herbs
    unit_type = db.Column(db.String(20))  # bunch, weight, punnet, pack
    price_per_unit = db.Column(db.Float, nullable=False)
    available = db.Column(db.Boolean, default=True)
    image_path = db.Column(db.String(200))

    def get_item_details(self):
        return {
            'ID': self.id,
            'Name': self.name,
            'Category': self.category,
            'Unit Type': self.unit_type,
            'Price per Unit': self.price_per_unit,
            'Available': self.available
        }


class PreMadeBox(db.Model):
    """Represents customizable premade boxes."""
    __tablename__ = 'premade_boxes'

    id = db.Column(db.Integer, primary_key=True)
    size = db.Column(db.String(20))  # small, medium, large
    base_price = db.Column(db.Float, nullable=False)
    max_items = db.Column(db.Integer, nullable=False)  # Maximum number of items for this size

    items = db.relationship('PreMadeBoxItem', back_populates='premade_box')
    quantity = db.Column(db.Integer, default=1)

    def calculate_price(self):
        """Calculates total price based on size and quantity."""
        base_prices = {
            'small': 30.0,
            'medium': 45.0,
            'large': 60.0
        }
        base_price = base_prices.get(self.size, 0)
        items_total = sum(box_item.calculate_price() for box_item in self.items)
        return max(base_price, items_total) * self.quantity

    def customize_box(self, new_items):
        """Customizes box contents based on available items."""
        if len(new_items) > self.max_items:
            raise ValueError(f"Cannot exceed {self.max_items} items for this box size")

        # Clear existing items
        PreMadeBoxItem.query.filter_by(premade_box_id=self.id).delete()

        # Add new items
        for item, quantity in new_items.items():
            if item.available:
                box_item = PreMadeBoxItem(
                    premade_box_id=self.id,
                    item_id=item.id,
                    quantity=quantity
                )
                db.session.add(box_item)

        db.session.commit()


class PreMadeBoxItem(db.Model):
    """Association table for items in a premade box with quantity and price tracking."""

    __tablename__ = 'premade_box_items'

    id = db.Column(db.Integer, primary_key=True)
    premade_box_id = db.Column(db.Integer, db.ForeignKey('premade_boxes.id'))
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'))
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float)  # Store price at time of addition

    # Relationships
    premade_box = db.relationship('PreMadeBox', back_populates='items')
    item = db.relationship('Item')

    def __init__(self, premade_box_id, item_id, quantity):
        self.premade_box_id = premade_box_id
        self.item_id = item_id
        self.quantity = quantity
        # Store the current price when adding to box
        item = Item.query.get(item_id)
        if item:
            self.unit_price = item.price_per_unit

    def calculate_price(self):
        """Calculate total price for this item in the box."""
        return self.unit_price * self.quantity

    def validate_quantity(self):
        """Validate if the requested quantity is available."""
        item = Item.query.get(self.item_id)
        if not item or not item.available:
            raise ValueError(f"Item {item.name if item else 'Unknown'} is not available")
        return True

    def to_dict(self):
        """Convert box item to dictionary for API/frontend use."""
        return {
            'id': self.id,
            'item_id': self.item_id,
            'item_name': self.item.name if self.item else 'Unknown',
            'quantity': self.quantity,
            'unit_type': self.item.unit_type if self.item else 'Unknown',
            'unit_price': self.unit_price,
            'total_price': self.calculate_price()
        }

    @staticmethod
    def create_default_items(box_id, size):
        """Create default items for a new premade box based on size."""
        default_items = {
            'small': [
                {'category': 'leafy_greens', 'quantity': 1},
                {'category': 'root_vegetables', 'quantity': 1},
                {'category': 'herbs', 'quantity': 1}
            ],
            'medium': [
                {'category': 'leafy_greens', 'quantity': 2},
                {'category': 'root_vegetables', 'quantity': 2},
                {'category': 'herbs', 'quantity': 1},
                {'category': 'seasonal', 'quantity': 1}
            ],
            'large': [
                {'category': 'leafy_greens', 'quantity': 3},
                {'category': 'root_vegetables', 'quantity': 3},
                {'category': 'herbs', 'quantity': 2},
                {'category': 'seasonal', 'quantity': 2}
            ]
        }

        if size not in default_items:
            raise ValueError(f"Invalid box size: {size}")

        items_to_add = []
        for item_spec in default_items[size]:
            # Get available item from specified category
            available_item = Item.query.filter_by(
                category=item_spec['category'],
                available=True
            ).first()

            if available_item:
                box_item = PreMadeBoxItem(
                    premade_box_id=box_id,
                    item_id=available_item.id,
                    quantity=item_spec['quantity']
                )
                items_to_add.append(box_item)

        return items_to_add


class Order(db.Model):
    """Represents an order with corporate discount handling."""
    __tablename__ = 'orders'

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'))
    status = db.Column(db.String(20), default='Pending')
    delivery = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    subtotal = db.Column(db.Float, nullable=False)
    discount = db.Column(db.Float, default=0.0)
    total_price = db.Column(db.Float, nullable=False)
    delivery_address = db.Column(db.String(200))
    delivery_distance = db.Column(db.Float)  # in kilometers
    delivery_fee = db.Column(db.Float, default=0.0)
    payment_status = db.Column(db.String(20), default='Pending')

    customer = db.relationship('Customer', back_populates='orders')
    items = db.relationship('OrderLine', back_populates='order')

    def calculate_total(self):
        """Calculates total with corporate discount and delivery fee if applicable."""
        self.subtotal = sum(line.calculate_price() for line in self.items)

        if isinstance(self.customer, CorporateCustomer):
            self.discount = self.subtotal * 0.1
            self.total_price = self.subtotal - self.discount
        else:
            self.discount = 0
            self.total_price = self.subtotal

        # Add delivery fee if applicable
        if self.delivery and self.delivery_distance <= 20:
            self.delivery_fee = 10.0
            self.total_price += self.delivery_fee

        return self.total_price

    def get_remaining_balance(self):
        """Calculate remaining balance after all payments."""
        paid_amount = sum(payment.amount for payment in self.payments)
        return self.total_price - paid_amount

    def can_be_placed(self):
        """Checks if order can be placed based on customer type and balance."""
        # Ensure total_price has a default value of 0.0 if it's None
        total_price = self.total_price if self.total_price is not None else 0.0
        return self.customer.can_place_order(total_price)


class OrderLine(db.Model):
    """Represents an individual line item in an order."""

    __tablename__ = 'order_lines'

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'))
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'))
    quantity = db.Column(db.Integer, nullable=False)
    total_price = db.Column(db.Float, nullable=False)

    # Relationships
    order = db.relationship('Order', back_populates='items')
    item = db.relationship('Item')

    def calculate_price(self):
        """Calculates the total price for this line item."""
        return self.item.price_per_unit * self.quantity

    def set_total_price(self):
        """Sets the total_price attribute with the calculated value."""
        self.total_price = self.calculate_price()


class Payment(db.Model):
    """Represents payment details for an order."""

    __tablename__ = 'payments'

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'))
    payment_method = db.Column(db.String(20))  # credit_card, debit_card, or account
    amount = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    installment_number = db.Column(db.Integer, default=1)
    transaction_id = db.Column(db.String(100))
    status = db.Column(db.String(20), default='pending')  # pending, completed, failed

    # Relationships
    order = db.relationship('Order', backref=db.backref('payments', lazy=True))

    def process_payment(self):
        """Process payment based on payment method."""
        try:
            if self.payment_method in ['credit_card', 'debit_card']:
                # Simulate card payment processing
                self.transaction_id = f"TR-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
                self.status = 'completed'
                return True
            elif self.payment_method == 'account':
                customer = self.order.customer
                if isinstance(customer, PrivateCustomer):
                    if (customer.balance + self.amount) > 100:
                        raise ValueError("Payment would exceed private customer limit")
                elif isinstance(customer, CorporateCustomer):
                    if customer.balance > customer.credit_limit:
                        raise ValueError("Payment would exceed credit limit")

                self.status = 'completed'
                self.transaction_id = f"ACC-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
                return True

            return False
        except Exception as e:
            self.status = 'failed'
            db.session.rollback()
            raise e

    def get_payment_details(self):
        """Returns a dictionary of payment details."""
        return {
            'payment_id': self.id,
            'order_id': self.order_id,
            'payment_method': self.payment_method,
            'amount': self.amount,
            'created_at': self.created_at,
            'installment_number': self.installment_number,
            'transaction_id': self.transaction_id,
            'status': self.status
        }
