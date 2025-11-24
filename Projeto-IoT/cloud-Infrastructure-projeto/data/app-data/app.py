# Local imports
import datetime
import os

# Third part imports
from flask import Flask
from flask import request
import pandas as pd
import joblib
import gzip
import json

from flask import Flask, request, jsonify
import pandas as pd
import joblib
import gzip
from sklearn.cluster import KMeans

from modules.functions import get_model_response

from flask import Flask, jsonify
from db import get_connection


def get_stats_day(cursor, year, month, week, day):
    cursor.execute("""
        SELECT 
            COUNT(*) AS sessions,
            SUM(energy_kwh) AS total_energy,
            AVG(energy_kwh) AS avg_energy,
            SUM(estimated_cost) AS total_cost,
            AVG(estimated_cost) AS avg_cost
        FROM sessions
        WHERE YEAR(start_time) = %s
        AND MONTH(start_time) = %s
        AND WEEK(start_time, 3) = %s
        AND DAY(start_time) = %s
    """, (year, month, week, day))
    row = cursor.fetchone()
    return row

def get_stats_month(cursor, year, month):
    cursor.execute("""
        SELECT 
            COUNT(*) AS sessions,
            SUM(energy_kwh) AS total_energy,
            AVG(energy_kwh) AS avg_energy,
            SUM(estimated_cost) AS total_cost,
            AVG(estimated_cost) AS avg_cost
        FROM sessions
        WHERE YEAR(start_time) = %s
        AND MONTH(start_time) = %s
    """, (year, month))
    row = cursor.fetchone()
    return row

def get_stats_year(cursor, year):
    cursor.execute("""
        SELECT 
            COUNT(*) AS sessions,
            SUM(energy_kwh) AS total_energy,
            AVG(energy_kwh) AS avg_energy,
            SUM(estimated_cost) AS total_cost,
            AVG(estimated_cost) AS avg_cost
        FROM sessions
        WHERE YEAR(start_time) = %s
    """, (year,))
    row = cursor.fetchone()
    return row

def row_to_json(row, cursor):
    # row pode ser tuple — e queremos nomes de colunas, por segurança mapeamos manualmente
    # se o teu cursor já retorna dicts, apenas adapta
    if not row:
        return {
            "sessions": 0,
            "total_energy": 0,
            "avg_energy": 0,
            "total_cost": 0,
            "avg_cost": 0
        }
    return {
        "sessions": row[0] or 0,
        "total_energy": float(row[1]) if row[1] is not None else 0,
        "avg_energy": float(row[2]) if row[2] is not None else 0,
        "total_cost": float(row[3]) if row[3] is not None else 0,
        "avg_cost": float(row[4]) if row[4] is not None else 0
    }



app = Flask(__name__)


MODEL_PATH = "model/energy-kmeans.dat.gz"
TRAIN_DATA_PATH = "data/EV-session.csv"

current_metrics = {
    "n_clusters": None,
    "inertia": None,
    "last_training": None
}

@app.route('/health', methods=['GET'])
def health():
    """Return service health"""
    return 'ok'


@app.get("/stats/range")
def stats_range():
    start = request.args.get("start")
    end = request.args.get("end")
    start_hour = request.args.get("startHour")
    end_hour = request.args.get("endHour")

    if not start or not end:
        return jsonify({"error": "Missing start or end date"}), 400

    conn = get_connection()
    cursor = conn.cursor()

    # ----------------------------------------
    # 1) Construir WHERE base (datas)
    # ----------------------------------------
    where = "DATE(start_time) BETWEEN %s AND %s"
    params = [start, end]

    # ----------------------------------------
    # 2) Se vierem HORAS → acrescentar ao WHERE
    # ----------------------------------------
    if start_hour and end_hour:
        where += " AND TIME(start_time) BETWEEN %s AND %s"
        params.append(start_hour)
        params.append(end_hour)

    # ----------------------------------------
    # 3) Executar a query
    # ----------------------------------------
    cursor.execute(f"""
        SELECT 
            COUNT(*) AS sessions,
            SUM(energy_kwh) AS total_energy,
            AVG(energy_kwh) AS avg_energy,
            SUM(duration_h) AS total_duration,
            AVG(duration_h) AS avg_duration,
            SUM(estimated_cost) AS total_cost,
            AVG(estimated_cost) AS avg_cost
        FROM sessions
        WHERE {where}
    """, params)

    row = cursor.fetchone()
    cursor.close()
    conn.close()

    return jsonify(row_to_json(row, cursor))


@app.get("/stats/year/<int:year>")
def stats_year(year):
    conn = get_connection()
    cursor = conn.cursor()
    row = get_stats_year(cursor, year)
    cursor.close()
    conn.close()
    return jsonify(row_to_json(row, cursor))


@app.get("/stats/month/<int:year>/<int:month>")
def stats_month(year, month):
    conn = get_connection()
    cursor = conn.cursor()
    row = get_stats_month(cursor, year, month)
    cursor.close()
    conn.close()
    return jsonify(row_to_json(row, cursor))

@app.get("/stats/week/<int:year>/<int:month>/<int:week>")
def stats_week(year, month, week):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            COUNT(*) AS sessions,
            SUM(energy_kwh) AS total_energy,
            AVG(energy_kwh) AS avg_energy,
            SUM(estimated_cost) AS total_cost,
            AVG(estimated_cost) AS avg_cost
        FROM sessions
        WHERE YEAR(start_time) = %s
            AND MONTH(start_time) = %s
            AND WEEK(start_time, 3) = %s
    """, (year, month, week))

    row = cursor.fetchone()

    cursor.close()
    conn.close()

    return jsonify(row_to_json(row, cursor))


@app.get("/stats/day/<int:year>/<int:month>/<int:week>/<int:day>")
def stats_day(year, month, week, day):
    conn = get_connection()
    cursor = conn.cursor()
    row = get_stats_day(cursor, year, month, week, day)
    cursor.close()
    conn.close()
    return jsonify(row_to_json(row, cursor))



# -----------------------------------------------------------
# 1) Available YEARS
# -----------------------------------------------------------
@app.get("/available-years")
def available_years():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT YEAR(start_time) AS year
        FROM sessions
        WHERE start_time IS NOT NULL
        ORDER BY year ASC
    """)

    years = [row[0] for row in cursor.fetchall()]

    cursor.close()
    conn.close()

    return jsonify({"years": years})


# -----------------------------------------------------------
# 2) Available MONTHS for a given year
# -----------------------------------------------------------
@app.get("/available-months/<int:year>")
def available_months(year):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT MONTH(start_time) AS month
        FROM sessions
        WHERE YEAR(start_time) = %s
        ORDER BY month ASC
    """, (year,))

    months = [row[0] for row in cursor.fetchall()]

    cursor.close()
    conn.close()

    return jsonify({"months": months})


@app.get("/available-weeks/<int:year>/<int:month>")
def available_weeks(year, month):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT WEEK(start_time, 3) AS week
        FROM sessions
        WHERE YEAR(start_time) = %s
        AND MONTH(start_time) = %s
        ORDER BY week ASC;
    """, (year, month))

    weeks = [row[0] for row in cursor.fetchall()]

    cursor.close()
    conn.close()

    return jsonify({"weeks": weeks})

# -----------------------------------------------------------
# 3) Available DAYS for a given year + month
# -----------------------------------------------------------
@app.get("/available-days/<int:year>/<int:month>/<int:week>")
def available_days(year, month, week):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT DAY(start_time) AS day
        FROM sessions
        WHERE YEAR(start_time) = %s
        AND MONTH(start_time) = %s
        AND WEEK(start_time, 3) = %s
        ORDER BY day ASC
    """, (year, month, week))

    days = [row[0] for row in cursor.fetchall()]

    

    cursor.close()
    conn.close()

    return jsonify({"days": days})

@app.get("/trends/daily/<int:year>/<int:month>")
def available_days_trends(year, month):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            DAY(start_time) AS day,
            COUNT(*) AS sessions
        FROM sessions
        WHERE YEAR(start_time) = %s
            AND MONTH(start_time) = %s
        GROUP BY DAY(start_time)
        ORDER BY day ASC;
    """, (year, month))

    result = [
        {"day": row[0], "sessions": row[1]}
        for row in cursor.fetchall()
    ]

    cursor.close()
    conn.close()

    return jsonify(result)

@app.get("/trends/weekly/<int:year>/<int:month>")
def available_weeks_trends(year, month):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            WEEK(start_time, 3) AS week,  -- modo 3 = ISO week (segunda-feira)
            COUNT(*) AS sessions
        FROM sessions
        WHERE YEAR(start_time) = %s
            AND MONTH(start_time) = %s
        GROUP BY WEEK(start_time, 3)
        ORDER BY week ASC;
    """, (year, month))

    result = [
        {"week": row[0], "sessions": row[1]}
        for row in cursor.fetchall()
    ]

    cursor.close()
    conn.close()

    return jsonify(result)

@app.get("/trends/monthly/<int:year>")
def available_months_trends(year):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            DISTINCT MONTH(start_time) AS month,
            COUNT(*) AS sessions
        FROM sessions
        WHERE YEAR(start_time) = %s
        GROUP BY MONTH(start_time)
        ORDER BY month ASC;
    """, (year,))

    result = [
        {"month": row[0], "sessions": row[1]}
        for row in cursor.fetchall()
    ]

    cursor.close()
    conn.close()

    return jsonify(result)


@app.get("/stats/time-of-day")
def stats_time_of_day():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            time_of_day,
            COUNT(*) AS sessions
        FROM sessions
        GROUP BY time_of_day
        ORDER BY sessions DESC;
    """)

    result = [
        {"period": row[0], "sessions": row[1]}
        for row in cursor.fetchall()
    ]

    cursor.close()
    conn.close()

    return jsonify(result)

@app.route('/train', methods=['POST'])
def train():
    """Treina novamente o modelo e devolve métricas"""

    df = pd.read_csv(TRAIN_DATA_PATH, sep=";")

    df.columns = [
        "user_id",
        "vehicle_model",
        "battery_capacity",
        "station_id",
        "charging_start_time",
        "charging_end_time",
        "energy_consumed",
        "charging_duration",
        "charging_rate",
        "charging_cost",
        "time_of_day",
        "day_of_week",
        "soc_start",
        "soc_end",
        "distance",
        "temperature",
        "vehicle_age"
    ]

    df["energy_consumed"] = (
        df["energy_consumed"].astype(str).str.replace(",", ".").astype(float)
    )

    X = df[["energy_consumed"]]

    kmeans = KMeans(n_clusters=3, random_state=42)
    kmeans.fit(X)

    os.makedirs("model", exist_ok=True)
    joblib.dump(kmeans, gzip.open(MODEL_PATH, "wb"))

    # Guardar métricas
    current_metrics["n_clusters"] = 3
    current_metrics["inertia"] = float(kmeans.inertia_)
    current_metrics["last_training"] = datetime.datetime.now().isoformat()

    return {
        "status": "trained",
        "metrics": current_metrics
    }, 200



'''
@app.route('/predict', methods=['POST'])
def predict():
    feature_dict = request.get_json()
    if not feature_dict:
        return {
            'error': 'Body is empty.'
        }, 500

    try:
        data = []
        model_name = feature_dict[0]['model']
        model = joblib.load('model/' + model_name + '.dat.gz')
        data.append(feature_dict[1])
        response = get_model_response(data, model)
    except ValueError as e:
        return {'error': str(e).split('\n')[-1].strip()}, 500

    return response, 200
'''

@app.route('/predict', methods=['POST'])
def predict():
    """Recebe energy_consumed e devolve o cluster"""

    try:
        payload = request.get_json()

        if "energy_consumed" not in payload:
            return {"error": "Missing 'energy_consumed'"}, 400

        energy_val = float(payload["energy_consumed"])

        # carregar modelo
        model = joblib.load(gzip.open(MODEL_PATH))

        cluster = int(model.predict([[energy_val]])[0])

        return {
            "cluster": cluster,
            "input_energy": energy_val
        }, 200

    except Exception as e:
        return {"error": str(e)}, 500


@app.route('/metrics', methods=['GET'])
def metrics():
    """Dashboard chama isto para mostrar info do modelo"""
    return current_metrics, 200



if __name__ == '__main__':
    app.run(host='0.0.0.0')
