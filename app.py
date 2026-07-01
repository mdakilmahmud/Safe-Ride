from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from flask_wtf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from datetime import datetime
import random
import string
import qrcode
import os
import smtplib
from email.mime.text import MIMEText
from email_validator import validate_email, EmailNotValidError
from dotenv import load_dotenv

load_dotenv()

GMAIL_ADDRESS = os.environ.get('GMAIL_ADDRESS')
GMAIL_APP_PASSWORD = os.environ.get('GMAIL_APP_PASSWORD')
SECRET_KEY = os.environ.get('SECRET_KEY')
FLASK_DEBUG = os.environ.get('FLASK_DEBUG', 'False') == 'True'

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///saferide.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = SECRET_KEY
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB max upload size

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

csrf = CSRFProtect(app)
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"]
)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# ─── Models ───────────────────────────────────────────────

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    gender = db.Column(db.String(20), nullable=True)
    profile_photo = db.Column(db.String(200), nullable=True)
    role = db.Column(db.String(20), default='none')
    account_status = db.Column(db.String(20), default='active')
    is_verified = db.Column(db.Boolean, default=False)
    otp_code = db.Column(db.String(200), nullable=True)
    otp_created_at = db.Column(db.DateTime, nullable=True)
    registered_at = db.Column(db.DateTime, default=datetime.utcnow)

    rider_profile = db.relationship('RiderProfile', backref='user', uselist=False)
    passenger_profile = db.relationship('PassengerProfile', backref='user', uselist=False)

class RiderProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    bike_brand = db.Column(db.String(100), nullable=False)
    bike_model = db.Column(db.String(100), nullable=False)
    plate_area = db.Column(db.String(50), nullable=False)
    plate_category = db.Column(db.String(10), nullable=False)
    plate_number = db.Column(db.String(20), nullable=False)
    rider_code = db.Column(db.String(10), unique=True, nullable=False)
    trips = db.relationship('Trip', backref='rider', lazy=True)

class PassengerProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    address = db.Column(db.String(500), nullable=True)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    passenger_code = db.Column(db.String(10), unique=True, nullable=False)

class Trip(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    trip_code = db.Column(db.String(15), unique=True, nullable=False)
    rider_id = db.Column(db.Integer, db.ForeignKey('rider_profile.id'), nullable=False)
    passenger_name = db.Column(db.String(100), nullable=False)
    passenger_phone = db.Column(db.String(20), nullable=False)
    origin = db.Column(db.String(300), nullable=True)
    origin_lat = db.Column(db.Float, nullable=True)
    origin_lng = db.Column(db.Float, nullable=True)
    destination = db.Column(db.String(200), nullable=False)
    fare = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class SiteStats(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hit_count = db.Column(db.Integer, default=0)

# ─── Helpers ──────────────────────────────────────────────

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

def generate_rider_code():
    while True:
        code = 'SR-' + ''.join(random.choices(string.digits, k=6))
        if not RiderProfile.query.filter_by(rider_code=code).first():
            return code

def generate_trip_code():
    while True:
        code = 'TR-' + ''.join(random.choices(string.digits, k=8))
        if not Trip.query.filter_by(trip_code=code).first():
            return code

def generate_passenger_code():
    while True:
        code = 'PS-' + ''.join(random.choices(string.digits, k=6))
        if not PassengerProfile.query.filter_by(passenger_code=code).first():
            return code

def generate_otp():
    plain = ''.join(random.choices(string.digits, k=6))
    hashed = bcrypt.generate_password_hash(plain).decode('utf-8')
    return plain, hashed

def _send_email_task(to_email, subject, body):
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = GMAIL_ADDRESS
    msg['To'] = to_email
    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_ADDRESS, to_email, msg.as_string())
    except Exception as e:
        print(f'Email send failed: {e}')

def send_otp_email(to_email, otp_code, first_name):
    import threading
    subject = 'Your SafeRide Verification Code'
    body = f"""Hi {first_name},

Your SafeRide verification code is: {otp_code}

This code expires in 10 minutes. If you didn't request this, you can ignore this email.

— SafeRide Team
"""
    thread = threading.Thread(
        target=_send_email_task,
        args=(to_email, subject, body)
    )
    thread.daemon = True
    thread.start()
    return True

def generate_qr_code(rider_code):
    qr = qrcode.make(rider_code)
    folder = os.path.join('static', 'qrcodes')
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f'{rider_code}.png')
    qr.save(path)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_profile_photo(file, user_id):
    from werkzeug.utils import secure_filename
    folder = os.path.join('static', 'uploads')
    os.makedirs(folder, exist_ok=True)
    safe_name = secure_filename(file.filename)
    ext = safe_name.rsplit('.', 1)[-1].lower()
    filename = f'user_{user_id}.{ext}'
    file.save(os.path.join(folder, filename))
    return filename

def is_valid_email(email):
    try:
        validate_email(email, check_deliverability=True)
        return True
    except EmailNotValidError:
        return False

def is_valid_phone(phone):
    return phone.isdigit() and len(phone) == 11

def is_strong_password(password):
    if len(password) < 8:
        return False
    has_letter = any(c.isalpha() for c in password)
    has_digit = any(c.isdigit() for c in password)
    return has_letter and has_digit

def get_or_create_stats():
    stats = SiteStats.query.first()
    if not stats:
        stats = SiteStats(hit_count=0)
        db.session.add(stats)
        db.session.commit()
    return stats

def increment_hits():
    try:
        stats = get_or_create_stats()
        stats.hit_count += 1
        db.session.commit()
        return stats.hit_count
    except Exception:
        db.session.rollback()
        stats = get_or_create_stats()
        return stats.hit_count

# ─── Routes ───────────────────────────────────────────────

@app.route('/')
def home():
    hits = increment_hits()
    return render_template('home.html', hits=hits)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/changelog')
def changelog():
    return render_template('changelog.html')

# ── Signup ──

@app.route('/signup', methods=['GET', 'POST'])
@limiter.limit("5 per hour")
def signup():
    if request.method == 'POST':
        email = request.form['email'].strip()
        phone = request.form['phone'].strip()

        if not is_valid_email(email):
            flash('Please enter a valid email address.', 'error')
            return redirect(url_for('signup'))

        if not is_valid_phone(phone):
            flash('Please enter a valid 11-digit Bangladeshi mobile number.', 'error')
            return redirect(url_for('signup'))

        if User.query.filter_by(email=email).first():
            flash('This email is already registered.', 'error')
            return redirect(url_for('signup'))

        if User.query.filter_by(phone=phone).first():
            flash('This phone number is already registered.', 'error')
            return redirect(url_for('signup'))

        if not is_strong_password(request.form['password']):
            flash('Password must be at least 8 characters and include both letters and numbers.', 'error')
            return redirect(url_for('signup'))

        if request.form['password'] != request.form['confirm_password']:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('signup'))
        
        hashed_pw = bcrypt.generate_password_hash(request.form['password']).decode('utf-8')
        otp_plain, otp_hashed = generate_otp()
        first_name = request.form['first_name'].strip()

        user = User(
            email=email,
            password=hashed_pw,
            first_name=first_name,
            last_name=request.form['last_name'].strip(),
            phone=phone,
            gender=request.form['gender'],
            role='none',
            is_verified=False,
            otp_code=otp_hashed,
            otp_created_at=datetime.utcnow()
        )
        db.session.add(user)
        db.session.commit()

        session['pending_user_id'] = user.id
        session['otp_method'] = request.form.get('otp_method', 'email')

        email_sent = send_otp_email(email, otp_plain, first_name)
        if not email_sent:
            flash('Could not send verification email. Please check your email address and try again.', 'error')

        return redirect(url_for('verify_otp'))

    return render_template('signup.html')

# ── OTP Verification ──

@app.route('/verify-otp', methods=['GET', 'POST'])
@limiter.limit("10 per hour")
def verify_otp():
    user_id = session.get('pending_user_id')
    if not user_id:
        return redirect(url_for('signup'))

    user = db.session.get(User, user_id)
    if not user:
        return redirect(url_for('signup'))

    otp_method = session.get('otp_method', 'email')

    if request.method == 'POST':
        entered_otp = request.form['otp'].strip()
        otp_expired = (
            user.otp_created_at is None or
            (datetime.utcnow() - user.otp_created_at).total_seconds() > 600
        )
        if otp_expired:
            flash('Your OTP has expired. Please request a new one.', 'error')
        elif user.otp_code and bcrypt.check_password_hash(user.otp_code, entered_otp):
            user.is_verified = True
            user.otp_code = None
            user.otp_created_at = None
            db.session.commit()
            session.pop('pending_user_id', None)
            session.pop('otp_method', None)
            login_user(user)
            return redirect(url_for('choose_role'))
        else:
            flash('Invalid OTP. Please try again.', 'error')

    return render_template('verify_otp.html', user=user, otp_method=otp_method)

@app.route('/resend-otp')
@limiter.limit("3 per hour")
def resend_otp():
    user_id = session.get('pending_user_id')
    if not user_id:
        return redirect(url_for('signup'))
    user = db.session.get(User, user_id)
    if user:
        otp_plain, otp_hashed = generate_otp()
        user.otp_code = otp_hashed
        user.otp_created_at = datetime.utcnow()
        db.session.commit()
        email_sent = send_otp_email(user.email, otp_plain, user.first_name)
        if email_sent:
            flash('A new OTP has been sent to your email.', 'success')
        else:
            flash('Could not resend the email. Please try again.', 'error')
    return redirect(url_for('verify_otp'))

# ── Login ──

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per hour")
def login():
    if request.method == 'POST':
        identifier = request.form['identifier'].strip()
        password = request.form['password']

        if is_valid_email(identifier):
            user = User.query.filter_by(email=identifier).first()
        elif is_valid_phone(identifier):
            user = User.query.filter_by(phone=identifier).first()
        else:
            user = None

        if user and bcrypt.check_password_hash(user.password, password):
            if not user.is_verified:
                session['pending_user_id'] = user.id
                flash('Please verify your account first.', 'error')
                return redirect(url_for('verify_otp'))
            login_user(user)
            return redirect(url_for('dashboard'))

        flash('Invalid credentials. Please try again.', 'error')

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

# ── Role Selection ──

@app.route('/choose-role')
@login_required
def choose_role():
    return render_template('choose_role.html')

# ── Rider Registration ──

@app.route('/register-rider', methods=['GET', 'POST'])
@login_required
def register_rider():
    if current_user.rider_profile:
        flash('You already have a rider profile.', 'error')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        rider_code = generate_rider_code()
        profile = RiderProfile(
            user_id=current_user.id,
            bike_brand=request.form['bike_brand'],
            bike_model=request.form['bike_model'],
            plate_area=request.form['plate_area'],
            plate_category=request.form['plate_category'],
            plate_number=request.form['plate_number'],
            rider_code=rider_code
        )
        db.session.add(profile)
        if current_user.role == 'passenger':
            current_user.role = 'both'
        else:
            current_user.role = 'rider'
        db.session.commit()
        generate_qr_code(rider_code)
        return redirect(url_for('dashboard'))
    return render_template('register_rider.html')

# ── Passenger Registration ──

@app.route('/register-passenger', methods=['GET', 'POST'])
@login_required
def register_passenger():
    if current_user.passenger_profile:
        flash('You already have a passenger profile.', 'error')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        profile = PassengerProfile(
            user_id=current_user.id,
            address=request.form.get('address'),
            latitude=request.form.get('latitude') or None,
            longitude=request.form.get('longitude') or None,
            passenger_code=generate_passenger_code()
        )
        db.session.add(profile)
        if current_user.role == 'rider':
            current_user.role = 'both'
        else:
            current_user.role = 'passenger'
        db.session.commit()
        return redirect(url_for('dashboard'))
    return render_template('register_passenger.html')

# ── Dashboard ──

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', user=current_user)

# ── Profile Photo Upload ──

@app.route('/upload-photo', methods=['POST'])
@login_required
def upload_photo():
    if 'photo' in request.files:
        file = request.files['photo']
        if file.filename != '' and allowed_file(file.filename):
            filename = save_profile_photo(file, current_user.id)
            current_user.profile_photo = filename
            db.session.commit()
        elif file.filename != '':
            flash('Invalid file type. Please upload a PNG, JPG, GIF, or WEBP image.', 'error')
    return redirect(url_for('dashboard'))

# ── Trip Logging ──

@app.route('/trip', methods=['GET', 'POST'])
@login_required
@limiter.limit("20 per hour")
def log_trip():
    if request.method == 'POST':
        rider_code = request.form['rider_code'].strip()
        rider = RiderProfile.query.filter_by(rider_code=rider_code).first()
        if not rider:
            return render_template('trip.html', error='Rider code not found. Please check and try again.')
        if rider.user_id == current_user.id:
            return render_template('trip.html', error='You cannot log a trip using your own rider code.')
        try:
            fare = float(request.form['fare'])
        except (ValueError, TypeError):
            return render_template('trip.html', error='Please enter a valid fare amount.')

        new_trip = Trip(
            trip_code=generate_trip_code(),
            rider_id=rider.id,
            passenger_name=request.form['passenger_name'],
            passenger_phone=request.form['passenger_phone'],
            origin=request.form.get('origin'),
            origin_lat=request.form.get('origin_lat') or None,
            origin_lng=request.form.get('origin_lng') or None,
            destination=request.form['destination'],
            fare=fare
        )
        db.session.add(new_trip)
        db.session.commit()
        return render_template('trip_success.html', trip=new_trip)
    return render_template('trip.html')

# ── Trip History ──

@app.route('/history')
@login_required
def history():
    trips = Trip.query.order_by(Trip.timestamp.desc()).all()
    return render_template('history.html', trips=trips)

# ─── Init DB ──────────────────────────────────────────────

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=FLASK_DEBUG)