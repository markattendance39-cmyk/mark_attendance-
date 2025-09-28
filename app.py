<<<<<<< HEAD
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
=======

from flask import Flask, render_template, request, redirect
from flask_sqlalchemy import SQLAlchemy
import os, cv2, pickle, pandas as pd
from datetime import datetime
import face_recognition
import smtplib
from email.mime.text import MIMEText
from apscheduler.schedulers.background import BackgroundScheduler
import plotly.express as px

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
db = SQLAlchemy(app)

# Folders
DATASET_DIR = "dataset"
ENCODINGS_PATH = "encodings/encodings.pickle"
ATTENDANCE_REPORTS = "attendance_reports"

os.makedirs(DATASET_DIR, exist_ok=True)
os.makedirs("encodings", exist_ok=True)
os.makedirs(ATTENDANCE_REPORTS, exist_ok=True)

# ==============================
# Database Models
# ==============================
class Student(db.Model):
    student_id = db.Column(db.String, primary_key=True)  # You can use roll number as primary key
    name = db.Column(db.String)
    roll_number = db.Column(db.String)  
    email = db.Column(db.String)
    registered_on = db.Column(db.DateTime, default=datetime.now)


class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String, db.ForeignKey('student.student_id'))
    lecture = db.Column(db.String)
    date = db.Column(db.Date)
    timestamp = db.Column(db.DateTime, default=datetime.now)
    student = db.relationship('Student')

# Create tables inside app context
with app.app_context():
    db.create_all()

# ==============================
# Helper Functions
# ==============================
def encode_faces():
    known_encodings = []
    known_ids = []
    for student_id in os.listdir(DATASET_DIR):
        student_path = os.path.join(DATASET_DIR, student_id)
        if not os.path.isdir(student_path):
            continue
        for img_name in os.listdir(student_path):
            img_path = os.path.join(student_path, img_name)
            image = cv2.imread(img_path)
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            boxes = face_recognition.face_locations(rgb)
            encs = face_recognition.face_encodings(rgb, boxes)
            for enc in encs:
                known_encodings.append(enc)
                known_ids.append(student_id)
    with open(ENCODINGS_PATH, "wb") as f:
        pickle.dump((known_encodings, known_ids), f)

def send_email(to_email, subject, body):
    EMAIL_ADDRESS = "markattendance39@gmail.com"
    EMAIL_PASSWORD = "ayushdivyansh"
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = to_email
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
    except Exception as e:
        print("Email failed:", e)

# ==============================
# Routes
# ==============================
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        student_id = request.form["student_id"]
        name = request.form["name"]
        email = request.form["email"]
        lecture_name = request.form["lecture"]

        # Register student if new
        student = Student.query.filter_by(student_id=student_id).first()
        if not student:
            student = Student(student_id=student_id, name=name, email=email)
            db.session.add(student)
            db.session.commit()

        # Capture 5 face images
        student_path = os.path.join(DATASET_DIR, student_id)
        os.makedirs(student_path, exist_ok=True)
        cap = cv2.VideoCapture(0)
        for i in range(5):
            ret, frame = cap.read()
            if ret:
                cv2.imwrite(os.path.join(student_path, f"{i+1}.jpg"), frame)
        cap.release()
        cv2.destroyAllWindows()

        # Encode faces
        encode_faces()

        # Recognize face and mark attendance
        with open(ENCODINGS_PATH, "rb") as f:
            known_encodings, known_ids = pickle.load(f)

        cap = cv2.VideoCapture(0)
        scanned = False
        while not scanned:
            ret, frame = cap.read()
            if not ret:
                continue
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            face_locations = face_recognition.face_locations(rgb_frame)
            face_encs = face_recognition.face_encodings(rgb_frame, face_locations)
            for face_enc in face_encs:
                matches = face_recognition.compare_faces(known_encodings, face_enc)
                if True in matches:
                    idx = matches.index(True)
                    student_id_detected = known_ids[idx]
                    today = datetime.now().date()
                    # Check if attendance already marked
                    if not Attendance.query.filter_by(student_id=student_id_detected, lecture=lecture_name, date=today).first():
                        db.session.add(Attendance(student_id=student_id_detected, lecture=lecture_name, date=today))
                        db.session.commit()
                    scanned = True
                    break
        cap.release()
        cv2.destroyAllWindows()
        return f"Attendance marked for {student_id_detected} for {lecture_name}"

    return render_template("index.html")

@app.route("/teacher")
def teacher():
    attendances = Attendance.query.all()
    return render_template("teacher.html", attendances=attendances)

@app.route("/visualization")
def visualization():
    df = pd.read_sql("SELECT student_id, COUNT(*) as lectures_attended FROM attendance GROUP BY student_id", db.session.bind)
    total_lectures = len(set([a.lecture for a in Attendance.query.all()]))
    df['percent'] = df['lectures_attended']/total_lectures*100 if total_lectures>0 else 0
    fig = px.bar(df, x='student_id', y='percent', title="Monthly Attendance %")
    fig.write_html(os.path.join("static", "attendance_chart.html"))
    return render_template("visualization.html")

# ==============================
# Monthly Defaulter Email Function
# ==============================
def monthly_defaulters_email():
    df = pd.read_sql("SELECT student_id, COUNT(*) as lectures_attended FROM attendance GROUP BY student_id", db.session.bind)
    total_lectures = len(set([a.lecture for a in Attendance.query.all()]))
    if total_lectures==0:
        return
    df['percent'] = df['lectures_attended']/total_lectures*100
    for _, row in df.iterrows():
        if row['percent'] < 75:
            student = Student.query.filter_by(student_id=row['student_id']).first()
            if student:
                send_email(student.email, "Monthly Attendance Warning", f"Dear {student.name}, your monthly attendance is {row['percent']:.2f}%. Please improve.")

# Scheduler to run monthly
scheduler = BackgroundScheduler()
scheduler.add_job(monthly_defaulters_email, 'cron', day=28, hour=18, minute=0)
>>>>>>> adbdfeec7a6aebbfc79fe793fdfbb283e9a5e06b
scheduler.start()

if __name__ == "__main__":
    app.run(debug=True)
