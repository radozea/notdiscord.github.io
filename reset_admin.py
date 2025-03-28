
import pickle
import os
import random
import string
import argparse
from werkzeug.security import generate_password_hash

# Parse command line arguments
parser = argparse.ArgumentParser(description='Reset or create admin user with a specified username and password')
parser.add_argument('-u', '--username', default="robozo", help='Admin username (default: robozo)')
parser.add_argument('-p', '--password', help='Admin password (if not provided, a random one will be generated)')
parser.add_argument('-ua', '--unadmin', help='Remove admin privileges from specified user')
args = parser.parse_args()

# Data storage
data_file = 'chat_data.pkl'

# Load existing data
if os.path.exists(data_file):
    with open(data_file, 'rb') as f:
        data = pickle.load(f)
    users = data.get('users', {})
    chatrooms = data.get('chatrooms', {})
    invites = data.get('invites', {})
    pending_users = data.get('pending_users', {})
    feedback = data.get('feedback', [])
else:
    print("No data file found. Please run the main application first.")
    exit(1)

# Handle unadmin request
if args.unadmin:
    if args.unadmin in users:
        if users[args.unadmin].get('is_admin', False):
            users[args.unadmin]['is_admin'] = False
            print(f"Admin privileges removed from user: {args.unadmin}")
        else:
            print(f"User {args.unadmin} is not an admin.")
    else:
        print(f"User {args.unadmin} not found.")
else:
    # Set username and generate password if not provided
    ADMIN_USERNAME = args.username
    admin_password = args.password
    if not admin_password:
        admin_password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))

    # Update admin account
    if ADMIN_USERNAME in users:
        users[ADMIN_USERNAME]['password'] = generate_password_hash(admin_password)
        users[ADMIN_USERNAME]['is_admin'] = True
        print(f"Admin password reset. Username: {ADMIN_USERNAME}, Password: {admin_password}")
    else:
        users[ADMIN_USERNAME] = {
            'password': generate_password_hash(admin_password),
            'profile_pic': 'default.png',
            'is_admin': True,
            'email': 'admin@example.com',
            'joined_chatrooms': ['general'],
            'name_color': '#ff5555',
            'name_font': 'Arial, sans-serif',
            'is_rickrolled': False
        }
        print(f"Admin account created. Username: {ADMIN_USERNAME}, Password: {admin_password}")

# Save data
data = {
    'users': users,
    'chatrooms': chatrooms,
    'invites': invites,
    'pending_users': pending_users,
    'feedback': feedback
}
with open(data_file, 'wb') as f:
    pickle.dump(data, f)

print("Data saved successfully.")
print("\nIMPORTANT: You must restart the chat application for these changes to take effect.")
