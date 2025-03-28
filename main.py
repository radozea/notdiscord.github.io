from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash, send_from_directory
import json
import os
import time
import random
import string
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import pickle

app = Flask(__name__, static_url_path='/static')
app.config['APP_NAME'] = 'Not Discord'  # Set application name
app.secret_key = os.urandom(24).hex()  # Create a random secret key for session
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB max upload

# Create uploads directory if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'pfp'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'music'), exist_ok=True)

# Copy the Opera GX music file as default music if it doesn't exist
default_music_path = os.path.join(app.config['UPLOAD_FOLDER'], 'music', 'default.mp3')
if not os.path.exists(default_music_path):
    source_music = 'attached_assets/Opera GX Browser Dynamic Background Music - Evolve (Full Activity).mp3'
    if os.path.exists(source_music):
        import shutil
        shutil.copy2(source_music, default_music_path)

# Default admin username (cannot be changed)
ADMIN_USERNAME = "robozo"

# Data storage
data_file = 'chat_data.pkl'

# Initialize data structures
if os.path.exists(data_file):
    with open(data_file, 'rb') as f:
        data = pickle.load(f)
    users = data.get('users', {})
    chatrooms = data.get('chatrooms', {})
    invites = data.get('invites', {})
    pending_users = data.get('pending_users', {})
    feedback = data.get('feedback', [])
    real_names_set = data.get('real_names_set', set())
    polls = data.get('polls', {})

    # Initialize real_names_set if not in saved data
    if real_names_set is None:
        real_names_set = set()
        # Add users who already have real names set
        for username, user_data in users.items():
            if user_data.get('real_name', ''):
                real_names_set.add(username)
else:
    # Store users in memory (in a real app, you'd use a database)
    users = {}
    # Chatrooms data structure
    chatrooms = {
        'general': {
            'name': 'General',
            'messages': [],
            'members': []
        },
        'changelog': {
            'name': 'Changelog',
            'messages': [],
            'members': [],
            'is_permanent': True
        }
    }
    # Track users who have set their real name
    real_names_set = set()
    # Store invites
    invites = {}
    # Store pending users (awaiting approval)
    pending_users = {}
    # Store user feedback
    feedback = []
    # Store polls
    polls = {}

# Ensure polls chatroom exists
if 'polls' not in chatrooms:
    chatrooms['polls'] = {
        'name': '📊 Polls',
        'messages': [],
        'members': [],
        'is_polls_room': True,
        'polls': []
    }

# Make sure all users are members of the polls and changelog chatrooms
for username in users:
    if 'joined_chatrooms' not in users[username]:
        users[username]['joined_chatrooms'] = ['general']

    # Add polls room
    if 'polls' not in users[username]['joined_chatrooms']:
        users[username]['joined_chatrooms'].append('polls')

    # Add changelog room
    if 'changelog' not in users[username]['joined_chatrooms']:
        users[username]['joined_chatrooms'].append('changelog')

    # Make sure users are in the members list of the polls chatroom
    if username not in chatrooms['polls']['members']:
        chatrooms['polls']['members'].append(username)

    # Make sure users are in the members list of the changelog chatroom
    if username not in chatrooms['changelog']['members']:
        chatrooms['changelog']['members'].append(username)

# Ensure admin account exists
if ADMIN_USERNAME not in users:
    # Create admin account if it doesn't exist
    admin_password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
    users[ADMIN_USERNAME] = {
        'password': generate_password_hash(admin_password),
        'profile_pic': 'default.png',
        'is_admin': True,
        'email': 'admin@example.com',
        'joined_chatrooms': ['general'],
        'name_color': '#ff5555',
        'name_font': 'Arial, sans-serif',
        'is_rickrolled': False,
        'online_status': 'offline',
        'last_active': datetime.now().timestamp()
    }
    print(f"Admin account created with password: {admin_password}")
    # Add admin to general chatroom if not already there
    if ADMIN_USERNAME not in chatrooms['general']['members']:
        chatrooms['general']['members'].append(ADMIN_USERNAME)


# Function to save data
def save_data():
    data = {
        'users': users,
        'chatrooms': chatrooms,
        'invites': invites,
        'pending_users': pending_users,
        'feedback': feedback,
        'real_names_set': real_names_set,
        'polls': polls
    }
    with open(data_file, 'wb') as f:
        pickle.dump(data, f)

# Function to send email invite (placeholder)
def send_invite_email(email, invite_code, sender_name):
    try:
        # This is a placeholder - in production, you'd configure SMTP properly
        # For now we'll just print the invite info
        print(f"Invite email would be sent to {email} with code {invite_code} from {sender_name}")
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

# Helper function to check if filename is valid (now allows all file types)
def allowed_file(filename):
    return '.' in filename  # Just check that the filename has an extension


@app.route('/')
def home():
    if 'username' in session:
        username = session['username']

        # Check if the user is set to be in a rickroll room
        if users.get(username, {}).get('current_room') and users.get(username, {}).get('is_rickrolled', False):
            rickroll_room = users[username]['current_room']
            # Check if the room exists and is a rickroll room
            if rickroll_room in chatrooms and chatrooms[rickroll_room].get('is_rickroll_room', False):
                # Send them to a special rickroll-only page
                return render_template('rickroll.html',
                                      username=username)

        # Normal room handling
        if session.get('current_chatroom') is None:
            session['current_chatroom'] = 'general'

        # Get the current chatroom
        current_room = session.get('current_chatroom')
        # Ensure the room exists
        if current_room not in chatrooms:
            session['current_chatroom'] = 'general'
            current_room = 'general'

        # Ensure user is a member of the current room
        if username not in chatrooms[current_room]['members']:
            chatrooms[current_room]['members'].append(username)
            save_data()

        # Check if user needs to set their real name
        needs_real_name = session.get('needs_real_name', False)

        return render_template('chat.html', 
                              username=username, 
                              chatrooms=chatrooms,
                              current_room=current_room,
                              users=users,
                              is_admin=users.get(username, {}).get('is_admin', False),
                              needs_real_name=needs_real_name)
    else:
        return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if username in users and check_password_hash(users[username]['password'], password):
            session['username'] = username
            session['current_chatroom'] = 'general'

            # Check if user has set their real name
            name_status = users[username].get('name', 'ask')
            has_real_name = username in real_names_set or (users[username].get('real_name', '') and name_status == 'done')

            if not has_real_name:
                session['needs_real_name'] = True
                print(f"User {username} needs to set real name")
                flash('Please set your real name to continue.')
            else:
                session['needs_real_name'] = False
                print(f"User {username} already has real name set: {users[username].get('real_name', '')}")

            return redirect(url_for('home'))
        else:
            flash('Invalid username or password')
            return render_template('login.html')

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        email = request.form.get('email') or ""  # Make email optional
        invite_code = request.form.get('invite_code')

        # Check if this is an invite registration
        if invite_code:
            if invite_code not in invites or (email and invites[invite_code]['email'] != email):
                flash('Invalid invite code')
                return render_template('register.html')

        if username and password:
            if username in users or username in pending_users:
                flash('Username already exists')
                return render_template('register.html')

            # Set admin status (only for the predefined admin username)
            is_admin = (username == ADMIN_USERNAME)

            # Hash the password before storing
            hashed_password = generate_password_hash(password)

            # For the admin account, create it directly
            if is_admin:
                users[username] = {
                    'password': hashed_password,
                    'profile_pic': 'default.png',
                    'is_admin': is_admin,
                    'email': email,
                    'joined_chatrooms': ['general', 'polls', 'changelog'],
                    'name_color': '#000000',  # Default black color
                    'name_font': 'Arial, sans-serif', # Default font
                    'is_rickrolled': False, # Added is_rickrolled field
                    'online_status': 'online',
                    'last_active': datetime.now().timestamp(),
                    'real_name': '',  # Store user's real name
                    'name': 'ask'  # Default to ask for name
                }

                # Add admin to general chatroom
                if username not in chatrooms['general']['members']:
                    chatrooms['general']['members'].append(username)

                # Save data
                save_data()

                # Log the admin in
                session['username'] = username
                session['current_chatroom'] = 'general'
                return redirect(url_for('home'))
            else:
                # For regular users, add to pending approval
                pending_users[username] = {
                    'password': hashed_password,
                    'profile_pic': 'default.png',
                    'is_admin': False,
                    'email': email,
                    'joined_chatrooms': ['general', 'polls', 'changelog'],
                    'name_color': '#000000',  # Default black color
                    'name_font': 'Arial, sans-serif', # Default font
                    'is_rickrolled': False, # Added is_rickrolled field
                    'online_status': 'offline',
                    'last_active': datetime.now().timestamp(),
                    'registration_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'invite_code': invite_code if invite_code else None,
                    'real_name': '',  # Store user's real name
                    'name': 'ask'  # Default to ask for name
                }

                # Save data
                save_data()

                flash('Your account has been created and is pending approval from an administrator')
                return render_template('registration_pending.html')
        else:
            flash('Username and password are required')
            return render_template('register.html')

    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/classroom')
def classroom():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    username = session.get('username')
    user_data = users.get(username, {})
    
    # Create classroom directory if it doesn't exist
    classroom_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'classroom')
    os.makedirs(classroom_dir, exist_ok=True)
    
    # Set default file if none exists
    default_file = os.path.join(classroom_dir, 'default.html')
    if not os.path.exists(default_file):
        with open('attached_assets/dis.html', 'r', encoding='utf-8') as src:
            with open(default_file, 'w', encoding='utf-8') as dst:
                dst.write(src.read())
    
    # If user has custom classroom file and isn't using default
    if not user_data.get('use_default_classroom', True) and user_data.get('classroom_html_file'):
        try:
            file_path = os.path.join(classroom_dir, user_data['classroom_html_file'])
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # Add base tag to fix relative paths
                    if '<head>' in content:
                        base_tag = '<base href="/static/uploads/classroom/">'
                        content = content.replace('<head>', f'<head>{base_tag}')
                    return content
        except Exception as e:
            print(f"Error loading custom classroom file: {e}")
    
    # Otherwise use default template file
    try:
        with open(default_file, 'r', encoding='utf-8') as f:
            content = f.read()
            if '<head>' in content:
                base_tag = '<base href="/static/uploads/classroom/">'
                content = content.replace('<head>', f'<head>{base_tag}')
            return content
    except Exception as e:
        print(f"Error loading default classroom file: {e}")
        return render_template('dis.html', username=username, is_admin=user_data.get('is_admin', False))

@app.route('/static/uploads/classroom/<path:filename>')
def serve_classroom_file(filename):
    """Serve files from the classroom upload directory"""
    return send_from_directory(os.path.join(app.config['UPLOAD_FOLDER'], 'classroom'), filename)

@app.route('/admin/pending_users')
def pending_users_list():
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']
    if not users.get(username, {}).get('is_admin', False):
        flash('You do not have permission to access this page')
        return redirect(url_for('home'))

    return render_template('pending_users.html', 
                          pending_users=pending_users,
                          admin_username=username)

@app.route('/api/pending_users')
def api_pending_users():
    if 'username' not in session:
        return jsonify({"error": "Not logged in"}), 401

    username = session['username']
    if not users.get(username, {}).get('is_admin', False):
        return jsonify({"error": "Not authorized"}), 403

    return jsonify(pending_users)

@app.route('/admin/approve_user/<username>', methods=['POST'])
def approve_user(username):
    if 'username' not in session:
        return jsonify({"error": "Not logged in"}), 401

    admin_username = session['username']
    if not users.get(admin_username, {}).get('is_admin', False):
        return jsonify({"error": "You don't have permission to approve users"}), 403

    if username not in pending_users:
        return jsonify({"error": "User not found in pending list"}), 404

    # Move user from pending to approved
    user_data = pending_users[username]
    users[username] = user_data

    # Add user to general, polls, and changelog chatrooms if not already there
    for room_id in ['general', 'polls', 'changelog']:
        if username not in chatrooms[room_id]['members']:
            chatrooms[room_id]['members'].append(username)

    # If registering with invite, add to the specific chatroom
    invite_code = user_data.get('invite_code')
    if invite_code and invite_code in invites:
        chatroom_id = invites[invite_code]['chatroom']
        if chatroom_id in chatrooms and username not in chatrooms[chatroom_id]['members']:
            chatrooms[chatroom_id]['members'].append(username)
            users[username]['joined_chatrooms'].append(chatroom_id)
        # Remove the used invite
        del invites[invite_code]

    # Remove from pending users
    del pending_users[username]

    save_data()

    return jsonify({"success": True})

@app.route('/admin/reject_user/<username>', methods=['POST'])
def reject_user(username):
    if 'username' not in session:
        return jsonify({"error": "Not logged in"}), 401

    admin_username = session['username']
    if not users.get(admin_username, {}).get('is_admin', False):
        return jsonify({"error": "You don't have permission to reject users"}), 403

    if username not in pending_users:
        return jsonify({"error": "User not found in pending list"}), 404

    # Simply remove from pending users
    del pending_users[username]
    save_data()

    return jsonify({"success": True})

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']

    if request.method == 'POST':
        # Handle music settings
        if 'update_music' in request.form:
            use_default = request.form.get('use_default_music') == 'on'
            enable_music = request.form.get('enable_music') == 'on'

            users[username]['use_default_music'] = use_default
            users[username]['enable_music'] = enable_music

            if 'bg_music' in request.files:
                file = request.files['bg_music']
                if file and file.filename and file.filename.endswith('.mp3'):
                    filename = secure_filename(f"{username}_{int(time.time())}_music.mp3")
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'music', filename)
                    file.save(filepath)
                    users[username]['bg_music_file'] = filename
                    flash('Music updated successfully')
            save_data()
            return redirect(url_for('profile'))

        # Handle profile picture upload
        if 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(f"{username}_{int(time.time())}.{file.filename.rsplit('.', 1)[1].lower()}")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'pfp', filename)
                file.save(filepath)

                # Update user profile pic
                users[username]['profile_pic'] = filename
                save_data()
                flash('Profile picture updated successfully')
            elif file.filename:
                flash('Invalid file type. Please upload a PNG, JPG, JPEG, or GIF.')

        # Handle classroom HTML file upload
        if 'update_classroom' in request.form:
            use_default = request.form.get('use_default_classroom') == 'on'
            users[username]['use_default_classroom'] = use_default

            if 'classroom_html' in request.files:
                file = request.files['classroom_html']
                if file and file.filename and file.filename.endswith('.html'):
                    filename = secure_filename(f"{username}_{int(time.time())}_classroom.html")
                    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'classroom'), exist_ok=True)
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'classroom', filename)
                    file.save(filepath)
                    users[username]['classroom_html_file'] = filename
                    flash('Classroom template updated successfully')
            save_data()
            return redirect(url_for('profile'))

        # Handle name color update
        name_color = request.form.get('name_color')
        if name_color:
            users[username]['name_color'] = name_color
            save_data()
            flash('Name color updated successfully')

        # Handle name font update
        name_font = request.form.get('name_font')
        if name_font:
            users[username]['name_font'] = name_font
            save_data()
            flash('Name font updated successfully')

        return redirect(url_for('profile'))

    # Initialize real name display settings if they don't exist
    if 'show_in_room' not in users[username]:
        users[username]['show_in_room'] = True
    if 'show_in_chat' not in users[username]:
        users[username]['show_in_chat'] = False
    if 'show_in_profile' not in users[username]:
        users[username]['show_in_profile'] = False
    save_data()

    return render_template('profile.html', 
                          username=username, 
                          user=users[username],
                          is_admin=users[username]['is_admin'],
                          chatrooms=chatrooms)

@app.route('/update_name_settings', methods=['POST'])
def update_name_settings():
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']

    # Update real name display settings
    users[username]['show_in_room'] = request.form.get('show_in_room') == 'on'
    users[username]['show_in_chat'] = request.form.get('show_in_chat') == 'on'
    users[username]['show_in_profile'] = request.form.get('show_in_profile') == 'on'

    save_data()
    flash('Name display settings updated successfully')
    return redirect(url_for('profile'))

@app.route('/uploads/pfp/<filename>')
def uploaded_file(filename):
    return send_from_directory(os.path.join(app.config['UPLOAD_FOLDER'], 'pfp'), filename)

@app.route('/create_chatroom', methods=['POST'])
def create_chatroom():
    if 'username' not in session:
        return jsonify({"error": "Not logged in"}), 401

    username = session['username']
    room_name = request.form.get('room_name')

    if not room_name or not room_name.strip():
        return jsonify({"error": "Chatroom name is required"}), 400

    # Create a unique ID for the chatroom
    room_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))

    # Generate a join code for the chatroom
    join_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

    # Create the chatroom
    chatrooms[room_id] = {
        'name': room_name,
        'messages': [],
        'members': [username],
        'created_by': username,
        'join_code': join_code,
        'is_private': request.form.get('is_private') == 'true',
        'is_permanent': request.form.get('is_permanent') == 'true'
    }

    # Add this chatroom to the user's joined rooms
    if 'joined_chatrooms' not in users[username]:
        users[username]['joined_chatrooms'] = []

    users[username]['joined_chatrooms'].append(room_id)

    # Save data
    save_data()

    return jsonify({"success": True, "room_id": room_id})

@app.route('/join_chatroom/<room_id>')
def join_chatroom(room_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    if room_id not in chatrooms:
        flash('Chatroom does not exist')
        return redirect(url_for('home'))

    username = session['username']

    # Check if room is private and user is not a member
    if chatrooms[room_id].get('is_private', False) and username not in chatrooms[room_id]['members']:
        flash('This room is private. Please use a join code to access it.')
        return redirect(url_for('home'))

    # Add user to the chatroom if not already a member
    if username not in chatrooms[room_id]['members']:
        chatrooms[room_id]['members'].append(username)

        # Update user's joined chatrooms
        if 'joined_chatrooms' not in users[username]:
            users[username]['joined_chatrooms'] = []

        if room_id not in users[username]['joined_chatrooms']:
            users[username]['joined_chatrooms'].append(room_id)

        save_data()

    # Set current chatroom
    session['current_chatroom'] = room_id

    return redirect(url_for('home'))

@app.route('/join_by_code', methods=['POST'])
def join_by_code():
    if 'username' not in session:
        return jsonify({"error": "Not logged in"}), 401

    username = session['username']
    join_code = request.form.get('join_code')

    if not join_code:
        return jsonify({"error": "Join code is required"}), 400

    # Find room with matching join code
    room_id = None
    for rid, room in chatrooms.items():
        if room.get('join_code') == join_code:
            room_id = rid
            break

    if not room_id:
        return jsonify({"error": "Invalid join code"}), 404

    # Add user to the chatroom
    if username not in chatrooms[room_id]['members']:
        chatrooms[room_id]['members'].append(username)

        # Update user's joined chatrooms
        if 'joined_chatrooms' not in users[username]:
            users[username]['joined_chatrooms'] = []

        if room_id not in users[username]['joined_chatrooms']:
            users[username]['joined_chatrooms'].append(room_id)

        save_data()

    return jsonify({"success": True, "room_id": room_id})

@app.route('/switch_chatroom/<room_id>')
def switch_chatroom(room_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    if room_id not in chatrooms:
        flash('Chatroom does not exist')
        return redirect(url_for('home'))

    username = session['username']

    # Ensure user is a member of the chatroom
    if username not in chatrooms[room_id]['members']:
        flash('You are not a member of this chatroom')
        return redirect(url_for('home'))

    # Set current chatroom
    session['current_chatroom'] = room_id

    return redirect(url_for('home'))

@app.route('/invite', methods=['POST'])
def invite_user():
    if 'username' not in session:
        return jsonify({"error": "Not logged in"}), 401

    username = session['username']
    email = request.form.get('email')
    chatroom_id = request.form.get('chatroom_id')

    if not email or not chatroom_id:
        return jsonify({"error": "Email and chatroom are required"}), 400

    if chatroom_id not in chatrooms:
        return jsonify({"error": "Chatroom does not exist"}), 404

    # Generate a unique invite code
    invite_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))

    # Store the invite
    invites[invite_code] = {
        'email': email,
        'chatroom': chatroom_id,
        'invited_by': username,
        'created_at': datetime.now().isoformat()
    }

    # Send the invite email
    invite_url = url_for('register', _external=True)
    if send_invite_email(email, invite_code, username):
        save_data()
        return jsonify({"success": True, "invite_code": invite_code})
    else:
        # If email sending fails, remove the invite
        if invite_code in invites:
            del invites[invite_code]
        return jsonify({"error": "Failed to send invite email"}), 500

@app.route('/update_user_style', methods=['POST'])
def update_user_style():
    if 'username' not in session:
        return jsonify({"error": "Not logged in"}), 401

    username = session['username']
    target_user = request.form.get('username')
    name_color = request.form.get('name_color')
    name_font = request.form.get('name_font')

    # Check if user is admin
    is_admin = users.get(username, {}).get('is_admin', False)

    if not is_admin:
        return jsonify({"error": "You don't have permission to update user styles"}), 403

    if not target_user or target_user not in users:
        return jsonify({"error": "Invalid user"}), 400

    # Update the user's style
    if name_color:
        users[target_user]['name_color'] = name_color

    if name_font:
        users[target_user]['name_font'] = name_font

    save_data()

    return jsonify({"success": True})

@app.route('/move_user', methods=['POST'])
def move_user():
    if 'username' not in session:
        return jsonify({"error": "Not logged in"}), 401

    username = session['username']
    target_user = request.form.get('username')
    destination_room = request.form.get('room_id')

    # Check if user is admin
    is_admin = users.get(username, {}).get('is_admin', False)

    if not is_admin:
        return jsonify({"error": "You don't have permission to move users"}), 403

    if not target_user or target_user not in users:
        return jsonify({"error": "Invalid user"}), 400

    if not destination_room or destination_room not in chatrooms:
        return jsonify({"error": "Invalid destination room"}), 400

    # Add the user to the destination room if not already a member
    if target_user not in chatrooms[destination_room]['members']:
        chatrooms[destination_room]['members'].append(target_user)

    # Update user's joined chatrooms list
    if 'joined_chatrooms' not in users[target_user]:
        users[target_user]['joined_chatrooms'] = []

    if destination_room not in users[target_user]['joined_chatrooms']:
        users[target_user]['joined_chatrooms'].append(destination_room)

    # Create a notification message in the destination room
    message_id = f"{int(time.time())}-{random.randint(1000, 9999)}"
    message = {
        'id': message_id,
        'user': 'robozo',
        'content': f"{target_user} has been moved to this room by {username}",
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'profile_pic': usersget('robozo', {}).get('profile_pic', 'default.png'),
    }

    chatrooms[destination_room]['messages'].append(message)
    save_data()

    return jsonify({"success": True})

@app.route('/create_rickroll_room', methods=['POST'])
def create_rickroll_room():
    if 'username' not in session:
        return jsonify({"error": "Not logged in"}), 401

    username = session['username']

    # Check if user is admin
    is_admin = users.get(username, {}).get('is_admin', False)

    if not is_admin:
        return jsonify({"error": "You don't have permission to create special rooms"}), 403

    # Create a unique ID for the chatroom with 'rickroll' prefix
    room_id = 'rickroll_' + ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))

    # Create the rickroll room
    chatrooms[room_id] = {
        'name': '🎵 Never Gonna Give You Up 🎵',
        'messages': [],
        'members': [],
        'created_by': username,
        'is_private': True,
        'is_rickroll_room': True  # Special flag for rickroll rooms
    }

    save_data()
    return jsonify({"success": True, "room_id": room_id})

@app.route('/check_rickroll_status')
def check_rickroll_status():
    if 'username' not in session:
        return jsonify({"is_rickrolled": False}), 401

    username = session['username']
    is_rickrolled = users.get(username, {}).get('is_rickrolled', False)
    return jsonify({"is_rickrolled": is_rickrolled, "force_reload": True})

@app.route('/rickroll_user', methods=['POST'])
def rickroll_user():
    if 'username' not in session:
        return jsonify({"error": "Not logged in"}), 401

    username = session['username']
    target_user = request.form.get('username')
    as_system = request.form.get('as_system') == 'true'

    # Check if user is admin
    is_admin = users.get(username, {}).get('is_admin', False)

    if not is_admin:
        return jsonify({"error": "You don't have permission to rickroll users"}), 403

    if not target_user or target_user not in users:
        return jsonify({"error": "Invalid user"}), 400

    # First, find or create a rickroll room
    rickroll_room_id = None
    for room_id, room in chatrooms.items():
        if room.get('is_rickroll_room'):
            rickroll_room_id = room_id
            break

    # Create a new rickroll room if none exists
    if not rickroll_room_id:
        # Create a unique ID for the rickroll room
        rickroll_room_id = 'rickroll_' + ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))

        # Create the special rickroll chatroom
        chatrooms[rickroll_room_id] = {
            'name': '🎵 Never Gonna Give You Up 🎵',
            'messages': [],
            'members': [target_user],
            'created_by': username,
            'is_private': True,
            'is_rickroll_room': True  # Special flag for rickroll rooms
        }
    else:
                # Add the user to the existing rickroll room
        if target_user not in chatrooms[rickroll_room_id]['members']:
            chatrooms[rickroll_room_id]['members'].append(target_user)

    # Add rickroll room to user's joined rooms and make it their current room
    if 'joined_chatrooms' not in users[target_user]:
        users[target_user]['joined_chatrooms'] = []

    if rickroll_room_id not in users[target_user]['joined_chatrooms']:
        users[target_user]['joined_chatrooms'].append(rickroll_room_id)

    # Flag the user as rickrolled
    users[target_user]['is_rickrolled'] = True
    users[target_user]['current_room'] = rickroll_room_id

    # No message in general chat - stealth rickroll
    save_data()

    return jsonify({"success": True, "room_id": rickroll_room_id})

@app.route('/add_user_to_room', methods=['POST'])
def add_user_to_room():
    if 'username' not in session:
        return jsonify({"error": "Not logged in"}), 401

    username = session['username']
    target_user = request.form.get('username')
    chatroom_id = request.form.get('chatroom_id')

    # Check if user is admin
    is_admin = users.get(username, {}).get('is_admin', False)

    if not is_admin:
        return jsonify({"error": "You don't have permission to add users to rooms"}), 403

    if not target_user or not chatroom_id:
        return jsonify({"error": "Username and chatroom are required"}), 400

    if chatroom_id not in chatrooms:
        return jsonify({"error": "Chatroom does not exist"}), 404

    if target_user not in users:
        return jsonify({"error": "User does not exist"}), 404

    # Add user to chatroom if not already a member
    if target_user not in chatrooms[chatroom_id]['members']:
        chatrooms[chatroom_id]['members'].append(target_user)

        # Update user's joined chatrooms
        if 'joined_chatrooms' not in users[target_user]:
            users[target_user]['joined_chatrooms'] = []

        if chatroom_id not in users[target_user]['joined_chatrooms']:
            users[target_user]['joined_chatrooms'].append(chatroom_id)

        # Create a notification message in the chatroom
        message_id = f"{int(time.time())}-{random.randint(1000, 9999)}"
        message = {
            'id': message_id,
            'user': 'SYSTEM',
            'content': f"{target_user} has been added to this room by {username}",
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'profile_pic': 'default.png',
            'is_system': True
        }

        chatrooms[chatroom_id]['messages'].append(message)
        save_data()

        return jsonify({"success": True})
    else:
        return jsonify({"error": "User is already a member of this chatroom"}), 409

@app.route('/kick_user', methods=['POST'])
def kick_user():
    if 'username' not in session:
        return jsonify({"error": "Not logged in"}), 401

    username = session['username']
    target_user = request.form.get('username')
    chatroom_id = request.form.get('chatroom_id')

    # Check if user is admin
    is_admin = users.get(username, {}).get('is_admin', False)
    print(f"User {username} admin status: {is_admin}")

    if not is_admin:
        return jsonify({"error": "You don't have permission to kick users"}), 403

    if not target_user or not chatroom_id:
        return jsonify({"error": "Username and chatroom are required"}), 400

    if chatroom_id not in chatrooms:
        return jsonify({"error": "Chatroom does not exist"}), 404

    if target_user not in chatrooms[chatroom_id]['members']:
        return jsonify({"error": "User is not in this chatroom"}), 404

    # Remove user from chatroom
    chatrooms[chatroom_id]['members'].remove(target_user)

    # Remove chatroom from user's joined chatrooms
    if target_user in users and 'joined_chatrooms' in users[target_user]:
        if chatroom_id in users[target_user]['joined_chatrooms']:
            users[target_user]['joined_chatrooms'].remove(chatroom_id)

    save_data()

    return jsonify({"success": True})

@app.route('/delete_user', methods=['POST'])
def delete_user():
    if 'username' not in session:
        return jsonify({"error": "Not logged in"}), 401

    username = session['username']
    target_user = request.form.get('username')

    # Check if user is admin
    is_admin = users.get(username, {}).get('is_admin', False)

    if not is_admin:
        return jsonify({"error": "You don't have permission to delete users"}), 403

    if not target_user:
        return jsonify({"error": "Username is required"}), 400

    if target_user == ADMIN_USERNAME:
        return jsonify({"error": "Cannot delete the admin user"}), 403

    if target_user not in users:
        return jsonify({"error": "User does not exist"}), 404

    # Remove user from all chatrooms
    for room_id in list(chatrooms.keys()):
        if target_user in chatrooms[room_id]['members']:
            chatrooms[room_id]['members'].remove(target_user)

    # Delete user
    del users[target_user]

    save_data()

    return jsonify({"success": True})

@app.route('/delete_chatroom', methods=['POST'])
def delete_chatroom():
    if 'username' not in session:
        return jsonify({"error": "Not logged in"}), 401

    username = session['username']
    chatroom_id = request.form.get('chatroom_id')

    # Check if user is admin
    is_admin = users.get(username, {}).get('is_admin', False)

    if not is_admin:
        return jsonify({"error": "You don't have permission to delete chatrooms"}), 403

    if not chatroom_id:
        return jsonify({"error": "Chatroom ID is required"}), 400

    if chatroom_id not in chatrooms:
        return jsonify({"error": "Chatroom does not exist"}), 404

    if chatroom_id == 'general':
        return jsonify({"error": "Cannot delete the general chatroom"}), 403

    # Prevent permanent rooms from being deleted
    if chatrooms[chatroom_id].get('is_permanent', False):
        return jsonify({"error": "Cannot delete a permanent chatroom"}), 403

    # Remove chatroom from all users' joined_chatrooms
    for user_id in users:
        if 'joined_chatrooms' in users[user_id] and chatroom_id in users[user_id]['joined_chatrooms']:
            users[user_id]['joined_chatrooms'].remove(chatroom_id)

    # Delete chatroom
    del chatrooms[chatroom_id]

    save_data()

    # If current chatroom was deleted, switch to general
    if session.get('current_chatroom') == chatroom_id:
        session['current_chatroom'] = 'general'

    return jsonify({"success": True})

# Cache for message responses
message_cache = {}

@app.route('/messages', methods=['GET'])
def get_messages():
    if 'username' not in session:
        return jsonify({"error": "Not logged in"}), 401

    # If requesting user style information
    get_user_style = request.args.get('get_user_style')
    if get_user_style and get_user_style in users:
        user_style = {
            'name_color': users[get_user_style].get('name_color', '#000000'),
            'name_font': users[get_user_style].get('name_font', 'Arial, sans-serif')
        }
        return jsonify(user_style)

    room_id = request.args.get('room_id', session.get('current_chatroom', 'general'))

    if room_id not in chatrooms:
        return jsonify([])

    # Get client's cache parameter - use timestamp directly
    client_cache_param = request.args.get('_')

    # Get username for user-specific cache
    username = session.get('username', 'anonymous')

    # Use room_id, username and timestamp for better caching
    cache_key = f"{room_id}_{username}_{client_cache_param}"
    messages = chatrooms[room_id]['messages']

    # Only return actual message data if needed
    message_count = len(messages)

    # If no new messages since last request, return 304 Not Modified
    if cache_key in message_cache and message_count > 0:
        if message_cache[cache_key] == message_count:
            return "", 304

    # Update cache with current message count
    message_cache[cache_key] = message_count

    # More aggressive cache cleanup
    if len(message_cache) > 500:
        # Remove oldest 40% of entries
        keys_to_remove = sorted(message_cache.keys())[:200]
        for key in keys_to_remove:
            message_cache.pop(key, None)

    # Return only the most recent 50 messages for faster transmission
    return jsonify(messages[-50:] if len(messages) > 50 else messages)

@app.route('/send_file', methods=['POST'])
def send_file():
    if 'username' not in session:
        return jsonify({"error": "You must be logged in to send files"}), 401

    username = session['username']
    room_id = request.form.get('room_id', session.get('current_chatroom', 'general'))
    message_content = request.form.get('message', '')

    # Check if the user is admin
    is_admin = users.get(username, {}).get('is_admin', False)

    # Allow all users to send files
    pass

    if room_id not in chatrooms:
        return jsonify({"error": "Chatroom does not exist"}), 404

    if username not in chatrooms[room_id]['members']:
        return jsonify({"error": "You are not a member of this chatroom"}), 403

    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(f"{username}_{int(time.time())}_{file.filename}")
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # Generate a unique message ID
        message_id = f"{int(time.time())}-{random.randint(1000, 9999)}"

        message = {
            'id': message_id,
            'user': username,
            'content': message_content,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'profile_pic': users[username]['profile_pic'],
            'file_path': f"/static/uploads/{filename}",
            'file_name': file.filename,
            'file_type': file.content_type
        }

        chatrooms[room_id]['messages'].append(message)
        save_data()
        return jsonify({"success": True})

    return jsonify({"error": "File type not allowed"}), 400

@app.route('/send', methods=['POST'])
def send_message():
    if 'username' not in session:
        return jsonify({"error": "You must be logged in to send messages"}), 401

    username = session['username']
    content = request.form.get('message')
    room_id = request.form.get('room_id', session.get('current_chatroom', 'general'))
    as_system = request.form.get('as_system') == 'true'

    # Check if the user is admin
    is_admin = users.get(username, {}).get('is_admin', False)

    # Allow all users to send messages
    pass

    # Only admins can send as system
    if as_system and not is_admin:
        return jsonify({"error": "Only admins can send messages as system"}), 403

    if room_id not in chatrooms:
        return jsonify({"error": "Chatroom does not exist"}), 404

    if username not in chatrooms[room_id]['members']:
        return jsonify({"error": "You are not a member of this chatroom"}), 403

    if content and content.strip():
        # Check for ping command
        ping_target = None
        whisper_content = None
        if content.startswith('/ping '):
            parts = content.split(' ', 2)
            if len(parts) >= 2:
                ping_target = parts[1].strip()
                # If there's a message after the username
                ping_message = parts[2] if len(parts) > 2 else ""

                # Verify the target user exists
                if ping_target in users:
                    # Add a special ping flag to the message
                    content = f"🔔 <span class='ping-highlight'>@{ping_target}</span> {ping_message}"
                else:
                    content = f"⚠️ User '{ping_target}' not found."
                    ping_target = None


        # Generate a unique message ID
        message_id = f"{int(time.time())}-{random.randint(1000, 9999)}"

        message = {
            'id': message_id,
            'user': 'SYSTEM' if as_system else username,
            'content': content,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'profile_pic': 'default.png' if as_system else users[username]['profile_pic'],
            'is_system': as_system
        }

        # Add ping info if it's a ping message
        if ping_target:
            message['is_ping'] = True
            message['ping_target'] = ping_target
            message['ping_sender'] = username

        # Add whisper info if it's a whisper message
        if whisper_content:
            message['is_whisper'] = True
            message['whisper_content'] = whisper_content

        chatrooms[room_id]['messages'].append(message)
        save_data()
        return jsonify({"success": True})
    return jsonify({"error": "Message cannot be empty"}), 400

@app.route('/delete_message', methods=['POST'])
def delete_message():
    if 'username' not in session:
        return jsonify({"error": "Not logged in"}), 401

    username = session['username']
    message_id = request.form.get('message_id')
    room_id = request.form.get('room_id', session.get('current_chatroom', 'general'))

    if not message_id or room_id not in chatrooms:
        return jsonify({"error": "Invalid request"}), 400

    is_admin = users.get(username, {}).get('is_admin', False)

    # Find and delete the message
    for i, message in enumerate(chatrooms[room_id]['messages']):
        if message['id'] == message_id:
            # Only allow deletion if user is the message author or an admin
            if message['user'] == username or is_admin:
                # Completely remove the message
                del chatrooms[room_id]['messages'][i]
                save_data()
                return jsonify({"success": True})
            else:
                return jsonify({"error": "You cannot delete other users' messages"}), 403

    return jsonify({"error": "Message not found"}), 404

@app.route('/clear_messages', methods=['POST'])
def clear_messages():
    if 'username' not in session:
        return jsonify({"error": "Not logged in"}), 401

    username = session['username']
    room_id = request.form.get('room_id', session.get('current_chatroom', 'general'))

    if room_id not in chatrooms:
        return jsonify({"error": "Chatroom does not exist"}), 404

    is_admin = users.get(username, {}).get('is_admin', False)

    # Only admins can clear the whole chat
    if not is_admin:
        return jsonify({"error": "You don't have permission to clear the chat"}), 403

    # Clear all messages in the chatroom
    chatrooms[room_id]['messages'] = []
    save_data()

    return jsonify({"success": True})

@app.route('/update_display_name', methods=['POST'])
def update_display_name():
    if 'username' not in session:
        return jsonify({"error": "Not logged in"}), 401

    username = session['username']
    display_name = request.form.get('display_name', '').strip()

    if username in users:
        users[username]['display_name'] = display_name
        save_data()
        return jsonify({"success": True})

    return jsonify({"error": "User not found"}), 404

@app.route('/update_status', methods=['POST'])
def update_status():
    if 'username' in session:
        username = session['username']
        status = request.form.get('status', 'online')

        if username in users:
            users[username]['online_status'] = status
            users[username]['last_active'] = datetime.now().timestamp()
            save_data()
            return jsonify({"success": True})
    return jsonify({"success": False}), 401

@app.route('/get_online_users')
def get_online_users():
    if 'username' not in session:
        return jsonify({"error": "Not logged in"}), 401

    online_users = {}
    current_time = datetime.now().timestamp()
    # Consider users offline after 20 seconds of inactivity
    timeout_period = 20  

    for user_id, user_data in users.items():
        last_active = user_data.get('last_active', 0)
        if current_time - last_active < timeout_period:
            online_users[user_id] = 'online'
        else:
            online_users[user_id] = 'offline'

    return jsonify(online_users)

@app.route('/reset_rickroll', methods=['POST'])
def reset_rickroll():
    if 'username' in session:
        username = session['username']
        if username in users:
            users[username]['is_rickrolled'] = False
            save_data()
            return jsonify({"success": True})
    return jsonify({"success": False}), 401

@app.route('/set_real_name', methods=['POST'])
def set_real_name():
    if 'username' not in session:
        return jsonify({"error": "Not logged in"}), 401

    username = session['username']
    real_name = request.form.get('real_name', '').strip()

    if not real_name:
        return jsonify({"error": "Real name cannot be empty"}), 400

    if username in users:
        users[username]['real_name'] = real_name
        # Set name status to done
        users[username]['name'] = 'done'
        # Add to the set of users who have set their real name
        global real_names_set
        real_names_set.add(username)
        # Remove the flag from session
        session['needs_real_name'] = False
        # Set default display settings for real name
        users[username]['show_in_room'] = True
        users[username]['show_in_chat'] = False
        users[username]['show_in_profile'] = False
        save_data()
        print(f"Real name set for {username}: {real_name}")
        return jsonify({"success": True})

    return jsonify({"error": "User not found"}), 404

@app.route('/remove_real_name', methods=['POST'])
def remove_real_name():
    if 'username' not in session:
        return jsonify({"error": "Not logged in"}), 401

    admin_username = session['username']
    if not users.get(admin_username, {}).get('is_admin', False):
        return jsonify({"error": "You don't have permission to remove real names"}), 403

    target_username = request.form.get('username')
    if not target_username or target_username not in users:
        return jsonify({"error": "Invalid username"}), 400

    # Remove real name
    users[target_username]['real_name'] = ''
    users[target_username]['name'] = 'ask'

    # Remove from the set of users who have set their real name
    global real_names_set
    if target_username in real_names_set:
        real_names_set.remove(target_username)

    save_data()
    print(f"Real name removed for {target_username} by admin {admin_username}")
    return jsonify({"success": True})

@app.route('/feedback')
def feedback_page():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('feedback.html')

@app.route('/submit_feedback', methods=['POST'])
def submit_feedback():
    if 'username' not in session:
        return jsonify({"error": "Not logged in"}), 401

    username = session['username']
    feedback_content = request.form.get('feedback')

    if not feedback_content or not feedback_content.strip():
        return jsonify({"error": "Feedback cannot be empty"}), 400

    # Create unique feedback ID
    feedback_id = f"{int(time.time())}-{random.randint(1000, 9999)}"

    # Add the feedback
    feedback.append({
        'id': feedback_id,
        'username': username,
        'content': feedback_content,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'read': False
    })

    save_data()

    return jsonify({"success": True})

@app.route('/admin/feedback')
def admin_feedback():
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']
    if not users.get(username, {}).get('is_admin', False):
        flash('You do not have permission to access this page')
        return redirect(url_for('home'))

    return render_template('feedback_list.html')

@app.route('/api/feedback')
def api_feedback():
    if 'username' not in session:
        return jsonify({"error": "Not logged in"}), 401

    username = session['username']
    if not users.get(username, {}).get('is_admin', False):
        return jsonify({"error": "Not authorized"}), 403

    # Return the feedback in reverse chronological order (newest first)
    return jsonify(sorted(feedback, key=lambda x: x['timestamp'], reverse=True))

@app.route('/admin/feedback/<feedback_id>/toggle_read', methods=['POST'])
def toggle_feedback_read(feedback_id):
    if 'username' not in session:
        return jsonify({"error": "Not logged in"}), 401

    username = session['username']
    if not users.get(username, {}).get('is_admin', False):
        return jsonify({"error": "Not authorized"}), 403

    for item in feedback:
        if item['id'] == feedback_id:
            item['read'] = not item['read']
            save_data()
            return jsonify({"success": True})

    return jsonify({"error": "Feedback not found"}), 404

@app.route('/admin/feedback/<feedback_id>/delete', methods=['POST'])
def delete_feedback(feedback_id):
    if 'username' not in session:
        return jsonify({"error": "Not logged in"}), 401

    username = session['username']
    if not users.get(username, {}).get('is_admin', False):
        return jsonify({"error": "Not authorized"}), 403

    global feedback
    feedback = [item for item in feedback if item['id'] != feedback_id]
    save_data()

    return jsonify({"success": True})

@app.route('/create_poll', methods=['POST'])
def create_poll():
    if 'username' not in session:
        return jsonify({"error": "Not logged in"}), 401

    username = session['username']

    # Only admins can create polls
    if not users.get(username, {}).get('is_admin', False):
        return jsonify({"error": "Only admins can create polls"}), 403

    question = request.form.get('question')
    options = request.form.getlist('options[]')
    allow_multiple = request.form.get('allow_multiple') == 'true'

    if not question or not options or len(options) < 2:
        return jsonify({"error": "Question and at least 2 options are required"}), 400

    # Create unique poll ID
    poll_id = f"poll_{int(time.time())}_{random.randint(1000, 9999)}"

    # Create poll structure
    poll = {
        'id': poll_id,
        'question': question,
        'options': options,
        'allow_multiple': allow_multiple,
        'created_by': username,
        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'active': True,
        'votes': {option: [] for option in options}  # Store usernames who voted for each option
    }

    # Add poll to the polls dict
    polls[poll_id] = poll

    # Add poll to polls chatroom
    if 'polls' not in chatrooms:
        chatrooms['polls'] = {
            'name': '📊 Polls',
            'messages': [],
            'members': [],
            'is_polls_room': True,
            'polls': []
        }

    # Create a message to announce the poll
    message_id = f"{int(time.time())}-{random.randint(1000, 9999)}"
    poll_message = {
        'id': message_id,
        'user': 'SYSTEM',
        'content': f"📊 New Poll: {question}",
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'profile_pic': 'default.png',
        'is_system': True,
        'is_poll': True,
        'poll_id': poll_id
    }

    chatrooms['polls']['messages'].append(poll_message)
    save_data()

    return jsonify({"success": True, "poll_id": poll_id})

@app.route('/vote', methods=['POST'])
def vote_in_poll():
    if 'username' not in session:
        return jsonify({"error": "Not logged in"}), 401

    username = session['username']
    poll_id = request.form.get('poll_id')
    remove_vote = request.form.get('remove_vote') == 'true'

    if not poll_id:
        return jsonify({"error": "Poll ID is required"}), 400

    if poll_id not in polls:
        return jsonify({"error": "Poll not found"}), 404

    poll = polls[poll_id]

    if not poll['active']:
        return jsonify({"error": "This poll is closed"}), 400

    # If we're just removing votes
    if remove_vote:
        # Remove all votes by this user
        for option in poll['votes']:
            if username in poll['votes'][option]:
                poll['votes'][option].remove(username)
        save_data()
        return jsonify({"success": True})

    # Otherwise process normal voting
    option_indices = request.form.getlist('option_index[]')
    if not option_indices:
        return jsonify({"error": "Option indices are required when voting"}), 400

    # Convert option indices to integers
    option_indices = [int(idx) for idx in option_indices]

    # Validate option indices
    for idx in option_indices:
        if idx < 0 or idx >= len(poll['options']):
            return jsonify({"error": "Invalid option index"}), 400

    # If multiple votes are not allowed, ensure only one option is selected
    if not poll['allow_multiple'] and len(option_indices) > 1:
        return jsonify({"error": "Multiple votes are not allowed for this poll"}), 400

    # Remove previous votes by this user
    for option in poll['votes']:
        if username in poll['votes'][option]:
            poll['votes'][option].remove(username)

    # Add new votes
    for idx in option_indices:
        option = poll['options'][idx]
        poll['votes'][option].append(username)

    save_data()

    return jsonify({"success": True})

@app.route('/close_poll', methods=['POST'])
def close_poll():
    if 'username' not in session:
        return jsonify({"error": "Not logged in"}), 401

    username = session['username']

    # Only admins can close polls
    if not users.get(username, {}).get('is_admin', False):
        return jsonify({"error": "Only admins can close polls"}), 403

    poll_id = request.form.get('poll_id')

    if not poll_id:
        return jsonify({"error": "Poll ID is required"}), 400

    if poll_id not in polls:
        return jsonify({"error": "Poll not found"}), 404

    polls[poll_id]['active'] = False

    # Create a message to announce the poll closure
    message_id = f"{int(time.time())}-{random.randint(1000, 9999)}"

    # Calculate results
    results = {}
    for option, voters in polls[poll_id]['votes'].items():
        results[option] = len(voters)

    # Find winning option(s)
    if results:
        max_votes = max(results.values())
        winning_options = [option for option, votes in results.items() if votes == max_votes]

        result_message = f"📊 Poll Closed: \"{polls[poll_id]['question']}\"\n\nResults:\n"
        for option in polls[poll_id]['options']:
            vote_count = len(polls[poll_id]['votes'][option])
            result_message += f"- {option}: {vote_count} vote(s)"
            if option in winning_options and max_votes > 0:
                result_message += " 🏆"
            result_message += "\n"
    else:
        result_message = f"📊 Poll Closed: \"{polls[poll_id]['question']}\"\n\nNo votes were cast."

    poll_closure = {
        'id': message_id,
        'user': 'SYSTEM',
        'content': result_message,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'profile_pic': 'default.png',
        'is_system': True,
        'is_poll_result': True,
        'poll_id': poll_id
    }

    chatrooms['polls']['messages'].append(poll_closure)
    save_data()

    return jsonify({"success": True})

@app.route('/clear_all_polls', methods=['POST'])
def clear_all_polls():
    if 'username' not in session:
        return jsonify({"error": "Not logged in"}), 401

    username = session['username']

    # Only admins can clear all polls
    if not users.get(username, {}).get('is_admin', False):
        return jsonify({"error": "Only admins can clear all polls"}), 403

    # Clear all polls
    global polls
    polls = {}

    # Create a system message to announce polls were cleared
    message_id = f"{int(time.time())}-{random.randint(1000, 9999)}"
    poll_cleared_message = {
        'id': message_id,
        'user': 'SYSTEM',
        'content': f"📊 All polls have been cleared by {username}",
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'profile_pic': 'default.png',
        'is_system': True
    }

    # Add message to polls chatroom
    if 'polls' in chatrooms:
        chatrooms['polls']['messages'].append(poll_cleared_message)

    save_data()

    return jsonify({"success": True})

@app.route('/get_polls')
def get_polls():
    if 'username' not in session:
        return jsonify({"error": "Not logged in"}), 401

    # Return all polls with their current results
    poll_data = {}
    for poll_id, poll in polls.items():
        # Clone the poll data without the votes list to avoid exposing who voted for what
        poll_info = {
            'id': poll['id'],
            'question': poll['question'],
            'options': poll['options'],
            'allow_multiple': poll['allow_multiple'],
            'created_by': poll['created_by'],
            'created_at': poll['created_at'],
            'active': poll['active'],
            'results': {option: len(voters) for option, voters in poll['votes'].items()},
            'user_votes': {}
        }

        # Add info about which options the current user voted for
        username = session['username']
        for option, voters in poll['votes'].items():
            poll_info['user_votes'][option] = username in voters

        poll_data[poll_id] = poll_info

    return jsonify(poll_data)

@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)

# Create default admin profile picture if it doesn't exist
if not os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], 'pfp', 'default.png')):
    from PIL import Image, ImageDraw

    # Create a simple default profile image
    img = Image.new('RGB', (200, 200), color=(73, 109, 137))
    d = ImageDraw.Draw(img)
    d.ellipse((50, 50, 150, 150), fill=(255, 255, 255))

    img.save(os.path.join(app.config['UPLOAD_FOLDER'], 'pfp', 'default.png'))

@app.route('/edit_message', methods=['POST'])
def edit_message():
    if 'username' not in session:
        return jsonify({"error": "Not logged in"}), 401

    username = session['username']
    message_id = request.form.get('message_id')
    new_content = request.form.get('new_content')
    room_id = request.form.get('room_id')

    if not message_id or not new_content or not room_id:
        return jsonify({"error": "Invalid request"}), 400

    if room_id not in chatrooms:
        return jsonify({"error": "Chatroom not found"}), 404

    is_admin = users.get(username, {}).get('is_admin', False)

    for i, message in enumerate(chatrooms[room_id]['messages']):
        if message['id'] == message_id:
            if message['user'] == username or is_admin:
                # Update message content and add edited info
                message['content'] = new_content
                message['edited'] = True
                message['edited_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                # Force cache invalidation by updating message ID
                message['id'] = f"{int(time.time())}-{random.randint(1000, 9999)}"
                save_data()
                return jsonify({"success": True})
            else:
                return jsonify({"error": "You cannot edit other users' messages"}), 403

    return jsonify({"error": "Message not found"}), 404

if __name__ == '__main__':
    # Save data before starting
    save_data()
    app.run(host='0.0.0.0', port=8080, debug=False)