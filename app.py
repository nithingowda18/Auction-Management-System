from datetime import datetime, timedelta
from functools import wraps
import sqlite3
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, session, flash, g
from werkzeug.security import generate_password_hash, check_password_hash

BASE = Path(__file__).resolve().parent
app = Flask(__name__)
app.config['SECRET_KEY'] = 'change-this-demo-secret-before-deployment'
app.config['DATABASE'] = str(BASE / 'auction.db')

def db():
    if 'db' not in g:
        g.db = sqlite3.connect(app.config['DATABASE'])
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON')
    return g.db

@app.teardown_appcontext
def close_db(_error=None):
    conn = g.pop('db', None)
    if conn is not None: conn.close()

def init_db():
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.executescript('''
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
      email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS listings (
      id INTEGER PRIMARY KEY AUTOINCREMENT, seller_id INTEGER NOT NULL,
      title TEXT NOT NULL, description TEXT NOT NULL, category TEXT NOT NULL,
      starting_price REAL NOT NULL CHECK(starting_price > 0),
      ends_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active',
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(seller_id) REFERENCES users(id));
    CREATE TABLE IF NOT EXISTS bids (
      id INTEGER PRIMARY KEY AUTOINCREMENT, listing_id INTEGER NOT NULL,
      bidder_id INTEGER NOT NULL, amount REAL NOT NULL CHECK(amount > 0),
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(listing_id) REFERENCES listings(id),
      FOREIGN KEY(bidder_id) REFERENCES users(id));
    CREATE TABLE IF NOT EXISTS transactions (
      id INTEGER PRIMARY KEY AUTOINCREMENT, listing_id INTEGER NOT NULL UNIQUE,
      buyer_id INTEGER NOT NULL, amount REAL NOT NULL,
      status TEXT NOT NULL DEFAULT 'demo_pending',
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(listing_id) REFERENCES listings(id),
      FOREIGN KEY(buyer_id) REFERENCES users(id));
    ''')
    conn.commit(); conn.close()

def login_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get('user_id'):
            flash('Please sign in to continue.', 'warning'); return redirect(url_for('login'))
        return fn(*args, **kwargs)
    return wrapped

def current_user():
    if session.get('user_id'):
        return db().execute('SELECT id,name,email FROM users WHERE id=?',(session['user_id'],)).fetchone()
    return None

@app.context_processor
def inject_user(): return {'current_user': current_user(), 'now': datetime.now()}

@app.route('/')
def index():
    rows = db().execute('''SELECT l.*, u.name seller,
      COALESCE((SELECT MAX(amount) FROM bids WHERE listing_id=l.id),l.starting_price) current_price,
      (SELECT COUNT(*) FROM bids WHERE listing_id=l.id) bid_count
      FROM listings l JOIN users u ON u.id=l.seller_id
      WHERE l.status='active' AND l.ends_at>? ORDER BY l.created_at DESC''',(datetime.now().isoformat(timespec='minutes'),)).fetchall()
    return render_template('index.html', listings=rows)

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        name=request.form.get('name','').strip(); email=request.form.get('email','').strip().lower(); password=request.form.get('password','')
        if not name or not email or len(password)<8:
            flash('Enter your name and email, and use a password of at least 8 characters.', 'danger')
        else:
            try:
                cur=db().execute('INSERT INTO users(name,email,password_hash) VALUES(?,?,?)',(name,email,generate_password_hash(password)))
                db().commit(); session['user_id']=cur.lastrowid; flash('Account created. Welcome!', 'success'); return redirect(url_for('index'))
            except sqlite3.IntegrityError: flash('That email is already registered.', 'danger')
    return render_template('auth.html', mode='register')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method=='POST':
        user=db().execute('SELECT * FROM users WHERE email=?',(request.form.get('email','').strip().lower(),)).fetchone()
        if user and check_password_hash(user['password_hash'],request.form.get('password','')):
            session.clear(); session['user_id']=user['id']; flash('Signed in successfully.', 'success'); return redirect(url_for('index'))
        flash('Email or password is incorrect.', 'danger')
    return render_template('auth.html', mode='login')

@app.route('/logout')
def logout(): session.clear(); flash('You have signed out.', 'info'); return redirect(url_for('index'))

@app.route('/create', methods=['GET','POST'])
@login_required
def create_listing():
    if request.method=='POST':
        title=request.form.get('title','').strip(); desc=request.form.get('description','').strip(); category=request.form.get('category','Other').strip()
        try: price=float(request.form.get('starting_price','0'))
        except ValueError: price=0
        try: hours=int(request.form.get('hours','24'))
        except ValueError: hours=0
        if not title or not desc or price<=0 or not 1<=hours<=168:
            flash('Complete every field. Price must be positive and duration must be 1–168 hours.', 'danger')
        else:
            end=(datetime.now()+timedelta(hours=hours)).isoformat(timespec='minutes')
            db().execute('INSERT INTO listings(seller_id,title,description,category,starting_price,ends_at) VALUES(?,?,?,?,?,?)',(session['user_id'],title,desc,category,price,end)); db().commit()
            flash('Your auction is live.', 'success'); return redirect(url_for('index'))
    return render_template('create.html')

@app.route('/listing/<int:listing_id>')
def listing_detail(listing_id):
    item=db().execute('''SELECT l.*,u.name seller,COALESCE((SELECT MAX(amount) FROM bids WHERE listing_id=l.id),l.starting_price) current_price,
      (SELECT COUNT(*) FROM bids WHERE listing_id=l.id) bid_count FROM listings l JOIN users u ON u.id=l.seller_id WHERE l.id=?''',(listing_id,)).fetchone()
    if not item: flash('Auction not found.', 'danger'); return redirect(url_for('index'))
    bids=db().execute('SELECT b.amount,b.created_at,u.name bidder FROM bids b JOIN users u ON u.id=b.bidder_id WHERE b.listing_id=? ORDER BY b.amount DESC LIMIT 10',(listing_id,)).fetchall()
    return render_template('detail.html', item=item, bids=bids)

@app.route('/listing/<int:listing_id>/bid', methods=['POST'])
@login_required
def place_bid(listing_id):
    conn=db(); item=conn.execute('SELECT * FROM listings WHERE id=?',(listing_id,)).fetchone()
    if not item: flash('Auction not found.', 'danger'); return redirect(url_for('index'))
    if item['seller_id']==session['user_id']: flash('You cannot bid on your own listing.', 'warning'); return redirect(url_for('listing_detail',listing_id=listing_id))
    if item['status']!='active' or datetime.fromisoformat(item['ends_at'])<=datetime.now():
        flash('This auction has ended.', 'warning'); return redirect(url_for('listing_detail',listing_id=listing_id))
    try: amount=float(request.form.get('amount','0'))
    except ValueError: amount=0
    highest=conn.execute('SELECT MAX(amount) m FROM bids WHERE listing_id=?',(listing_id,)).fetchone()['m']
    minimum=(highest if highest is not None else item['starting_price']) + 0.01
    if amount < minimum:
        flash(f'Your bid must be at least ₹{minimum:.2f}.', 'danger')
    else:
        conn.execute('INSERT INTO bids(listing_id,bidder_id,amount) VALUES(?,?,?)',(listing_id,session['user_id'],amount)); conn.commit(); flash('Bid placed successfully!', 'success')
    return redirect(url_for('listing_detail',listing_id=listing_id))

@app.route('/dashboard')
@login_required
def dashboard():
    conn=db(); uid=session['user_id']
    my_listings=conn.execute('''SELECT l.*,COALESCE((SELECT MAX(amount) FROM bids WHERE listing_id=l.id),l.starting_price) current_price,
      (SELECT COUNT(*) FROM bids WHERE listing_id=l.id) bid_count FROM listings l WHERE seller_id=? ORDER BY created_at DESC''',(uid,)).fetchall()
    my_bids=conn.execute('''SELECT b.amount,b.created_at,l.id listing_id,l.title,l.ends_at,l.status,
      (SELECT MAX(amount) FROM bids WHERE listing_id=l.id) highest FROM bids b JOIN listings l ON l.id=b.listing_id WHERE b.bidder_id=? ORDER BY b.created_at DESC''',(uid,)).fetchall()
    wins=conn.execute('''SELECT l.id,l.title,t.amount,t.status,t.created_at FROM transactions t JOIN listings l ON l.id=t.listing_id WHERE t.buyer_id=? ORDER BY t.created_at DESC''',(uid,)).fetchall()
    return render_template('dashboard.html', my_listings=my_listings, my_bids=my_bids, wins=wins)

@app.route('/listing/<int:listing_id>/close', methods=['POST'])
@login_required
def close_auction(listing_id):
    conn=db(); item=conn.execute('SELECT * FROM listings WHERE id=?',(listing_id,)).fetchone()
    if not item or item['seller_id']!=session['user_id']:
        flash('Only the seller can close this auction.', 'danger'); return redirect(url_for('dashboard'))
    top=conn.execute('SELECT bidder_id,amount FROM bids WHERE listing_id=? ORDER BY amount DESC, id ASC LIMIT 1',(listing_id,)).fetchone()
    conn.execute("UPDATE listings SET status='closed' WHERE id=?",(listing_id,))
    if top:
        conn.execute("INSERT OR IGNORE INTO transactions(listing_id,buyer_id,amount,status) VALUES(?,?,?,'demo_pending')",(listing_id,top['bidder_id'],top['amount']))
    conn.commit(); flash('Auction closed. Any winning transaction is marked as demo-only; no payment was taken.', 'success'); return redirect(url_for('dashboard'))

@app.cli.command('seed-demo')
def seed_demo():
    'Add sample accounts and listings for a quick demonstration.'
    conn=db()
    users=[('Demo Seller','seller@example.com','DemoPass123!'),('Demo Buyer','buyer@example.com','DemoPass123!')]
    ids={}
    for name,email,pw in users:
        found=conn.execute('SELECT id FROM users WHERE email=?',(email,)).fetchone()
        if found: ids[email]=found['id']
        else:
            cur=conn.execute('INSERT INTO users(name,email,password_hash) VALUES(?,?,?)',(name,email,generate_password_hash(pw))); ids[email]=cur.lastrowid
    if conn.execute('SELECT COUNT(*) n FROM listings').fetchone()['n']==0:
        seller=ids['seller@example.com']
        samples=[('Vintage Film Camera','A classic 35mm film camera in good demo condition.','Electronics',2500),('Minimal Desk Lamp','A clean modern lamp for a home office.','Home',800),('Mechanical Keyboard','Compact mechanical keyboard for a desk setup.','Electronics',1800)]
        for title,desc,cat,price in samples:
            conn.execute('INSERT INTO listings(seller_id,title,description,category,starting_price,ends_at) VALUES(?,?,?,?,?,?)',(seller,title,desc,cat,price,(datetime.now()+timedelta(days=2)).isoformat(timespec='minutes')))
    conn.commit(); print('Demo accounts: seller@example.com / DemoPass123! and buyer@example.com / DemoPass123!')

init_db()
if __name__=='__main__': app.run(debug=True)
