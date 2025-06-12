# app/earned_point.py

from app.db import get_db

def calculate_earned_points(match_id):
    db = get_db()
    with db.cursor() as cursor:
        # Get match info
        cursor.execute("""
            SELECT id, final_score_home, final_score_away, outcome, final_winner, stage, is_jocker, is_hunter 
            FROM matches WHERE id = %s
        """, (match_id,))
        match = cursor.fetchone()

        if match['final_score_home'] is None or match['final_score_away'] is None:
            # Match not finished yet → set all to 0
            cursor.execute("""
                UPDATE predictions SET earned_point = 0 WHERE match_id = %s
            """, (match_id,))
            db.commit()
            return

        # Get all predictions for this match
        cursor.execute("""
            SELECT p.*, u.is_jocker, u.is_hunter 
            FROM predictions p 
            JOIN users u ON p.user_id = u.id
            WHERE p.match_id = %s
        """, (match_id,))
        predictions = cursor.fetchall()

        for pred in predictions:
            point = 0
            fh, fa = match['final_score_home'], match['final_score_away']
            ph, pa = pred['pred_home'], pred['pred_away']
            mo, po = match['outcome'], pred['pred_outcome']
            mw, pw = match['final_winner'], pred['pred_final_winner']
            stage = match['stage']

            if ph is None or pa is None:
                point = -1  # No participation
            elif fh == ph and fa == pa and mo == po and mw == pw:
                point = 5  # Exact prediction
            elif mo != "Draw" and mo == po and mw == pw:
                if (fh - fa) == (ph - pa):
                    point = 3  # Correct winner + goal diff
                else:
                    point = 2  # Correct winner only
            elif mo == "Draw":
                if stage == "Group" and po == "Draw":
                    if fh != ph or fa != pa:
                        point = 2  # Correct outcome, wrong score
                    else:
                        point = 0
                elif stage == "Knockout":
                    if pw == mw:
                        if (fh != ph or fa != pa) or po != mo:
                            point = 2
                        else:
                            point = 0
                    elif pw != mw and mo == po:
                        point = 1  # Wrong final winner
            else:
                point = 0  # Default

            # Joker or Hunter effect
            if match['is_hunter']:
                point = 0
            elif match['is_jocker']:
                if pred['is_jocker']:
                    point *= 2

            # Update prediction
            cursor.execute("""
                UPDATE predictions 
                SET earned_point = %s 
                WHERE user_id = %s AND match_id = %s
            """, (point, pred['user_id'], match_id))

        db.commit()
