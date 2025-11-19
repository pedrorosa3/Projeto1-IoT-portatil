import json
import uuid
import paho.mqtt.client as mqtt
import os
import mysql.connector
import time
import pandas as pd
from load_db import load_stations, load_users
from load_db import load_sessions

import joblib
kmeans = joblib.load("energy_cluster_kmeans.pkl")

# ========================
# CONFIG: MQTT & DB (definidas no docker-compose)
# ========================
MQTT_BROKER = os.getenv("MQTT_BROKER_HOST", "mosquitto")
MQTT_PORT = 8883
MQTT_TOPIC = "idc/iris"

DB_HOST = os.getenv("DB_HOST", "mysql")
DB_USER = os.getenv("DB_USER", "root")
DB_PASS = os.getenv("DB_PASS", "root")
DB_NAME = os.getenv("DB_NAME", "evcharging")

# ========================
# DATABASE CONNECTION
# ========================

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
        print("✅ PROCESSOR ligado ao MySQL",flush=True)
        break
    except Exception as e:
        print(f"Erro ao conectar ao MySQL: {e}")
        print("⏳ Esperando MySQL...")
        time.sleep(3)



print("✅ PROCESSOR ligado ao MySQL e ao MQTT Broker",flush=True)
# ========================
# MQTT CALLBACK
# ========================
def on_message(client, userdata, message):
    payload = json.loads(message.payload.decode("utf-8"))
    print(f"📥 Recebido via MQTT → {payload}")

    user_fk = None,
    station_fk = payload.get("station_id")
    start_time= None
    stop_time= None
    source="mqtt"

    cursor.execute("""
        INSERT INTO sessions (
            user_id, station_id, start_time, end_time,
            energy_kwh, duration_h, rate_kw, estimated_cost,
            time_of_day, day_of_week, soc_start, soc_end,
            distance_km, temperature_c, source
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'mqtt')
    """,
    (
        user_fk,
        station_fk,
        start_time,
        stop_time,
        payload.get("energy_consumed"),
        payload.get("charging_duration"),
        payload.get("charging_rate"),
        payload.get("charging_cost"),
        payload.get("time_of_day"),
        payload.get("day_of_week"),
        payload.get("soc_start"),
        payload.get("soc_end"),
        payload.get("distance"),
        payload.get("temperature"),
        source,
    ))
    energy_value = payload.get("energy_consumed")
    if energy_value is not None:
        cluster = int(kmeans.predict([[energy_value]])[0])
        print(f"⚡ Cluster atribuído: {cluster}")
    else:
        cluster = None

    print("💾 Sessão inserida na BD.")

load_stations()
df_sessions = pd.read_csv("EV-session.csv", sep=";")
print(df_sessions["Vehicle Age (years)"].unique())
df_sessions["Charging Start Time"] = pd.to_datetime(
    df_sessions["Charging Start Time"], dayfirst=True, errors="coerce"
)

df_sessions["Charging End Time"] = pd.to_datetime(
    df_sessions["Charging End Time"], dayfirst=True, errors="coerce"
)
load_users(df_sessions)
load_sessions(df_sessions)
db.commit()
print("✅ Dados offline carregados!",flush=True)


# ========================
# SUBSCRIBE
# ========================


def on_connect(client, userdata, flags, return_code):
    if return_code == 0:
        print("connected")
        client.subscribe("idc/iris")
    else:
        print("could not connect, return code:", return_code)


def on_message(client, userdata, message):
    print("Received message: " ,str(message.payload.decode("utf-8")),flush=True)

client = mqtt.Client("Cliente-Processor")

client.tls_set(ca_certs="ca.crt",
certfile="client.crt",
keyfile="client.key",
)

client.tls_insecure_set(True)

#client = mqtt.Client("Client-Processor", protocol=mqtt.MQTTv311)
#client = mqtt.Client(f"processor-{uuid.uuid4()}", protocol=mqtt.MQTTv311, callback_api_version=2)
client.on_connect = on_connect
client.on_message = on_message
client.connect(MQTT_BROKER, MQTT_PORT)
#client.subscribe(MQTT_TOPIC)

print(f"🚀 PROCESSOR a escutar tópico: {MQTT_TOPIC}")
client.loop_start()

try:
    time.sleep(1000000)
finally:
    client.loop_stop()