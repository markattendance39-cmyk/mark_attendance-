
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
scheduler.start()

if __name__ == "__main__":
    app.run(debug=True)
