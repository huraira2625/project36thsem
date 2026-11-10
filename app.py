import os
import sqlite3
from functools import wraps
from html import escape
from flask import (
    Flask, request, redirect, url_for,
    flash, render_template_string, session
)
from markupsafe import Markup

# ==========================================
# FLASK CONFIGURATION
# ==========================================

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "result-system-secret-key")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# Vercel serverless temporary DB support
DATABASE = "/tmp/results.db" if os.environ.get("VERCEL") else "results.db"


# ==========================================
# DATABASE CONNECTION & INITIALIZATION
# ==========================================

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_db_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            roll_no TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            department TEXT NOT NULL,
            semester TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            credits INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            course_id INTEGER NOT NULL,
            marks REAL NOT NULL,
            grade TEXT NOT NULL,
            gpa REAL NOT NULL,
            FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
            FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
            UNIQUE(student_id, course_id)
        );
    """)
    conn.commit()
    conn.close()

init_db()


# ==========================================
# GRADING HELPER FUNCTION
# ==========================================

def calculate_grade(marks):
    if marks >= 80:
        return 'A+', 4.00
    elif marks >= 75:
        return 'A', 3.75
    elif marks >= 70:
        return 'A-', 3.50
    elif marks >= 65:
        return 'B+', 3.25
    elif marks >= 60:
        return 'B', 3.00
    elif marks >= 55:
        return 'B-', 2.75
    elif marks >= 50:
        return 'C', 2.50
    elif marks >= 40:
        return 'D', 2.00
    else:
        return 'F', 0.00


# ==========================================
# BASE HTML TEMPLATE (Tailwind CSS)
# ==========================================

BASE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Student Result Processing System</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-50 text-slate-800 min-h-screen flex flex-col">
    <!-- Navbar -->
    <nav class="bg-indigo-900 text-white shadow-md">
        <div class="max-w-7xl mx-auto px-4 py-3 flex justify-between items-center">
            <a href="/" class="text-xl font-bold tracking-wide flex items-center gap-2">🎓 Result Processing System</a>
            <div class="space-x-2 text-sm font-medium">
                <a href="/" class="px-3 py-2 rounded-lg hover:bg-indigo-800 transition">Dashboard</a>
                <a href="/students" class="px-3 py-2 rounded-lg hover:bg-indigo-800 transition">Students</a>
                <a href="/courses" class="px-3 py-2 rounded-lg hover:bg-indigo-800 transition">Courses</a>
                <a href="/results" class="px-3 py-2 rounded-lg hover:bg-indigo-800 transition">Results & GPA</a>
            </div>
        </div>
    </nav>

    <!-- Main Content Container -->
    <main class="flex-grow max-w-7xl w-full mx-auto px-4 py-8">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                <div class="space-y-3 mb-6">
                    {% for category, message in messages %}
                        {% set colors = {
                            'danger': 'bg-red-50 text-red-700 border-red-200',
                            'success': 'bg-emerald-50 text-emerald-700 border-emerald-200',
                            'info': 'bg-blue-50 text-blue-700 border-blue-200'
                        } %}
                        <div class="p-4 rounded-xl text-sm font-medium border {{ colors.get(category, colors['info']) }}">
                            {{ message }}
                        </div>
                    {% endfor %}
                </div>
            {% endif %}
        {% endwith %}

        {{ content | safe }}
    </main>

    <!-- Footer -->
    <footer class="bg-white border-t border-slate-200 text-center py-4 text-sm text-slate-500">
        Academic Lab Project &bull; Flask & Tailwind CSS
    </footer>
</body>
</html>
"""


# ==========================================
# ROUTES: HOME / DASHBOARD
# ==========================================

@app.route("/")
def index():
    conn = get_db_connection()
    total_students = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
    total_courses = conn.execute("SELECT COUNT(*) FROM courses").fetchone()[0]
    total_results = conn.execute("SELECT COUNT(*) FROM results").fetchone()[0]
    conn.close()

    content = f"""
    <div class="space-y-8">
        <div class="bg-gradient-to-r from-indigo-800 to-indigo-600 text-white p-8 rounded-2xl shadow-sm">
            <h1 class="text-3xl font-extrabold mb-2">Student Result Management Portal</h1>
            <p class="text-indigo-100 max-w-2xl">Manage student profiles, register university courses, input semester marks, and automatically compute letter grades and GPA transcripts.</p>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 flex items-center justify-between">
                <div>
                    <p class="text-sm font-medium text-slate-500 uppercase">Total Students</p>
                    <p class="text-3xl font-bold text-slate-900 mt-1">{total_students}</p>
                </div>
                <a href="/students" class="p-3 bg-indigo-50 text-indigo-600 rounded-xl hover:bg-indigo-100 transition font-medium text-sm">Manage &rarr;</a>
            </div>
            <div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 flex items-center justify-between">
                <div>
                    <p class="text-sm font-medium text-slate-500 uppercase">Total Courses</p>
                    <p class="text-3xl font-bold text-slate-900 mt-1">{total_courses}</p>
                </div>
                <a href="/courses" class="p-3 bg-indigo-50 text-indigo-600 rounded-xl hover:bg-indigo-100 transition font-medium text-sm">Manage &rarr;</a>
            </div>
            <div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 flex items-center justify-between">
                <div>
                    <p class="text-sm font-medium text-slate-500 uppercase">Recorded Results</p>
                    <p class="text-3xl font-bold text-slate-900 mt-1">{total_results}</p>
                </div>
                <a href="/results" class="p-3 bg-indigo-50 text-indigo-600 rounded-xl hover:bg-indigo-100 transition font-medium text-sm">Manage &rarr;</a>
            </div>
        </div>
    </div>
    """
    return render_template_string(BASE_HTML, content=Markup(content))


# ==========================================
# ROUTES: STUDENTS MANAGEMENT
# ==========================================

@app.route("/students", methods=["GET", "POST"])
def manage_students():
    conn = get_db_connection()
    if request.method == "POST":
        roll_no = request.form.get("roll_no", "").strip()
        name = request.form.get("name", "").strip()
        department = request.form.get("department", "").strip()
        semester = request.form.get("semester", "").strip()

        if not roll_no or not name or not department or not semester:
            flash("All student fields are required.", "danger")
        else:
            try:
                conn.execute(
                    "INSERT INTO students (roll_no, name, department, semester) VALUES (?, ?, ?, ?)",
                    (roll_no, name, department, semester)
                )
                conn.commit()
                flash("Student added successfully!", "success")
            except sqlite3.IntegrityError:
                flash("Roll number already exists!", "danger")
        return redirect(url_for("manage_students"))

    students = conn.execute("SELECT * FROM students ORDER BY id DESC").fetchall()
    conn.close()

    rows = ""
    for s in students:
        rows += f"""
        <tr class="hover:bg-slate-50 border-b border-slate-100">
            <td class="px-6 py-4 text-sm font-semibold text-slate-900">{escape(s['roll_no'])}</td>
            <td class="px-6 py-4 text-sm text-slate-800">{escape(s['name'])}</td>
            <td class="px-6 py-4 text-sm text-slate-600">{escape(s['department'])}</td>
            <td class="px-6 py-4 text-sm text-slate-600">{escape(s['semester'])}</td>
            <td class="px-6 py-4 text-sm">
                <a href="/transcript/{s['id']}" class="px-3 py-1 bg-indigo-50 text-indigo-700 rounded-lg font-medium hover:bg-indigo-100 transition">View Transcript</a>
            </td>
        </tr>
        """

    content = f"""
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <!-- Add Student Form -->
        <div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 h-fit">
            <h2 class="text-xl font-bold text-slate-900 mb-4">Add New Student</h2>
            <form method="POST" class="space-y-4">
                <div>
                    <label class="block text-sm font-medium text-slate-700 mb-1">Roll / ID Number</label>
                    <input type="text" name="roll_no" required class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none">
                </div>
                <div>
                    <label class="block text-sm font-medium text-slate-700 mb-1">Full Name</label>
                    <input type="text" name="name" required class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none">
                </div>
                <div>
                    <label class="block text-sm font-medium text-slate-700 mb-1">Department</label>
                    <input type="text" name="department" value="CSE" required class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none">
                </div>
                <div>
                    <label class="block text-sm font-medium text-slate-700 mb-1">Semester / Year</label>
                    <input type="text" name="semester" placeholder="e.g. 6th Semester" required class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none">
                </div>
                <button type="submit" class="w-full py-3 bg-indigo-600 text-white font-semibold rounded-xl hover:bg-indigo-700 transition">Save Student</button>
            </form>
        </div>

        <!-- Student Directory Table -->
        <div class="lg:col-span-2 bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
            <div class="bg-slate-900 text-white px-6 py-4">
                <h3 class="font-bold text-lg">Registered Students Directory</h3>
            </div>
            <div class="overflow-x-auto">
                <table class="min-w-full divide-y divide-slate-200">
                    <thead class="bg-slate-50 text-left text-xs font-semibold text-slate-500 uppercase">
                        <tr>
                            <th class="px-6 py-3">Roll No</th>
                            <th class="px-6 py-3">Name</th>
                            <th class="px-6 py-3">Department</th>
                            <th class="px-6 py-3">Semester</th>
                            <th class="px-6 py-3">Action</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-slate-200 bg-white">
                        {rows if rows else '<tr><td colspan="5" class="px-6 py-6 text-center text-slate-500">No students registered yet.</td></tr>'}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
    """
    return render_template_string(BASE_HTML, content=Markup(content))


# ==========================================
# ROUTES: COURSES MANAGEMENT
# ==========================================

@app.route("/courses", methods=["GET", "POST"])
def manage_courses():
    conn = get_db_connection()
    if request.method == "POST":
        code = request.form.get("code", "").strip().upper()
        title = request.form.get("title", "").strip()
        credits = request.form.get("credits", "3")

        if not code or not title:
            flash("Course code and title are required.", "danger")
        else:
            try:
                conn.execute(
                    "INSERT INTO courses (code, title, credits) VALUES (?, ?, ?)",
                    (code, title, int(credits))
                )
                conn.commit()
                flash("Course added successfully!", "success")
            except sqlite3.IntegrityError:
                flash("Course code already exists!", "danger")
        return redirect(url_for("manage_courses"))

    courses = conn.execute("SELECT * FROM courses ORDER BY id DESC").fetchall()
    conn.close()

    rows = ""
    for c in courses:
        rows += f"""
        <tr class="hover:bg-slate-50 border-b border-slate-100">
            <td class="px-6 py-4 text-sm font-semibold text-indigo-600">{escape(c['code'])}</td>
            <td class="px-6 py-4 text-sm text-slate-900">{escape(c['title'])}</td>
            <td class="px-6 py-4 text-sm text-slate-600">{c['credits']} Credits</td>
        </tr>
        """

    content = f"""
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <!-- Add Course Form -->
        <div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 h-fit">
            <h2 class="text-xl font-bold text-slate-900 mb-4">Add New Course</h2>
            <form method="POST" class="space-y-4">
                <div>
                    <label class="block text-sm font-medium text-slate-700 mb-1">Course Code</label>
                    <input type="text" name="code" placeholder="e.g. CSE-3101" required class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none">
                </div>
                <div>
                    <label class="block text-sm font-medium text-slate-700 mb-1">Course Title</label>
                    <input type="text" name="title" placeholder="e.g. Operating Systems" required class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none">
                </div>
                <div>
                    <label class="block text-sm font-medium text-slate-700 mb-1">Credit Hours</label>
                    <select name="credits" class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none">
                        <option value="3">3 Credits</option>
                        <option value="4">4 Credits</option>
                        <option value="2">2 Credits</option>
                        <option value="1.5">1.5 Credits (Lab)</option>
                    </select>
                </div>
                <button type="submit" class="w-full py-3 bg-indigo-600 text-white font-semibold rounded-xl hover:bg-indigo-700 transition">Save Course</button>
            </form>
        </div>

        <!-- Course Directory Table -->
        <div class="lg:col-span-2 bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
            <div class="bg-slate-900 text-white px-6 py-4">
                <h3 class="font-bold text-lg">Available Courses Directory</h3>
            </div>
            <div class="overflow-x-auto">
                <table class="min-w-full divide-y divide-slate-200">
                    <thead class="bg-slate-50 text-left text-xs font-semibold text-slate-500 uppercase">
                        <tr>
                            <th class="px-6 py-3">Course Code</th>
                            <th class="px-6 py-3">Course Title</th>
                            <th class="px-6 py-3">Credits</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-slate-200 bg-white">
                        {rows if rows else '<tr><td colspan="3" class="px-6 py-6 text-center text-slate-500">No courses added yet.</td></tr>'}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
    """
    return render_template_string(BASE_HTML, content=Markup(content))


# ==========================================
# ROUTES: RESULTS & MARKS ENTRY
# ==========================================

@app.route("/results", methods=["GET", "POST"])
def manage_results():
    conn = get_db_connection()
    if request.method == "POST":
        student_id = request.form.get("student_id")
        course_id = request.form.get("course_id")
        marks_input = request.form.get("marks")

        if not student_id or not course_id or not marks_input:
            flash("All result fields are required.", "danger")
        else:
            try:
                marks = float(marks_input)
                if not (0 <= marks <= 100):
                    raise ValueError()
                
                grade, gpa = calculate_grade(marks)

                conn.execute(
                    """
                    INSERT INTO results (student_id, course_id, marks, grade, gpa)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(student_id, course_id) 
                    DO UPDATE SET marks=excluded.marks, grade=excluded.grade, gpa=excluded.gpa
                    """,
                    (student_id, course_id, marks, grade, gpa)
                )
                conn.commit()
                flash("Result recorded successfully!", "success")
            except ValueError:
                flash("Please enter valid marks between 0 and 100.", "danger")
        return redirect(url_for("manage_results"))

    students = conn.execute("SELECT id, roll_no, name FROM students").fetchall()
    courses = conn.execute("SELECT id, code, title FROM courses").fetchall()
    
    results = conn.execute("""
        RERESULTS AS ...
        SELECT results.id, students.roll_no, students.name, courses.code, courses.title, results.marks, results.grade, results.gpa
        FROM results
        JOIN students ON results.student_id = students.id
        JOIN courses ON results.course_id = courses.id
        ORDER BY results.id DESC
    """).fetchall()
    conn.close()

    student_options = "".join([f'<option value="{s["id"]}">{s["roll_no"]} - {s["name"]}</option>' for s in students])
    course_options = "".join([f'<option value="{c["id"]}">{c["code"]} ({c["title"]})</option>' for c in courses])

    rows = ""
    for r in results:
        rows += f"""
        <tr class="hover:bg-slate-50 border-b border-slate-100">
            <td class="px-6 py-4 text-sm font-semibold text-slate-900">{escape(r['roll_no'])}</td>
            <td class="px-6 py-4 text-sm text-slate-800">{escape(r['name'])}</td>
            <td class="px-6 py-4 text-sm text-indigo-600 font-medium">{escape(r['code'])}</td>
            <td class="px-6 py-4 text-sm text-slate-600">{r['marks']}</td>
            <td class="px-6 py-4 text-sm font-bold text-slate-900">{r['grade']}</td>
            <td class="px-6 py-4 text-sm font-semibold text-emerald-600">{r['gpa']:.2f}</td>
        </tr>
        """

    content = f"""
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <!-- Enter Marks Form -->
        <div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 h-fit">
            <h2 class="text-xl font-bold text-slate-900 mb-4">Record Student Marks</h2>
            <form method="POST" class="space-y-4">
                <div>
                    <label class="block text-sm font-medium text-slate-700 mb-1">Select Student</label>
                    <select name="student_id" required class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none">
                        <option value="">Choose student...</option>
                        {student_options}
                    </select>
                </div>
                <div>
                    <label class="block text-sm font-medium text-slate-700 mb-1">Select Course</label>
                    <select name="course_id" required class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none">
                        <option value="">Choose course...</option>
                        {course_options}
                    </select>
                </div>
                <div>
                    <label class="block text-sm font-medium text-slate-700 mb-1">Marks Obtained (0-100)</label>
                    <input type="number" step="0.5" min="0" max="100" name="marks" required class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none">
                </div>
                <button type="submit" class="w-full py-3 bg-indigo-600 text-white font-semibold rounded-xl hover:bg-indigo-700 transition">Calculate & Save Result</button>
            </form>
        </div>

        <!-- Recorded Results Table -->
        <div class="lg:col-span-2 bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
            <div class="bg-slate-900 text-white px-6 py-4">
                <h3 class="font-bold text-lg">Recorded Student Marks & Grades</h3>
            </div>
            <div class="overflow-x-auto">
                <table class="min-w-full divide-y divide-slate-200">
                    <thead class="bg-slate-50 text-left text-xs font-semibold text-slate-500 uppercase">
                        <tr>
                            <th class="px-6 py-3">Roll No</th>
                            <th class="px-6 py-3">Student Name</th>
                            <th class="px-6 py-3">Course</th>
                            <th class="px-6 py-3">Marks</th>
                            <th class="px-6 py-3">Grade</th>
                            <th class="px-6 py-3">GPA</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-slate-200 bg-white">
                        {rows if rows else '<tr><td colspan="6" class="px-6 py-6 text-center text-slate-500">No results recorded yet.</td></tr>'}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
    """
    return render_template_string(BASE_HTML, content=Markup(content))


# ==========================================
# ROUTES: STUDENT TRANSCRIPT
# ==========================================

@app.route("/transcript/<int:student_id>")
def transcript(student_id):
    conn = get_db_connection()
    student = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
    
    if not student:
        conn.close()
        flash("Student not found.", "danger")
        return redirect(url_for("manage_students"))

    results = conn.execute("""
        SELECT courses.code, courses.title, courses.credits, results.marks, results.grade, results.gpa
        FROM results
        JOIN courses ON results.course_id = courses.id
        WHERE results.student_id = ?
    """, (student_id,)).fetchall()
    conn.close()

    total_credits = sum(r['credits'] for r in results)
    weighted_points = sum(r['credits'] * r['gpa'] for r in results)
    cgpa = (weighted_points / total_credits) if total_credits > 0 else 0.0

    rows = ""
    for r in results:
        rows += f"""
        <tr class="border-b border-slate-100">
            <td class="px-6 py-4 text-sm font-semibold text-slate-900">{escape(r['code'])}</td>
            <td class="px-6 py-4 text-sm text-slate-800">{escape(r['title'])}</td>
            <td class="px-6 py-4 text-sm text-slate-600">{r['credits']}</td>
            <td class="px-6 py-4 text-sm text-slate-600">{r['marks']}</td>
            <td class="px-6 py-4 text-sm font-bold text-slate-900">{r['grade']}</td>
            <td class="px-6 py-4 text-sm font-semibold text-emerald-600">{r['gpa']:.2f}</td>
        </tr>
        """

    content = f"""
    <div class="max-w-4xl mx-auto bg-white p-8 rounded-2xl shadow-sm border border-slate-200 space-y-6">
        <div class="flex justify-between items-start border-b pb-6">
            <div>
                <h1 class="text-2xl font-extrabold text-slate-900">Official Academic Transcript</h1>
                <p class="text-slate-500 text-sm mt-1">Department of {escape(student['department'])} &bull; {escape(student['semester'])}</p>
            </div>
            <a href="/students" class="px-4 py-2 bg-slate-100 text-slate-700 rounded-lg text-sm font-medium hover:bg-slate-200 transition">&larr; Back to Students</a>
        </div>

        <div class="grid grid-cols-2 md:grid-cols-4 gap-4 bg-slate-50 p-4 rounded-xl border border-slate-100">
            <div>
                <p class="text-xs font-medium text-slate-500 uppercase">Student Name</p>
                <p class="text-base font-bold text-slate-900">{escape(student['name'])}</p>
            </div>
            <div>
                <p class="text-xs font-medium text-slate-500 uppercase">Roll / ID</p>
                <p class="text-base font-bold text-slate-900">{escape(student['roll_no'])}</p>
            </div>
            <div>
                <p class="text-xs font-medium text-slate-500 uppercase">Total Credits</p>
                <p class="text-base font-bold text-slate-900">{total_credits}</p>
            </div>
            <div>
                <p class="text-xs font-medium text-slate-500 uppercase">Cumulative GPA</p>
                <p class="text-base font-extrabold text-emerald-600">{cgpa:.2f}</p>
            </div>
        </div>

        <div class="overflow-x-auto">
            <table class="min-w-full divide-y divide-slate-200">
                <thead class="bg-slate-50 text-left text-xs font-semibold text-slate-500 uppercase">
                    <tr>
                        <th class="px-6 py-3">Course Code</th>
                        <th class="px-6 py-3">Course Title</th>
                        <th class="px-6 py-3">Credits</th>
                        <th class="px-6 py-3">Marks</th>
                        <th class="px-6 py-3">Letter Grade</th>
                        <th class="px-6 py-3">GPA</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-slate-200 bg-white">
                    {rows if rows else '<tr><td colspan="6" class="px-6 py-6 text-center text-slate-500">No course results posted for this student yet.</td></tr>'}
                </tbody>
            </table>
        </div>
    </div>
    """
    return render_template_string(BASE_HTML, content=Markup(content))


# ==========================================
# RUN APPLICATION
# ==========================================

if __name__ == "__main__":
    app.run(debug=True)