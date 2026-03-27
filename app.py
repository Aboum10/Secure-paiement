from flask import Flask, render_template, request, redirect, session
import sqlite3
import random
import smtplib

app = Flask(__name__)
app.secret_key = "supersecretkey"  # pour sessions OTP

# -------------------------------------------
# Produits du shop
products = [
    {"name":"Smart Watch","price":120,"image":"https://images.unsplash.com/photo-1516574187841-cb9cc2ca948b"},
    {"name":"Laptop","price":700,"image":"https://images.unsplash.com/photo-1517336714731-489689fd1ca8"},
    {"name":"Desktop Computer","price":900,"image":"https://images.unsplash.com/photo-1587202372775-e229f172b9d7"},
    {"name":"Smartphone","price":400,"image":"https://images.unsplash.com/photo-1511707171634-5f897ff02aa9"},
]

# -------------------------------------------
# Base de données (SQLite)
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
# SMTP OTP
def send_otp(email):
    otp = random.randint(100000,999999)
    server = smtplib.SMTP("smtp.gmail.com",587)
    server.starttls()
    server.login("abakarabagana15@gmail.com","Aa60459147")  # <== à changer
    message = f"Subject: Votre OTP\n\nVotre code OTP est : {otp}"
    server.sendmail("tonemail@gmail.com",email,message)
    server.quit()
    return str(otp)

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
    if request.method=="POST":
        name = request.form["name"]
        card = request.form["card"]
        exp = request.form["exp"]
        cvv = request.form["cvv"]
        amount = request.form["amount"]

        # enregistrer transaction avec status "PENDING"
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO transactions(name, card, exp, cvv, amount, status)
            VALUES (?,?,?,?,?,?)
        """,(name,card,exp,cvv,amount,"PENDING"))
        conn.commit()
        conn.close()

        # générer OTP
        session["otp"] = send_otp("client@gmail.com")  # <== email du client
        session["transaction_id"] = cursor.lastrowid
        return redirect("/otp")
    else:
        return render_template("payment.html")

@app.route("/admin")
def admin():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM transactions")
    transactions = cursor.fetchall()

    conn.close()

    return render_template("admin.html", transactions=transactions)
    
@app.route("/otp", methods=["GET","POST"])
def otp():
    if request.method=="POST":
        user_otp = request.form["otp"]
        if user_otp == session.get("otp"):
            # mettre transaction à SUCCESS
            conn = sqlite3.connect("database.db")
            cursor = conn.cursor()
            cursor.execute("UPDATE transactions SET status=? WHERE id=?",
                           ("SUCCESS",session.get("transaction_id")))
            conn.commit()
            conn.close()
            return redirect("/success")
        else:
            return "OTP incorrect"
    else:
        return render_template("otp.html")

@app.route("/success")
def success():
    return "Paiement réussi !"

@app.route("/dashboard")
def dashboard():
    # récupérer toutes les transactions
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT amount FROM transactions")
    data = [row[0] for row in cursor.fetchall()]
    conn.close()
    return render_template("dashboard.html", stats=data)

# -------------------------------------------
# Lancement du serveur HTTPS local
if __name__ == "__main__":
    # lancer en HTTPS avec cert.pem et key.pem
    app.run(host="0.0.0.0", port=5000, ssl_context=("cert.pem","key.pem"), debug=True)
