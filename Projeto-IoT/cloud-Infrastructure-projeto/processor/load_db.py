import pandas as pd
import time
import mysql.connector

'''
def clean_float(v):
    if v is None:
        return None
    v = str(v).strip()
    if v.lower() in ["nan", "none", "", "null"]:
        return None
    v = v.replace(",", ".")
    try:
        return float(v)
    except:
        return None
'''

def clean_float(v):
    if v is None:
        return None
    if isinstance(v, float) and pd.isna(v):
        return None
    v = str(v).strip().replace(",", ".")
    if v.lower() in ["nan", "none", "", "null", "-", "--"]:
        return None
    try:
        return float(v)
    except:
        return None


def clean_str(v):
    if v is None:
        return None
    if isinstance(v, float) and pd.isna(v):
        return None
    v = str(v).strip()
    if v.lower() in ["nan", "none", "", "null"]:
        return None
    return v

def clean_int(v):
    if v is None:
        return None
    v = str(v).strip()
    if v.lower() in ["nan", "none", "", "null"]:
        return None
    v = v.replace(",", ".")
    try:
        return int(float(v))
    except:
        return None


# -----------------------------
# CONFIG BD
# -----------------------------
DB_HOST = "mysql"     # ou "mysql" se fores usar Docker
DB_USER = "root"
DB_PASS = "root"
DB_NAME = "evcharging"

# -----------------------------
# LIGAR BD
# -----------------------------
def connect_db():
    for i in range(10):  # tenta 10 vezes, espera 2s entre tentativas
        try:
            return mysql.connector.connect(
                host=DB_HOST,
                user=DB_USER,
                password=DB_PASS,
                database=DB_NAME,
            )
        except mysql.connector.Error as e:
            print(f"MySQL ainda não está pronto ({e}). Tentativa {i+1}/10...")
            time.sleep(2)

    raise RuntimeError("❌ Não consegui ligar ao MySQL depois de 10 tentativas.")


while True:
    try:
        db = connect_db()
        cursor = db.cursor()
        print("✅ PROCESSOR ligado ao MySQL- load_db")
        break
    except Exception as e:
        print(f"Erro ao conectar ao MySQL -load_db: {e}")
        print("⏳ Esperando MySQL na load_db...")
        time.sleep(3)
        
# -----------------------------
# 1️⃣ CARREGAR ESTAÇÕES (EV-stations)
# -----------------------------
def load_stations():
    #df = pd.read_csv("EV-stations.csv")
    df = pd.read_csv("EV-stations.csv", sep=";")  # ajustar extensão se for xlsx

    for _, row in df.iterrows():
        cursor.execute("""
            INSERT INTO stations (
                station_code, distrito, concelho, freguesia,
                latitude, longitude, power_kw, connection_points
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE
                distrito=VALUES(distrito),
                concelho=VALUES(concelho),
                freguesia=VALUES(freguesia),
                latitude=VALUES(latitude),
                longitude=VALUES(longitude),
                power_kw=VALUES(power_kw),
                connection_points=VALUES(connection_points)
        """, (
            row["Station ID"],
            row["Distrito"],
            row["Concelho"],
            row["Freguesia"],
            row["Latitude"],
            row["Longitude"],
            row["Potência Máxima Admissível (kW)"],
            row["Pontos de ligação para instalações de PCVE"]
        ))
    db.commit()
    print("📌 Estações carregadas com sucesso.")

# -----------------------------
# 2️⃣ CARREGAR USERS (EV-session)
# -----------------------------
def load_users(df):
    for _, row in df.iterrows():
    

        cursor.execute("""
            INSERT INTO ev_users (
                user_code, vehicle_model, battery_capacity_kwh, vehicle_age_years
            )
            VALUES (%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE
                vehicle_model=VALUES(vehicle_model),
                battery_capacity_kwh=VALUES(battery_capacity_kwh),
                vehicle_age_years=VALUES(vehicle_age_years)
        """, (
            clean_str(row["User ID"]),
            clean_str(row["Vehicle Model"]),
            clean_float(row["Battery Capacity (kWh)"]),
            clean_int(row["Vehicle Age (years)"])
        ))
    db.commit()
    print("👤 Users carregados.")

# -----------------------------
# 3️⃣ CARREGAR SESSÕES (EV-session)
# -----------------------------


def load_sessions(df):
    for _, row in df.iterrows():

        # FK do user
        cursor.execute("SELECT user_id FROM ev_users WHERE user_code=%s",
                       (row["User ID"],))
        user_fk = cursor.fetchone()
        user_fk = user_fk[0] if user_fk else None
        

        station_code = str(row["Charging Station ID"]).strip()

        if station_code.lower() in ["nan", "", "none"]:
            print("⚠ Estação não encontrada:", station_code)
            continue   # ignora linha inválida

        start = row["Charging Start Time"]
        end = row["Charging End Time"]

        # VALIDAR AS DATAS
        if pd.isna(start) or pd.isna(end):
            print("⚠ Sessão ignorada por ter data inválida:", row["User ID"], start, end)
            continue

        # AGORA SIM FAZ O FORMATO
        start = start.strftime("%Y-%m-%d %H:%M:%S")
        end   = end.strftime("%Y-%m-%d %H:%M:%S")
        
        # FK da estação
        cursor.execute("SELECT station_id FROM stations WHERE station_code=%s",
                       (station_code,))
        st_fk = cursor.fetchone()
        st_fk = st_fk[0] if st_fk else None

        cursor.execute("""
            INSERT INTO sessions (
                user_id, station_id, start_time, end_time,
                energy_kwh, duration_h, rate_kw, estimated_cost,
                time_of_day, day_of_week, soc_start, soc_end,
                distance_km, temperature_c, source
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'offline')
        """, (
            user_fk,
            st_fk,
            start,
            end,
            clean_float(row["Energy Consumed (kWh)"]),
            clean_float(row["Charging Duration (hours)"]),
            clean_float(row["Charging Rate (kW)"]),
            clean_float(row["Charging Cost (EUR)"]),
            row["Time of Day"],
            row["Day of Week"],
            clean_int(row["State of Charge (Start %)"]),
            clean_int(row["State of Charge (End %)"]),
            clean_float(row["Distance Driven (since last charge) (km)"]),
            clean_float(row["Temperature (C)"])
        ))
    db.commit()
    print("📈 Sessões offline carregadas.")