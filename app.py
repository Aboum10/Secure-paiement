from flask import Flask, render_template, request, redirect, session
import sqlite3
import random
import smtplib
from email.mime.text import MIMEText
import os

# ========== SÉCURISATION AJOUTÉE ==========
import hashlib
import re
from functools import wraps
from flask import url_for
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from cryptography.fernet import Fernet
# ===========================================

app = Flask(__name__)

# ========== SÉCURISATION : Clé secrète sécurisée ==========
app.secret_key = os.getenv("FLASK_SECRET_KEY", hashlib.sha256(os.urandom(32)).hexdigest())

# ========== SÉCURISATION : Clé de chiffrement AES ==========
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", Fernet.generate_key())
cipher = Fernet(ENCRYPTION_KEY)

# ========== SÉCURISATION : Rate Limiting ==========
limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

# ========== SÉCURISATION : Headers de sécurité ==========
@app.after_request
def add_security_headers(response):
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
    response.headers['Strict-Transport-Security'] = 'max-age=63072000; includeSubDomains; preload'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    return response

# ========== SÉCURISATION : Décorateur admin_required ==========
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

# ========== SÉCURISATION : Validation des entrées ==========
def validate_card_data(name, email, card, exp, cvv):
    errors = []
    
    # Validation du nom
    if not name or len(name.strip()) < 2:
        errors.append("Nom invalide")
    
    # Validation de l'email
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not email or not re.match(email_pattern, email):
        errors.append("Email invalide")
    
    # Validation de la carte bancaire (16 chiffres)
    card_clean = card.replace(" ", "").replace("-", "")
    if not card_clean or not card_clean.isdigit() or len(card_clean) != 16:
        errors.append("Numéro de carte invalide")
    
    # Validation de la date d'expiration (MM/AA)
    exp_pattern = r'^(0[1-9]|1[0-2])/\d{2}$'
    if not exp or not re.match(exp_pattern, exp):
        errors.append("Date d'expiration invalide")
    
    # Validation du CVV (3 ou 4 chiffres)
    if not cvv or not cvv.isdigit() or len(cvv) not in [3, 4]:
        errors.append("CVV invalide")
    
    return errors

# ========== SÉCURISATION : Chiffrement des données bancaires ==========
def encrypt_sensitive_data(card, exp, cvv):
    encrypted_card = cipher.encrypt(card.encode()).decode()
    encrypted_exp = cipher.encrypt(exp.encode()).decode()
    encrypted_cvv = cipher.encrypt(cvv.encode()).decode()
    return encrypted_card, encrypted_exp, encrypted_cvv

# ========== SÉCURISATION : Déchiffrement des données bancaires ==========
def decrypt_sensitive_data(encrypted_card, encrypted_exp, encrypted_cvv):
    decrypted_card = cipher.decrypt(encrypted_card.encode()).decode()
    decrypted_exp = cipher.decrypt(encrypted_exp.encode()).decode()
    decrypted_cvv = cipher.decrypt(encrypted_cvv.encode()).decode()
    return decrypted_card, decrypted_exp, decrypted_cvv

# ========== SÉCURISATION : Masquer le numéro de carte ==========
def mask_card_number(card):
    return f"**** **** **** {card[-4:]}"

# -------------------------------------------
# Produits du shop
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
    },
]

# -------------------------------------------
# Base de données (sécurisée : colonnes chiffrées)
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

# -------------------------------------------
# OTP + EMAIL
def generate_otp(email):

    otp = str(random.randint(100000, 999999))

    print("=================================")
    print("OTP DU CLIENT :", otp)
    print("=================================")

    sender = os.getenv("EMAIL_USER")
    password = os.getenv("EMAIL_PASS")

    # Vérification Render
    if not sender or not password:
        print("VARIABLES EMAIL MANQUANTES")
        return otp

    msg = MIMEText(f"Votre code OTP est : {otp}")
    msg["Subject"] = "Code OTP SecureShop"
    msg["From"] = sender
    msg["To"] = email

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()

        server.login(sender, password)

        server.sendmail(sender, email, msg.as_string())

        server.quit()

        print("EMAIL OTP ENVOYÉ")

    except Exception as e:
        print("ERREUR EMAIL :", e)

    return otp

# -------------------------------------------
# ROUTES
@app.route("/")
def index():
    return render_template("index.html")

# -------------------------------------------
@app.route("/shop")
def shop():
    return render_template("shop.html", products=products)

# -------------------------------------------
@app.route("/payment", methods=["GET", "POST"])
def payment():

    product_prices = {
        "Smart Watch": 120,
        "Laptop": 700,
        "Desktop Computer": 900,
        "Smartphone": 400
    }

    # =========================
    # GET
    # =========================
    if request.method == "GET":

        product = request.args.get("product")

        # empêcher crash
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

    # =========================
    # POST (SÉCURISÉ : validation + chiffrement)
    # =========================
    if request.method == "POST":

        name = request.form.get("name")
        email = request.form.get("email")
        card = request.form.get("card")
        exp = request.form.get("exp")
        cvv = request.form.get("cvv")

        # SÉCURISATION : Validation des entrées
        errors = validate_card_data(name, email, card, exp, cvv)
        if errors:
            return f"Erreur de validation : {', '.join(errors)}", 400

        session["name"] = name
        session["email"] = email
        
        # SÉCURISATION : Chiffrement des données bancaires
        encrypted_card, encrypted_exp, encrypted_cvv = encrypt_sensitive_data(card, exp, cvv)
        session["card"] = encrypted_card
        session["exp"] = encrypted_exp
        session["cvv"] = encrypted_cvv

        otp = generate_otp(session["email"])

        session["otp"] = otp

        return redirect("/otp")

# -------------------------------------------
@app.route("/otp", methods=["GET", "POST"])
@limiter.limit("10 per minute")  # SÉCURISATION : Rate limiting sur l'OTP
def otp():

    if request.method == "POST":

        user_otp = request.form["otp"]

        conn = sqlite3.connect(
            "database.db",
            check_same_thread=False
        )

        cursor = conn.cursor()

        # -----------------------------------
        # OTP CORRECT
        if user_otp == session.get("otp"):

            cursor.execute("""
                INSERT INTO transactions
                (name, card_encrypted, exp_encrypted, cvv_encrypted, amount, status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                session.get("name"),
                session.get("card"),   # déjà chiffré
                session.get("exp"),    # déjà chiffré
                session.get("cvv"),    # déjà chiffré
                session.get("amount"),
                "SUCCESS"
            ))

            conn.commit()
            conn.close()

            print("TRANSACTION SUCCESS SAVED")

            return redirect("/success")

        # -----------------------------------
        # OTP INCORRECT
        else:

            cursor.execute("""
                INSERT INTO transactions
                (name, card_encrypted, exp_encrypted, cvv_encrypted, amount, status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                session.get("name"),
                session.get("card"),   # déjà chiffré
                session.get("exp"),    # déjà chiffré
                session.get("cvv"),    # déjà chiffré
                session.get("amount"),
                "FAILED"
            ))

            conn.commit()
            conn.close()

            print("TRANSACTION FAILED SAVED")

            return "OTP incorrect"

    return render_template("otp.html")

# -------------------------------------------
@app.route("/success")
def success():
    return render_template("success.html")

# -------------------------------------------
@app.route("/admin")
def admin():
    return redirect("/dashboard")

# -------------------------------------------
@app.route("/dashboard")
@admin_required  # SÉCURISATION : Authentification obligatoire
def dashboard():

    if not session.get("admin"):
        return redirect("/login")

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

    # SÉCURISATION : Déchiffrer et masquer les données pour l'affichage
    transactions_secure = []
    for t in transactions:
        try:
            card, exp, cvv = decrypt_sensitive_data(t[2], t[3], t[4])
            transactions_secure.append((
                t[0],                    # id
                t[1],                    # name
                mask_card_number(card),  # carte masquée
                exp,                     # date d'exp
                "***",                   # CVV masqué
                t[5],                    # amount
                t[6],                    # status
                t[7]                     # created_at
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

# -------------------------------------------
# LOGIN ADMIN (SÉCURISÉ : rate limiting)
@app.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute")  # SÉCURISATION : 5 tentatives max par minute
def login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        if username == "admin" and password == "admin123":

            session["admin"] = True

            return redirect("/dashboard")

        else:

            return "Accès refusé"

    return render_template("login.html")

# -------------------------------------------
@app.route("/logout")
def logout():

    session.clear()

    return redirect("/login")

# -------------------------------------------
# LANCEMENT APPLICATION
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
