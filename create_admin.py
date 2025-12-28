"""
Quick setup script to create your first admin user
Run this after first installing the app
"""

from app import create_app, db
from app.models import User, List
from getpass import getpass

def create_admin():
    app = create_app('development')
    
    with app.app_context():
        print("\n=== Create First Admin User ===\n")
        
        email = input("Email address: ").strip()
        name = input("Your name: ").strip()
        password = getpass("Password: ")
        password2 = getpass("Confirm password: ")
        
        if password != password2:
            print("\nError: Passwords don't match!")
            return
        
        if not email or not name or not password:
            print("\nError: All fields are required!")
            return
        
        # Check if user already exists
        existing = User.query.filter_by(email=email.lower()).first()
        if existing:
            print(f"\nError: User with email {email} already exists!")
            return
        
        # Create admin user
        admin = User(
            email=email.lower(),
            name=name,
            is_admin=True
        )
        admin.set_password(password)
        
        db.session.add(admin)
        db.session.flush()
        
        # Create admin's list
        admin_list = List(
            owner_id=admin.id,
            name=f"{name}'s List"
        )
        db.session.add(admin_list)
        db.session.commit()
        
        print(f"\n✓ Admin user created successfully!")
        print(f"Email: {email}")
        print(f"Name: {name}")
        print("\nYou can now log in and start inviting family members!")

if __name__ == '__main__':
    create_admin()
