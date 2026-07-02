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
from email_validator import validate_email, EmailNotValidError
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-me'
FLASK_DEBUG = os.environ.get('FLASK_DEBUG', 'False') == 'True'


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///saferide.db')
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

@app.errorhandler(429)
def rate_limit_error(e):
    flash('You are trying too many times. Please wait a few minutes and try again.', 'error')
    return redirect(request.referrer or url_for('home'))

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
        validate_email(email, check_deliverability=False)
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

def parse_optional_float(value):
    if value in (None, ''):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

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
@limiter.limit("200 per hour")
def signup():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        gender = request.form.get('gender', '').strip()

        if not all([first_name, last_name, email, phone, gender, password, confirm_password]):
            flash('Please fill in all required fields.', 'error')
            return redirect(url_for('signup'))

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

        if not is_strong_password(password):
            flash('Password must be at least 8 characters and include both letters and numbers.', 'error')
            return redirect(url_for('signup'))

        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('signup'))
        
        hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')
        otp_plain, otp_hashed = generate_otp()

        user = User(
            email=email,
            password=hashed_pw,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            gender=gender,
            role='none',
            is_verified=False,
            otp_code=otp_hashed,
            otp_created_at=datetime.utcnow()
        )
        db.session.add(user)
        db.session.commit()

        session['pending_user_id'] = user.id
        session['otp_method'] = request.form.get('otp_method', 'email')
        session['demo_otp'] = otp_plain
        return redirect(url_for('verify_otp'))

    return render_template('signup.html')

# ── OTP Verification ──

@app.route('/verify-otp', methods=['GET', 'POST'])
@limiter.limit("200 per hour")
def verify_otp():
    user_id = session.get('pending_user_id')
    if not user_id:
        return redirect(url_for('signup'))

    user = db.session.get(User, user_id)
    if not user:
        return redirect(url_for('signup'))

    otp_method = session.get('otp_method', 'email')

    if request.method == 'POST':
        entered_otp = request.form.get('otp', '').strip()
        if not entered_otp:
            flash('Please enter your OTP.', 'error')
            return render_template('verify_otp.html', user=user, otp_method=otp_method, demo_otp=session.get('demo_otp', ''))

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
            session.pop('demo_otp', None)
            login_user(user)
            return redirect(url_for('choose_role'))
        else:
            flash('Invalid OTP. Please try again.', 'error')

    demo_otp = session.get('demo_otp', '')
    return render_template('verify_otp.html', user=user, otp_method=otp_method, demo_otp=demo_otp)

@app.route('/resend-otp')
@limiter.limit("100 per hour")
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
        session['demo_otp'] = otp_plain
        flash('A new OTP has been generated.', 'success')
    return redirect(url_for('verify_otp'))

# ── Login ──

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("300 per hour")
def login():
    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip()
        password = request.form.get('password', '')

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
        bike_brand = request.form.get('bike_brand', '').strip()
        bike_model = request.form.get('bike_model', '').strip()
        plate_area = request.form.get('plate_area', '').strip()
        plate_category = request.form.get('plate_category', '').strip()
        plate_number = request.form.get('plate_number', '').strip()

        if not all([bike_brand, bike_model, plate_area, plate_category, plate_number]):
            flash('Please fill in all rider registration fields.', 'error')
            return redirect(url_for('register_rider'))

        rider_code = generate_rider_code()
        profile = RiderProfile(
            user_id=current_user.id,
            bike_brand=bike_brand,
            bike_model=bike_model,
            plate_area=plate_area,
            plate_category=plate_category,
            plate_number=plate_number,
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
        address = request.form.get('address', '').strip()
        latitude = parse_optional_float(request.form.get('latitude'))
        longitude = parse_optional_float(request.form.get('longitude'))

        if not address or latitude is None or longitude is None:
            flash('Please select a valid location on the map.', 'error')
            return redirect(url_for('register_passenger'))

        profile = PassengerProfile(
            user_id=current_user.id,
            address=address,
            latitude=latitude,
            longitude=longitude,
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
        rider_code = request.form.get('rider_code', '').strip()
        passenger_name = request.form.get('passenger_name', '').strip()
        passenger_phone = request.form.get('passenger_phone', '').strip()
        destination = request.form.get('destination', '').strip()
        origin = request.form.get('origin', '').strip()
        origin_lat = parse_optional_float(request.form.get('origin_lat'))
        origin_lng = parse_optional_float(request.form.get('origin_lng'))

        if not rider_code:
            return render_template('trip.html', error='Please enter a rider code.')

        rider = RiderProfile.query.filter_by(rider_code=rider_code).first()
        if not rider:
            return render_template('trip.html', error='Rider code not found. Please check and try again.')
        if rider.user_id == current_user.id:
            return render_template('trip.html', error='You cannot log a trip using your own rider code.')

        if not passenger_name:
            return render_template('trip.html', error='Please enter your name.')
        if not is_valid_phone(passenger_phone):
            return render_template('trip.html', error='Please enter a valid 11-digit Bangladeshi mobile number.')
        if not destination:
            return render_template('trip.html', error='Please enter your destination.')

        try:
            fare = float(request.form.get('fare', ''))
        except (ValueError, TypeError):
            return render_template('trip.html', error='Please enter a valid fare amount.')
        if fare <= 0:
            return render_template('trip.html', error='Please enter a fare greater than 0.')

        new_trip = Trip(
            trip_code=generate_trip_code(),
            rider_id=rider.id,
            passenger_name=passenger_name,
            passenger_phone=passenger_phone,
            origin=origin or None,
            origin_lat=origin_lat,
            origin_lng=origin_lng,
            destination=destination,
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
