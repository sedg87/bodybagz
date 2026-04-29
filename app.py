from flask import Flask, redirect, render_template, url_for, session, request, flash
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import random
import os
from werkzeug.utils import secure_filename
from datetime import datetime
from collections import defaultdict
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

app = Flask(__name__)

DATABASE = 'database.db'

app.config['ADMIN_AVATAR'] = '/static/images/me.jpeg'
app.config['ADMIN_NAME'] = 'Craig'

UPLOAD_FOLDER= 'static/uploads'
ALLOWED_EXTENSIONS = ('png', 'jpg', 'jpeg', 'gif', 'webp')

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

# For Contact Form
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"]
)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Horror Quotes
HORROR_QUOTES = [
    "God is in his holy temple",
    "They come at night...mostly",
    "Sweets to the sweets",
    "You can't see the eyes of the demon, until 'im come callin'",
    "This...is God!",
    "They're here!",
    "This is my...boomstick!",
    "I have such sights to show you",
    "Would you like some...wishes"
]

# Date Filter For Posts
@app.template_filter('format_date')
def format_date(date_str):
    dt = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
    # Format: Feb 23, 3:45pm
    formatted = dt.strftime('%b %d, %I:%M%p').lower()
    # Remove leading zero from day (Feb 03 -> Feb 3)
    formatted = formatted.replace(' 0', ' ')
    return formatted

# Date Filter For Coming Soon
@app.template_filter('format_release_date')
def format_release_date(date_str):
    if not date_str:
        return "TBA"
    dt = datetime.strptime(date_str, '%Y-%m-%d')
    return dt.strftime('%B %d, %Y')  # February 27, 2026

# DB Helper
def db_helper():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# Rating Filter
@app.template_filter('stars')
def stars(rating):
    if not rating:
        return ""
    filled = '<i class="fa-solid fa-star"></i>' * int(rating)
    empty = '<i class="fa-regular fa-star"></i>' * (5 - int(rating))
    return filled + empty



# DB Init
def init_db():

    with db_helper() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                password TEXT NOT NULL,
                full_name TEXT NOT NULL,
                is_admin INTEGER DEFAULT 0
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                author_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                image_url TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS movies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL UNIQUE,
                genre TEXT NOT NULL,
                year_released TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS my_favourites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL UNIQUE,
                genre TEXT NOT NULL,
                year_released TEXT NOT NULL,
                comments TEXT NOT NULL,
                thumbnail TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS contact (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                reason TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        print("Database up and running!")

# Home
@app.route('/')
def home():
    with db_helper() as conn:
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM posts WHERE category = "Reviews" ORDER BY created_at DESC LIMIT 4')
        reviews = cursor.fetchall()

        cursor.execute('SELECT * FROM posts WHERE category = "Coming Soon" ORDER BY created_at DESC LIMIT 4')
        coming_soon = cursor.fetchall()

        cursor.execute('''
            SELECT * FROM posts 
            WHERE category NOT IN ("Coming Soon") 
            ORDER BY created_at DESC
        ''')
        posts = cursor.fetchall()

        cursor.execute('SELECT * FROM posts WHERE is_featured = 1 LIMIT 2')
        featured = cursor.fetchall()

        # Top rated reviews
        cursor.execute('''
            SELECT * FROM posts 
            WHERE category = "Reviews" AND rating IS NOT NULL 
            ORDER BY rating DESC, views DESC 
            LIMIT 4
        ''')
        top_rated = cursor.fetchall()

    return render_template('index.html', reviews=reviews, coming_soon=coming_soon, posts=posts[:10], total_posts=len(posts), featured=featured, top_rated=top_rated)

# Movies
@app.route('/movies')
def movies():
    with db_helper() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM posts 
            WHERE media_type = "Movie" OR category = "Movies"
            ORDER BY created_at DESC
        ''')
        all_movie_posts = cursor.fetchall()

    # Sort in Python for different sections
    popular = sorted(all_movie_posts, key=lambda p: p['views'] or 0, reverse=True)[:10]
    recent = all_movie_posts[:10]  # Already sorted by created_at

    return render_template('movies.html', popular=popular, recent=recent, all_posts=all_movie_posts[:10])

# TV
@app.route('/tv')
def tv():
    with db_helper() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM posts 
            WHERE media_type = "TV" OR category = "TV"
            ORDER BY created_at DESC
        ''')
        all_tv_posts = cursor.fetchall()

    # Sort in Python for different sections
    popular = sorted(all_tv_posts, key=lambda p: p['views'] or 0, reverse=True)[:10]
    recent = all_tv_posts[:10]  # Already sorted by created_at

    return render_template('tv.html', popular=popular, recent=recent, all_posts=all_tv_posts[:10])

# Games
@app.route('/games')
def games():
    with db_helper() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM posts 
            WHERE media_type = "Game" OR category = "Games"
            ORDER BY created_at DESC
        ''')
        all_game_posts = cursor.fetchall()

    # Sort in Python for different sections
    popular = sorted(all_game_posts, key=lambda p: p['views'] or 0, reverse=True)[:10]
    recent = all_game_posts[:10]  # Already sorted by created_at

    return render_template('games.html', popular=popular, recent=recent, all_posts=all_game_posts[:10])


# Reviews
@app.route('/reviews')
def reviews():
    with db_helper() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM posts 
            WHERE category = "Reviews"
            ORDER BY created_at DESC
        ''')
        all_review_posts = cursor.fetchall()

    # Sort in Python for different sections
    popular = sorted(all_review_posts, key=lambda p: p['views'] or 0, reverse=True)[:10]
    recent = all_review_posts[:10]  # Already sorted by created_at

    return render_template('reviews.html', popular=popular, recent=recent, all_posts=all_review_posts[:10])

# Lists
@app.route('/lists')
def lists():
    with db_helper() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM posts 
            WHERE category = "Lists"
            ORDER BY created_at DESC
        ''')
        all_list_posts = cursor.fetchall()

    # Sort in Python for different sections
    popular = sorted(all_list_posts, key=lambda p: p['views'] or 0, reverse=True)[:10]
    recent = all_list_posts[:10]  # Already sorted by created_at

    return render_template('lists.html', popular=popular, recent=recent, all_posts=all_list_posts[:10])

# Opinion
@app.route('/opinion')
def opinion():
    with db_helper() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM posts 
            WHERE category = "Opinion"
            ORDER BY created_at DESC
        ''')
        all_opinion_posts = cursor.fetchall()

    # Sort in Python for different sections
    popular = sorted(all_opinion_posts, key=lambda p: p['views'] or 0, reverse=True)[:10]
    recent = all_opinion_posts[:10]  # Already sorted by created_at

    return render_template('opinion.html', popular=popular, recent=recent, all_posts=all_opinion_posts[:10])


# Upcoming
@app.route('/upcoming')
def upcoming():
    with db_helper() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM posts 
            WHERE category = "Coming Soon"
            ORDER BY created_at DESC
        ''')
        all_upcoming_posts = cursor.fetchall()

    # Sort in Python for different sections
    popular = sorted(all_upcoming_posts, key=lambda p: p['views'] or 0, reverse=True)[:10]
    recent = all_upcoming_posts[:10]  # Already sorted by created_at

    return render_template('upcoming.html', popular=popular, recent=recent, all_posts=all_upcoming_posts[:10])

# About
@app.route('/about')
def about():
    return render_template('about.html')

# Contact
@app.route('/contact', methods=['GET', 'POST'])
@limiter.limit("5 per hour", methods=["POST"])
def contact():
    if request.method == 'POST':
        if request.form.get('website'):
            return redirect(url_for('home'))

        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        reason = request.form.get('reason', '').strip()
        message = request.form.get('message', '').strip()

        if len(message) > 1000 or len(name) > 100 or len(email) > 100:
            return "Message too long", 400

        if not all([name, email, reason, message]):
            return "Please fill in all fields", 400

        with db_helper() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO contact (name, email, reason, message)
                VALUES (?, ?, ?, ?)
            ''', (name, email, reason, message))
            conn.commit()

        flash('Thanks for your message! We will get back to you soon.')
        return redirect(url_for('contact'))

    return render_template('contact.html')

# Search
@app.route('/search')
def search():
    query = request.args.get('q', '')

    if not query:
        return redirect(url_for('home'))

    with db_helper() as conn:
        cursor = conn.cursor()
        cursor.execute('''
                    SELECT * FROM posts 
                    WHERE title LIKE ? OR content LIKE ? OR excerpt LIKE ?
                    ORDER BY created_at DESC
                ''', (f'%{query}%', f'%{query}%', f'%{query}%'))
        results = cursor.fetchall()

        return render_template('search.html', results=results, query=query)

# Admin
@app.route('/admin')
def admin():
    random_quote = random.choice(HORROR_QUOTES)

    if 'user_id' not in session or session.get('is_admin') != 1:
        return redirect(url_for('login'))

    with db_helper() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM posts 
            ORDER BY created_at DESC
        ''')
        all_posts = cursor.fetchall()

    # Group by category in Python (super fast for small/medium data)
    grouped = defaultdict(list)
    for post in all_posts:
        cat = post['category']  # or post['category'].strip() if needed
        grouped[cat].append(post)

    # Now pull out the ones you want to pass to the template
    # (if a category has no posts → empty list, which is fine)
    posts     = all_posts  # still useful to have the full list somewhere
    reviews   = grouped.get("Reviews", [])
    news      = grouped.get("News", [])
    opinions  = grouped.get("Opinion", [])
    upcoming  = grouped.get("Coming Soon", [])
    lists     = grouped.get("Lists", [])
    cryptids  = grouped.get("Cryptids", [])

    return render_template(
        'admin.html',
        quote=random_quote,
        posts=posts,
        reviews=reviews,
        news=news,
        opinions=opinions,
        upcoming=upcoming,
        lists=lists,
        cryptids=cryptids
    )

# Quill Upload Limits
@app.route('/admin/upload-image', methods=['POST'])
def upload_image():
    if 'user_id' not in session or session.get('is_admin') != 1:
        return {'error': 'Unauthorized'}, 401

    image = request.files.get('image')
    if image and allowed_file(image.filename):
        filename = secure_filename(image.filename)
        import time
        filename = f"{int(time.time())}_{filename}"
        image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        return {'url': f'/static/uploads/{filename}'}

    return {'error': 'Invalid file'}, 400

# Admin Manage Posts
@app.route('/admin/manage_posts')
def manage_posts():
    random_quote = random.choice(HORROR_QUOTES)

    if 'user_id' not in session or session.get('is_admin') != 1:
        return redirect(url_for('login'))

    # One query — get everything we care about
    with db_helper() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM posts 
            ORDER BY created_at DESC
        ''')
        all_posts = cursor.fetchall()

    # Group by category in Python (super fast for small/medium data)
    grouped = defaultdict(list)
    for post in all_posts:
        cat = post['category']  # or post['category'].strip() if needed
        grouped[cat].append(post)

    # Now pull out the ones you want to pass to the template
    # (if a category has no posts → empty list, which is fine)
    posts     = all_posts  # still useful to have the full list somewhere
    reviews   = grouped.get("Reviews", [])
    news      = grouped.get("News", [])
    opinions  = grouped.get("Opinion", [])
    upcoming  = grouped.get("Coming Soon", [])
    lists     = grouped.get("Lists", [])
    cryptids  = grouped.get("Cryptids", [])
    movies = grouped.get("Movies", [])
    games = grouped.get("Games", [])
    tv = grouped.get("TV", [])

    # Also group by media_type for reviews/news/etc
    media_grouped = defaultdict(list)
    for post in all_posts:
        if post['media_type']:
            media_grouped[post['media_type']].append(post)

    # Get game-related posts (any category with media_type = Game)
    games_all = media_grouped.get("Game", [])
    movies_all = media_grouped.get("Movie", [])
    tv_all = media_grouped.get("TV", [])

    return render_template(
        'manage_posts.html',
        quote=random_quote,
        posts=posts,
        reviews=reviews,
        news=news,
        opinions=opinions,
        upcoming=upcoming,
        lists=lists,
        cryptids=cryptids,
        movies=movies_all,  # All movie-related posts
        games=games_all,  # All game-related posts
        tv=tv_all
    )



# Admin Add Post
@app.route('/admin/add_post', methods=['GET', 'POST'])
def add_post():
    random_quote = random.choice(HORROR_QUOTES)

    # Admin check
    if 'user_id' not in session or session.get('is_admin') != 1:
        return redirect(url_for('login'))

    if request.method == 'POST':
        # Get form data
        title = request.form.get('title')
        content = request.form.get('content')
        category = request.form.get('category')
        excerpt = request.form.get('excerpt')
        media_type = request.form.get('media_type')
        release_date = request.form.get('release_date')
        trailer_url = request.form.get('trailer_url')
        rating = request.form.get('rating')
        verdict = request.form.get('verdict')
        played_on = request.form.get('played_on')
        developer = request.form.get('developer')
        platforms = request.form.get('platforms')
        genre = request.form.get('genre')
        cryptids = request.form.get('cryptids')
        image_caption = request.form.get('image_caption')
        starring = request.form.get('starring')
        director = request.form.get('director')
        synopsis = request.form.get('synopsis')
        is_featured = 1 if request.form.get('is_featured') else 0
        

        # Handle image upload
        image = request.files.get('image')
        image_filename = None

        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            # Add timestamp to make filename unique
            import time
            filename = f"{int(time.time())}_{filename}"
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            image_filename = f"/static/uploads/{filename}"

        # Insert into database
        with db_helper() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO posts (title, content, category, author_id, image_url, excerpt, media_type, release_date, trailer_url, rating, verdict, played_on, developer, platforms, genre, cryptids, image_caption, starring, director,
                synopsis, is_featured)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (title, content, category, session['user_id'], image_filename, excerpt, media_type, release_date, trailer_url, rating, verdict, played_on, developer, platforms, genre, cryptids, image_caption, starring, director,
                  synopsis, is_featured))
            conn.commit()

        return redirect(url_for('manage_posts'))

    return render_template('add_post.html', quote=random_quote)


# Post
@app.route('/post/<int:post_id>')
def view_post(post_id):
    with db_helper() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM posts WHERE id = ?', (post_id,))
        post = cursor.fetchone()

        if not post:
            return "Post not found", 404

        cursor.execute('UPDATE posts SET views = views + 1 WHERE id = ?', (post_id,))
        conn.commit()

        cursor.execute('SELECT * FROM posts ORDER BY views DESC LIMIT 5')
        trending = cursor.fetchall()

        # Get related posts by category, excluding current post
        cursor.execute('''
            SELECT * FROM posts 
            WHERE category = ? AND id != ?
            ORDER BY created_at DESC
            LIMIT 4
        ''', (post['category'], post_id))
        related = cursor.fetchall()

    return render_template('post.html', post=post, trending=trending, related=related)

# Delete Post
@app.route('/admin/delete-post/<int:post_id>', methods=['POST'])
def delete_post(post_id):
    # Admin check
    if 'user_id' not in session or session.get('is_admin') != 1:
        return redirect(url_for('login'))

    with db_helper() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM posts WHERE id = ?', (post_id,))
        conn.commit()

    return redirect(url_for('manage_posts'))

# Edit Post
@app.route('/admin/edit-post/<int:post_id>', methods=['GET', 'POST'])
def edit_post(post_id):
    random_quote = random.choice(HORROR_QUOTES)

    # Admin check
    if 'user_id' not in session or session.get('is_admin') != 1:
        return redirect(url_for('login'))

    if request.method == 'POST':
        # Get all form data
        title = request.form.get('title')
        content = request.form.get('content')
        category = request.form.get('category')
        excerpt = request.form.get('excerpt')
        media_type = request.form.get('media_type')
        release_date = request.form.get('release_date')
        trailer_url = request.form.get('trailer_url')
        rating = request.form.get('rating')
        verdict = request.form.get('verdict')
        played_on = request.form.get('played_on')
        developer = request.form.get('developer')
        platforms = request.form.get('platforms')
        genre = request.form.get('genre')
        cryptids = request.form.get('cryptids')
        image_caption = request.form.get('image_caption')
        starring = request.form.get('starring')
        director = request.form.get('director')
        synopsis = request.form.get('synopsis')
        is_featured = 1 if request.form.get('is_featured') else 0


        # Handle image upload (optional - only if new image uploaded)
        image_filename = None
        image = request.files.get('image')
        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            import time
            filename = f"{int(time.time())}_{filename}"
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            image_filename = f"/static/uploads/{filename}"

        # Update database
        with db_helper() as conn:
            cursor = conn.cursor()

            if image_filename:  # New image uploaded
                cursor.execute('''
                    UPDATE posts SET 
                    title=?, content=?, category=?, excerpt=?, media_type=?, 
                    release_date=?, trailer_url=?, rating=?, verdict=?, 
                    played_on=?, developer=?, platforms=?, image_url=?, genre=?,
                    cryptids=?, image_caption=?, starring=?, director=?, synopsis=?, is_featured=?
                    WHERE id=?
                ''', (title, content, category, excerpt, media_type, release_date,
                      trailer_url, rating, verdict, played_on, developer, platforms,
                      image_filename, genre, cryptids, image_caption, starring, director, synopsis, is_featured, post_id))
            else:  # Keep existing image
                cursor.execute('''
                    UPDATE posts SET 
                    title=?, content=?, category=?, excerpt=?, media_type=?, 
                    release_date=?, trailer_url=?, rating=?, verdict=?,
                    played_on=?, developer=?, platforms=?, genre=?,
                    cryptids=?, image_caption=?, starring=?, director=?, synopsis=?, is_featured=?
                    WHERE id=?
                ''', (title, content, category, excerpt, media_type, release_date,
                      trailer_url, rating, verdict, played_on, developer, platforms,
                      genre, cryptids, image_caption, starring, director, synopsis, is_featured, post_id))

            conn.commit()


        return redirect(url_for('manage_posts'))

    # GET - fetch post data
    with db_helper() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM posts WHERE id = ?', (post_id,))
        post = cursor.fetchone()

    if not post:
        return "Post not found", 404

    return render_template('edit_post.html', post=post, quote=random_quote)

# Load More Posts
@app.route('/api/load-more-posts')
def load_more_posts():
    offset = request.args.get('offset', 0, type=int)
    limit = request.args.get('limit', 10, type=int)
    media_type = request.args.get('media_type', '')
    category = request.args.get('category', '')

    with db_helper() as conn:
        cursor = conn.cursor()

        if media_type:
            cursor.execute('''
                SELECT * FROM posts 
                WHERE media_type = ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            ''', (media_type, limit, offset))
        elif category:
            cursor.execute('''
                SELECT * FROM posts 
                WHERE category = ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            ''', (category, limit, offset))
        else:
            cursor.execute('''
                SELECT * FROM posts 
                WHERE category NOT IN ("Coming Soon")
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            ''', (limit, offset))

        posts = cursor.fetchall()

    posts_list = []
    for post in posts:
        posts_list.append({
            'id': post['id'],
            'title': post['title'],
            'excerpt': post['excerpt'],
            'image_url': post['image_url'],
            'category': post['category'],
            'created_at': format_date(post['created_at'])
        })

    return {'posts': posts_list}

# Admin Messages
@app.route('/admin/inbox')
def inbox():
    random_quote = random.choice(HORROR_QUOTES)

    if 'user_id' not in session or session.get('is_admin') != 1:
        return redirect(url_for('login'))

    with db_helper() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM contact ORDER BY created_at DESC')
        messages = cursor.fetchall()

    return render_template('inbox.html', messages=messages, quote=random_quote)

# Admin Manage Users
@app.route('/admin/manage_users')
def manage_users():
    random_quote = random.choice(HORROR_QUOTES)

    if 'user_id' not in session or session.get('is_admin') != 1:
        return redirect(url_for('login'))

    return render_template('manage_users.html', quote=random_quote)



# Admin Favourites
@app.route('/admin/my_favourites')
def my_favourites():
    random_quote = random.choice(HORROR_QUOTES)

    if 'user_id' not in session or session.get('is_admin') != 1:
        return redirect(url_for('login'))

    with db_helper() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM my_favourites')
        favourites = cursor.fetchall()

    return render_template('my_favourites.html', quote=random_quote, favourites=favourites)

# Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        with db_helper() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id, email, password, is_admin, full_name FROM users WHERE email = ?', (email,))
            user = cursor.fetchone()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['full_name']
            session['is_admin'] = user['is_admin']

            return redirect(url_for('admin'))
        else:
            return "Invalid Login Info"

    return render_template('login.html')

# Register
@app.route('/register', methods=['GET', 'POST'])
def register():
    return render_template('register.html')


@app.route('/logout')
def logout():
    session.clear()

    return redirect(url_for('home'))










if __name__ == '__main__':
    init_db()
    app.run(debug=True)



