# app/commands.py
import click
from flask.cli import with_appcontext
from .extensions import db
from .models import Customer, Staff
from flask import current_app, Flask
from .models import Item


@click.command('create-staff-user')
@with_appcontext
@click.option('--username', prompt=True)
@click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True)
@click.option('--name', prompt='Full Name')
def create_staff_user(username, password, name):
    """Create a new staff user."""
    staff = Staff(
        username=username,
        name=name
    )
    staff.set_password(password)
    try:
        db.session.add(staff)
        db.session.commit()
        click.echo(f'Staff user {username} created successfully!')
    except Exception as e:
        db.session.rollback()
        click.echo(f'Error creating staff user: {str(e)}')


@click.command('create-test-users')
@with_appcontext
def create_test_users():
    """Create test users for development."""

    # Create a test customer
    customer = Customer(
        username='test_customer',
        name='Test Customer',
        contact_info='test@example.com',
        customer_type='private'  # Set the customer_type explicitly
    )
    customer.set_password('customer123')

    # Create a test staff member
    staff = Staff(
        username='test_staff',
        name='Test Staff'
        # No need to set 'role' as it's handled by the property
    )
    staff.set_password('staff123')

    try:
        db.session.add(customer)
        db.session.add(staff)
        db.session.commit()
        click.echo('Test users created successfully!')
        click.echo('Customer login: test_customer / customer123')
        click.echo('Staff login: test_staff / staff123')
    except Exception as e:
        db.session.rollback()
        click.echo(f'Error creating test users: {str(e)}')



@click.command("seed-items")
def seed_items():
    # Sample items to insert into the Item table
    items = [
        Item(name="Carrot", unit_type="kg", price_per_unit=2.5, image_path="static/images/carrot.jpg"),
        Item(name="Broccoli", unit_type="kg", price_per_unit=3.0, image_path="static/images/broccoli.jpg"),
        Item(name="Spinach", unit_type="bunch", price_per_unit=1.5, image_path="static/images/spinach.webp"),
        Item(name="Tomato", unit_type="kg", price_per_unit=4.0, image_path="static/images/tomatoes.jpg"),
        Item(name="Potato", unit_type="kg", price_per_unit=1.2, image_path="static/images/potatos.webp"),
        Item(name="Onion", unit_type="kg", price_per_unit=1.8, image_path="static/images/onion.webp"),
        Item(name="Garlic", unit_type="pack", price_per_unit=2.2, image_path="static/images/garlic.webp"),
        Item(name="Lettuce", unit_type="bunch", price_per_unit=1.8, image_path="static/images/lettuce.webp"),
        Item(name="Cucumber", unit_type="piece", price_per_unit=0.9, image_path="static/images/cucumber.jpg"),
        Item(name="Bell Pepper", unit_type="piece", price_per_unit=1.1, image_path="static/images/bell-pepper.webp")
    ]

    try:
        db.session.bulk_save_objects(items)
        db.session.commit()
        click.echo("10 items have been added to the database.")
    except Exception as e:
        db.session.rollback()
        click.echo(f"Error seeding items: {str(e)}")


@click.command("seed-premade-boxes")
def seed_premade_boxes():
    """Add premade box options to the database"""
    items = [
        Item(
            name="Customizable Veggie Box",
            category="premade_box",
            unit_type="box",
            price_per_unit=0,  # Base price, actual price calculated based on selections
            image_path="static/images/veggie-box.jpg"
        )
    ]

    try:
        db.session.bulk_save_objects(items)
        db.session.commit()
        click.echo("Premade box option has been added to the database.")
    except Exception as e:
        db.session.rollback()
        click.echo(f"Error seeding premade box: {str(e)}")