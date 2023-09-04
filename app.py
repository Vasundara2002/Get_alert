from flask import Flask, render_template, request, redirect, session
from flask_mysqldb import MySQL
import os
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
import requests  # To send HTTP requests for SMS
from twilio.rest import Client
app = Flask(__name__)
app.secret_key = os.urandom(24)  # Set your own secret key for session
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'library'
 
mysql = MySQL(app)


@app.route("/signup", methods=["GET", "POST"])
def signup():
    error=""
    if request.method == "POST":
       
        name = request.form["name"]
        id = request.form["id"]
        email = request.form["email"]
        branch = request.form["branch"]
        password = request.form["password"]
        repeat_password = request.form["repeat_password"]
        phone=request.form["phone"]
        gender = request.form["gender"]
        # Here, you can add validation for passwords matching, email uniqueness, etc.
        # Store the user data in the session
        session["user"] = {
            "name": name,
            "id": id,
            "email": email,
            "branch": branch,
            "gender": gender,
            "phone":phone
        }
        if password==repeat_password:
               cursor = mysql.connection.cursor()
               cursor.execute('''INSERT INTO info_table VALUES(%s,%s,%s,%s,%s,%s,%s)''',(name,id,email,branch,password,phone,gender))
               mysql.connection.commit()
               cursor.close()
               error="no"
        else:
            error="yes"       
        d={'error' :error}
        if d=="yes":
          return redirect("/signup")
        else:
          return redirect("/login")
    return render_template('signup.html', error="")  # Render the signup page for GET requests

@app.route("/login", methods=["GET", "POST"])
def login():
    error = ""
    success_message=""
    if request.method == "POST":
        
        mail = request.form["mail"]
        Pas = request.form["Pas"]

        cursor = mysql.connection.cursor()
        cursor.execute("SELECT email, password,id FROM info_table WHERE email = %s", (mail,))
        result = cursor.fetchone()
        cursor.close()

        if result:
            email_in_db, password_in_db,user_id = result
            if password_in_db == Pas:
                session["logged_in"] = True
                session["user_email"] = email_in_db
                session["user_id"] = user_id
                return redirect("/add_book")
            else:
                error = "Invalid credentials. Please check your email and password."
        else:
            error = "Email not found. Please register or use a different email."

    return render_template("login.html", error=error, success_message=success_message)
@app.route("/add_book", methods=["GET", "POST"])
def add_book():
    error = ""
    if request.method == "POST":
        bookname = request.form["bookname"]
        # Remove the "date" field from the form processing

        email = session.get("user_email")  # Retrieve the email from the session

        cursor = mysql.connection.cursor()
        cursor.execute("SELECT id,name FROM info_table WHERE email = %s", (email,))
        result = cursor.fetchone()

        if result:
            user_id, user_name = result  # Fetch the user_id from the result

            # Get the current system date
            date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Use the current_date instead of the "date" from the form
            cursor.execute('''INSERT INTO books_table (user_id, user_name, bookname, date) VALUES (%s, %s, %s, %s)''',
                           (user_id, user_name, bookname,date))
            mysql.connection.commit()
            cursor.close()
            
            return redirect("/show_books")
        else:
            error = "User not found. Please log in again."

    return render_template("add_book.html", error=error)
@app.route("/show_books")
def show_books():
    if "logged_in" in session and session["logged_in"]:
        user_email = session.get("user_email")

        cursor = mysql.connection.cursor()
        # Fetch the user_id from the info_table based on user_email
        cursor.execute('''SELECT id FROM info_table WHERE email = %s''', (user_email,))
        result = cursor.fetchone()
        if result:
            user_id = result[0]  # Fetch the user_id from the result
            # Fetch books based on the user_id
            cursor.execute('''SELECT * FROM books_table WHERE user_id = %s''', (user_id,))
            books = cursor.fetchall()
            cursor.close()
            return render_template("/show_books.html",books=books)
        if result:
            user_id = result[0]  # Fetch the user_id from the result
            # Fetch books based on the user_id
            cursor.execute('''SELECT * FROM books_table WHERE user_id = %s''', (user_id,))
            books = cursor.fetchall()
            cursor.close()
            return redirect("/alerts")
        
        else:
            # Handle the case when the user is not found in the info_table
            return "User not found. Please log in again."
    else:
        return redirect("/login")  
# ... (existing imports and Flask app setup)


account_sid = 'AC95741bd270d14516e25b123f9ba27c33'
auth_token = '5446c8280f3160e05107ac45308b19f1'
twilio_phone_number = '+14705180248'
client = Client(account_sid, auth_token)
# ... (existing imports and Flask app setup)

# Function to send an SMS alert to the user
@app.route('/alerts',methods=["GET","POST"])
def alerts():

    cursor = mysql.connection.cursor()

    # Fetch books added 1 minute ago that have not been notified yet
    one_minute_ago = (datetime.now() - timedelta(minutes=1)).strftime('%Y-%m-%d')
    cursor.execute('''
        SELECT books_table.user_id, info_table.name, books_table.bookname, info_table.phone
        FROM books_table
        JOIN info_table ON books_table.user_id = info_table.id
        WHERE books_table.date = %s AND books_table.notified = 0
    ''', (one_minute_ago,))
    result = cursor.fetchall()
    print(result)
    for row in result:
        user_id, user_name, book_name, phone = row
        message = f"Hi {user_name}, don't forget to return the book: {book_name}"

        try:
            # Use the Twilio client to send the alert message to the user's phone number
            client.messages.create(
                body=message,
                from_=twilio_phone_number,
                to=phone
            )

            # If the message was sent successfully, update the 'notified' status for the book
            cursor.execute("UPDATE books_table SET notified = 1 WHERE user_id = %s AND date = %s", (user_id, one_minute_ago))
            mysql.connection.commit()

        except Exception as e:
            print("Failed to send SMS:", str(e))

    cursor.close()
    return "Hii"

# ... (existing routes and functions)


if __name__ == "__main__":
    # Schedule the send_alert_messages function to run every 1 minute
    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(alerts, trigger='interval', minutes=1)
    scheduler.start()

    app.run(debug=True)
