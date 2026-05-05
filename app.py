from flask import Flask, render_template, request, redirect, session
import sqlite3
import random
import smtplib
from email.mime.text import MIMEText

app = Flask(__name__)
app.secret_key = "supersecretkey"

# -------------------------------------------
# Produits du shop
products = [
    {"name": "Smart Watch", "price": 120, "image": "https://images.unsplash.com/photo-1516574187841-cb9cc2ca948b"},
    {"name": "Laptop", "price": 700, "image": "https://images.unsplash.com/photo-1517336714731-489689fd1ca8"},
    {"name": "Desktop Computer", "price": 900, "image": "https://images.unsplash.com/photo-1587202372775-e229f172b9d7"},
    {"name": "Smartphone", "price": 400, "image": "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9"},
]

# -------------------------------------------
# Base de données
def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            card TEXT,
            exp TEXT,
            cvv TEXT,
            amount REAL,
            status TEXT
        )
    """)

    conn.commit()
    conn.close()

init_db()

# -------------------------------------------
# OTP
def generate_otp():
    otp = str(random.randint(100000, 999999))
    print("=================================")
    print("OTP DU CLIENT :", otp)
    print("=================================")
    return otp

# -------------------------------------------
# EMAIL OTP
def send_otp_email(email, otp):
    try:
        msg = MIMEText(f"Votre code OTP est : {otp}")
        msg["Subject"] = "Code OTP Paiement"
        msg["From"] = "abakarabagana15@gmail.com"
        msg["To"] = email

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()

        # ⚠️ IMPORTANT : MET TON MOT DE PASSE D’APPLICATION ICI
        server.login("abakarabagana15@gmail.com", "hywt dntt vzga fytc")

        server.send_message(msg)
        server.quit()

        print("OTP envoyé par email ✔️")

    except Exception as e:
        print("Erreur envoi email :", e)

# -------------------------------------------
# Routes
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/shop")
def shop():
    return render_template("shop.html", products=products)


@app.route("/payment", methods=["GET","POST"])
def payment():

    # mapping sécurisé
    product_prices = {
        "Smart Watch": 120,
        "Laptop": 700,
        "Desktop Computer": 900,
        "Smartphone": 400
    }

    product = request.args.get("product")

    if product not in product_prices:
        return "Produit invalide"

    amount = product_prices[product]

    # stocker côté serveur
    session["amount"] = amount
    session["product"] = product

    if request.method == "POST":

        session["name"] = request.form["name"]
        session["card"] = request.form["card"]
        session["exp"] = request.form["exp"]
        session["cvv"] = request.form["cvv"]
        session["email"] = request.form["email"]

        otp = generate_otp()
        session["otp"] = otp

        # ENVOI EMAIL OTP
        send_otp_email(session["email"], otp)

        return redirect("/otp")

    return render_template("payment.html",
                           product=product,
                           amount=amount)


@app.route("/otp", methods=["GET", "POST"])
def otp():

    if request.method == "POST":
        user_otp = request.form["otp"]

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        if user_otp == session.get("otp"):

            cursor.execute("""
                INSERT INTO transactions (name, card, exp, cvv, amount, status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                session.get("name"),
                session.get("card"),
                session.get("exp"),
                session.get("cvv"),
                session.get("amount"),
                "SUCCESS"
            ))

            conn.commit()
            conn.close()

            print("TRANSACTION SUCCESS SAVED")
            return redirect("/success")

        else:
            cursor.execute("""
                INSERT INTO transactions (name, card, exp, cvv, amount, status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                session.get("name"),
                session.get("card"),
                session.get("exp"),
                session.get("cvv"),
                session.get("amount"),
                "FAILED"
            ))

            conn.commit()
            conn.close()

            print("TRANSACTION FAILED SAVED")
            return "OTP incorrect"

    return render_template("otp.html")


@app.route("/success")
def success():
    return render_template("success.html")


@app.route("/admin")
def admin():
    return redirect("/dashboard")


@app.route("/dashboard")
def dashboard():

    if not session.get("admin"):
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM transactions")
    transactions = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) FROM transactions")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT SUM(amount) FROM transactions")
    revenue = cursor.fetchone()[0]

    conn.close()

    return render_template(
        "dashboard.html",
        transactions=transactions,
        total=total,
        revenue=revenue if revenue else 0,
        clients=total
    )

# -------------------------------------------
# LOGIN ADMIN
@app.route("/login", methods=["GET", "POST"])
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


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# -------------------------------------------
if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        ssl_context=("cert.pem", "key.pem"),
        debug=True
    )
