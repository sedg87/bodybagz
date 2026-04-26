from flask import Flask, render_template, redirect, session, url_for, request
import sqlite3
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'tanjiro-kamado-strongest'  # Change this in production!

DATABASE = 'database.db'

# Upload config for profile pics
UPLOAD_FOLDER = 'static/uploads/avatars'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                is_admin INTEGER DEFAULT 0,
                join_date TEXT NOT NULL,
                name TEXT,
                age INTEGER,
                phone TEXT,
                address TEXT,
                pin TEXT,
                profile_pic TEXT DEFAULT NULL
            )
        """)

        # Safe add profile_pic column if missing
        cursor.execute("PRAGMA table_info(users)")
        columns = [row['name'] for row in cursor.fetchall()]
        if 'profile_pic' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN profile_pic TEXT DEFAULT NULL")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                checkin_time TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        conn.commit()
    print("Database initialized!")


# ====================
# Home
# ====================
@app.route('/')
def home():
    return render_template('index.html')


# ====================
# Register
# ====================
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()

        if not all([username, email, password]):
            return "Please fill all fields"

        hashed_pw = generate_password_hash(password)
        join_date = datetime.now().strftime('%d/%m/%Y')

        try:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'INSERT INTO users (username, email, password, join_date) VALUES (?, ?, ?, ?)',
                    (username, email, hashed_pw, join_date)
                )
                conn.commit()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            return "Username or email already exists!"

    return render_template('register.html')


# ====================
# Login
# ====================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username_or_email = request.form.get('username_or_email', '').strip()
        password = request.form.get('password', '').strip()

        if not all([username_or_email, password]):
            return "Please enter username/email and password"

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT id, username, email, password, is_admin FROM users WHERE username = ? OR email = ?',
                (username_or_email, username_or_email)
            )
            user = cursor.fetchone()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['email'] = user['email']
            session['is_admin'] = user['is_admin']

            if user['is_admin'] == 1:
                return redirect(url_for('admin'))
            else:
                return redirect(url_for('dashboard'))
        else:
            return "Invalid username/email or password"

    return render_template('login.html')


# ====================
# Dashboard (user)
# ====================
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],))
        user = cursor.fetchone()

    return render_template('dashboard.html', user=user)


# ====================
# Admin Panel
# ====================
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if 'user_id' not in session or session.get('is_admin') != 1:
        return redirect(url_for('login'))

    message = None
    message_type = 'info'

    with get_db() as conn:
        cursor = conn.cursor()

        # Current admin's profile pic for top bar
        cursor.execute("SELECT profile_pic FROM users WHERE id = ?", (session['user_id'],))
        current_user = cursor.fetchone()

        # All users
        cursor.execute("""
            SELECT id, username, email, name, pin, join_date, profile_pic 
            FROM users 
            ORDER BY username
        """)
        users = cursor.fetchall()

        # Handle PIN update or photo upload
        if request.method == 'POST':
            user_id = request.form.get('user_id')

            # PIN update
            if 'pin' in request.form:
                new_pin = request.form.get('pin', '').strip()
                if not user_id or not new_pin:
                    message = "Please enter a PIN"
                    message_type = 'error'
                elif len(new_pin) != 4 or not new_pin.isdigit():
                    message = "PIN must be exactly 4 digits (0-9)"
                    message_type = 'error'
                else:
                    cursor.execute("SELECT id FROM users WHERE pin = ? AND id != ?", (new_pin, user_id))
                    if cursor.fetchone():
                        message = "This PIN is already used by another member"
                        message_type = 'error'
                    else:
                        cursor.execute("UPDATE users SET pin = ? WHERE id = ?", (new_pin, user_id))
                        conn.commit()
                        message = f"PIN updated for user #{user_id}"
                        message_type = 'success'

            # Profile picture upload
            if 'profile_pic' in request.files and user_id:
                file = request.files['profile_pic']
                if file and allowed_file(file.filename):
                    filename = secure_filename(f"user_{user_id}_{file.filename}")
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(filepath)
                    rel_path = f"/{filepath.replace(os.sep, '/')}"
                    cursor.execute("UPDATE users SET profile_pic = ? WHERE id = ?", (rel_path, user_id))
                    conn.commit()
                    message = f"Profile picture updated for user #{user_id}"
                    message_type = 'success'
                else:
                    message = "Invalid or no file selected"
                    message_type = 'error'

        # Attendance data
        cursor.execute("""
            SELECT 
                a.id, 
                a.checkin_time,
                u.username,
                u.name,
                u.pin
            FROM attendance a
            JOIN users u ON a.user_id = u.id
            ORDER BY a.checkin_time DESC
            LIMIT 50
        """)
        recent_checkins = cursor.fetchall()

        today_start = datetime.now().strftime('%Y-%m-%d 00:00:00')
        cursor.execute("SELECT COUNT(*) FROM attendance WHERE checkin_time >= ?", (today_start,))
        today_count = cursor.fetchone()[0]

        week_start = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d 00:00:00')
        cursor.execute("SELECT COUNT(*) FROM attendance WHERE checkin_time >= ?", (week_start,))
        week_count = cursor.fetchone()[0]

    return render_template('admin.html',
                           users=users,
                           recent_checkins=recent_checkins,
                           today_count=today_count,
                           week_count=week_count,
                           message=message,
                           message_type=message_type,
                           current_user=current_user)


# ====================
# User Profile
# ====================
@app.route('/profile/<int:user_id>')
def profile(user_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if session.get('is_admin') != 1 and session['user_id'] != user_id:
        return "Access denied", 403

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()

        if not user:
            return "User not found", 404

        cursor.execute("SELECT COUNT(*) FROM attendance WHERE user_id = ?", (user_id,))
        total_checkins = cursor.fetchone()[0]

        cursor.execute("SELECT MAX(checkin_time) FROM attendance WHERE user_id = ?", (user_id,))
        last_checkin = cursor.fetchone()[0] or "Never"

    return render_template('profile.html',
                           user=user,
                           total_checkins=total_checkins,
                           last_checkin=last_checkin,
                           is_admin=session.get('is_admin'))


# ====================
# Kiosk Check-In
# ====================
@app.route('/kiosk', methods=['GET', 'POST'])
def kiosk():
    error = None

    if request.method == 'POST':
        pin = request.form.get('pin', '').strip()

        if not pin or len(pin) != 4 or not pin.isdigit():
            error = "Please enter a valid 4-digit PIN"
        else:
            with get_db() as conn:
                cursor = conn.cursor()

                # Find user by PIN
                cursor.execute("SELECT id, username, name FROM users WHERE pin = ?", (pin,))
                user = cursor.fetchone()

                if user:
                    # Check for same-day duplicate check-in
                    today_start = datetime.now().strftime('%Y-%m-%d 00:00:00')
                    today_end = datetime.now().strftime('%Y-%m-%d 23:59:59')

                    cursor.execute("""
                        SELECT COUNT(*) FROM attendance 
                        WHERE user_id = ? 
                        AND checkin_time >= ? 
                        AND checkin_time <= ?
                    """, (user['id'], today_start, today_end))

                    already_checked = cursor.fetchone()[0] > 0

                    if already_checked:
                        error = f"You've already checked in today, {user['name'] or user['username']}! See you tomorrow 💪"
                    else:
                        # Record new check-in
                        checkin_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        cursor.execute(
                            "INSERT INTO attendance (user_id, checkin_time) VALUES (?, ?)",
                            (user['id'], checkin_time)
                        )
                        conn.commit()

                        # Get user's profile pic for success screen
                        cursor.execute("SELECT profile_pic FROM users WHERE id = ?", (user['id'],))
                        profile_data = cursor.fetchone()
                        profile_pic = profile_data['profile_pic'] if profile_data else None

                        display_name = user['name'] or user['username']
                        return render_template('kiosk_success.html',
                                               success_name=display_name,
                                               profile_pic=profile_pic)
                else:
                    error = "PIN not found — try again"

    return render_template('kiosk.html', error=error)


# ====================
# Logout
# ====================
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


if __name__ == '__main__':
    init_db()
    app.run(debug=True)