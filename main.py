# THIS IS THE FINAL, COMPLETE main.py
# It is synchronized with the final db_setup.py and the dashboard HTML.

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime
import json # Import json at the top

app = Flask(__name__)
app.secret_key = 'your_secret_key_here_make_it_secure'

DB_CONFIG = {
    "host": "localhost",
    "port": 3307,
    "user": "root",
    "password": "",
    "database": "edugradedb"
}

def get_db_connection():
    try: return mysql.connector.connect(**DB_CONFIG)
    except mysql.connector.Error: return None

def execute_query(query, params=None, fetch=False):
    connection = get_db_connection()
    if not connection: return None if fetch else False
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(query, params or ())
        if fetch: result = cursor.fetchall()
        else: connection.commit(); result = True
        return result
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()

def teacher_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'role' not in session or session.get('role') != 'teacher':
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index(): return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        access_code = request.form.get('access_code')
        password = request.form.get('password')
        query = "SELECT * FROM login WHERE username=%s"
        user_data = execute_query(query, (access_code,), fetch=True)
        if user_data and check_password_hash(user_data[0]['password'], password):
            user = user_data[0]
            session.clear()
            session['user_id'] = user['loginID']
            session['username'] = user['username']
            session['teachID'] = user['teachID']
            session['role'] = 'teacher'
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials. Please try again.', 'error')
    return render_template('login.html')

@app.route('/users_signup', methods=['GET', 'POST'])
def user_signup():
    if request.method == 'POST':
        access_code = request.form['access_code']
        password = request.form['password']
        if password != request.form['confirm_password']:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('user_signup'))
        if execute_query("SELECT 1 FROM login WHERE username = %s", (access_code,), fetch=True):
            flash('This Access Code is already taken.', 'error')
            return redirect(url_for('user_signup'))
        
        connection = get_db_connection()
        try:
            cursor = connection.cursor()
            teacher_query = "INSERT INTO teachers (teachname, email, gender, class) VALUES (%s, %s, %s, %s)"
            cursor.execute(teacher_query, (f"Teacher {access_code}", f"{access_code}@school.com", 'Not Specified', 'Unassigned'))
            new_teach_id = cursor.lastrowid
            
            hashed_password = generate_password_hash(password)
            login_query = "INSERT INTO login (username, password, teachID) VALUES (%s, %s, %s)"
            cursor.execute(login_query, (access_code, hashed_password, new_teach_id))
            
            connection.commit()
            flash('Teacher account created successfully! Please log in.', 'success')
            return redirect(url_for('login'))
        except mysql.connector.Error as e:
            if connection: connection.rollback()
            flash(f"Database error: {e}", "error")
        finally:
            if connection and connection.is_connected():
                cursor.close()
                connection.close()
    return render_template('sign_up.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

@app.route('/dashboard')
@teacher_login_required
def dashboard():
    teacher_data = execute_query("SELECT teachname FROM teachers WHERE teachID = %s", (session['teachID'],), fetch=True)
    teacher_name = teacher_data[0]['teachname'] if teacher_data else "Teacher"
    total_students = execute_query("SELECT COUNT(*) as count FROM students WHERE teachID = %s", (session['teachID'],), fetch=True)[0]['count']
    return render_template('teachers_dashboard.html', teacher_name=teacher_name, total_students=total_students)

# --- TEACHER DASHBOARD API ENDPOINTS ---

@app.route('/teacher/dashboard_data')
@teacher_login_required
def dashboard_data():
    total_students = execute_query("SELECT COUNT(*) as count FROM students WHERE teachID = %s", (session['teachID'],), fetch=True)[0]['count']
    return jsonify({'success': True, 'total_students': total_students})

@app.route('/teacher/my_classes')
@teacher_login_required
def my_classes():
    query = """
        SELECT DISTINCT c.classID as id, c.classname as name, 
               CASE 
                   WHEN c.classname LIKE '%grade 1%' THEN 'Grade 1 (Lower Primary)'
                   WHEN c.classname LIKE '%grade 2%' THEN 'Grade 2 (Lower Primary)'
                   WHEN c.classname LIKE '%grade 3%' THEN 'Grade 3 (Lower Primary)'
                   WHEN c.classname LIKE '%grade 4%' THEN 'Grade 4 (Upper Primary)'
                   WHEN c.classname LIKE '%grade 5%' THEN 'Grade 5 (Upper Primary)'
                   ELSE 'Other'
               END as grade,
               'General Studies' as subject_taught,
               (SELECT COUNT(*) FROM students s WHERE s.class = c.classname AND s.teachID = %s) as student_count
        FROM classes c
        WHERE EXISTS (SELECT 1 FROM students s WHERE s.class = c.classname AND s.teachID = %s)
        ORDER BY c.classname
    """
    classes = execute_query(query, (session['teachID'], session['teachID']), fetch=True)
    return jsonify({'success': True, 'classes': classes or []})

@app.route('/teacher/get_my_students')
@teacher_login_required
def get_my_students():
    query = """
        SELECT s.studID as id, s.studname as full_name, s.admno as admission_number,
               CASE 
                   WHEN s.class LIKE '%grade 1%' THEN 'Grade 1 (Lower Primary)'
                   WHEN s.class LIKE '%grade 2%' THEN 'Grade 2 (Lower Primary)'
                   WHEN s.class LIKE '%grade 3%' THEN 'Grade 3 (Lower Primary)'
                   WHEN s.class LIKE '%grade 4%' THEN 'Grade 4 (Upper Primary)'
                   WHEN s.class LIKE '%grade 5%' THEN 'Grade 5 (Upper Primary)'
                   ELSE 'Other'
               END as grade,
               s.class as class_name
        FROM students s
        WHERE s.teachID = %s
        ORDER BY s.studname
    """
    students = execute_query(query, (session['teachID'],), fetch=True)
    return jsonify({'success': True, 'students': students or []})

@app.route('/teacher/add_student', methods=['POST'])
@teacher_login_required
def add_student():
    try:
        full_name = request.form.get('fullName')
        admission_number = request.form.get('admissionNumber')
        age = request.form.get('age')
        grade = request.form.get('grade')
        class_id = request.form.get('classId')
        password = request.form.get('password')
        
        # Get class name from class ID
        class_query = "SELECT classname FROM classes WHERE classID = %s"
        class_data = execute_query(class_query, (class_id,), fetch=True)
        if not class_data:
            return jsonify({'success': False, 'message': 'Selected class not found.'})
        
        class_name = class_data[0]['classname']
        
        # Calculate date of birth from age
        from datetime import date
        current_year = date.today().year
        birth_year = current_year - int(age)
        dob = f"{birth_year}-01-01"  # Approximate DOB
        
        # Insert student
        student_query = """
            INSERT INTO students (studname, admno, gender, dob, class, teachID) 
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        success = execute_query(student_query, (full_name, admission_number, 'Not Specified', dob, class_name, session['teachID']))
        
        if success:
            return jsonify({'success': True, 'message': 'Student added successfully!'})
        else:
            return jsonify({'success': False, 'message': 'Failed to add student. Admission number might already exist.'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@app.route('/teacher/delete_student/<int:student_id>', methods=['DELETE'])
@teacher_login_required
def delete_student(student_id):
    success = execute_query("DELETE FROM students WHERE studID = %s AND teachID = %s", (student_id, session['teachID']))
    return jsonify({'success': success, 'message': 'Student deleted successfully.' if success else 'Error deleting student.'})

@app.route('/teacher/students_for_marks')
@teacher_login_required
def students_for_marks():
    term = request.args.get('term', 'Term 1')
    query = """
        SELECT s.studID as id, s.studname as full_name, s.admno as admission_number,
               CASE 
                   WHEN s.class LIKE '%grade 1%' THEN 'Grade 1 (Lower Primary)'
                   WHEN s.class LIKE '%grade 2%' THEN 'Grade 2 (Lower Primary)'
                   WHEN s.class LIKE '%grade 3%' THEN 'Grade 3 (Lower Primary)'
                   WHEN s.class LIKE '%grade 4%' THEN 'Grade 4 (Upper Primary)'
                   WHEN s.class LIKE '%grade 5%' THEN 'Grade 5 (Upper Primary)'
                   ELSE 'Other'
               END as grade,
               m.ovrscore as overall_average, m.meanscore, m.remark as overall_remark,
               m.updated_at, m.term, m.year
        FROM students s
        LEFT JOIN marks m ON s.studID = m.studID AND m.term = %s
        WHERE s.teachID = %s
        ORDER BY s.studname
    """
    students = execute_query(query, (term, session['teachID']), fetch=True)
    
    # Process students to add grade and remark
    for student in students:
        if student['overall_average']:
            grade_info = get_grade_info(student['overall_average'])
            student['overall_grade'] = grade_info['grade']
            student['overall_remark'] = student['overall_remark'] or grade_info['remark']
        else:
            student['overall_grade'] = 'N/A'
            student['overall_remark'] = 'N/A'
    
    return jsonify({'success': True, 'students': students or []})

@app.route('/teacher/student_marks/<int:student_id>')
@teacher_login_required
def student_marks(student_id):
    term = request.args.get('term', 'Term 1')
    
    # Get student info
    student_query = """
        SELECT s.studID as id, s.studname as full_name, s.admno as admission_number,
               CASE 
                   WHEN s.class LIKE '%grade 1%' THEN 'Grade 1 (Lower Primary)'
                   WHEN s.class LIKE '%grade 2%' THEN 'Grade 2 (Lower Primary)'
                   WHEN s.class LIKE '%grade 3%' THEN 'Grade 3 (Lower Primary)'
                   WHEN s.class LIKE '%grade 4%' THEN 'Grade 4 (Upper Primary)'
                   WHEN s.class LIKE '%grade 5%' THEN 'Grade 5 (Upper Primary)'
                   ELSE 'Other'
               END as grade,
               s.class as class_name
        FROM students s
        WHERE s.studID = %s AND s.teachID = %s
    """
    student_data = execute_query(student_query, (student_id, session['teachID']), fetch=True)
    
    if not student_data:
        return jsonify({'success': False, 'message': 'Student not found or not assigned to you.'})
    
    student = student_data[0]
    
    # Get existing marks
    marks_query = "SELECT * FROM marks WHERE studID = %s AND term = %s ORDER BY year DESC LIMIT 1"
    marks_data = execute_query(marks_query, (student_id, term), fetch=True)
    
    if marks_data:
        # Parse the marks data structure
        marks_details = {}
        if marks_data[0].get('marks_details'):
            try:
                marks_details = json.loads(marks_data[0]['marks_details'])
            except:
                marks_details = {}
        
        student['marks_data'] = marks_details
    
    return jsonify({'success': True, 'student': student})

@app.route('/teacher/save_marks/<int:student_id>', methods=['POST'])
@teacher_login_required
def save_marks(student_id):
    try:
        data = request.json
        term = data.get('term', 'Term 1')
        subjects = data.get('subjects', {})
        overall = data.get('overall', {})
        
        # Calculate overall scores
        total_score = float(overall.get('total', 0))
        average_score = float(overall.get('average', 0))
        grade_info = get_grade_info(average_score)
        
        # Store marks with detailed structure
        marks_details = json.dumps(subjects)
        
        # Check if marks exist for this student and term
        existing_query = "SELECT markID FROM marks WHERE studID = %s AND term = %s"
        existing = execute_query(existing_query, (student_id, term), fetch=True)
        
        if existing:
            # Update existing marks
            update_query = """
                UPDATE marks SET ovrscore = %s, meanscore = %s, remark = %s, 
                               marks_details = %s, updated_at = NOW()
                WHERE studID = %s AND term = %s
            """
            success = execute_query(update_query, (
                total_score, average_score, overall.get('remark', grade_info['remark']),
                marks_details, student_id, term
            ))
        else:
            # Insert new marks
            insert_query = """
                INSERT INTO marks (studID, ovrscore, meanscore, remark, term, year, marks_details, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            """
            success = execute_query(insert_query, (
                student_id, total_score, average_score, overall.get('remark', grade_info['remark']),
                term, datetime.now().year, marks_details
            ))
        
        return jsonify({'success': success, 'message': 'Marks saved successfully!' if success else 'Failed to save marks.'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@app.route('/teacher/generate_report_data/<int:student_id>')
@teacher_login_required
def generate_report_data(student_id):
    term = request.args.get('term', 'Term 1')
    
    # Get student and marks data
    query = """
        SELECT s.studID, s.studname as full_name, s.admno as admission_number,
               CASE 
                   WHEN s.class LIKE '%grade 1%' THEN 'Grade 1 (Lower Primary)'
                   WHEN s.class LIKE '%grade 2%' THEN 'Grade 2 (Lower Primary)'
                   WHEN s.class LIKE '%grade 3%' THEN 'Grade 3 (Lower Primary)'
                   WHEN s.class LIKE '%grade 4%' THEN 'Grade 4 (Upper Primary)'
                   WHEN s.class LIKE '%grade 5%' THEN 'Grade 5 (Upper Primary)'
                   ELSE 'Other'
               END as grade,
               s.class as class_name, t.teachname as teacher_name,
               m.ovrscore, m.meanscore, m.remark, m.marks_details
        FROM students s
        LEFT JOIN teachers t ON s.teachID = t.teachID
        LEFT JOIN marks m ON s.studID = m.studID AND m.term = %s
        WHERE s.studID = %s AND s.teachID = %s
    """
    data = execute_query(query, (term, student_id, session['teachID']), fetch=True)
    
    if not data:
        return jsonify({'success': False, 'message': 'Student not found or not assigned to you.'})
    
    student_data = data[0]
    
    # Parse marks details
    marks_details = {}
    if student_data.get('marks_details'):
        try:
            marks_details = json.loads(student_data['marks_details'])
        except:
            marks_details = {}
    
    # Calculate overall performance
    overall_average = student_data.get('meanscore', 0)
    grade_info = get_grade_info(overall_average)
    
    report_data = {
        'full_name': student_data['full_name'],
        'admission_number': student_data['admission_number'],
        'grade': student_data['grade'],
        'class_name': student_data['class_name'],
        'teacher_name': student_data['teacher_name'],
        'term': term,
        'overall_average': overall_average,
        'overall_grade': grade_info['grade'],
        'overall_remark': student_data.get('remark') or grade_info['remark'],
        'marks_details': marks_details,
        'report_generated_on': datetime.now().strftime('%B %d, %Y')
    }
    
    return jsonify({'success': True, 'data': report_data})

@app.route('/teacher/my_reports')
@teacher_login_required
def my_reports():
    query = """
        SELECT m.markID, s.studname as student_name, s.admno as admission_number,
               m.term, m.meanscore as overall_average, m.remark as overall_remark
        FROM marks m
        JOIN students s ON m.studID = s.studID
        WHERE s.teachID = %s
        ORDER BY m.term DESC, s.studname
    """
    reports = execute_query(query, (session['teachID'],), fetch=True)
    
    # Add grade information
    for report in reports:
        if report['overall_average']:
            grade_info = get_grade_info(report['overall_average'])
            report['overall_grade'] = grade_info['grade']
        else:
            report['overall_grade'] = 'N/A'
    
    return jsonify({'success': True, 'reports': reports or []})

@app.route('/teacher/get_report_data/<int:mark_id>')
@teacher_login_required
def get_report_data(mark_id):
    query = """
        SELECT m.*, s.studname as full_name, s.admno as admission_number,
               CASE 
                   WHEN s.class LIKE '%grade 1%' THEN 'Grade 1 (Lower Primary)'
                   WHEN s.class LIKE '%grade 2%' THEN 'Grade 2 (Lower Primary)'
                   WHEN s.class LIKE '%grade 3%' THEN 'Grade 3 (Lower Primary)'
                   WHEN s.class LIKE '%grade 4%' THEN 'Grade 4 (Upper Primary)'
                   WHEN s.class LIKE '%grade 5%' THEN 'Grade 5 (Upper Primary)'
                   ELSE 'Other'
               END as grade,
               s.class as class_name, t.teachname as teacher_name
        FROM marks m
        JOIN students s ON m.studID = s.studID
        LEFT JOIN teachers t ON s.teachID = t.teachID
        WHERE m.markID = %s AND s.teachID = %s
    """
    data = execute_query(query, (mark_id, session['teachID']), fetch=True)
    
    if not data:
        return jsonify({'success': False, 'message': 'Report not found.'})
    
    mark_data = data[0]
    
    # Parse marks details
    marks_details = {}
    if mark_data.get('marks_details'):
        try:
            marks_details = json.loads(mark_data['marks_details'])
        except:
            marks_details = {}
    
    # Calculate overall performance
    overall_average = mark_data.get('meanscore', 0)
    grade_info = get_grade_info(overall_average)
    
    report_data = {
        'full_name': mark_data['full_name'],
        'admission_number': mark_data['admission_number'],
        'grade': mark_data['grade'],
        'class_name': mark_data['class_name'],
        'teacher_name': mark_data['teacher_name'],
        'term': mark_data['term'],
        'overall_average': overall_average,
        'overall_grade': grade_info['grade'],
        'overall_remark': mark_data.get('remark') or grade_info['remark'],
        'marks_details': marks_details,
        'report_generated_on': datetime.now().strftime('%B %d, %Y')
    }
    
    return jsonify({'success': True, 'data': report_data})

def get_grade_info(average):
    if average is None:
        return {'grade': 'E', 'remark': 'Needs Intervention'}
    if average >= 80:
        return {'grade': 'A', 'remark': 'Exceeding Expectations'}
    elif average >= 60:
        return {'grade': 'B', 'remark': 'Meeting Expectations'}
    elif average >= 40:
        return {'grade': 'C', 'remark': 'Approaching Expectations'}
    elif average >= 20:
        return {'grade': 'D', 'remark': 'Below Expectations'}
    else:
        return {'grade': 'E', 'remark': 'Needs Intervention'}

# --- LEGACY API ENDPOINTS (for backward compatibility) ---
@app.route('/api/get_classes')
@teacher_login_required
def get_classes():
    """Fetches all class names from the 'classes' table for the dropdown."""
    query = "SELECT classname FROM classes ORDER BY classname ASC"
    classes_data = execute_query(query, fetch=True)
    return jsonify({'success': True, 'classes': classes_data}) if classes_data else jsonify({'success': False})

@app.route('/api/get_students')
@teacher_login_required
def get_students():
    query = "SELECT studID, studname, admno, gender, class FROM students ORDER BY studname"
    students = execute_query(query, fetch=True)
    return jsonify({'success': True, 'students': students or []})

# <<< FIX: Renamed function to avoid conflict with the new /teacher/add_student endpoint >>>
@app.route('/api/add_student', methods=['POST'])
@teacher_login_required
def add_student_legacy():
    data = request.json
    query = "INSERT INTO students (studname, admno, gender, dob, class, teachID) VALUES (%s, %s, %s, %s, %s, %s)"
    params = (data['studname'], data['admno'], data['gender'], data['dob'], data['class'], session['teachID'])
    success = execute_query(query, params)
    return jsonify({'success': success, 'message': 'Student added!' if success else 'Failed to add student. Adm No. might exist.'})

# <<< FIX: Renamed function to avoid conflict with the new /teacher/delete_student endpoint >>>
@app.route('/api/delete_student/<int:stud_id>', methods=['DELETE'])
@teacher_login_required
def delete_student_legacy(stud_id):
    success = execute_query("DELETE FROM students WHERE studID = %s", (stud_id,))
    return jsonify({'success': success, 'message': 'Student deleted.' if success else 'Error deleting student.'})

@app.route('/api/get_marks_list')
@teacher_login_required
def get_marks_list():
    query = "SELECT s.studID, s.studname, s.admno, s.class, m.meanscore, m.remark FROM students s LEFT JOIN marks m ON s.studID = m.studID ORDER BY s.studname"
    marks = execute_query(query, fetch=True)
    return jsonify({'success': True, 'marks': marks or []})

@app.route('/api/get_single_mark/<int:stud_id>')
@teacher_login_required
def get_single_mark(stud_id):
    query = "SELECT ovrscore, meanscore, remark FROM marks WHERE studID = %s ORDER BY year DESC, term DESC LIMIT 1"
    mark = execute_query(query, (stud_id,), fetch=True)
    return jsonify({'success': True, 'mark': mark[0]}) if mark else jsonify({'success': False})

@app.route('/api/save_mark', methods=['POST'])
@teacher_login_required
def save_mark():
    data = request.json
    query = "INSERT INTO marks (studID, ovrscore, meanscore, remark, term, year) VALUES (%s, %s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE ovrscore=VALUES(ovrscore), meanscore=VALUES(meanscore), remark=VALUES(remark)"
    params = (data.get('studID'), data.get('ovrscore'), data.get('meanscore'), data.get('remark'), 'Term 1', 2024)
    success = execute_query(query, params)
    return jsonify({'success': success, 'message': 'Marks saved!' if success else 'Save failed.'})

@app.route('/api/generate_report')
@teacher_login_required
def generate_report():
    stud_id, term = request.args.get('studID'), request.args.get('term')
    query = "SELECT s.studname, s.admno, s.class as Classname, m.* FROM students s JOIN marks m ON s.studID = m.studID WHERE s.studID = %s AND m.term = %s"
    data = execute_query(query, (stud_id, term), fetch=True)
    return jsonify({'success': True, 'data': data[0]}) if data else jsonify({'success': False, 'message': 'No report data found.'})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)