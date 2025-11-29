import paho.mqtt.client as mqtt
import mysql.connector
from mysql.connector import Error
import pandas as pd
import time
import os
import json
import ssl

# config do mqtt
MQTT_BROKER_HOST = os.getenv("MQTT_BROKER_HOST", "mqtt-broker")
MQTT_BROKER_PORT = int(os.getenv("MQTT_BROKER_PORT", 8883)) # Porta Segura
MQTT_TOPIC = "iot/ev-station" 
MQTT_ML_TOPIC = "iot/ev-station/ml/run"

# config da db
DB_HOST = os.getenv("DB_HOST", "database")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "evdatasetpassword")
DB_NAME = os.getenv("DB_NAME", "ev_charging_db")


def connect_to_db():
    attempts = 0
    while attempts < 5:
        try:
            print(f"Attempting to connect to DB at {DB_HOST}...")
            conn = mysql.connector.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME)
            if conn.is_connected():
                print("Successfully connected to the DB!")
                return conn
        except Error as e:
            print(f"DB Error: {e}")
            attempts += 1
            time.sleep(3)
    return None


def create_tables(conn):
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ev_stations (
                station_id VARCHAR(255) PRIMARY KEY, distrito VARCHAR(255), concelho VARCHAR(255),
                freguesia VARCHAR(255), latitude DECIMAL(9, 6), longitude DECIMAL(9, 6),
                potencia_max_adm FLOAT, pontos_ligacao INT, codigo_distrito VARCHAR(255),
                codigo_concelho VARCHAR(255), codigo_freguesia VARCHAR(255),
                cluster_profile INT DEFAULT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS charging (
                session_id INT AUTO_INCREMENT PRIMARY KEY, user_id VARCHAR(255),
                vehicle_model VARCHAR(255), battery_capacity INT, station_id VARCHAR(255),
                start_time DATETIME, end_time DATETIME, energy_consumed DECIMAL(10, 2),
                duration DECIMAL(10, 1), rate DECIMAL(10, 2), cost DECIMAL(10, 2),
                time_of_day VARCHAR(255), day_of_week VARCHAR(255),
                state_of_charge_start DECIMAL(10, 2), state_of_charge_end DECIMAL(10, 2),
                distance_driven DECIMAL(10, 3), temperature DECIMAL(10, 2), vehicle_age INT,
                FOREIGN KEY (station_id) REFERENCES ev_stations(station_id)
            )
        """)
        print("Tables checked/created.")
        cursor.close()
    except Error as e: print(f"Creating tables error: {e}")


def load_offline_data(conn):
    print("Checking for offline data...")
    try:
        cursor = conn.cursor()
        valid_ids = set()

        cursor.execute("SELECT COUNT(*) FROM ev_stations")
        if cursor.fetchone()[0] == 0:
            print("Loading stations...")
            df = pd.read_csv('/app/data/EV-Stations_with_ids_coords.csv', delimiter=';')
            df['Potência Máxima Admissível (kW)'] = pd.to_numeric(df['Potência Máxima Admissível (kW)'], errors='coerce').fillna(0)
            valid_ids = set(df['Station ID'])
            
            data = [
                (row['Station ID'], row['Distrito'], row['Concelho'], row['Freguesia'], 
                 row['Latitude'], row['Longitude'], row['Potência Máxima Admissível (kW)'], 
                 row['Pontos de ligação para instalações de PCVE'], row['CodDistrito'], 
                 row['CodDistritoConcelho'], row['CodDistritoConcelhoFreguesia']) 
                for index, row in df.iterrows()
            ]
            sql = "INSERT INTO ev_stations (station_id, distrito, concelho, freguesia, latitude, longitude, potencia_max_adm, pontos_ligacao, codigo_distrito, codigo_concelho, codigo_freguesia) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
            cursor.executemany(sql, data)
            conn.commit()
            print(f"Loaded {len(data)} stations.")
        else:
            cursor.execute("SELECT station_id FROM ev_stations")
            valid_ids = set(row[0] for row in cursor.fetchall())

        cursor.execute("SELECT COUNT(*) FROM charging")
        if cursor.fetchone()[0] == 0:
            print("Loading sessions...")
            df = pd.read_csv('/app/data/dataset-EV_with_stations.csv', delimiter=';')
            cols = ['Battery Capacity (kWh)', 'Energy Consumed (kWh)', 'Charging Duration (hours)', 'Charging Rate (kW)', 'Charging Cost (EUR)', 'State of Charge (Start %)', 'State of Charge (End %)', 'Distance Driven (since last charge) (km)', 'Temperature (C)', 'Vehicle Age (years)']
            for col in cols:
                df[col] = df[col].astype(str).str.replace(',', '.', regex=False)
                df[col] = pd.to_numeric(df[col], errors='coerce')
            df = df.where(pd.notnull(df), None)

            df = df[df['Charging Station ID'].isin(valid_ids)]

            data = [
                (row['User ID'], row['Vehicle Model'], row['Battery Capacity (kWh)'], row['Charging Station ID'],
                 row['Charging Start Time'], row['Charging End Time'], row['Energy Consumed (kWh)'], 
                 row['Charging Duration (hours)'], row['Charging Rate (kW)'], row['Charging Cost (EUR)'],
                 row['Time of Day'], row['Day of Week'], row['State of Charge (Start %)'], 
                 row['State of Charge (End %)'], row['Distance Driven (since last charge) (km)'], 
                 row['Temperature (C)'], row['Vehicle Age (years)'])
                for index, row in df.iterrows()
            ]
            sql = """INSERT INTO charging (user_id, vehicle_model, battery_capacity, station_id, start_time, end_time, energy_consumed, duration, rate, cost, time_of_day, day_of_week, state_of_charge_start, state_of_charge_end, distance_driven, temperature, vehicle_age) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
            cursor.executemany(sql, data)
            conn.commit()
            print(f"Loaded {len(data)} sessions.")
        cursor.close()
    except Exception as e: print(f"Error loading data: {e}")


def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print(f"Connected to MQTT! Listening on {MQTT_TOPIC}")
        client.subscribe(MQTT_TOPIC)


def on_message(client, userdata, msg):
    print(f"Received msg on: {msg.topic}")
    def clean(val): return val.replace(',', '.') if isinstance(val, str) else val

    try:
        payload = msg.payload.decode('utf-8', errors='ignore')
        if not payload or payload == "run" or payload == "update": return
        
        data = json.loads(payload)
        conn = userdata
        if not conn or not conn.is_connected():
            conn = connect_to_db()
            client.user_data_set(conn)
            if not conn: return

        cursor = conn.cursor()
        sql = """INSERT INTO charging (vehicle_model, battery_capacity, station_id, energy_consumed, duration, rate, cost, time_of_day, day_of_week, state_of_charge_start, state_of_charge_end, distance_driven, temperature, vehicle_age) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
        
        vals = (
            data.get('Vehicle Model'), clean(data.get('Battery Capacity (kWh)')), data.get('Charging Station ID'),
            clean(data.get('Energy Consumed (kWh)')), clean(data.get('Charging Duration (hours)')),
            clean(data.get('Charging Rate (kW)')), clean(data.get('Charging Cost (EUR)')),
            data.get('Time of Day'), data.get('Day of Week'), clean(data.get('State of Charge (Start %)')),
            clean(data.get('State of Charge (End %)')), clean(data.get('Distance Driven (since last charge) (km)')),
            clean(data.get('Temperature (C)')), clean(data.get('Vehicle Age (years)'))
        )
        cursor.execute(sql, vals)
        conn.commit()
        cursor.close()
        print(f"Online data saved!: {data.get('Charging Station ID')}")

        client.publish(MQTT_ML_TOPIC, "update")

    except Exception as e: print(f"Error processing msg: {e}")

def main():
    conn = connect_to_db()
    if not conn: return
    
    create_tables(conn)
    client = mqtt.Client() 
    client.user_data_set(conn)

    client.tls_set(ca_certs="/app/certs/ca.crt", tls_version=ssl.PROTOCOL_TLSv1_2)
    client.tls_insecure_set(True)

    load_offline_data(conn)
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        print("Connecting to MQTT...")
        client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, 60)
        print("Triggering ML training..")
        client.publish(MQTT_ML_TOPIC, "run", qos=1)
        client.loop_forever()
    except Exception as e:
        print(f"MQTT Error: {e}")
        conn.close()

if __name__ == "__main__":
    main()