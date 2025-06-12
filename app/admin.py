# app/admin.py

from flask import Blueprint, render_template, request, redirect, session, url_for, flash
from app.db import get_db
from app.earned_point import calculate_earned_points
from datetime import datetime
import pandas as pd

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def admin_required():
    if not session.get('user_id') or not session.get('is_admin'):
        return redirect(url_for('auth.phone_step'))

@admin_bp.route('/dashboard')
def dashboard():
    if not session.get('is_admin'):
        return redirect(url_for('auth.phone_step'))
    return render_template('admin.html', name=session['name'])


@admin_bp.route('/update_scores', methods=['GET', 'POST'])
def update_scores():
    admin_required()
    db = get_db()
    with db.cursor() as cursor:
        if request.method == 'POST':
            match_id = request.form['match_id']
            score_home = request.form['final_score_home']
            score_away = request.form['final_score_away']

            # Calculate outcome + final_winner
            score_home, score_away = int(score_home), int(score_away)
            outcome = ""
            final_winner = ""
            cursor.execute("SELECT team1, team2, stage FROM matches WHERE id = %s", (match_id,))
            match = cursor.fetchone()

            if score_home > score_away:
                outcome = match['team1']
                final_winner = outcome
            elif score_home < score_away:
                outcome = match['team2']
                final_winner = outcome
            else:
                outcome = "Draw"
                final_winner = "Draw"
                if match['stage'] == "Knockout":
                    final_winner = request.form.get('final_winner')

            cursor.execute("""
                UPDATE matches
                SET final_score_home=%s, final_score_away=%s, outcome=%s, final_winner=%s
                WHERE id = %s
            """, (score_home, score_away, outcome, final_winner, match_id))

            db.commit()
            calculate_earned_points(match_id)
            flash("تم تحديث النتائج وتحديث النقاط", "success")
            return redirect(url_for('admin.update_scores'))

        cursor.execute("SELECT * FROM matches ORDER BY date_time DESC")
        matches = cursor.fetchall()
    return render_template('admin_update_scores.html', matches=matches)

@admin_bp.route('/user_control', methods=['GET', 'POST'])
def user_control():
    admin_required()
    db = get_db()
    with db.cursor() as cursor:
        if request.method == 'POST':
            name = request.form['name']
            phone = request.form['phone']
            is_jocker = int(request.form.get('is_jocker', 0))
            is_hunter = int(request.form.get('is_hunter', 0))
            password = request.form['password']

            cursor.execute("""
                INSERT INTO users (name, phone, is_jocker, is_hunter, password, first_login)
                VALUES (%s, %s, %s, %s, %s, 1)
            """, (name, phone, is_jocker, is_hunter, password))
            db.commit()
            flash("تم إضافة المستخدم بنجاح", "success")
            return redirect(url_for('admin.user_control'))

        cursor.execute("SELECT * FROM users ORDER BY id DESC")
        users = cursor.fetchall()
    return render_template('admin_user_control.html', users=users)

@admin_bp.route('/match_control', methods=['GET', 'POST'])
def match_control():
    admin_required()
    db = get_db()
    with db.cursor() as cursor:
        if request.method == 'POST':
            team1 = request.form['team1']
            team2 = request.form['team2']
            stage = request.form['stage']
            date_time = request.form['date_time']
            cursor.execute("""
                INSERT INTO matches (team1, team2, stage, date_time)
                VALUES (%s, %s, %s, %s)
            """, (team1, team2, stage, date_time))
            db.commit()
            flash("تمت إضافة المباراة", "success")
            return redirect(url_for('admin.match_control'))

        cursor.execute("SELECT * FROM matches ORDER BY date_time DESC")
        matches = cursor.fetchall()
    return render_template('admin_match_control.html', matches=matches)


@admin_bp.route('/ranking')
def admin_ranking():
    admin_required()
    db = get_db()
    with db.cursor() as cursor:
        cursor.execute("""
            SELECT u.id, u.name, 
                   SUM(p.earned_point) AS total_point,
                   SUM(p.earned_point = 5) AS exact_point_5,
                   SUM(p.earned_point = 3) AS goal_diff_point_3,
                   SUM(p.earned_point = 2) AS winner_only_point_2,
                   SUM(p.earned_point = 1) AS draw_wrong_winner_1,
                   SUM(p.earned_point = -1) AS no_participation_m1
            FROM users u
            LEFT JOIN predictions p ON u.id = p.user_id
            GROUP BY u.id, u.name
        """)
        rows = cursor.fetchall()
    df = pd.DataFrame(rows).fillna(0)
    df[[
        'total_point', 'exact_point_5', 'goal_diff_point_3',
        'winner_only_point_2', 'draw_wrong_winner_1', 'no_participation_m1'
    ]] = df[[
        'total_point', 'exact_point_5', 'goal_diff_point_3',
        'winner_only_point_2', 'draw_wrong_winner_1', 'no_participation_m1'
    ]].astype(int)
    df.sort_values(
        by=['total_point', 'exact_point_5', 'goal_diff_point_3',
            'winner_only_point_2', 'draw_wrong_winner_1', 'no_participation_m1', 'name'],
        ascending=[False]*5 + [True]*2,
        inplace=True
    )
    df['rank'] = range(1, len(df)+1)
    return render_template('ranking.html', df=df, current_user_id=None)


@admin_bp.route('/stats')
def stats():
    admin_required()
    db = get_db()
    with db.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) AS total_users FROM users")
        total_users = cursor.fetchone()['total_users']
        cursor.execute("SELECT COUNT(DISTINCT user_id) AS active_users FROM predictions")
        active_users = cursor.fetchone()['active_users']
        cursor.execute("SELECT COUNT(*) AS total_predictions FROM predictions")
        total_predictions = cursor.fetchone()['total_predictions']
    return render_template("admin_stats.html", users=total_users, active=active_users, predictions=total_predictions)


@admin_bp.route('/stats')
def admin_stats():
    admin_required()
    db = get_db()
    with db.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) AS total_users FROM users")
        total_users = cursor.fetchone()['total_users']
        cursor.execute("SELECT COUNT(DISTINCT user_id) AS active_users FROM predictions")
        active_users = cursor.fetchone()['active_users']
        cursor.execute("SELECT COUNT(*) AS total_predictions FROM predictions")
        total_predictions = cursor.fetchone()['total_predictions']
    return render_template("admin_stats.html", users=total_users, active=active_users, predictions=total_predictions)
