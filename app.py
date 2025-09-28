from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
import pandas as pd
import plotly.express as px
import smtplib
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///attendance.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ---------- MODELS ----------
class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    roll_number = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    registered_on = db.Column(db.DateTime, default=datetime.now)

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    roll_number = db.Column(db.String(50), db.ForeignKey('student.roll_number'))
    lecture = db.Column(db.String(100), nullable=False)
    date = db.Column(db.Date, default=date.today)
    timestamp = db.Column(db.DateTime, default=datetime.now)

with app.app_context():
    db.create_all()

# ---------- ROUTES ----------
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/mark", methods=["POST"])
def mark_attendance():
    roll = request.form['roll']
    name = request.form['name']
    email = request.form['email']
    lecture = request.form['lecture']

    student = Student.query.filter_by(roll_number=roll).first()
    if not student:
        student = Student(roll_number=roll, name=name, email=email)
        db.session.add(student)
        db.session.commit()

    att = Attendance(roll_number=roll, lecture=lecture)
    db.session.add(att)
    db.session.commit()

    return redirect(url_for("dashboard"))

@app.route("/dashboard")
def dashboard():
    records = Attendance.query.all()
    data = [{"Roll": r.roll_number, "Lecture": r.lecture, "Date": r.date} for r in records]
    df = pd.DataFrame(data)

    if not df.empty:
        fig = px.histogram(df, x="Roll", title="Attendance Count per Student")
        graph = fig.to_html(full_html=False)
    else:
        graph = "<p>No attendance records yet.</p>"

    return render_template("dashboard.html", graph=graph)

@app.route("/defaulters")
def defaulters():
    records = Attendance.query.all()
    data = [{"Roll": r.roll_number, "Date": r.date} for r in records]
    df = pd.DataFrame(data)

    defaulters = []
    if not df.empty:
        total_classes = df['Date'].nunique()
        counts = df.groupby("Roll").size().reset_index(name="Present")
        counts["Percentage"] = (counts["Present"] / total_classes) * 100
        defaulters = counts[counts["Percentage"] < 75].to_dict(orient="records")

    return render_template("defaulters.html", defaulters=defaulters)

# ---------- EMAIL SCHEDULER ----------
def send_defaulter_emails():
    records = Attendance.query.all()
    data = [{"Roll": r.roll_number, "Date": r.date} for r in records]
    df = pd.DataFrame(data)

    if not df.empty:
        total_classes = df['Date'].nunique()
        counts = df.groupby("Roll").size().reset_index(name="Present")
        counts["Percentage"] = (counts["Present"] / total_classes) * 100
        defaulters = counts[counts["Percentage"] < 75]

        for _, row in defaulters.iterrows():
            student = Student.query.filter_by(roll_number=row["Roll"]).first()
            if student:
                try:
                    server = smtplib.SMTP("smtp.gmail.com", 587)
                    server.starttls()
                    server.login("markattendance39@gmail.com", "ayushdivyansh")
                    msg = f"Subject: Attendance Shortage\n\nDear {student.name}, your attendance is {row['Percentage']:.2f}%. You are in defaulters list."
                    server.sendmail("markattendance39@gmail.com", student.email, msg)
                    server.quit()
                except Exception as e:
                    print("Email error:", e)

scheduler = BackgroundScheduler()
scheduler.add_job(func=send_defaulter_emails, trigger="interval", days=30)
scheduler.start()

if __name__ == "__main__":
    app.run(debug=True)
