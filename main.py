import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta, date
import plotly.express as px
import plotly.graph_objects as go
from dataclasses import dataclass
import time
import threading
import schedule

# Set page config
st.set_page_config(
    page_title="Clinic Reminder System",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #2E86AB;
        text-align: center;
        margin-bottom: 2rem;
        font-weight: bold;
    }
    .metric-card {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin: 0.5rem 0;
    }
    .success-message {
        padding: 1rem;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 5px;
        color: #155724;
        margin: 1rem 0;
    }
    .alert-message {
        padding: 1rem;
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        border-radius: 5px;
        color: #721c24;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

@dataclass
class Patient:
    name: str
    phone: str
    email: str
    whatsapp_number: str

@dataclass
class Doctor:
    name: str
    phone: str
    email: str
    specialty: str

@dataclass
class Appointment:
    patient_id: int
    doctor_id: int
    appointment_date: str
    appointment_type: str
    status: str
    follow_up_required: bool
    notes: str = ""

class DatabaseManager:
    def __init__(self, db_path="clinic_app.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create tables
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS patients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                email TEXT,
                whatsapp_number TEXT,
                created_date TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS doctors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                email TEXT NOT NULL,
                specialty TEXT,
                created_date TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER,
                doctor_id INTEGER,
                appointment_date TEXT NOT NULL,
                appointment_type TEXT,
                status TEXT DEFAULT 'scheduled',
                follow_up_required BOOLEAN DEFAULT FALSE,
                notes TEXT,
                created_date TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (patient_id) REFERENCES patients (id),
                FOREIGN KEY (doctor_id) REFERENCES doctors (id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reminder_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                appointment_id INTEGER,
                reminder_type TEXT,
                sent_date TEXT DEFAULT CURRENT_TIMESTAMP,
                status TEXT,
                FOREIGN KEY (appointment_id) REFERENCES appointments (id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def add_patient(self, patient: Patient):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO patients (name, phone, email, whatsapp_number)
            VALUES (?, ?, ?, ?)
        ''', (patient.name, patient.phone, patient.email, patient.whatsapp_number))
        patient_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return patient_id
    
    def add_doctor(self, doctor: Doctor):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO doctors (name, phone, email, specialty)
            VALUES (?, ?, ?, ?)
        ''', (doctor.name, doctor.phone, doctor.email, doctor.specialty))
        doctor_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return doctor_id
    
    def add_appointment(self, appointment: Appointment):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO appointments 
            (patient_id, doctor_id, appointment_date, appointment_type, 
             status, follow_up_required, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (appointment.patient_id, appointment.doctor_id, 
              appointment.appointment_date, appointment.appointment_type,
              appointment.status, appointment.follow_up_required, appointment.notes))
        appointment_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return appointment_id
    
    def get_patients(self):
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query("SELECT * FROM patients ORDER BY name", conn)
        conn.close()
        return df
    
    def get_doctors(self):
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query("SELECT * FROM doctors ORDER BY name", conn)
        conn.close()
        return df
    
    def get_appointments(self):
        conn = sqlite3.connect(self.db_path)
        query = '''
            SELECT a.*, p.name as patient_name, d.name as doctor_name, d.specialty
            FROM appointments a
            JOIN patients p ON a.patient_id = p.id
            JOIN doctors d ON a.doctor_id = d.id
            ORDER BY a.appointment_date DESC
        '''
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    
    def get_upcoming_appointments(self, days_ahead=7):
        conn = sqlite3.connect(self.db_path)
        future_date = (datetime.now() + timedelta(days=days_ahead)).strftime('%Y-%m-%d')
        query = '''
            SELECT a.*, p.name as patient_name, p.phone as patient_phone, 
                   p.email as patient_email, p.whatsapp_number,
                   d.name as doctor_name, d.phone as doctor_phone, 
                   d.email as doctor_email, d.specialty
            FROM appointments a
            JOIN patients p ON a.patient_id = p.id
            JOIN doctors d ON a.doctor_id = d.id
            WHERE a.appointment_date >= ? AND a.appointment_date <= ? 
            AND a.status = 'scheduled'
            ORDER BY a.appointment_date
        ''', (datetime.now().strftime('%Y-%m-%d'), future_date)
        df = pd.read_sql_query(query[0], conn, params=query[1])
        conn.close()
        return df
    
    def log_reminder(self, appointment_id, reminder_type, status):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO reminder_log (appointment_id, reminder_type, status)
            VALUES (?, ?, ?)
        ''', (appointment_id, reminder_type, status))
        conn.commit()
        conn.close()

class ReminderService:
    @staticmethod
    def send_whatsapp(phone, message):
        # Simulate WhatsApp sending
        time.sleep(0.5)  # Simulate API call
        return True
    
    @staticmethod
    def send_sms(phone, message):
        # Simulate SMS sending
        time.sleep(0.5)  # Simulate API call
        return True
    
    @staticmethod
    def send_email(email, subject, message):
        # Simulate Email sending
        time.sleep(0.5)  # Simulate API call
        return True

# Initialize database
@st.cache_resource
def init_db():
    return DatabaseManager()

db = init_db()

# App Header
st.markdown('<h1 class="main-header">🏥 Clinic Reminder System</h1>', unsafe_allow_html=True)

# Sidebar Navigation
st.sidebar.title("📋 Navigation")
page = st.sidebar.selectbox(
    "Choose a page:",
    ["Dashboard", "Patients", "Doctors", "Appointments", "Send Reminders", "Analytics"]
)

# Dashboard Page
if page == "Dashboard":
    st.header("📊 Dashboard Overview")
    
    # Get statistics
    patients_df = db.get_patients()
    doctors_df = db.get_doctors()
    appointments_df = db.get_appointments()
    upcoming_df = db.get_upcoming_appointments()
    
    # Metrics row
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("👥 Total Patients", len(patients_df))
    
    with col2:
        st.metric("👨‍⚕️ Total Doctors", len(doctors_df))
    
    with col3:
        st.metric("📅 Total Appointments", len(appointments_df))
    
    with col4:
        st.metric("⏰ Upcoming (7 days)", len(upcoming_df))
    
    st.markdown("---")
    
    # Quick Actions
    st.subheader("🚀 Quick Actions")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("➕ Add New Patient", use_container_width=True):
            st.switch_page("Patients")
    
    with col2:
        if st.button("👨‍⚕️ Add New Doctor", use_container_width=True):
            st.switch_page("Doctors")
    
    with col3:
        if st.button("📅 Schedule Appointment", use_container_width=True):
            st.switch_page("Appointments")
    
    # Recent appointments
    if not appointments_df.empty:
        st.subheader("📋 Recent Appointments")
        recent_appointments = appointments_df.head(5)
        st.dataframe(
            recent_appointments[['patient_name', 'doctor_name', 'appointment_date', 'appointment_type', 'status']],
            use_container_width=True
        )
    
    # Upcoming appointments alert
    if not upcoming_df.empty:
        st.subheader("⚠️ Upcoming Appointments Needing Reminders")
        for _, apt in upcoming_df.iterrows():
            with st.expander(f"📅 {apt['patient_name']} - {apt['appointment_date']}"):
                st.write(f"**Doctor:** Dr. {apt['doctor_name']}")
                st.write(f"**Type:** {apt['appointment_type']}")
                st.write(f"**Phone:** {apt['patient_phone']}")
                st.write(f"**Email:** {apt['patient_email']}")

# Patients Page
elif page == "Patients":
    st.header("👥 Patient Management")
    
    tab1, tab2 = st.tabs(["Add New Patient", "View Patients"])
    
    with tab1:
        st.subheader("➕ Add New Patient")
        
        with st.form("add_patient_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                name = st.text_input("Full Name *", placeholder="John Doe")
                phone = st.text_input("Phone Number *", placeholder="+1234567890")
            
            with col2:
                email = st.text_input("Email", placeholder="john@email.com")
                whatsapp = st.text_input("WhatsApp Number", placeholder="+1234567890")
            
            submitted = st.form_submit_button("Add Patient", type="primary")
            
            if submitted:
                if name and phone:
                    patient = Patient(name, phone, email, whatsapp)
                    patient_id = db.add_patient(patient)
                    st.success(f"✅ Patient '{name}' added successfully! (ID: {patient_id})")
                    st.rerun()
                else:
                    st.error("❌ Please fill in required fields (Name and Phone)")
    
    with tab2:
        st.subheader("📋 All Patients")
        patients_df = db.get_patients()
        
        if not patients_df.empty:
            st.dataframe(patients_df, use_container_width=True)
            st.info(f"📊 Total Patients: {len(patients_df)}")
        else:
            st.info("No patients found. Add your first patient!")

# Doctors Page
elif page == "Doctors":
    st.header("👨‍⚕️ Doctor Management")
    
    tab1, tab2 = st.tabs(["Add New Doctor", "View Doctors"])
    
    with tab1:
        st.subheader("➕ Add New Doctor")
        
        with st.form("add_doctor_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                name = st.text_input("Doctor Name *", placeholder="Dr. Sarah Smith")
                phone = st.text_input("Phone Number *", placeholder="+1987654321")
            
            with col2:
                email = st.text_input("Email *", placeholder="dr.smith@clinic.com")
                specialty = st.selectbox("Specialty", [
                    "General Practice", "Cardiology", "Dermatology", 
                    "Pediatrics", "Orthopedics", "Neurology", "Other"
                ])
            
            submitted = st.form_submit_button("Add Doctor", type="primary")
            
            if submitted:
                if name and phone and email:
                    doctor = Doctor(name, phone, email, specialty)
                    doctor_id = db.add_doctor(doctor)
                    st.success(f"✅ Doctor '{name}' added successfully! (ID: {doctor_id})")
                    st.rerun()
                else:
                    st.error("❌ Please fill in all required fields")
    
    with tab2:
        st.subheader("📋 All Doctors")
        doctors_df = db.get_doctors()
        
        if not doctors_df.empty:
            st.dataframe(doctors_df, use_container_width=True)
            st.info(f"📊 Total Doctors: {len(doctors_df)}")
        else:
            st.info("No doctors found. Add your first doctor!")

# Appointments Page
elif page == "Appointments":
    st.header("📅 Appointment Management")
    
    tab1, tab2 = st.tabs(["Schedule Appointment", "View Appointments"])
    
    with tab1:
        st.subheader("➕ Schedule New Appointment")
        
        patients_df = db.get_patients()
        doctors_df = db.get_doctors()
        
        if patients_df.empty or doctors_df.empty:
            st.warning("⚠️ Please add at least one patient and one doctor before scheduling appointments.")
        else:
            with st.form("add_appointment_form"):
                col1, col2 = st.columns(2)
                
                with col1:
                    patient_options = {f"{row['name']} (ID: {row['id']})": row['id'] 
                                     for _, row in patients_df.iterrows()}
                    selected_patient = st.selectbox("Select Patient *", patient_options.keys())
                    patient_id = patient_options[selected_patient]
                    
                    appointment_date = st.date_input("Appointment Date *", min_value=date.today())
                    appointment_time = st.time_input("Appointment Time *")
                
                with col2:
                    doctor_options = {f"Dr. {row['name']} - {row['specialty']} (ID: {row['id']})": row['id'] 
                                    for _, row in doctors_df.iterrows()}
                    selected_doctor = st.selectbox("Select Doctor *", doctor_options.keys())
                    doctor_id = doctor_options[selected_doctor]
                    
                    appointment_type = st.selectbox("Appointment Type *", [
                        "Consultation", "Follow-up", "Check-up", "Emergency", 
                        "Surgery", "Therapy", "Vaccination", "Other"
                    ])
                
                follow_up_required = st.checkbox("Follow-up Required")
                notes = st.text_area("Notes", placeholder="Any special instructions or notes...")
                
                submitted = st.form_submit_button("Schedule Appointment", type="primary")
                
                if submitted:
                    appointment_datetime = f"{appointment_date} {appointment_time}"
                    appointment = Appointment(
                        patient_id, doctor_id, appointment_datetime, 
                        appointment_type, "scheduled", follow_up_required, notes
                    )
                    appointment_id = db.add_appointment(appointment)
                    st.success(f"✅ Appointment scheduled successfully! (ID: {appointment_id})")
                    st.rerun()
    
    with tab2:
        st.subheader("📋 All Appointments")
        appointments_df = db.get_appointments()
        
        if not appointments_df.empty:
            # Filter options
            col1, col2, col3 = st.columns(3)
            with col1:
                status_filter = st.selectbox("Filter by Status", 
                    ["All", "scheduled", "completed", "missed", "cancelled"])
            with col2:
                doctor_filter = st.selectbox("Filter by Doctor", 
                    ["All"] + list(appointments_df['doctor_name'].unique()))
            
            # Apply filters
            filtered_df = appointments_df.copy()
            if status_filter != "All":
                filtered_df = filtered_df[filtered_df['status'] == status_filter]
            if doctor_filter != "All":
                filtered_df = filtered_df[filtered_df['doctor_name'] == doctor_filter]
            
            st.dataframe(filtered_df[[
                'patient_name', 'doctor_name', 'appointment_date', 
                'appointment_type', 'status', 'follow_up_required'
            ]], use_container_width=True)
            
            st.info(f"📊 Showing {len(filtered_df)} of {len(appointments_df)} appointments")
        else:
            st.info("No appointments found. Schedule your first appointment!")

# Send Reminders Page
elif page == "Send Reminders":
    st.header("📱 Send Reminders")
    
    upcoming_df = db.get_upcoming_appointments(days_ahead=7)
    
    if upcoming_df.empty:
        st.info("🎉 No upcoming appointments in the next 7 days!")
    else:
        st.subheader(f"⏰ {len(upcoming_df)} Upcoming Appointments")
        
        # Bulk reminder options
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("📱 Send All WhatsApp Reminders", type="primary", use_container_width=True):
                progress_bar = st.progress(0)
                success_count = 0
                
                for i, (_, apt) in enumerate(upcoming_df.iterrows()):
                    if apt['whatsapp_number']:
                        message = f"🏥 Reminder: You have an appointment with Dr. {apt['doctor_name']} on {apt['appointment_date']}"
                        if ReminderService.send_whatsapp(apt['whatsapp_number'], message):
                            db.log_reminder(apt['id'], 'WhatsApp', 'sent')
                            success_count += 1
                    progress_bar.progress((i + 1) / len(upcoming_df))
                
                st.success(f"✅ Sent {success_count} WhatsApp reminders!")
        
        with col2:
            if st.button("📨 Send All SMS Reminders", type="primary", use_container_width=True):
                progress_bar = st.progress(0)
                success_count = 0
                
                for i, (_, apt) in enumerate(upcoming_df.iterrows()):
                    if apt['patient_phone']:
                        message = f"Clinic Reminder: Appointment with Dr. {apt['doctor_name']} on {apt['appointment_date']}"
                        if ReminderService.send_sms(apt['patient_phone'], message):
                            db.log_reminder(apt['id'], 'SMS', 'sent')
                            success_count += 1
                    progress_bar.progress((i + 1) / len(upcoming_df))
                
                st.success(f"✅ Sent {success_count} SMS reminders!")
        
        with col3:
            if st.button("📧 Send All Email Reminders", type="primary", use_container_width=True):
                progress_bar = st.progress(0)
                success_count = 0
                
                for i, (_, apt) in enumerate(upcoming_df.iterrows()):
                    if apt['patient_email']:
                        subject = f"Appointment Reminder - {apt['appointment_date']}"
                        message = f"Dear {apt['patient_name']}, you have an appointment with Dr. {apt['doctor_name']} on {apt['appointment_date']}"
                        if ReminderService.send_email(apt['patient_email'], subject, message):
                            db.log_reminder(apt['id'], 'Email', 'sent')
                            success_count += 1
                    progress_bar.progress((i + 1) / len(upcoming_df))
                
                st.success(f"✅ Sent {success_count} email reminders!")
        
        st.markdown("---")
        
        # Individual appointment reminders
        st.subheader("📋 Individual Reminders")
        
        for _, apt in upcoming_df.iterrows():
            with st.expander(f"📅 {apt['patient_name']} - {apt['appointment_date']}"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write(f"**Patient:** {apt['patient_name']}")
                    st.write(f"**Doctor:** Dr. {apt['doctor_name']}")
                    st.write(f"**Type:** {apt['appointment_type']}")
                    st.write(f"**Date:** {apt['appointment_date']}")
                
                with col2:
                    st.write(f"**Phone:** {apt['patient_phone']}")
                    st.write(f"**Email:** {apt['patient_email']}")
                    st.write(f"**WhatsApp:** {apt['whatsapp_number']}")
                
                # Individual send buttons
                btn_col1, btn_col2, btn_col3 = st.columns(3)
                
                with btn_col1:
                    if st.button(f"📱 WhatsApp", key=f"wa_{apt['id']}"):
                        if apt['whatsapp_number']:
                            st.success("WhatsApp sent!")
                            db.log_reminder(apt['id'], 'WhatsApp', 'sent')
                        else:
                            st.error("No WhatsApp number")
                
                with btn_col2:
                    if st.button(f"📨 SMS", key=f"sms_{apt['id']}"):
                        if apt['patient_phone']:
                            st.success("SMS sent!")
                            db.log_reminder(apt['id'], 'SMS', 'sent')
                        else:
                            st.error("No phone number")
                
                with btn_col3:
                    if st.button(f"📧 Email", key=f"email_{apt['id']}"):
                        if apt['patient_email']:
                            st.success("Email sent!")
                            db.log_reminder(apt['id'], 'Email', 'sent')
                        else:
                            st.error("No email address")

# Analytics Page
elif page == "Analytics":
    st.header("📊 Analytics & Reports")
    
    appointments_df = db.get_appointments()
    
    if appointments_df.empty:
        st.info("No data available for analytics. Add some appointments first!")
    else:
        # Appointment status distribution
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📈 Appointment Status Distribution")
            status_counts = appointments_df['status'].value_counts()
            fig_pie = px.pie(
                values=status_counts.values, 
                names=status_counts.index,
                title="Appointment Status Breakdown"
            )
            st.plotly_chart(fig_pie, use_container_width=True)
        
        with col2:
            st.subheader("👨‍⚕️ Appointments by Doctor")
            doctor_counts = appointments_df['doctor_name'].value_counts()
            fig_bar = px.bar(
                x=doctor_counts.index, 
                y=doctor_counts.values,
                title="Appointments per Doctor"
            )
            fig_bar.update_xaxes(title_text="Doctor")
            fig_bar.update_yaxes(title_text="Number of Appointments")
            st.plotly_chart(fig_bar, use_container_width=True)
        
        # Monthly trend
        st.subheader("📅 Monthly Appointment Trend")
        appointments_df['month'] = pd.to_datetime(appointments_df['appointment_date']).dt.to_period('M')
        monthly_counts = appointments_df['month'].value_counts().sort_index()
        
        fig_line = px.line(
            x=monthly_counts.index.astype(str), 
            y=monthly_counts.values,
            title="Appointments Over Time"
        )
        fig_line.update_xaxes(title_text="Month")
        fig_line.update_yaxes(title_text="Number of Appointments")
        st.plotly_chart(fig_line, use_container_width=True)
        
        # Summary statistics
        st.subheader("📋 Summary Statistics")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Appointments", len(appointments_df))
        
        with col2:
            completed = len(appointments_df[appointments_df['status'] == 'completed'])
            st.metric("Completed", completed)
        
        with col3:
            missed = len(appointments_df[appointments_df['status'] == 'missed'])
            st.metric("Missed", missed)
        
        with col4:
            if len(appointments_df) > 0:
                completion_rate = (completed / len(appointments_df)) * 100
                st.metric("Completion Rate", f"{completion_rate:.1f}%")

# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #666; padding: 1rem;'>"
    "🏥 Clinic Reminder System | Built with ❤️ using Streamlit"
    "</div>", 
    unsafe_allow_html=True
)