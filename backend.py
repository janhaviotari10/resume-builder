from flask import Flask, render_template, request, redirect, session
import mysql.connector
import json # CRITICAL: Import json for handling list/dictionary data stored as strings in DB

# NOTE: The template_folder is set to 'frontend' to match your setup.
app = Flask(__name__, template_folder='frontend', static_folder='static')
app.secret_key = 'your_secret_key_here' # **CRITICAL: Change this to a unique, secret value**

# --- Database Connection ---
class DummyCursor:
    """A safe placeholder if the database connection fails."""
    def execute(self, *args): pass
    def fetchone(self): return None
    def fetchall(self): return []
    def commit(self): pass

try:
    db = mysql.connector.connect(
        host="localhost",
        user="root",
        password="", # Update if you have a password
        database="resumebuilder"
    )
    # Use dictionary=True so that fetchone returns a dictionary (column_name: value)
    cursor = db.cursor(buffered=True, dictionary=True) 
    print("Database connection successful.")
except mysql.connector.Error as err:
    print(f"Database Connection Error: {err}. Authentication and data saving are disabled.")
    # Use the dummy cursor if connection fails
    cursor = DummyCursor()
    
# Helper function to ensure user is logged in
def check_login():
    if 'resume_email' not in session:
        return redirect('/login.html')
    return None

# --- Helper function to fetch and structure resume data ---
def get_resume_data(email):
    """Fetches resume data from DB and returns a structured dictionary."""
    try:
        # Fetch the resume data. We select all columns from the resumes table.
        cursor.execute("SELECT * FROM resumes WHERE email=%s", (email,))
        resume_data_dict = cursor.fetchone()
        
        if not resume_data_dict:
            return None # No data found

        # 1. Deserialize the JSON strings back into Python objects
        # Safely parse JSON fields, defaulting to an empty dict/list if the data is NULL or parsing fails.
        def safe_json_load(data, default_type):
            if data:
                try:
                    return json.loads(data)
                except (json.JSONDecodeError, TypeError):
                    print(f"Warning: Could not decode JSON data: {data}")
            return default_type()

        structured_resume = {
            # Assuming your 'resumes' table has these columns (adjust if needed)
            'email': resume_data_dict.get('email'),
            'personal_data': safe_json_load(resume_data_dict.get('personal_data'), dict),
            'summary': resume_data_dict.get('summary', ''),
            'experience': safe_json_load(resume_data_dict.get('experience'), list),
            'education': safe_json_load(resume_data_dict.get('education'), list),
            'skills': safe_json_load(resume_data_dict.get('skills'), list),
            'template': resume_data_dict.get('template', 'modern') # Default to 'modern'
        }
        
        return structured_resume

    except Exception as e:
        print(f"Database error during resume data fetch: {e}")
        return None

# --- Authentication Routes ---
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
        full_name = f"{fname} {lname}"
        
        try:
            cursor.execute("SELECT email FROM users WHERE email=%s", (email,))
            if cursor.fetchone():
                return render_template('signup.html', error="Email already registered.")
            
            cursor.execute("INSERT INTO users (name, email, password) VALUES (%s, %s, %s)", (full_name, email, password))
            # CRITICAL: Create an initial resume entry for the new user
            cursor.execute("INSERT INTO resumes (email, template) VALUES (%s, 'modern')", (email,))
            db.commit()
            
            session['resume_email'] = email
            return redirect('/login.html')
        except Exception as e:
            if isinstance(cursor, DummyCursor):
                 return render_template('signup.html', error="Signup is disabled due to a database connection error.")
            print(f"Signup error: {e}")
            return render_template('signup.html', error="A database error occurred.")
        
    return render_template('signup.html', error=None)

@app.route('/login.html', methods=['GET', 'POST'])
def login():
    error = None

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        try:
            cursor.execute("SELECT password FROM users WHERE email=%s", (email,))
            result = cursor.fetchone()

            if result:
                stored_password = result['password']
                if password == stored_password:
                    session['resume_email'] = email
                    return redirect('/dashboard.html')
                else:
                    error = "Incorrect password. Please try again."
            else:
                error = "No account found with that email. Please sign up first."
        except Exception as e:
            if isinstance(cursor, DummyCursor):
                error = "Login is disabled due to a database connection error."
            else:
                error = f"A database error occurred during login: {e}"

    return render_template('login.html', error=error)

@app.route('/dashboard.html')
def dashboard():
    if check_login(): return check_login()
    return render_template('dashboard.html')

@app.route('/logout.html')
def logout():
    session.pop('resume_email', None)
    return redirect('/login.html')

# --- Data Saving Routes ---
@app.route('/save_personal', methods=['POST'])
def save_personal():
    if check_login(): return check_login()
    user_email = session['resume_email']
    
    personal_data = {
        'fname': request.form.get('fname'),
        'lname': request.form.get('lname'),
        'email': request.form.get('email'),
        'phone': request.form.get('phone'),
        'address': request.form.get('address'),
        'linkedin': request.form.get('linkedin')
    }
    
    try:
        cursor.execute("UPDATE resumes SET personal_data=%s WHERE email=%s", 
                      (json.dumps(personal_data), user_email))
        db.commit()
        return redirect('/summary.html')
    except Exception as e:
        print(f"Error saving personal data: {e}")
        return redirect('/personal.html')

@app.route('/save_summary', methods=['POST'])
def save_summary():
    if check_login(): return check_login()
    user_email = session['resume_email']
    summary_text = request.form.get('summary', '')
    
    try:
        cursor.execute("UPDATE resumes SET summary=%s WHERE email=%s", 
                      (summary_text, user_email))
        db.commit()
        return redirect('/experience.html')
    except Exception as e:
        print(f"Error saving summary: {e}")
        return redirect('/summary.html')

@app.route('/save_experience', methods=['POST'])
def save_experience():
    if check_login(): return check_login()
    user_email = session['resume_email']
    
    experiences = []
    # Handle multiple experience entries
    job_titles = request.form.getlist('job_title[]')
    companies = request.form.getlist('company[]')
    durations = request.form.getlist('duration[]')
    descriptions = request.form.getlist('description[]')
    
    for i in range(len(job_titles)):
        if job_titles[i]:  # Only add non-empty entries
            experiences.append({
                'job_title': job_titles[i],
                'company': companies[i],
                'duration': durations[i],
                'description': descriptions[i]
            })
    
    try:
        cursor.execute("UPDATE resumes SET experience=%s WHERE email=%s", 
                      (json.dumps(experiences), user_email))
        db.commit()
        return redirect('/education.html')
    except Exception as e:
        print(f"Error saving experience: {e}")
        return redirect('/experience.html')

@app.route('/save_education', methods=['POST'])
def save_education():
    if check_login(): return check_login()
    user_email = session['resume_email']
    
    educations = []
    degrees = request.form.getlist('degree[]')
    institutions = request.form.getlist('institution[]')
    years = request.form.getlist('year[]')
    
    for i in range(len(degrees)):
        if degrees[i]:  # Only add non-empty entries
            educations.append({
                'degree': degrees[i],
                'institution': institutions[i],
                'year': years[i]
            })
    
    try:
        cursor.execute("UPDATE resumes SET education=%s WHERE email=%s", 
                      (json.dumps(educations), user_email))
        db.commit()
        return redirect('/skills.html')
    except Exception as e:
        print(f"Error saving education: {e}")
        return redirect('/education.html')

@app.route('/save_skills', methods=['POST'])
def save_skills():
    if check_login(): return check_login()
    user_email = session['resume_email']
    
    skills = request.form.get('skills', '').split(',')
    skills = [skill.strip() for skill in skills if skill.strip()]
    
    try:
        cursor.execute("UPDATE resumes SET skills=%s WHERE email=%s", 
                      (json.dumps(skills), user_email))
        db.commit()
        return redirect('/project.html')
    except Exception as e:
        print(f"Error saving skills: {e}")
        return redirect('/skills.html')

@app.route('/save_projects', methods=['POST'])
def save_projects():
    if check_login(): return check_login()
    user_email = session['resume_email']
    
    projects = []
    project_names = request.form.getlist('project_name[]')
    project_descriptions = request.form.getlist('project_description[]')
    
    for i in range(len(project_names)):
        if project_names[i]:  # Only add non-empty entries
            projects.append({
                'name': project_names[i],
                'description': project_descriptions[i]
            })
    
    try:
        cursor.execute("UPDATE resumes SET projects=%s WHERE email=%s", 
                      (json.dumps(projects), user_email))
        db.commit()
        return redirect('/template.html')
    except Exception as e:
        print(f"Error saving projects: {e}")
        return redirect('/project.html')

# --- Resume Step Routes ---
@app.route('/personal.html', methods=['GET', 'POST'])
def personal():
    if check_login(): return check_login()
    if request.method == 'POST':
        return save_personal()
    
    # Load existing data if available
    user_email = session['resume_email']
    resume_data = get_resume_data(user_email)
    return render_template('personal.html', resume=resume_data)

@app.route('/summary.html', methods=['GET', 'POST'])
def summary():
    if check_login(): return check_login()
    if request.method == 'POST':
        return save_summary()
    
    # Load existing data if available
    user_email = session['resume_email']
    resume_data = get_resume_data(user_email)
    return render_template('summary.html', resume=resume_data)

@app.route('/experience.html', methods=['GET', 'POST'])
def experience():
    if check_login(): return check_login()
    if request.method == 'POST':
        return save_experience()
    
    # Load existing data if available
    user_email = session['resume_email']
    resume_data = get_resume_data(user_email)
    return render_template('experience.html', resume=resume_data)

@app.route('/education.html', methods=['GET', 'POST'])
def education():
    if check_login(): return check_login()
    if request.method == 'POST':
        return save_education()
    
    # Load existing data if available
    user_email = session['resume_email']
    resume_data = get_resume_data(user_email)
    return render_template('education.html', resume=resume_data)

@app.route('/skills.html', methods=['GET', 'POST'])
def skills():
    if check_login(): return check_login()
    if request.method == 'POST':
        return save_skills()
    
    # Load existing data if available
    user_email = session['resume_email']
    resume_data = get_resume_data(user_email)
    return render_template('skills.html', resume=resume_data)

@app.route('/project.html', methods=['GET', 'POST'])
def project():
    if check_login(): return check_login()
    if request.method == 'POST':
        return save_projects()
    
    # Load existing data if available
    user_email = session['resume_email']
    resume_data = get_resume_data(user_email)
    return render_template('project.html', resume=resume_data)

# --- Template Selection and Preview Routes ---
@app.route('/select_template/<template_name>')
def select_template(template_name):
    if check_login(): return check_login()
    user_email = session['resume_email']
    
    # 1. Validate template name
    valid_templates = [ 'modern', 'classic', 'clean', 'simple', 'professional' ]
    if template_name not in valid_templates:
        return redirect('/template.html') 
        
    try:
        # 2. Save the new template selection to the database
        cursor.execute("UPDATE resumes SET template=%s WHERE email=%s", 
                       (template_name, user_email))
        db.commit()
    except Exception as e:
        print(f"Database error saving template: {e}")
        
    # 3. Redirect the user to the preview page for the selected template
    return redirect(f'/{template_name}.html') 

@app.route('/template.html', methods=['GET'])
def template_selector():
    if check_login(): return check_login() 
    user_email = session['resume_email']
    
    resume_data = get_resume_data(user_email)
    return render_template('template.html', resume=resume_data)

# *** TEMPLATE PREVIEW ROUTES ***
# These routes are for *viewing* the resume and must fetch existing data.

def render_template_preview(template_name):
    """Helper function to fetch resume data and render the specific template."""
    user_email = session.get('resume_email')
    if not user_email:
        return redirect('/login.html')

    structured_resume_data = get_resume_data(user_email)
    
    # If no data is found, provide a default empty structure so the template doesn't crash
    if not structured_resume_data:
        # Create an empty, safe structure for the Jinja template to use
        structured_resume_data = {
            'email': user_email,
            'personal_data': {},
            'summary': '',
            'experience': [],
            'education': [],
            'skills': [],
            'template': template_name
        }

    # CRITICAL FIX: Render the specific template file (e.g., 'modern.html')
    return render_template(f'{template_name}.html', resume=structured_resume_data)

@app.route('/modern.html')
def modern_preview():
    if check_login(): return check_login()
    # Renders 'modern.html' with data
    return render_template_preview('modern')

@app.route('/classic.html')
def classic_preview():
    if check_login(): return check_login()
    # Renders 'classic.html' with data
    return render_template_preview('classic')

@app.route('/clean.html')
def clean_preview():
    if check_login(): return check_login()
    # Renders 'clean.html' with data
    return render_template_preview('clean')

@app.route('/simple.html')
def simple_preview():  # Changed from clean_preview to simple_preview
    if check_login(): return check_login()
    # Renders 'simple.html' with data
    return render_template_preview('simple')

@app.route('/professional.html')
def professional_preview():  # Changed from clean_preview to professional_preview
    if check_login(): return check_login()
    # Renders 'professional.html' with data
    return render_template_preview('professional')

# Optional: Redirect /preview.html to the currently selected template for consistency
@app.route('/preview.html')
def preview():
    user_email = session.get('resume_email')
    if not user_email: return redirect('/login.html')
    
    resume_data = get_resume_data(user_email)
    
    # Redirect to the currently selected template route
    template = resume_data.get('template', 'modern') if resume_data else 'modern'
    return redirect(f'/{template}.html')

if __name__ == '__main__':
    # Run with debug=True during development
    app.run(debug=True)
