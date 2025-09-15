import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import warnings
import json

warnings.filterwarnings('ignore')

app = Flask(__name__)

# --- Configuration and Initialization ---
app.config['SECRET_KEY'] = 'a-very-secret-and-unique-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# --- Database Models ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    assessments = db.relationship('Assessment', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Assessment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.DateTime, nullable=False, default=pd.Timestamp.now)
    risk_score = db.Column(db.Float, nullable=False)
    risk_level = db.Column(db.String(20), nullable=False)
    data = db.Column(db.JSON, nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Rules-Based "Model" for Risk Prediction ---
def predict_risk(age, lump, skin_changes, nipple_changes, family_history, menarche_age, first_pregnancy_age, hrt, breast_problems, alcohol, activity, weight, smoking):
    score = 0
    max_score = 25 # Total maximum possible score

    # Basic Info
    if age > 50: score += 2
    if lump == 'yes': score += 5
    if skin_changes == 'yes': score += 3
    if nipple_changes == 'yes': score += 3
    
    # Family & Personal History
    if family_history == 'one': score += 3
    if family_history == 'multiple': score += 5
    if breast_problems != 'no': score += 2
    
    # Reproductive History
    if menarche_age == 'before_12': score += 1
    if first_pregnancy_age == 'after_30': score += 2
    if first_pregnancy_age == 'never': score += 3
    if hrt == 'yes': score += 1

    # Lifestyle Factors
    if alcohol == 'heavy': score += 2
    if smoking == 'current': score += 2
    if weight == 'overweight' or weight == 'obese': score += 2
    if activity == 'sedentary': score += 1

    risk_percentage = min((score / max_score) * 100, 100)
    
    return risk_percentage

def get_risk_level(score):
    if score >= 70:
        return 'High Risk'
    elif score >= 30:
        return 'Moderate Risk'
    else:
        return 'Low Risk'

# --- Application Routes ---
@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('home.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        if user:
            flash('Username already exists. Please choose a different one.')
            return redirect(url_for('signup'))

        new_user = User(username=username)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        
        login_user(new_user)
        flash('Account created successfully!')
        return redirect(url_for('dashboard'))
    
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password. Please try again.')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.')
    return redirect(url_for('home'))

# The new multi-step questionnaire routes
@app.route('/assessment')
@login_required
def dashboard():
    return redirect(url_for('step1'))

@app.route('/assessment/step1', methods=['GET', 'POST'])
@login_required
def step1():
    if request.method == 'POST':
        session['age'] = request.form['age']
        session['lump'] = request.form['lump']
        session['skin_changes'] = request.form['skin_changes']
        session['nipple_changes'] = request.form['nipple_changes']
        return redirect(url_for('step2'))
    return render_template('step1.html')

@app.route('/assessment/step2', methods=['GET', 'POST'])
@login_required
def step2():
    if request.method == 'POST':
        session['family_history'] = request.form['family_history']
        session['breast_problems'] = request.form['breast_problems']
        return redirect(url_for('step3'))
    return render_template('step2.html')

@app.route('/assessment/step3', methods=['GET', 'POST'])
@login_required
def step3():
    if request.method == 'POST':
        session['menarche_age'] = request.form['menarche_age']
        session['first_pregnancy_age'] = request.form['first_pregnancy_age']
        session['hrt'] = request.form['hrt']
        return redirect(url_for('step4'))
    return render_template('step3.html')

@app.route('/assessment/step4', methods=['GET', 'POST'])
@login_required
def step4():
    if request.method == 'POST':
        session['alcohol'] = request.form['alcohol']
        session['activity'] = request.form['activity']
        session['weight'] = request.form['weight']
        session['smoking'] = request.form['smoking']

        # Get all data from the session
        age = int(session.get('age', 0))
        lump = session.get('lump')
        skin_changes = session.get('skin_changes')
        nipple_changes = session.get('nipple_changes')
        family_history = session.get('family_history')
        breast_problems = session.get('breast_problems')
        menarche_age = session.get('menarche_age')
        first_pregnancy_age = session.get('first_pregnancy_age')
        hrt = session.get('hrt')
        alcohol = session.get('alcohol')
        activity = session.get('activity')
        weight = session.get('weight')
        smoking = session.get('smoking')

        risk_score = predict_risk(age, lump, skin_changes, nipple_changes, family_history, menarche_age, first_pregnancy_age, hrt, breast_problems, alcohol, activity, weight, smoking)
        risk_level = get_risk_level(risk_score)

        assessment_data = {
            'age': age,
            'lump': lump,
            'skin_changes': skin_changes,
            'nipple_changes': nipple_changes,
            'family_history': family_history,
            'breast_problems': breast_problems,
            'menarche_age': menarche_age,
            'first_pregnancy_age': first_pregnancy_age,
            'hrt': hrt,
            'alcohol': alcohol,
            'activity': activity,
            'weight': weight,
            'smoking': smoking
        }

        # Save assessment to database
        new_assessment = Assessment(
            user_id=current_user.id,
            risk_score=risk_score,
            risk_level=risk_level,
            data=json.dumps(assessment_data)
        )
        db.session.add(new_assessment)
        db.session.commit()
        
        session.pop('age', None)
        session.pop('lump', None)
        session.pop('skin_changes', None)
        session.pop('nipple_changes', None)
        session.pop('family_history', None)
        session.pop('breast_problems', None)
        session.pop('menarche_age', None)
        session.pop('first_pregnancy_age', None)
        session.pop('hrt', None)
        session.pop('alcohol', None)
        session.pop('activity', None)
        session.pop('weight', None)
        session.pop('smoking', None)
        
        return redirect(url_for('show_result', assessment_id=new_assessment.id))
    
    return render_template('step4.html')


@app.route('/results')
@login_required
def results():
    user_assessments = Assessment.query.filter_by(user_id=current_user.id).order_by(Assessment.date.desc()).all()
    # Decode the JSON data for display
    for assessment in user_assessments:
        assessment.data = json.loads(assessment.data)
    
    return render_template('results.html', assessments=user_assessments)

@app.route('/result/<int:assessment_id>')
@login_required
def show_result(assessment_id):
    assessment = Assessment.query.get_or_404(assessment_id)
    if assessment.user_id != current_user.id:
        flash("You are not authorized to view this assessment.")
        return redirect(url_for('results'))
    
    assessment_data = json.loads(assessment.data)

    risk_level = assessment.risk_level
    risk_score = assessment.risk_score
    
    # Simple logic for recommendations
    if risk_score > 70:
        recommendations = 'high'
    elif risk_score > 30:
        recommendations = 'moderate'
    else:
        recommendations = 'low'
    
    return render_template('results.html', 
                           assessments=[assessment],
                           current_assessment_data=assessment_data,
                           risk_level=risk_level,
                           risk_score=risk_score,
                           recommendations=recommendations,
                           is_single_result=True
                          )
    
# --- Main Entry Point ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)