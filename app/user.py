# app/user.py
from flask import Blueprint, render_template, session, redirect, url_for, request, flash, make_response
from app.db import get_db
from app.utils import html_to_image
import pandas as pd
import uuid
import os
import tempfile
from datetime import datetime, timedelta
import pytz

user_bp = Blueprint('user', __name__, url_prefix='/user')

def get_ksa_time():
    return datetime.now(pytz.timezone('Asia/Riyadh'))

@user_bp.route('/dashboard')
def dashboard():
    db = get_db()
    with db.cursor() as cursor:
        cursor.execute("""
            SELECT u.id, u.name, 
                   SUM(p.earned_point) AS total_point,
                   SUM(p.earned_point = 5) AS exact_point_5,
                   SUM(p.earned_point = 3) AS goal_diff_point_3,
                   SUM(p.earned_point = 2) AS similar_point_2,
                   SUM(p.earned_point = 1) AS draw_point_1,
                   SUM(p.earned_point = -1) AS no_participation_point
            FROM users u
            LEFT JOIN predictions p ON u.id = p.user_id
            GROUP BY u.id, u.name
        """)
        rows = cursor.fetchall()

    df = pd.DataFrame(rows).fillna(0)
    for col in df.columns:
        if col != 'name':
            df[col] = df[col].astype(int)

    df.sort_values(
        by=['total_point', 'exact_point_5', 'goal_diff_point_3',
            'similar_point_2', 'draw_point_1', 'no_participation_point', 'name'],
        ascending=[False, False, False, False, False, False, True],
        inplace=True
    )
    df['rank'] = range(1, len(df) + 1)

    return render_template("user.html", name=session['name'], df=df)

@user_bp.route('/open_matches')
def open_matches():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('auth.phone_step'))

    now = get_ksa_time()
    db = get_db()
    with db.cursor() as cursor:
        # BETWEEN 15 minutes and 24 hours from now
        cursor.execute("""
            SELECT m.*, 
                   p.pred_home, p.pred_away, p.pred_outcome, p.pred_final_winner
            FROM matches m
            LEFT JOIN predictions p ON m.id = p.match_id AND p.user_id = %s
            WHERE TIMESTAMPDIFF(MINUTE, %s, m.match_time) BETWEEN 15 AND 1440
            ORDER BY m.match_time ASC
        """, (user_id, now))
        matches = cursor.fetchall()

    return render_template('open_matches.html', matches=matches, now=now)

@user_bp.route('/save_prediction', methods=['POST'])
def save_prediction():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('auth.phone_step'))

    match_id = request.form.get('match_id')
    pred_home = request.form.get('pred_home')
    pred_away = request.form.get('pred_away')

    db = get_db()
    with db.cursor() as cursor:
        cursor.execute("SELECT home_team, away_team, match_stage FROM matches WHERE id = %s", (match_id,))
        match = cursor.fetchone()

        if not all([pred_home, pred_away]):
            flash("يرجى إدخال التوقعات بشكل صحيح", 'danger')
            return redirect(url_for('user.open_matches'))

        pred_home = int(pred_home)
        pred_away = int(pred_away)

        if pred_home > pred_away:
            pred_outcome = match['home_team']
            pred_final_winner = pred_outcome
        elif pred_home < pred_away:
            pred_outcome = match['away_team']
            pred_final_winner = pred_outcome
        else:
            if match['match_stage'] == "Group":
                pred_outcome = "Draw"
                pred_final_winner = "Draw"
            elif match['match_stage'] == "Knockout":
                pred_outcome = "Final Winner"
                pred_final_winner = request.form.get('final_winner') or ""
                if not pred_final_winner:
                    flash("اختر الفريق الفائز عند التعادل في مرحلة خروج المغلوب", 'danger')
                    return redirect(url_for('user.open_matches'))
            else:
                pred_outcome = "Unknown"
                pred_final_winner = ""

        cursor.execute("""
            INSERT INTO predictions (user_id, match_id, pred_home, pred_away, pred_outcome, pred_final_winner)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                pred_home = VALUES(pred_home),
                pred_away = VALUES(pred_away),
                pred_outcome = VALUES(pred_outcome),
                pred_final_winner = VALUES(pred_final_winner)
        """, (user_id, match_id, pred_home, pred_away, pred_outcome, pred_final_winner))
        db.commit()

    flash("تم حفظ التوقع بنجاح", 'success')
    return redirect(url_for('user.open_matches'))

@user_bp.route('/closed_matches')
def closed_matches():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('auth.phone_step'))

    now = get_ksa_time()
    db = get_db()
    with db.cursor() as cursor:
        cursor.execute("""
            SELECT m.*, 
                   p.pred_home, p.pred_away, p.pred_outcome, p.pred_final_winner, p.earned_point
            FROM matches m
            LEFT JOIN predictions p ON m.id = p.match_id AND p.user_id = %s
            WHERE m.match_time <= %s - INTERVAL 15 MINUTE
            ORDER BY m.match_time DESC
        """, (user_id, now))
        matches = cursor.fetchall()

    return render_template('closed_matches.html', matches=matches, now=now)

@user_bp.route('/privileges')
def privileges():
    return "Privileges"

@user_bp.route('/ranking')
def ranking():
    return "Ranking Table"

@user_bp.route('/rules')
def rules():
    return "Rules"

@user_bp.route('/export_match/<int:match_id>')
def export_match(match_id):
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('auth.phone_step'))

    db = get_db()
    with db.cursor() as cursor:
        cursor.execute("SELECT * FROM matches WHERE id = %s", (match_id,))
        match = cursor.fetchone()

        cursor.execute("""
            SELECT * FROM predictions WHERE user_id = %s AND match_id = %s
        """, (user_id, match_id))
        my_pred = cursor.fetchone()

        cursor.execute("""
            SELECT u.name, p.pred_home, p.pred_away, p.pred_outcome, p.earned_point
            FROM predictions p
            JOIN users u ON u.id = p.user_id
            WHERE match_id = %s
        """, (match_id,))
        others = cursor.fetchall()

    html = render_template('export_template.html', match=match, my_pred=my_pred, others=others)
    temp_path = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4().hex}.png")
    html_to_image(html, temp_path)

    with open(temp_path, "rb") as f:
        response = make_response(f.read())
        response.headers.set('Content-Type', 'image/png')
        response.headers.set('Content-Disposition', f'attachment; filename=match_{match_id}.png')
        return response
