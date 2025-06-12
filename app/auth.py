# app/auth.py

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from app.db import get_db
import re

# Create Blueprint
auth_bp = Blueprint('auth', __name__)

# --- Phone normalization ---
def normalize_phone(phone):
    phone = re.sub(r'[\s\-\(\)]', '', phone)
    if phone.startswith('00966'):
        return '+966' + phone[5:]
    elif phone.startswith('966'):
        return '+966' + phone[3:]
    elif phone.startswith('05'):
        return '+966' + phone[1:]
    elif phone.startswith('5'):
        return '+966' + phone
    elif phone.startswith('+966'):
        return phone
    else:
        return None

# --- Step 1: Phone input ---
@auth_bp.route('/', methods=['GET', 'POST'])
def phone_step():
    if request.method == 'POST':
        phone_input = request.form.get('phone')
        phone = normalize_phone(phone_input)

        if not phone:
            flash("الرقم غير صحيح", 'danger')
            return render_template('login.html')

        db = get_db()
        with db.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE phone = %s", (phone,))
            user = cursor.fetchone()

        if user:
            session['login_phone'] = phone
            return redirect(url_for('auth.password_step'))
        else:
            flash("هذا الرقم غير مسجل", 'danger')

    return render_template('login.html')

# --- Step 2: Password verification ---
@auth_bp.route('/password', methods=['GET', 'POST'])
def password_step():
    phone = session.get('login_phone')
    if not phone:
        return redirect(url_for('auth.phone_step'))

    db = get_db()
    with db.cursor() as cursor:
        cursor.execute("SELECT * FROM users WHERE phone = %s", (phone,))
        user = cursor.fetchone()

    if request.method == 'POST':
        password_input = request.form.get('password')

        if user and str(user['password']) == str(password_input):
            session['user_id'] = user['id']
            session['name'] = user['name']
            session['is_admin'] = user['is_admin']
            session['first_login'] = user['first_login']

            if user['first_login']:
                return redirect(url_for('auth.first_login'))

            if user['is_admin']:
                return redirect(url_for('admin.dashboard'))
            else:
                return redirect(url_for('user.dashboard'))
        else:
            flash("كلمة المرور غير صحيحة", 'danger')

    return render_template('password.html', phone=phone)

# --- Step 3: First login - set password + upload photo ---
@auth_bp.route('/first_login', methods=['GET', 'POST'])
def first_login():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('auth.phone_step'))

    if request.method == 'POST':
        new_password = request.form.get('new_password')
        photo_file = request.files.get('photo')

        if not new_password or not photo_file:
            flash("يرجى إدخال كلمة مرور وتحميل صورة", 'warning')
            return render_template('first_login.html')

        photo_filename = f"{user_id}_{photo_file.filename}"
        photo_path = f"app/static/uploads/{photo_filename}"
        photo_file.save(photo_path)

        db = get_db()
        with db.cursor() as cursor:
            cursor.execute("""
                UPDATE users 
                SET password = %s, photo = %s, first_login = 0 
                WHERE id = %s
            """, (new_password, photo_filename, user_id))
            db.commit()

        session['first_login'] = 0

        if session['is_admin']:
            return redirect(url_for('admin.dashboard'))
        else:
            return redirect(url_for('user.dashboard'))

    return render_template('first_login.html')
