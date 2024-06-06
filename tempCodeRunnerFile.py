from flask import Flask, render_template, request, flash, redirect, url_for, session, jsonify
import subprocess
from mysql.connector import connection, Error
from datetime import datetime, date
import pandas as pd
import time
# from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'your_secret_key'

@app.route('/')
def index():
    if 'username' not in session or session.get('role') != 'user':
         return redirect(url_for('login'))
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']

        connection = create_connection()
        if connection is None:
            flash('Database connection failed', 'error')
            return redirect(url_for('login'))

        try:
            cursor = connection.cursor(dictionary=True)
            if role == 'admin':
                query = "SELECT * FROM admin WHERE adminusername = %s AND adminpassword = %s"
            else:
                query = "SELECT * FROM users WHERE username = %s AND password = %s"

            cursor.execute(query, (username, password))
            user = cursor.fetchone()

            if user:
                session['username'] = username
                session['role'] = role

                if role == 'admin':
                    return redirect(url_for('admin_dashboard'))
                else:
                    return redirect(url_for('index'))
            else:
                flash('Invalid credentials', 'error')
        except Error as e:
            flash(f"Database error: {e}", 'error')
        finally:
            cursor.close()
            connection.close()

        return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('role', None)
    return redirect(url_for('login'))





@app.route('/admin_dashboard')
def admin_dashboard():
    if 'username' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    return render_template('admin_dashboard.html')

def create_connection():
    """ create a database connection to the MySQL database """
    try:
        conn = connection.MySQLConnection(user='root', password='',
                                          host='127.0.0.1', database='attendance')
        if conn.is_connected():
            print("Connection to MySQL DB successful")
    except Error as e:
        print(f"The error '{e}' occurred")
    return conn

@app.route('/add_user', methods=['POST'])
def add_user():
    if 'username' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))

    new_username = request.form['new_username']
    new_password = request.form['new_password']

    connection = create_connection()
    if connection is None:
        flash('Database connection failed', 'error')
        return redirect(url_for('admin_dashboard'))

    try:
        cursor = connection.cursor()
        # Check if user already exists in both user and admin tables
        query = "SELECT * FROM users WHERE username = %s UNION SELECT * FROM admin WHERE adminusername = %s"
        cursor.execute(query, (new_username, new_username))
        user = cursor.fetchone()

        if user:
            flash('User already exists', 'error')
            session['scroll_position'] = request.args.get('scroll_position', type=int) or 0
            return redirect(url_for('admin_dashboard', scroll_position=session['scroll_position']))
        else:
            insert_query = "INSERT INTO users (username, password) VALUES (%s, %s)"
            cursor.execute(insert_query, (new_username, new_password))
            connection.commit()
            flash('User added successfully', 'success')
    except Error as e:
        flash(f"Database error: {e}", 'error')
    finally:
        cursor.close()
        connection.close()
    flash(f"User '{new_username}' created successfully!", 'success')
    # return redirect(url_for('admin_dashboard'))
    # Redirect to the same position on the page
    session['scroll_position'] = request.args.get('scroll_position', type=int) or 0
    return redirect(url_for('admin_dashboard', scroll_position=session['scroll_position']))



@app.route('/reset_password', methods=['POST'])
def reset_password():
    if 'username' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))

    reset_username = request.form['reset_username']
    new_password = request.form['reset_password']

    connection = create_connection()
    if connection is None:
        flash('Database connection failed', 'error')
        return redirect(url_for('admin_dashboard'))

    try:
        cursor = connection.cursor()
        # Check if the user exists
        cursor.execute("SELECT * FROM users WHERE username = %s", (reset_username,))
        user = cursor.fetchone()
        if user is None:
            flash(f"User '{reset_username}' not found", 'error')
        else:
            # Update the user's password
            query = "UPDATE users SET password = %s WHERE username = %s"
            cursor.execute(query, (new_password, reset_username))
            connection.commit()
            flash('Password reset successfully', 'success')
    except Error as e:
        flash(f"Database error: {e}", 'error')
    finally:
        cursor.close()
        connection.close()
    
    # Redirect to the same position on the page
    session['scroll_position'] = request.args.get('scroll_position', type=int) or 0
    return redirect(url_for('admin_dashboard', scroll_position=session['scroll_position']))




@app.route('/backhome')
def backhome():
    return render_template('index.html', selected_date='', no_data=False)

@app.route('/attendance_view')
def attendance_view():
    return render_template('attendance.html', selected_date='', no_data=False)

@app.route('/takeattendance')
def takeattendance():
    subprocess.run(["python", "attendance_taker.py"])
    return render_template('index.html', no_data=False)

@app.route('/add_student')
def add_student():
    subprocess.run(["python", "get_faces_from_camera_tkinter.py"])
    return render_template('index.html', no_data=False)

@app.route('/delete_student', methods=['POST'])
def delete_student():
    rollno = request.form.get('roll_no')
    name = request.form.get('sname')
    subprocess.run(["python", "delete_face.py", rollno, name])
    flash("Student Deleted Successfully","success")
    return render_template('remove.html', no_data=False, name='', roll_no='')

@app.route('/get_attendance_data')
def get_attendance_data():
    conn = create_connection()
    data = attendance_details()
    print(data)
    formatted_data = [(row[0], str(row[1]), str(row[2]), row[3]) for row in data]
    
    data_df = pd.DataFrame(formatted_data, columns=['name', 'time', 'date', 'roll_no'])

    cursor = conn.cursor()
    cursor.execute("SELECT count(name) as count FROM studentdetails")
    total_student = cursor.fetchone()[0]

    stcursor = conn.cursor()
    stcursor.execute("SELECT name, roll_no, COUNT(*) AS attendance FROM attendance GROUP BY name, roll_no;")
    all_day = stcursor.fetchall()

    cursorcount = conn.cursor()
    cursorcount.execute("SELECT COUNT(DISTINCT date) AS unique_dates_count FROM attendance")
    total_att = cursorcount.fetchone()[0]
    conn.close()

    total_records = total_student
    present_count = len(data_df)
    absent_count = total_records - present_count

    overall = {
        'present': present_count,
        'absent': absent_count
    }

    student_attendance = pd.DataFrame(all_day, columns=['name', 'roll_no', 'attendance']).groupby('name')['attendance'].mean() * 100 / total_att
    student_names = student_attendance.index.tolist()
    student_percentages = student_attendance.values.tolist()

    students = {
        'names': student_names,
        'attendance': student_percentages
    }

    return jsonify({'overall': overall, 'students': students})

@app.route('/get_today_attendance_data')
def get_today_attendance_data():
    attendance_data = attendance_details()
    print(attendance_data)
    formatted_data = [(row[0], str(row[1]), str(row[2]), row[3]) for row in attendance_data]

    today_attendance = {
        'students': {
            'names': [row[0] for row in formatted_data],
            'roll_no': [row[3] for row in formatted_data]
        }
    }

    return jsonify(today_attendance)

@app.route('/search_rollno')
def search_rollno():
    return render_template('remove.html', rollno='', name='', no_data=False)

@app.route('/search_rollno', methods=['POST'])
def search_student():
    rollno = request.form.get('rollno')
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM studentdetails WHERE roll_no = %s", (rollno,))
    name = cursor.fetchone()
    conn.close()

    if not name:
        return render_template('remove.html', roll_no='', name='', no_data=True)
    return render_template('remove.html', roll_no=rollno, name=name[0], no_data=False)

@app.route('/attendance', methods=['POST'])
def attendance():
    selected_date = request.form.get('selected_date')
    selected_date_obj = datetime.strptime(selected_date, '%Y-%m-%d')
    formatted_date = selected_date_obj.strftime('%Y-%m-%d')

    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT roll_no, name, time FROM attendance WHERE date = %s", (formatted_date,))
    attendance_data = cursor.fetchall()
    conn.close()

    if not attendance_data:
        return render_template('attendance.html', selected_date=selected_date, no_data=True)
    return render_template('attendance.html', selected_date=selected_date, attendance_data=attendance_data)

def attendance_details():
    formatted_date = datetime.today().strftime('%Y-%m-%d')
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name, time, date, roll_no FROM attendance WHERE date = %s", (formatted_date,))
    attendance_data = cursor.fetchall()
    conn.close()
    return attendance_data

@app.route('/classes')
def view_classes():
    conn = create_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT class, COUNT(*) as total_students FROM studentdetails GROUP BY class")
    class_summaries = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('classes.html', class_summaries=class_summaries)

@app.route('/class/<class_name>')
def view_class_details(class_name):
    conn = create_connection()
    cursor = conn.cursor(dictionary=True)
    
    query = """
    SELECT 
        s.name, 
        s.roll_no,
        IFNULL((COUNT(a.date) / (SELECT COUNT(DISTINCT date) FROM attendance) * 100), 0) AS attendance
    FROM 
        studentdetails s
    LEFT JOIN 
        attendance a ON s.roll_no = a.roll_no
    WHERE 
        s.class = %s
    GROUP BY 
        s.name, s.roll_no
    """
    
    cursor.execute(query, (class_name,))
    class_details = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(class_details)

if __name__ == '__main__':
    app.run(debug=True)
