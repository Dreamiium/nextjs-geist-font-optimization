from flask import Flask, render_template, redirect, url_for, request, flash, session, abort
from config import Config
from models import db, Category, Course, Enrollment
import pandas as pd
import os

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

# Create database tables
with app.app_context():
    db.create_all()

def import_data_from_excel():
    """Import course data from Excel."""
    print("Starting Excel import...")
    
    # Clear existing data
    print("Clearing existing data...")
    try:
        Enrollment.query.delete()
        Course.query.delete()
        Category.query.delete()
        db.session.commit()
        print("Existing data cleared successfully")
    except Exception as e:
        print(f"Error clearing data: {e}")
        db.session.rollback()
        return

    try:
        excel_file = '../sheet 1 data.xlsx'
        print(f"Checking for Excel file at: {os.path.abspath(excel_file)}")
        if not os.path.exists(excel_file):
            print(f"Excel file not found at: {os.path.abspath(excel_file)}")
            flash(f'Excel file {excel_file} not found.', 'danger')
            return
        print("Excel file found, proceeding with import")
        
        df = pd.read_excel(excel_file, engine='openpyxl')
        
        # Create categories and map them to their column ranges
        categories = {
            'Beautician and Skin Care': {'cols': (3, 10), 'id': None},
            'Building Electrician': {'cols': (10, 17), 'id': None},
            'Plumbing': {'cols': (17, 24), 'id': None},
            'CCTV Camera': {'cols': (24, 31), 'id': None},
            'Front Desk Operation': {'cols': (34, 41), 'id': None},
            'Food & Beverage (F&B)': {'cols': (41, 48), 'id': None}
        }

        # Add categories to database
        for cat_name in categories:
            category = Category(name=cat_name)
            db.session.add(category)
            db.session.commit()
            categories[cat_name]['id'] = category.id

        # Process data starting from row 3 (where actual data begins)
        print("Processing Excel rows...")
        for idx in range(3, len(df)):
            row = df.iloc[idx]
            cluster = row['Unnamed: 1']
            district = row['Unnamed: 2']
            
            if pd.isna(cluster) or pd.isna(district):
                continue

            # Process each category
            for cat_name, cat_info in categories.items():
                start_col, end_col = cat_info['cols']
                print(f"\nProcessing {cat_name} for {district} ({cluster})")
                
                course_name = f"{cat_name} - {district} ({cluster})"
                course = Course(
                    name=course_name,
                    category_id=cat_info['id']
                )
                db.session.add(course)
                db.session.commit()

                # Add week enrollments (first 3 columns)
                for week_idx in range(3):
                    col_idx = start_col + week_idx
                    value = row.iloc[col_idx]
                    if not pd.isna(value):
                        enrollment = Enrollment(
                            course_id=course.id,
                            period_type='week',
                            period_number=week_idx + 1,
                            student_count=int(value)
                        )
                        db.session.add(enrollment)

                # Add month enrollments (next 3 columns, representing months 2-4)
                for month_idx in range(3):
                    col_idx = start_col + 4 + month_idx
                    value = row.iloc[col_idx]
                    if not pd.isna(value):
                        enrollment = Enrollment(
                            course_id=course.id,
                            period_type='month',
                            period_number=month_idx + 2,  # months 2-4
                            student_count=int(value)
                        )
                        db.session.add(enrollment)
                
                db.session.commit()

    except Exception as e:
        print(f"Error during import: {e}")
        db.session.rollback()
        flash("Error during Excel import.", "danger")

# Import data on startup
with app.app_context():
    import_data_from_excel()

# Authentication decorator
def login_required(f):
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            flash('Please log in first!', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

# Routes
def get_enrollment_count(enrollments, period_type, period_number):
    enrollment = next(
        (e for e in enrollments 
         if e.period_type == period_type and e.period_number == period_number),
        None
    )
    return enrollment.student_count if enrollment else 0

@app.route('/')
@app.route('/dashboard')
def dashboard():
    categories = Category.query.all()
    chart_data = {}
    
    for category in categories:
        chart_data[category.id] = {
            'name': category.name,
            'courses': [],
            'week1_data': [],
            'week2_data': [],
            'week3_data': [],
            'week4_data': [],
            'month2_data': [],
            'month3_data': [],
            'month4_data': []
        }
        
        for course in category.courses:
            chart_data[category.id]['courses'].append(course.name)
            chart_data[category.id]['week1_data'].append(
                get_enrollment_count(course.enrollments, 'week', 1)
            )
            chart_data[category.id]['week2_data'].append(
                get_enrollment_count(course.enrollments, 'week', 2)
            )
            chart_data[category.id]['week3_data'].append(
                get_enrollment_count(course.enrollments, 'week', 3)
            )
            chart_data[category.id]['week4_data'].append(
                get_enrollment_count(course.enrollments, 'week', 4)
            )
            chart_data[category.id]['month2_data'].append(
                get_enrollment_count(course.enrollments, 'month', 2)
            )
            chart_data[category.id]['month3_data'].append(
                get_enrollment_count(course.enrollments, 'month', 3)
            )
            chart_data[category.id]['month4_data'].append(
                get_enrollment_count(course.enrollments, 'month', 4)
            )
    
    # For graphs, only pass week1 and week2 data
    graph_data = {}
    for cat_id, data in chart_data.items():
        graph_data[cat_id] = {
            'name': data['name'],
            'courses': data['courses'],
            'week1_data': data['week1_data'],
            'week2_data': data['week2_data']
        }
    
    print("Chart Data:", chart_data)  # Debug print
    print("Graph Data:", graph_data)  # Debug print
    return render_template('dashboard.html', categories=categories, chart_data=chart_data, graph_data=graph_data)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == 'admin' and password == 'password123':
            session['logged_in'] = True
            flash('Successfully logged in!', 'success')
            return redirect(url_for('admin'))
        else:
            flash('Invalid credentials. Please try again.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('dashboard'))

@app.route('/admin')
@login_required
def admin():
    categories = Category.query.all()
    return render_template('admin.html', categories=categories)

@app.route('/admin/course/new', methods=['GET', 'POST'])
@login_required
def new_course():
    categories = Category.query.all()
    if request.method == 'POST':
        try:
            course = Course(
                name=request.form.get('name'),
                category_id=request.form.get('category_id')
            )
            db.session.add(course)
            db.session.commit()

            # Add enrollments
            for week in range(1, 4):
                count = request.form.get(f'week_{week}')
                if count:
                    enrollment = Enrollment(
                        course_id=course.id,
                        period_type='week',
                        period_number=week,
                        student_count=int(count)
                    )
                    db.session.add(enrollment)

            for month in range(1, 5):
                count = request.form.get(f'month_{month}')
                if count:
                    enrollment = Enrollment(
                        course_id=course.id,
                        period_type='month',
                        period_number=month,
                        student_count=int(count)
                    )
                    db.session.add(enrollment)

            db.session.commit()
            flash('Course added successfully!', 'success')
            return redirect(url_for('admin'))
        except Exception as e:
            db.session.rollback()
            flash('Error adding course. Please check inputs.', 'danger')
    return render_template('course_form.html', action='new', categories=categories)

@app.route('/admin/course/edit/<int:course_id>', methods=['GET', 'POST'])
@login_required
def edit_course(course_id):
    course = Course.query.get_or_404(course_id)
    categories = Category.query.all()
    
    if request.method == 'POST':
        try:
            course.name = request.form.get('name')
            course.category_id = request.form.get('category_id')
            
            # Update enrollments
            for week in range(1, 4):
                count = request.form.get(f'week_{week}')
                enrollment = Enrollment.query.filter_by(
                    course_id=course.id,
                    period_type='week',
                    period_number=week
                ).first()
                
                if count:
                    if enrollment:
                        enrollment.student_count = int(count)
                    else:
                        enrollment = Enrollment(
                            course_id=course.id,
                            period_type='week',
                            period_number=week,
                            student_count=int(count)
                        )
                        db.session.add(enrollment)

            for month in range(1, 5):
                count = request.form.get(f'month_{month}')
                enrollment = Enrollment.query.filter_by(
                    course_id=course.id,
                    period_type='month',
                    period_number=month
                ).first()
                
                if count:
                    if enrollment:
                        enrollment.student_count = int(count)
                    else:
                        enrollment = Enrollment(
                            course_id=course.id,
                            period_type='month',
                            period_number=month,
                            student_count=int(count)
                        )
                        db.session.add(enrollment)

            db.session.commit()
            flash('Course updated successfully!', 'success')
            return redirect(url_for('admin'))
        except Exception as e:
            db.session.rollback()
            flash('Error updating course. Please check inputs.', 'danger')
    
    return render_template('course_form.html', 
                         action='edit', 
                         course=course, 
                         categories=categories)

@app.route('/admin/course/delete/<int:course_id>', methods=['POST'])
@login_required
def delete_course(course_id):
    course = Course.query.get_or_404(course_id)
    try:
        db.session.delete(course)
        db.session.commit()
        flash('Course deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error deleting course.', 'danger')
    return redirect(url_for('admin'))

@app.errorhandler(404)
def page_not_found(e):
    return render_template('error_404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('error_500.html'), 500

if __name__ == '__main__':
    app.run(debug=True, port=8000)
