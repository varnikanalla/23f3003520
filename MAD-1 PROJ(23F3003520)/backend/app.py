import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, date
from functools import wraps



# Configuration & Initialization
app = Flask(__name__, template_folder='../frontend/templates', static_folder='../frontend/static')
app.config['SECRET_KEY'] = 'change-this-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(os.path.dirname(__file__), 'instance', 'hospital.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

os.makedirs(os.path.join(os.path.dirname(__file__), 'instance'), exist_ok=True)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@app.errorhandler(404)
def not_found(e):
    flash("Page not found (404).", "danger")
    return redirect(url_for("index"))

@app.errorhandler(500)
def server_error(e):
    flash("Internal Server Error (500).", "danger")
    return redirect(url_for("index"))

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(180), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(50), nullable=False)
    full_name = db.Column(db.String(80), nullable=False)
    phone = db.Column(db.String(10))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)

class Department(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.Text)
    doctors = db.relationship('Doctor', backref='department', lazy=True)

class Doctor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'), nullable=False)
    specialization = db.Column(db.String(80))
    qualification = db.Column(db.String(100))
    experience_years = db.Column(db.Integer)
    consultation_fee = db.Column(db.Float, default=0.0)
    user = db.relationship('User', backref=db.backref('doctor_profile', uselist=False))
    appointments = db.relationship('Appointment', backref='doctor', lazy=True)
    availability = db.relationship('DoctorAvailability', backref='doctor', cascade='all, delete-orphan')

class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)
    date_of_birth = db.Column(db.Date)
    gender = db.Column(db.String(40))
    blood_group = db.Column(db.String(6))
    address = db.Column(db.Text)
    emergency_contact = db.Column(db.String(10))
    user = db.relationship('User', backref=db.backref('patient_profile', uselist=False))
    appointments = db.relationship('Appointment', backref='patient', lazy=True)

class DoctorAvailability(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    is_available = db.Column(db.Boolean, default=True)

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.id'), nullable=False)
    appointment_date = db.Column(db.Date, nullable=False)
    appointment_time = db.Column(db.Time, nullable=False)
    status = db.Column(db.String(50), default='Booked')
    reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    treatment = db.relationship('Treatment', backref='appointment', uselist=False, cascade='all, delete-orphan')

class Treatment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointment.id'), nullable=False, unique=True)
    diagnosis = db.Column(db.Text, nullable=False)
    prescription = db.Column(db.Text)
    notes = db.Column(db.Text)
    follow_up_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Helper Functions
@login_manager.user_loader
def load_user(user_id): return User.query.get(int(user_id))

def role_required(role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role != role:
                flash('Access denied', 'danger')
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def init_db():
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', email='admin@hospital.com', role='admin', full_name='Admin', phone='1234567890')
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print("Admin: admin/admin123")
        
        if Department.query.count()==0:
            for name, desc in [('Cardiology', 'Heart'), ('Neurology', 'Brain'), ('Orthopedics', 'Bones'), 
                               ('Pediatrics', 'Children'), ('Dermatology', 'Skin'), ('General Medicine', 'General')]:
                db.session.add(Department(name=name, description=desc))
            db.session.commit()
            print("Departments created")

# Routes - Home & Auth
@app.route('/')
def index(): return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('dashboard_redirect'))
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username')).first()
        if user and user.check_password(request.form.get('password')) and user.is_active:
            login_user(user)
            flash(f'Welcome {user.full_name}', 'success')
            return redirect(url_for('dashboard_redirect'))
        flash('Invalid credentials', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out', 'info')
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated: return redirect(url_for('dashboard_redirect'))
    if request.method == 'POST':
        if request.form.get('password') != request.form.get('confirm_password'):
            flash('Passwords do not match', 'danger')
            return redirect(url_for('register'))
        if User.query.filter_by(username=request.form.get('username')).first():
            flash('Username exists', 'danger')
            return redirect(url_for('register'))
        
        user = User(username=request.form.get('username'), email=request.form.get('email'), role='patient',
                   full_name=request.form.get('full_name'), phone=request.form.get('phone'))
        user.set_password(request.form.get('password'))
        db.session.add(user)
        db.session.flush()
        
        patient = Patient(user_id=user.id, 
                         date_of_birth=datetime.strptime(request.form.get('dob'), '%Y-%m-%d').date() if request.form.get('dob') else None,
                         gender=request.form.get('gender'), blood_group=request.form.get('blood_group'),
                         address=request.form.get('address'), emergency_contact=request.form.get('emergency_contact'))
        db.session.add(patient)
        db.session.commit()
        flash('Registration successful', 'success')
        return redirect(url_for('login'))
    return render_template('patient/register.html')

@app.route('/dashboard')
@login_required
def dashboard_redirect():
    return redirect(url_for(f"{current_user.role}_dashboard"))

# Admin Routes
@app.route('/admin/dashboard')
@login_required
@role_required('admin')
def admin_dashboard():
    return render_template('admin/dashboard.html',
        total_doctors=Doctor.query.join(User).filter(User.is_active).count(),
        total_patients=Patient.query.join(User).filter(User.is_active).count(),
        total_appointments=Appointment.query.count(),
        pending_appointments=Appointment.query.filter_by(status='Booked').count(),
        recent_appointments=Appointment.query.order_by(Appointment.created_at.desc()).limit(5).all())

@app.route('/admin/add-doctor', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def add_doctor():
    if request.method == 'POST':
        user = User(username=request.form.get('username'), email=request.form.get('email'), role='doctor',
                   full_name=request.form.get('full_name'), phone=request.form.get('phone'))
        user.set_password(request.form.get('password'))
        db.session.add(user)
        db.session.flush()
        doctor = Doctor(user_id=user.id, department_id=request.form.get('department_id'),
                       specialization=request.form.get('specialization'), qualification=request.form.get('qualification'),
                       experience_years=int(request.form.get('experience_years', 0)),
                       consultation_fee=float(request.form.get('consultation_fee', 0)))
        db.session.add(doctor)
        db.session.commit()
        flash('Doctor added', 'success')
        return redirect(url_for('admin_doctors'))
    return render_template('admin/add_doctor.html', departments=Department.query.all())

@app.route('/admin/doctors')
@login_required
@role_required('admin')
def admin_doctors():
    return render_template('admin/doctors.html', doctors=Doctor.query.join(User).filter(User.is_active).all())

@app.route('/admin/edit-doctor/<int:doctor_id>', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def edit_doctor(doctor_id):
    doctor = Doctor.query.get_or_404(doctor_id)
    if request.method == 'POST':
        doctor.user.full_name = request.form.get('full_name')
        doctor.user.email = request.form.get('email')
        doctor.user.phone = request.form.get('phone')
        doctor.department_id = request.form.get('department_id')
        doctor.specialization = request.form.get('specialization')
        doctor.qualification = request.form.get('qualification')
        doctor.experience_years = int(request.form.get('experience_years', 0))
        doctor.consultation_fee = float(request.form.get('consultation_fee', 0))
        if request.form.get('password'): doctor.user.set_password(request.form.get('password'))
        db.session.commit()
        flash('Updated', 'success')
        return redirect(url_for('admin_doctors'))
    return render_template('admin/edit_doctor.html', doctor=doctor, departments=Department.query.all())

@app.route('/admin/delete-doctor/<int:doctor_id>', methods=['POST'])
@login_required
@role_required('admin')
def delete_doctor(doctor_id):
    Doctor.query.get_or_404(doctor_id).user.is_active = False
    db.session.commit()
    flash('Doctor deactivated', 'success')
    return redirect(url_for('admin_doctors'))

@app.route('/admin/patients')
@login_required
@role_required('admin')
def admin_patients():
    return render_template('admin/patients.html', patients=Patient.query.join(User).filter(User.is_active).all())

@app.route('/admin/edit-patient/<int:patient_id>', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def edit_patient(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    if request.method == 'POST':
        patient.user.full_name = request.form.get('full_name')
        patient.user.email = request.form.get('email')
        patient.user.phone = request.form.get('phone')
        if request.form.get('dob'): patient.date_of_birth = datetime.strptime(request.form.get('dob'), '%Y-%m-%d').date()
        patient.gender = request.form.get('gender')
        patient.blood_group = request.form.get('blood_group')
        patient.address = request.form.get('address')
        patient.emergency_contact = request.form.get('emergency_contact')
        db.session.commit()
        flash('Updated', 'success')
        return redirect(url_for('admin_patients'))
    return render_template('admin/edit_patient.html', patient=patient)

@app.route('/admin/delete-patient/<int:patient_id>', methods=['POST'])
@login_required
@role_required('admin')
def delete_patient(patient_id):
    Patient.query.get_or_404(patient_id).user.is_active = False
    db.session.commit()
    flash('Patient deactivated', 'success')
    return redirect(url_for('admin_patients'))

@app.route('/admin/appointments')
@login_required
@role_required('admin')
def admin_appointments():
    status = request.args.get('status', 'all')
    query = Appointment.query if status == 'all' else Appointment.query.filter_by(status=status)
    return render_template('admin/appointments.html', 
        appointments=query.order_by(Appointment.appointment_date.desc()).all(), status_filter=status)

@app.route('/admin/search', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_search():
    results = {'doctors': [], 'patients': [], 'departments': []}
    search_query = ''
    if request.method == 'POST':
        search_query = request.form.get('search_query', '').strip()
        search_type = request.form.get('search_type', 'all')
        if search_query:
            if search_type in ['all', 'doctors']:
                results['doctors'] = Doctor.query.join(User).filter(User.is_active, 
                    (User.full_name.ilike(f'%{search_query}%')) | (Doctor.specialization.ilike(f'%{search_query}%'))).all()
            if search_type in ['all', 'patients']:
                results['patients'] = Patient.query.join(User).filter(User.is_active,
                    (User.full_name.ilike(f'%{search_query}%')) | (User.phone.ilike(f'%{search_query}%'))).all()
            if search_type in ['all', 'departments']:
                results['departments'] = Department.query.filter(Department.name.ilike(f'%{search_query}%')).all()
    return render_template('admin/search.html', results=results, search_query=search_query)

# Doctor Routes
@app.route('/doctor/dashboard')
@login_required
@role_required('doctor')
def doctor_dashboard():
    doctor = Doctor.query.filter_by(user_id=current_user.id).first()
    today, week_end = date.today(), date.today() + timedelta(days=7)
    return render_template('doctor/dashboard.html', doctor=doctor,
        upcoming_appointments=Appointment.query.filter(Appointment.doctor_id==doctor.id, 
            Appointment.appointment_date>=today, Appointment.appointment_date<=week_end, 
            Appointment.status=='Booked').order_by(Appointment.appointment_date, Appointment.appointment_time).all(),
        today_appointments=Appointment.query.filter_by(doctor_id=doctor.id, appointment_date=today)
            .order_by(Appointment.appointment_time).all(),
        total_patients=len(db.session.query(Appointment.patient_id).filter_by(doctor_id=doctor.id).distinct().all()))

@app.route('/doctor/appointments')
@login_required
@role_required('doctor')
def doctor_appointments():
    doctor = Doctor.query.filter_by(user_id=current_user.id).first()
    status = request.args.get('status', 'all')
    query = Appointment.query.filter_by(doctor_id=doctor.id)
    if status != 'all': query = query.filter_by(status=status)
    return render_template('doctor/appointments.html', 
        appointments=query.order_by(Appointment.appointment_date.desc()).all(), status_filter=status)

@app.route('/doctor/appointment/<int:appointment_id>/complete', methods=['GET', 'POST'])
@login_required
@role_required('doctor')
def complete_appointment(appointment_id):
    doctor = Doctor.query.filter_by(user_id=current_user.id).first()
    appointment = Appointment.query.filter_by(id=appointment_id, doctor_id=doctor.id).first_or_404()
    if request.method == 'POST':
        appointment.status = 'Completed'
        treatment = Treatment.query.filter_by(appointment_id=appointment.id).first()
        if treatment:
            treatment.diagnosis = request.form.get('diagnosis')
            treatment.prescription = request.form.get('prescription')
            treatment.notes = request.form.get('notes')
            if request.form.get('follow_up_date'): 
                treatment.follow_up_date = datetime.strptime(request.form.get('follow_up_date'), '%Y-%m-%d').date()
        else:
            treatment = Treatment(appointment_id=appointment.id, diagnosis=request.form.get('diagnosis'),
                prescription=request.form.get('prescription'), notes=request.form.get('notes'),
                follow_up_date=datetime.strptime(request.form.get('follow_up_date'), '%Y-%m-%d').date() 
                    if request.form.get('follow_up_date') else None)
            db.session.add(treatment)
        db.session.commit()
        flash('Appointment completed', 'success')
        return redirect(url_for('doctor_appointments'))
    return render_template('doctor/complete_appointment.html', appointment=appointment)

@app.route('/doctor/appointment/<int:appointment_id>/cancel', methods=['POST'])
@login_required
@role_required('doctor')
def doctor_cancel_appointment(appointment_id):
    doctor = Doctor.query.filter_by(user_id=current_user.id).first()
    Appointment.query.filter_by(id=appointment_id, doctor_id=doctor.id).first_or_404().status = 'Cancelled'
    db.session.commit()
    flash('Cancelled', 'success')
    return redirect(url_for('doctor_appointments'))

@app.route('/doctor/patient/<int:patient_id>/history')
@login_required
@role_required('doctor')
def patient_history(patient_id):
    doctor = Doctor.query.filter_by(user_id=current_user.id).first()
    patient = Patient.query.get_or_404(patient_id)
    appointments = Appointment.query.filter_by(patient_id=patient_id, doctor_id=doctor.id, status='Completed')\
        .order_by(Appointment.appointment_date.desc()).all()
    return render_template('doctor/patient_history.html', patient=patient, appointments=appointments)

@app.route('/doctor/availability', methods=['GET', 'POST'])
@login_required
@role_required('doctor')
def doctor_availability():
    doctor = Doctor.query.filter_by(user_id=current_user.id).first()
    today, week_end = date.today(), date.today() + timedelta(days=7)
    if request.method == 'POST':
        DoctorAvailability.query.filter(DoctorAvailability.doctor_id==doctor.id, 
            DoctorAvailability.date>=today, DoctorAvailability.date<=week_end).delete()
        for i in range(7):
            avail_date = today + timedelta(days=i)
            date_str = avail_date.strftime('%Y-%m-%d')
            if request.form.get(f'available_{date_str}'):
                start = request.form.get(f'start_time_{date_str}')
                end = request.form.get(f'end_time_{date_str}')
                if start and end:
                    db.session.add(DoctorAvailability(doctor_id=doctor.id, date=avail_date,
                        start_time=datetime.strptime(start, '%H:%M').time(),
                        end_time=datetime.strptime(end, '%H:%M').time(), is_available=True))
        db.session.commit()
        flash('Availability updated', 'success')
        return redirect(url_for('doctor_availability'))
    availability = DoctorAvailability.query.filter(DoctorAvailability.doctor_id==doctor.id,
        DoctorAvailability.date>=today, DoctorAvailability.date<=week_end).all()
    return render_template('doctor/availability.html', dates=[today + timedelta(days=i) for i in range(7)],
        availability_dict={a.date: a for a in availability})

# Patient Routes
@app.route('/patient/dashboard')
@login_required
@role_required('patient')
def patient_dashboard():
    patient = Patient.query.filter_by(user_id=current_user.id).first()
    today, week_end = date.today(), date.today() + timedelta(days=7)
    return render_template('patient/dashboard.html', patient=patient, departments=Department.query.all(),
        upcoming_appointments=Appointment.query.filter(Appointment.patient_id==patient.id,
            Appointment.appointment_date>=today, Appointment.status=='Booked')
            .order_by(Appointment.appointment_date, Appointment.appointment_time).limit(5).all(),
        available_doctors=Doctor.query.join(User).join(DoctorAvailability).filter(User.is_active,
            DoctorAvailability.date>=today, DoctorAvailability.date<=week_end, 
            DoctorAvailability.is_available).distinct().limit(6).all())

@app.route('/patient/profile', methods=['GET', 'POST'])
@login_required
@role_required('patient')
def patient_profile():
    patient = Patient.query.filter_by(user_id=current_user.id).first()
    if request.method == 'POST':
        current_user.full_name = request.form.get('full_name')
        current_user.email = request.form.get('email')
        current_user.phone = request.form.get('phone')
        if request.form.get('dob'): patient.date_of_birth = datetime.strptime(request.form.get('dob'), '%Y-%m-%d').date()
        patient.gender = request.form.get('gender')
        patient.blood_group = request.form.get('blood_group')
        patient.address = request.form.get('address')
        patient.emergency_contact = request.form.get('emergency_contact')
        if request.form.get('password'): current_user.set_password(request.form.get('password'))
        db.session.commit()
        flash('Profile updated', 'success')
        return redirect(url_for('patient_profile'))
    return render_template('patient/profile.html', patient=patient)

@app.route('/patient/doctors')
@login_required
@role_required('patient')
def patient_doctors():
    search = request.args.get('search', '')
    dept_id = request.args.get('department', '')
    query = Doctor.query.join(User).filter(User.is_active)
    if search: query = query.filter((User.full_name.ilike(f'%{search}%')) | (Doctor.specialization.ilike(f'%{search}%')))
    if dept_id: query = query.filter(Doctor.department_id==dept_id)
    doctors = query.all()
    today, week_end = date.today(), date.today() + timedelta(days=7)
    doctor_availability = {d.id: DoctorAvailability.query.filter(DoctorAvailability.doctor_id==d.id,
        DoctorAvailability.date>=today, DoctorAvailability.date<=week_end, 
        DoctorAvailability.is_available).all() for d in doctors}
    return render_template('patient/doctors.html', doctors=doctors, departments=Department.query.all(),
        doctor_availability=doctor_availability, search_query=search, selected_department=dept_id)

@app.route('/patient/book-appointment/<int:doctor_id>', methods=['GET', 'POST'])
@login_required
@role_required('patient')
def book_appointment(doctor_id):
    patient = Patient.query.filter_by(user_id=current_user.id).first()
    doctor = Doctor.query.get_or_404(doctor_id)
    today, week_end = date.today(), date.today() + timedelta(days=7)
    availability = DoctorAvailability.query.filter(DoctorAvailability.doctor_id==doctor.id,
        DoctorAvailability.date>=today, DoctorAvailability.date<=week_end, 
        DoctorAvailability.is_available).all()
    if request.method == 'POST':
        appt_date = datetime.strptime(request.form.get('appointment_date'), '%Y-%m-%d').date()
        appt_time = datetime.strptime(request.form.get('appointment_time'), '%H:%M').time()
        if Appointment.query.filter_by(doctor_id=doctor.id, appointment_date=appt_date, 
                appointment_time=appt_time, status='Booked').first():
            flash('Time slot already booked', 'danger')
            return redirect(url_for('book_appointment', doctor_id=doctor_id))
        db.session.add(Appointment(patient_id=patient.id, doctor_id=doctor.id, appointment_date=appt_date,
            appointment_time=appt_time, reason=request.form.get('reason'), status='Booked'))
        db.session.commit()
        flash('Appointment booked', 'success')
        return redirect(url_for('patient_appointments'))
    return render_template('patient/book_appointment.html', doctor=doctor, availability=availability)

@app.route('/patient/appointments')
@login_required
@role_required('patient')
def patient_appointments():
    patient = Patient.query.filter_by(user_id=current_user.id).first()
    status = request.args.get('status', 'all')
    query = Appointment.query.filter_by(patient_id=patient.id)
    if status != 'all': query = query.filter_by(status=status)
    return render_template('patient/my_appointments.html',
        appointments=query.order_by(Appointment.appointment_date.desc()).all(), status_filter=status)

@app.route('/patient/appointment/<int:appointment_id>/cancel', methods=['POST'])
@login_required
@role_required('patient')
def cancel_appointment(appointment_id):
    patient = Patient.query.filter_by(user_id=current_user.id).first()
    appointment = Appointment.query.filter_by(id=appointment_id, patient_id=patient.id).first_or_404()
    if appointment.status == 'Booked':
        appointment.status = 'Cancelled'
        db.session.commit()
        flash('Appointment cancelled', 'success')
    return redirect(url_for('patient_appointments'))

@app.route('/patient/treatment-history')
@login_required
@role_required('patient')
def treatment_history():
    patient = Patient.query.filter_by(user_id=current_user.id).first()
    appointments = Appointment.query.filter_by(patient_id=patient.id, status='Completed')\
        .order_by(Appointment.appointment_date.desc()).all()
    return render_template('patient/treatment_history.html', appointments=appointments)

# Error Handlers
@app.errorhandler(404)
def not_found(e): return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(e):
    db.session.rollback()
    return render_template('500.html'), 500

# Run
if __name__ == '__main__':
    init_db()
    app.run(debug=True)