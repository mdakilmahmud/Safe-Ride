# SafeRide 🏍️

> A full-stack safety verification platform for informal motorcycle rides in Bangladesh.

![Python](https://img.shields.io/badge/Python-3.13-blue?style=flat-square&logo=python)
![Flask](https://img.shields.io/badge/Flask-3.1-black?style=flat-square&logo=flask)
![SQLite](https://img.shields.io/badge/SQLite-Database-blue?style=flat-square&logo=sqlite)
![Tailwind CSS](https://img.shields.io/badge/Tailwind-CSS-38bdf8?style=flat-square&logo=tailwindcss)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)

---

## 🧠 The Problem

In Bangladesh, roadside motorcycle rides are one of the fastest and most affordable ways to travel. But this informal transport system has a serious safety gap:

- Passengers don't know the rider's verified identity
- Riders have no protection against false accusations
- There is no official record of the trip, fare, or destination
- If an incident occurs, police have no way to trace either party

## 💡 The Solution

SafeRide adds a **digital safety layer** to the existing informal system — without replacing it.

Riders register once with their bike details and receive a **unique Rider Code and QR code**. Before every ride, the passenger scans or enters the code, logs the trip with destination and fare, and a permanent timestamped record is created. Every ride becomes traceable and accountable.

---

## ✨ Features

| Feature | Description |
|---|---|
| 🔐 Auth System | Signup with real OTP verification via email, login with email or phone |
| 🏍️ Rider Registration | Bike details, BRTA-format plate number, unique Rider Code + QR code |
| 🧍 Passenger Registration | Interactive map-based address picker (Leaflet + OpenStreetMap) |
| 📋 Trip Logging | Unique Trip ID, pickup location map, destination, fare, timestamp |
| 📷 QR Scanner | Live camera-based QR scan to auto-fill rider code before a trip |
| 👤 Role Dashboard | Rider, Passenger, or Both — profile photo, ride history, passenger code |
| 🌙 Dark / Light Mode | Theme toggle with localStorage persistence |
| 📊 Trip History | All logged trips with rider and passenger details |
| 🔢 Hit Counter | Live site visit counter displayed on the home page |
| 📄 Changelog | Version history page tracking platform evolution |

---

## 🛡️ Security

- Passwords hashed with **Flask-Bcrypt**
- OTP codes hashed before storage and expire after **10 minutes**
- Real email OTP delivery via **Gmail SMTP**
- **CSRF protection** on all forms via Flask-WTF
- **Rate limiting** on login, signup, OTP routes via Flask-Limiter
- File upload validation (extension + secure filename)
- Environment secrets stored in `.env` (never committed to git)
- Debug mode controlled via environment variable

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.13, Flask |
| Database | SQLite, Flask-SQLAlchemy |
| Auth | Flask-Login, Flask-Bcrypt |
| Security | Flask-WTF (CSRF), Flask-Limiter |
| Frontend | Jinja2, Tailwind CSS (CDN) |
| Maps | Leaflet.js + OpenStreetMap + Nominatim |
| QR Code | Python qrcode library, jsQR (live camera scan) |
| Email | smtplib + Gmail SMTP |
| Environment | python-dotenv |
| Deployment | Gunicorn (production-ready) |

---

## 🚀 Setup Instructions

### 1. Clone the repository
```bash
git clone https://github.com/mdakilmahmud/Safe-Ride.git
cd Safe-Ride
```

### 2. Create and activate virtual environment
```bash
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Mac/Linux
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Create your `.env` file
Create a file named `.env` in the root folder:
SECRET_KEY=your-random-secret-key
GMAIL_ADDRESS=youremail@gmail.com
GMAIL_APP_PASSWORD=your-gmail-app-password
FLASK_DEBUG=True
> **Note:** To send real OTP emails, you need a Gmail account with 2-Step Verification enabled and a Gmail App Password generated from [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords).

### 5. Run the app
```bash
python app.py
```

### 6. Open in browser
http://127.0.0.1:5000

---

## 📁 Project Structure
Safe-Ride/
├── app.py                  # Main Flask application — all routes, models, logic

├── requirements.txt        # Python dependencies

├── .gitignore              # Excludes venv, .env, database, uploads

├── README.md

└── templates/

├── base.html           # Shared layout, navbar, theme toggle

├── home.html           # Landing page with hit counter

├── about.html          # About the project

├── signup.html         # User registration

├── login.html          # Login with email or phone

├── verify_otp.html     # OTP verification

├── choose_role.html    # Rider / Passenger selection

├── register_rider.html # Bike registration + plate format

├── register_passenger.html  # Map-based address picker

├── dashboard.html      # Role-based user dashboard

├── trip.html           # Trip logging with map + QR scanner

├── trip_success.html   # Trip confirmation

├── history.html        # All trip records

└── changelog.html      # Platform version history


---

## 📌 Important Notes

- This is a **portfolio project** — not a live national service
- OTP delivery requires a valid Gmail App Password in `.env`
- The QR camera scanner requires **HTTPS or localhost** (browser security restriction)
- SQLite is used for simplicity — can be swapped for PostgreSQL for production

---

## 👤 Author

**MD. Akil Mahmud**
A developer from Bangladesh building technology for real local problems.
This project was built from scratch with no prior HTML or CSS experience.

- GitHub: [@mdakilmahmud](https://github.com/mdakilmahmud)

---

> *SafeRide is a personal portfolio project demonstrating full-stack web development with Python, Flask, SQLite, and modern frontend design.*
