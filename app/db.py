import pymysql

def get_db():
    return pymysql.connect(
        host='srv790.hstgr.io',
        user='u897165517_swg',
        password='Ysaewplps@8',
        database='u897165517_soccer_whatsap',
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True
    )
