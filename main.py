from flask import Flask, render_template, request, redirect, session, url_for
import sqlite3
from datetime import date, datetime   
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.secret_key = "quiz_secret_key"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "database.db")

# ================= DATABASE =================
def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    db = get_db()
    c = db.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS teacher (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        teacher_id TEXT,
        phone TEXT,
        email TEXT UNIQUE,
        password TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS student (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT UNIQUE,
        roll_no TEXT,
        phone TEXT,
        dob TEXT,
        password TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS quiz (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        duration INTEGER,
        released INTEGER DEFAULT 0
    )
    """)
    

    c.execute("""
    CREATE TABLE IF NOT EXISTS question (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        quiz_id INTEGER,
        question TEXT,
        q_type TEXT,     -- mcq / short
        o1 TEXT,
        o2 TEXT,
        o3 TEXT,
        o4 TEXT,
        correct TEXT
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS result (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        quiz_id INTEGER,
        student_email TEXT,
        score INTEGER,
        released INTEGER DEFAULT 0
    )
    """)

    db.commit()
    db.close()
# ================= DEFAULT TEACHER =================
def create_default_teacher():
    db = get_db()
    c = db.cursor()

    email = "teacher@gmail.com"
    password = generate_password_hash("1234")

    c.execute("SELECT * FROM teacher WHERE email=?", (email,))
    if not c.fetchone():
        c.execute("""
            INSERT INTO teacher (name, email, password, phone, teacher_id)
            VALUES (?, ?, ?, ?, ?)
        """, ("Admin", email, password, "", ""))

    db.commit()
    db.close()
# ================= LANDING =================
@app.route("/")
def index():
    return render_template("index.html")
# ================= TEACHER =================
@app.route("/teacher/login", methods=["GET", "POST"])
def teacher_login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        db = get_db()
        t = db.execute("SELECT * FROM teacher WHERE email=?", (email,)).fetchone()
        db.close()

        if t and check_password_hash(t["password"], password):
            session["role"] = "teacher"
            session["email"] = email
            return redirect("/teacher/dashboard")

        return "Invalid Teacher Login"

    return render_template("teacher_login.html")

@app.route("/teacher/dashboard")
def teacher_dashboard():
    if session.get("role") != "teacher":
        return redirect("/")

    db = get_db()
    quizzes = db.execute("""
                        SELECT 
                        quiz.id,
                        quiz.title,
                        quiz.released,
                        COALESCE(
                            (SELECT MAX(released) FROM result WHERE quiz_id = quiz.id),
                            0
                        ) AS result_released
                    FROM quiz
                """).fetchall()
    db.close()

    return render_template("teacher_dashboard.html", quizzes=quizzes)

# ---------- CREATE STUDENT ----------
@app.route("/teacher/create_student", methods=["GET", "POST"])
def create_student():
    if session.get("role") != "teacher":
        return redirect("/")

    db = get_db()
    created_student = None

    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        roll_no = request.form.get("roll_no")
        phone = request.form.get("phone")
        dob = request.form.get("dob")
        password = generate_password_hash(request.form["password"])

        try:
            db.execute("""
                INSERT INTO student (name, email, password, phone, dob, roll_no)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (name, email, password, phone, dob, roll_no))
            db.commit()
            created_student = name
        except sqlite3.IntegrityError:
            db.close()
            return "Student already registered"

    # 🔹 Fetch students list
    students = db.execute("""
        SELECT name, roll_no FROM student
    """).fetchall()

    total_students = len(students)
    db.close()

    return render_template(
        "create_student.html",
        created_student=created_student,
        students=students,
        total_students=total_students
    )
# ---------- CREATE QUIZ ----------
@app.route("/teacher/create_quiz", methods=["GET", "POST"])
def create_quiz():
    if session.get("role") != "teacher":
        return redirect("/")

    if request.method == "POST":
        title = request.form["title"]
        duration = int(request.form["duration"])  # ⏱ NEW

        db = get_db()
        db.execute(
            "INSERT INTO quiz (title, duration) VALUES (?, ?)",
            (title, duration)
        )
        quiz_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.commit()
        db.close()

        return redirect(f"/teacher/add_question/{quiz_id}")

    return render_template("create_quiz.html")

# ---------- ADD QUESTION ----------
@app.route("/teacher/add_question/<int:quiz_id>", methods=["GET", "POST"])
def add_question(quiz_id):
    if session.get("role") != "teacher":
        return redirect("/")

    db = get_db()

    if request.method == "POST":
        q_type = request.form["q_type"]

        if q_type == "mcq":
            db.execute("""
            INSERT INTO question (quiz_id, question, q_type, o1, o2, o3, o4, correct)
            VALUES (?,?,?,?,?,?,?,?)
            """, (
                quiz_id,
                request.form["question"],
                "mcq",
                request.form["o1"],
                request.form["o2"],
                request.form["o3"],
                request.form["o4"],
                request.form["correct"]
            ))
        else:
            db.execute("""
            INSERT INTO question (quiz_id, question, q_type, correct)
            VALUES (?,?,?,?)
            """, (
                quiz_id,
                request.form["question"],
                "short",
                request.form["correct"]
            ))

        db.commit()

    questions = db.execute(
        "SELECT * FROM question WHERE quiz_id=?", (quiz_id,)
    ).fetchall()

    db.close()
    return render_template("add_question.html", quiz_id=quiz_id, questions=questions)

@app.route("/teacher/delete_question/<int:id>/<int:quiz_id>")
def delete_question(id, quiz_id):
    if session.get("role") != "teacher":
        return redirect("/")

    db = get_db()
    db.execute("DELETE FROM question WHERE id=?", (id,))
    db.commit()
    db.close()
    return redirect(f"/teacher/add_question/{quiz_id}")
'''@app.route("/teacher/change_password", methods=["GET", "POST"])
def teacher_change_password():
    if session.get("role") != "teacher":
        return redirect("/")

    if request.method == "POST":
        new_password = generate_password_hash(request.form["password"])

        db = get_db()
        db.execute(
            "UPDATE teacher SET password=? WHERE email=?",
            (new_password, session["email"])
       )
        db.commit()
        db.close()

        return redirect("/teacher/dashboard")

    return render_template("change_password.html", role="Teacher")'''
@app.route("/teacher/profile")
def teacher_profile():
    if session.get("role") != "teacher":
        return redirect("/")

    db = get_db()
    # Fetch latest details to display
    teacher_row = db.execute("""
        SELECT name, phone, teacher_id, email
        FROM teacher
        WHERE email=?
    """, (session["email"],)).fetchone()
    db.close()

    # Convert to dict for Jinja access
    teacher = dict(teacher_row) if teacher_row else {}

    return render_template("teacher_profile.html", teacher=teacher)


# Route to edit profile (name, phone, teacher_id)
@app.route("/teacher/edit_profile", methods=["GET", "POST"])
def edit_profile():
    if session.get("role") != "teacher":
        return redirect("/")

    db = get_db()
    teacher_row = db.execute("""
        SELECT name, phone, teacher_id
        FROM teacher
        WHERE email=?
    """, (session["email"],)).fetchone()

    # Convert to dict
    teacher = dict(teacher_row) if teacher_row else {}

    if request.method == "POST":
        name = request.form.get("name")
        phone = request.form.get("phone")
        teacher_id = request.form.get("teacher_id")

        db.execute("""
            UPDATE teacher
            SET name=?, phone=?, teacher_id=?
            WHERE email=?
        """, (name, phone, teacher_id, session["email"]))
        db.commit()
        db.close()
        return redirect("/teacher/profile")

    db.close()
    return render_template("edit_profile.html", teacher=teacher)


# Route to edit password
@app.route("/teacher/edit_password", methods=["GET", "POST"])
def edit_password():
    if session.get("role") != "teacher":
        return redirect("/")

    if request.method == "POST":
        new_password = request.form.get("password")
        if not new_password:
            return "Password required"

        hashed = generate_password_hash(new_password)
        db = get_db()
        db.execute(
            "UPDATE teacher SET password=? WHERE email=?",
            (hashed, session["email"])
        )
        db.commit()
        db.close()
        return redirect("/teacher/profile")

    return render_template("edit_password.html")
# ---------- RELEASE QUIZ ----------
@app.route("/teacher/release/<int:quiz_id>")
def release_quiz(quiz_id):
    if session.get("role") != "teacher":
        return redirect("/")

    db = get_db()

    # Optional safety check: quiz exists
    quiz = db.execute(
        "SELECT id FROM quiz WHERE id=?",
        (quiz_id,)
    ).fetchone()

    if not quiz:
        db.close()
        return "Quiz not found", 404

    db.execute(
        "UPDATE quiz SET released=1 WHERE id=?",
        (quiz_id,)
    )
    db.commit()
    db.close()

    return redirect("/teacher/dashboard")
@app.route("/teacher/release_result/<int:quiz_id>")
def release_result(quiz_id):
    if session.get("role") != "teacher":
        return redirect("/")

    db = get_db()

    # Optional safety check: at least one student attempted
    attempt = db.execute(
        "SELECT id FROM result WHERE quiz_id=?",
        (quiz_id,)
    ).fetchone()

    if not attempt:
        db.close()
        return "No student has attempted this quiz yet"

    db.execute(
        "UPDATE result SET released=1 WHERE quiz_id=?",
        (quiz_id,)
    )
    db.commit()
    db.close()

    return redirect("/teacher/dashboard")

# ================= STUDENT =================
@app.route("/student/login", methods=["GET", "POST"])
def student_login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form['password']

        db = get_db()
        s = db.execute("SELECT * FROM student WHERE email=?", (email,)).fetchone()
        db.close()

        if s and check_password_hash(s["password"], password):
            session["role"] = "student"
            session["email"] = email
            return redirect("/student/dashboard")

        return "Invalid Student Login"

    return render_template("student_login.html")

@app.route("/student/dashboard")
def student_dashboard():
    if session.get("role") != "student":
        return redirect("/")

    return render_template("student_dashboard.html")
@app.route("/student/view_quizzes")
def view_quizzes():
    if session.get("role") != "student":
        return redirect("/")

    db = get_db()
    quizzes = db.execute("""
        SELECT *
        FROM quiz
        WHERE released = 1
        AND id NOT IN (
            SELECT quiz_id
            FROM result
            WHERE student_email = ?
        )
    """, (session["email"],)).fetchall()
    db.close()

    return render_template("view_quizzes.html", quizzes=quizzes)
@app.route("/student/results")
def student_results():
    if session.get("role") != "student":
        return redirect("/")

    db = get_db()
    results = db.execute("""
        SELECT quiz.title, result.score
        FROM result
        JOIN quiz ON quiz.id = result.quiz_id
        WHERE result.student_email=?
        AND result.released=1
    """, (session["email"],)).fetchall()
    db.close()

    return render_template("student_results.html", results=results)
@app.route("/student/profile")
def student_profile():
    if session.get("role") != "student":
        return redirect("/")

    db = get_db()
    student = db.execute("""
        SELECT name, roll_no, dob, phone, email
        FROM student
        WHERE email=?
    """, (session["email"],)).fetchone()
    db.close()

    return render_template("student_profile.html", student=student)
@app.route("/student/edit_profile", methods=["GET", "POST"])
def edit_student_profile():
    if session.get("role") != "student":
        return redirect("/")

    db = get_db()
    student = db.execute("""
        SELECT name, roll_no, dob, phone
        FROM student
        WHERE email=?
    """, (session["email"],)).fetchone()
    
    if request.method == "POST":
        name = request.form.get("name")
        roll_no = request.form.get("roll_no")
        dob = student["dob"]
        formatted_dob = datetime.strptime(dob, "%Y-%m-%d").strftime("%d-%m-%Y")
        phone = request.form.get("phone")

        db.execute("""
            UPDATE student
            SET name=?, roll_no=?, dob=?, phone=?
            WHERE email=?
        """, (name, roll_no, dob, phone, session["email"]))
        db.commit()
        db.close()
        return redirect("/student/profile")

    db.close()
    # Pass Python date module to Jinja
    return render_template("edit_student_profile.html", student=student, date=date)
@app.route("/student/edit_password", methods=["GET", "POST"])
def edit_student_password():
    # Check session
    if session.get("role") != "student" or "email" not in session:
        return redirect("/student/login")  # redirect specifically to student login

    if request.method == "POST":
        password = request.form.get("password")
        if not password:
            return "Password required", 400

        hashed_password = generate_password_hash(password)
        db = get_db()
        db.execute("""
            UPDATE student
            SET password=?
            WHERE email=?
        """, (hashed_password, session["email"]))
        db.commit()
        db.close()

        return redirect("/student/profile")  # back to profile after changing password

    return render_template("edit_student_password.html")
@app.route("/student/quiz/<int:quiz_id>", methods=["GET", "POST"])
def take_quiz(quiz_id):
    # 🔒 Role check
    if session.get("role") != "student":
        return redirect("/")

    db = get_db()

    # 🔹 Check if quiz exists & is released
    quiz = db.execute(
        "SELECT * FROM quiz WHERE id=? AND released=1",
        (quiz_id,)
    ).fetchone()

    if not quiz:
        db.close()
        return "Quiz not available", 404

    # 🔹 Check if already attempted
    attempt = db.execute(
        "SELECT * FROM result WHERE quiz_id=? AND student_email=?",
        (quiz_id, session["email"])
    ).fetchone()

    if attempt:
        db.close()
        return redirect("/student/dashboard")

    # 🔹 Fetch questions
    questions = db.execute(
        "SELECT * FROM question WHERE quiz_id=?",
        (quiz_id,)
    ).fetchall()

    # Convert rows to dict (important for Jinja + POST loop)
    questions = [dict(q) for q in questions]

    # 🔹 Handle quiz submission
    if request.method == "POST":
        score = 0

        for q in questions:
            ans = request.form.get(str(q["id"]))
            if ans and ans.strip().lower() == q["correct"].strip().lower():
                score += 1

        db.execute(
            "INSERT INTO result (quiz_id, student_email, score) VALUES (?, ?, ?)",
            (quiz_id, session["email"], score)
        )
        db.commit()
        db.close()

        return redirect("/student/quiz_submitted")

    # 🔹 Remaining time (minutes → seconds)
    remaining_time = quiz["duration"] * 60

    db.close()

    return render_template(
        "take_quiz.html",
        quiz=quiz,
        questions=questions,
        remaining_time=remaining_time
    )
@app.route("/student/quiz_submitted")
def quiz_submitted():
    if session.get("role") != "student":
        return redirect("/")

    return render_template("quiz_submitted.html")
@app.route('/student/register', methods=['GET', 'POST'])
def student_register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password_raw = request.form.get('password')
        phone = request.form.get('phone')
        dob = request.form.get('dob')

        roll_no = request.form.get('roll_no')

        # Validate required fields
        if not name or not email or not password_raw or not roll_no:
            return "Please fill all required fields!", 400

        password = generate_password_hash(password_raw)

        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()

        try:
            cur.execute("""
                INSERT INTO student (name, email, password, phone, dob, roll_no)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (name, email, password, phone, dob, roll_no))
            conn.commit()
        except sqlite3.IntegrityError:
            return "Student already registered"

        conn.close()
        return redirect('/student/login')

    return render_template('student_register.html')
@app.route("/student/result/<int:quiz_id>")
def student_result_view(quiz_id):
    if session.get("role") != "student":
        return redirect("/")

    db = get_db()
    result = db.execute("""
        SELECT quiz.title, result.score, result.released
        FROM result
        JOIN quiz ON quiz.id = result.quiz_id
        WHERE result.quiz_id=? AND result.student_email=?
    """, (quiz_id, session["email"])).fetchone()
    db.close()

    if not result:
        return "Result not found", 404

    return render_template("student_result_view.html", result=result)
# ================= LOGOUT =================
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ================= RUN =================
if __name__ == "__main__":
    init_db()
    create_default_teacher()
    app.run(host="0.0.0.0", port=8080)
