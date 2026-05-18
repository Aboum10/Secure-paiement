from flask import Flask, render_template, request, redirect, session
import sqlite3
import random
import smtplib
from email.mime.text import MIMEText
import os
import hashlib
import re
from functools import wraps
from flask import url_for
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from cryptography.fernet import Fernet

app = Flask(__name__)

# =====================================================
# CLÉ SECRÈTE
# =====================================================
app.secret_key = os.getenv(
    "FLASK_SECRET_KEY",
    hashlib.sha256(os.urandom(32)).hexdigest()
)

# =====================================================
# CHIFFREMENT
# =====================================================
key = os.getenv("ENCRYPTION_KEY")

if key:
    key = key.encode()
else:
    key = Fernet.generate_key()

cipher = Fernet(key)

# =====================================================
# RATE LIMITER
# =====================================================
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

# =====================================================
# HEADERS SÉCURITÉ
# =====================================================
@app.after_request
def add_security_headers(response):

    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-XSS-Protection'] = '1; mode=block'

    return response

# =====================================================
# ADMIN REQUIRED
# =====================================================
def admin_required(f):

    @wraps(f)
    def decorated_function(*args, **kwargs):

        if not session.get("admin"):
            return redirect(url_for("login"))

        return f(*args, **kwargs)

    return decorated_function

# =====================================================
# VALIDATION
# =====================================================
def validate_card_data(name, email, card, exp, cvv):

    errors = []

    if not name or len(name.strip()) < 2:
        errors.append("Nom invalide")

    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

    if not email or not re.match(email_pattern, email):
        errors.append("Email invalide")

    card_clean = card.replace(" ", "").replace("-", "")

    if not card_clean.isdigit() or len(card_clean) != 16:
        errors.append("Carte invalide")

    exp_pattern = r'^(0[1-9]|1[0-2])/\d{2}$'

    if not re.match(exp_pattern, exp):
        errors.append("Expiration invalide")

    if not cvv.isdigit() or len(cvv) not in [3, 4]:
        errors.append("CVV invalide")

    return errors

# =====================================================
# CHIFFREMENT
# =====================================================
def encrypt_sensitive_data(card, exp, cvv):

    encrypted_card = cipher.encrypt(card.encode()).decode()

    encrypted_exp = cipher.encrypt(exp.encode()).decode()

    encrypted_cvv = cipher.encrypt(cvv.encode()).decode()

    return encrypted_card, encrypted_exp, encrypted_cvv

# =====================================================
# DÉCHIFFREMENT
# =====================================================
def decrypt_sensitive_data(card, exp, cvv):

    card = cipher.decrypt(card.encode()).decode()

    exp = cipher.decrypt(exp.encode()).decode()

    cvv = cipher.decrypt(cvv.encode()).decode()

    return card, exp, cvv

# =====================================================
# MASQUER CARTE
# =====================================================
def mask_card_number(card):

    return f"**** **** **** {card[-4:]}"

# =====================================================
# PRODUITS
# =====================================================
products = [

    {
        "name": "Smart Watch",
        "price": 120,
        "image": "https://images.unsplash.com/photo-1516574187841-cb9cc2ca948b"
    },

    {
        "name": "Laptop",
        "price": 700,
        "image": "https://images.unsplash.com/photo-1517336714731-489689fd1ca8"
    },

    {
        "name": "Desktop Computer",
        "price": 900,
        "image": "https://images.unsplash.com/photo-1587202372775-e229f172b9d7"
    },

    {
        "name": "Smartphone",
        "price": 400,
        "image": "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9"
    }
]

# =====================================================
# DATABASE
# =====================================================
def init_db():

    conn = sqlite3.connect(
        "database.db",
        check_same_thread=False
    )

    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            card_encrypted TEXT,
            exp_encrypted TEXT,
            cvv_encrypted TEXT,
            amount REAL,
            status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()

init_db()

# =====================================================
# OTP EMAIL
# =====================================================
def generate_otp(email):

    otp = str(random.randint(100000, 999999))

    print("================================")
    print("OTP :", otp)
    print("================================")

    sender = "abakarabagana15@gmail.com"

    password = "qttoqdkmdliocidl"

    if not sender or not password:
        print("EMAIL_USER_OU_EMAIL_PASS")
        return otp

    try:

        msg = MIMEText(f"Votre code OTP est : {otp}")

        msg["Subject"] = "Code OTP SecureShop"

        msg["From"] = sender

        msg["To"] = email

        server = smtplib.SMTP(
            "smtp.gmail.com",
            587,
            timeout=10
        )

        server.starttls()

        server.login(sender, password)

        server.sendmail(
            sender,
            email,
            msg.as_string()
        )

        server.quit()

        print("EMAIL OTP ENVOYÉ")

    except Exception as e:

        print("ERREUR EMAIL :", e)

    return otp

# =====================================================
# ROUTES
# =====================================================
@app.route("/")
def index():

    return render_template("index.html")

# =====================================================
@app.route("/shop")
def shop():

    return render_template(
        "shop.html",
        products=products
    )

# =====================================================
@app.route("/payment", methods=["GET", "POST"])
def payment():

    product_prices = {

        "Smart Watch": 120,
        "Laptop": 700,
        "Desktop Computer": 900,
        "Smartphone": 400
    }

    # ======================================
    # GET
    # ======================================
    if request.method == "GET":

        product = request.args.get("product")

        if not product:
            return redirect("/shop")

        if product not in product_prices:
            return redirect("/shop")

        session["product"] = product

        session["amount"] = product_prices[product]

        return render_template(
            "payment.html",
            product=product,
            amount=product_prices[product]
        )

    # ======================================
    # POST
    # ======================================
    if request.method == "POST":

        name = request.form.get("name")

        email = request.form.get("email")

        card = request.form.get("card")

        exp = request.form.get("exp")

        cvv = request.form.get("cvv")

        errors = validate_card_data(
            name,
            email,
            card,
            exp,
            cvv
        )

        if errors:
            return f"Erreur : {', '.join(errors)}"

        encrypted_card, encrypted_exp, encrypted_cvv = encrypt_sensitive_data(
            card,
            exp,
            cvv
        )

        session["name"] = name
        session["email"] = email
        session["card"] = encrypted_card
        session["exp"] = encrypted_exp
        session["cvv"] = encrypted_cvv

        otp = generate_otp(email)

        session["otp"] = otp

        return redirect("/otp")

# =====================================================
@app.route("/otp", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def otp():

    if request.method == "POST":

        user_otp = request.form["otp"]

        conn = sqlite3.connect(
            "database.db",
            check_same_thread=False
        )

        cursor = conn.cursor()

        status = "FAILED"

        if user_otp == session.get("otp"):
            status = "SUCCESS"

        cursor.execute("""
            INSERT INTO transactions
            (name, card_encrypted, exp_encrypted, cvv_encrypted, amount, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (

            session.get("name"),
            session.get("card"),
            session.get("exp"),
            session.get("cvv"),
            session.get("amount"),
            status
        ))

        conn.commit()
        conn.close()

        if status == "SUCCESS":
            return redirect("/success")

        return "OTP incorrect"

    return render_template("otp.html")

# =====================================================
@app.route("/success")
def success():

    return render_template("success.html")

# =====================================================
@app.route("/dashboard")
@admin_required
def dashboard():

    conn = sqlite3.connect(
        "database.db",
        check_same_thread=False
    )

    cursor = conn.cursor()

    cursor.execute("SELECT * FROM transactions")

    transactions = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) FROM transactions")

    total = cursor.fetchone()[0]

    cursor.execute("SELECT SUM(amount) FROM transactions")

    revenue = cursor.fetchone()[0]

    conn.close()

    transactions_secure = []

    for t in transactions:

        try:

            card, exp, cvv = decrypt_sensitive_data(
                t[2],
                t[3],
                t[4]
            )

            transactions_secure.append((
                t[0],
                t[1],
                mask_card_number(card),
                exp,
                "***",
                t[5],
                t[6],
                t[7]
            ))

        except:
            transactions_secure.append(t)

    return render_template(
        "dashboard.html",
        transactions=transactions_secure,
        total=total,
        revenue=revenue if revenue else 0,
        clients=total
    )

# =====================================================
@app.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def login():

    if request.method == "POST":

        username = request.form["username"]

        password = request.form["password"]

        if username == "aboum235@" and password == "Aa459147":

            session["admin"] = True

            return redirect("/dashboard")

        return "Accès refusé"

    return render_template("login.html")

# =====================================================
@app.route("/logout")
def logout():

    session.clear()

    return redirect("/login")

# =====================================================
# MAIN
# =====================================================
if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )