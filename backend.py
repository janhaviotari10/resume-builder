from flask import Flask, render_template, request, redirect, session
import mysql.connector

app = Flask(__name__, template_folder='frontend', static_folder='static')
app.secret_key = 'your_secret_key'  # Needed for session tracking

# Connect to MySQL
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="resumebuilder"
)
cursor = db.cursor()

# Home
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/signup.html', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        fname = request.form['fname']
        lname = request.form['lname']
        email = request.form['email']
        password = request.form['password']
        full_name = f"{fname} {lname}"  # Combine first and last name
        cursor.execute("INSERT INTO users (name, email, password) VALUES (%s, %s, %s)", (full_name, email, password))
        db.commit()
        session['resume_email'] = email
        return redirect('/login.html')
    return render_template('signup.html')

# Login
@app.route('/login.html', methods=['GET', 'POST'])
def login():
    error = None

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        cursor.execute("SELECT password FROM users WHERE email=%s", (email,))
        result = cursor.fetchone()

        if result:
            stored_password = result[0]
            if password == stored_password:
                session['resume_email'] = email
                return redirect('/dashboard.html')
            else:
                error = "Incorrect password. Please try again."
        else:
            error = "No account found with that email. Please sign up first."

    return render_template('login.html', error=error)

# Dashboard
@app.route('/dashboard.html')
def dashboard():
    if 'resume_email' not in session:
        return redirect('/login.html')
    return render_template('dashboard.html')

# Personal Info
@app.route('/personal.html', methods=['GET', 'POST'])
def personal():
    if 'resume_email' not in session:
        return redirect('/login.html')  # Redirect if not logged in

    email = session['resume_email']  # ✅ Auto-filled from login

    if request.method == 'POST':
        name = request.form['name']
        # Insert or update resume record
        cursor.execute(
            "INSERT INTO resumes (name, email) VALUES (%s, %s) ON DUPLICATE KEY UPDATE name=%s",
            (name, email, name)
        )
        db.commit()
        return redirect('/summary.html')

    return render_template('personal.html')

# Summary
@app.route('/summary.html', methods=['GET', 'POST'])
def summary():
    if request.method == 'POST':
        summary = request.form['summary']
        cursor.execute("UPDATE resumes SET summary=%s WHERE email=%s", (summary, session['resume_email']))
        db.commit()
        return redirect('/experience.html')
    return render_template('summary.html')

# Experience
@app.route('/experience.html', methods=['GET', 'POST'])
def experience():
    if request.method == 'POST':
        experience = request.form['experience']
        cursor.execute("UPDATE resumes SET experience=%s WHERE email=%s", (experience, session['resume_email']))
        db.commit()
        return redirect('/education.html')
    return render_template('experience.html')

# Education
@app.route('/education.html', methods=['GET', 'POST'])
def education():
    if request.method == 'POST':
        education = request.form['education']
        cursor.execute("UPDATE resumes SET education=%s WHERE email=%s", (education, session['resume_email']))
        db.commit()
        return redirect('/skills.html')
    return render_template('education.html')

# Skills
@app.route('/skills.html', methods=['GET', 'POST'])
def skills():
    if request.method == 'POST':
        skills = request.form['skills']
        cursor.execute("UPDATE resumes SET skills=%s WHERE email=%s", (skills, session['resume_email']))
        db.commit()
        return redirect('/template.html')
    return render_template('skills.html')

@app.route('/template.html', methods=['GET', 'POST'])
def template():
    if 'resume_email' not in session:
        return redirect('/dashboard.html')  # or login.html or show an error

    if request.method == 'POST':
        selected_template = request.form['template']
        cursor.execute("UPDATE resumes SET template=%s WHERE email=%s", (selected_template, session['resume_email']))
        db.commit()
        return redirect('/preview.html')
    return render_template('template.html')

# Resume preview (optional)
@app.route('/preview.html')
def preview():
    cursor.execute("SELECT * FROM resumes WHERE email=%s", (session.get('resume_email'),))
    resume = cursor.fetchone()
    return render_template('preview.html', resume=resume)

# Run the app
if __name__ == '__main__':
    app.run(debug=True)