from app.models import Customer, Staff, db
from werkzeug.security import generate_password_hash

def test_customer_login(client):
    # Set up a test customer
    customer = Customer(username="testcustomer", name="Test Customer", role="customer")
    customer.set_password("password")
    db.session.add(customer)
    db.session.commit()

    # Test login
    response = client.post("/login", data={
        "username": "testcustomer",
        "password": "password"
    }, follow_redirects=True)
    assert b"Welcome, Test Customer" in response.data

def test_staff_login(client):
    # Set up a test staff
    staff = Staff(username="teststaff", name="Test Staff", role="staff")
    staff.set_password("password")
    db.session.add(staff)
    db.session.commit()

    # Test login
    response = client.post("/login", data={
        "username": "teststaff",
        "password": "password"
    }, follow_redirects=True)
    assert b"Welcome, Test Staff" in response.data

def test_unauthorized_access(client):
    # Try to access the customer dashboard without logging in
    response = client.get("/customer/dashboard", follow_redirects=True)
    assert b"Login" in response.data  # Redirected to login page
