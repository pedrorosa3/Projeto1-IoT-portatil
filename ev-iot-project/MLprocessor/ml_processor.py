import paho.mqtt.client as mqtt
import mysql.connector
from mysql.connector import Error
import pandas as pd
import time
import os
import pickle
import ssl
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans

# config do mqtt
MQTT_BROKER_HOST = os.getenv("MQTT_BROKER_HOST", "mqtt-broker")
MQTT_BROKER_PORT = int(os.getenv("MQTT_BROKER_PORT", 8883)) 
MQTT_TRIGGER_TOPIC = "iot/ev-station/ml/run" 

# config da db
DB_HOST = os.getenv("DB_HOST", "database")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "evdatasetpassword")
DB_NAME = os.getenv("DB_NAME", "ev_charging_db")

MODEL_FILE = "kmeans_model.pkl"
SCALER_FILE = "scaler.pkl"
SESSION_MODEL_FILE = "kmeans_sessions.pkl"
SESSION_SCALER_FILE = "scaler_sessions.pkl"
TIME_MODEL_FILE = "kmeans_time.pkl"
TIME_SCALER_FILE = "scaler_time.pkl"


def setup_db_column(conn):
    try:
        cursor = conn.cursor()
        cursor.execute("ALTER TABLE ev_stations ADD COLUMN cluster_profile INT DEFAULT NULL")
        cursor.close()
    except Error as e:
        if e.errno != 1060: print(f"Erro SQL (Estações): {e}")


def get_training_data(db_connection):
    query = """
        SELECT 
            station_id,
            COUNT(*) as total_sessoes,
            AVG(duration) as duracao_media,
            SUM(energy_consumed) as total_energia,
            COUNT(DISTINCT user_id) as total_utilizadores_unicos
        FROM charging
        GROUP BY station_id;
    """
    return pd.read_sql(query, db_connection)


def update_db_clusters(conn, station_ids, clusters):
    cursor = conn.cursor()
    update_query = "UPDATE ev_stations SET cluster_profile = %s WHERE station_id = %s"
    data = list(zip([int(c) for c in clusters], station_ids))
    cursor.executemany(update_query, data)
    conn.commit()
    cursor.close()


def train_model(db_connection):
    print("ML Stations: Training...")
    try:
        setup_db_column(db_connection)
        df = get_training_data(db_connection)
        if df.empty: return

        features_df = df.drop('station_id', axis=1).fillna(0)
        scaler = StandardScaler()
        features_scaled = scaler.fit_transform(features_df)
        
        kmeans = KMeans(n_clusters=4, random_state=42, n_init=10)
        clusters = kmeans.fit_predict(features_scaled)

        with open(MODEL_FILE, "wb") as f: pickle.dump(kmeans, f)
        with open(SCALER_FILE, "wb") as f: pickle.dump(scaler, f)

        update_db_clusters(db_connection, df['station_id'], clusters)
        print(f"ML Stations{len(df)} stations updated.")
    except Exception as e: print(f"ML Erro: {e}")


def predict_updates(db_connection):
    if not os.path.exists(MODEL_FILE):
        train_model(db_connection)
        return
    try:
        with open(MODEL_FILE, "rb") as f: kmeans = pickle.load(f)
        with open(SCALER_FILE, "rb") as f: scaler = pickle.load(f)
        
        df = get_training_data(db_connection)
        if df.empty: return
        
        features_df = df.drop('station_id', axis=1).fillna(0)
        features_scaled = scaler.transform(features_df)
        predicted = kmeans.predict(features_scaled)
        
        update_db_clusters(db_connection, df['station_id'], predicted)
        print("ML (Estações): Atualizado.")
    except Exception as e: print(f"ML Erro: {e}")


def setup_session_column(conn):
    try:
        cursor = conn.cursor()
        cursor.execute("ALTER TABLE charging ADD COLUMN session_profile INT DEFAULT NULL")
        cursor.close()
    except Error as e:
        if e.errno != 1060: print(f"Erro SQL (Sessões): {e}")


def get_session_data(db_connection):
    query = """
        SELECT session_id, state_of_charge_start, state_of_charge_end, duration 
        FROM charging 
        WHERE state_of_charge_start IS NOT NULL AND state_of_charge_end IS NOT NULL;
    """
    return pd.read_sql(query, db_connection)


def train_session_model(db_connection):
    print("ML (Sessões): A iniciar TREINO...")
    try:
        setup_session_column(db_connection)
        df = get_session_data(db_connection)
        if df.empty or len(df) < 2: return

        df['delta_soc'] = df['state_of_charge_end'] - df['state_of_charge_start']
        features = df[['state_of_charge_start', 'delta_soc', 'duration']]
        
        scaler = StandardScaler()
        features_scaled = scaler.fit_transform(features)
        
        # 3 Clusters: Emergência, Full Charge, Top-up
        kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
        clusters = kmeans.fit_predict(features_scaled)

        with open(SESSION_MODEL_FILE, "wb") as f: pickle.dump(kmeans, f)
        with open(SESSION_SCALER_FILE, "wb") as f: pickle.dump(scaler, f)

        cursor = db_connection.cursor()
        update_query = "UPDATE charging SET session_profile = %s WHERE session_id = %s"
        data = list(zip([int(c) for c in clusters], df['session_id']))
        cursor.executemany(update_query, data)
        db_connection.commit()
        cursor.close()
        print(f"ML (Sessões): Feito.")
    except Exception as e: print(f"ML Erro: {e}")


def predict_session_updates(db_connection):
    if not os.path.exists(SESSION_MODEL_FILE):
        train_session_model(db_connection)
        return
    try:
        with open(SESSION_MODEL_FILE, "rb") as f: kmeans = pickle.load(f)
        with open(SESSION_SCALER_FILE, "rb") as f: scaler = pickle.load(f)
        
        query = """
            SELECT session_id, state_of_charge_start, state_of_charge_end, duration 
            FROM charging 
            WHERE session_profile IS NULL AND state_of_charge_start IS NOT NULL
        """
        df = pd.read_sql(query, db_connection)
        if df.empty: return

        df['delta_soc'] = df['state_of_charge_end'] - df['state_of_charge_start']
        features = df[['state_of_charge_start', 'delta_soc', 'duration']]
        
        features_scaled = scaler.transform(features)
        predicted = kmeans.predict(features_scaled)
        
        cursor = db_connection.cursor()
        update_query = "UPDATE charging SET session_profile = %s WHERE session_id = %s"
        data = list(zip([int(c) for c in predicted], df['session_id']))
        cursor.executemany(update_query, data)
        db_connection.commit()
        cursor.close()
        print("ML (Sessões): Atualizado.")
    except Exception as e: print(f"ML Erro: {e}")


def setup_time_column(conn):
    try:
        cursor = conn.cursor()
        cursor.execute("ALTER TABLE ev_stations ADD COLUMN time_profile INT DEFAULT NULL")
        cursor.close()
    except Error as e:
        if e.errno != 1060: print(f"Erro SQL (Horários): {e}")


def get_time_data(db_connection):
    """Calcula a % de uso em cada período do dia para cada estação"""
    query = """
        SELECT 
            station_id,
            SUM(CASE WHEN time_of_day = 'Morning' THEN 1 ELSE 0 END) / COUNT(*) as pct_morning,
            SUM(CASE WHEN time_of_day = 'Afternoon' THEN 1 ELSE 0 END) / COUNT(*) as pct_afternoon,
            SUM(CASE WHEN time_of_day = 'Evening' THEN 1 ELSE 0 END) / COUNT(*) as pct_evening,
            SUM(CASE WHEN time_of_day = 'Night' THEN 1 ELSE 0 END) / COUNT(*) as pct_night
        FROM charging
        GROUP BY station_id;
    """
    return pd.read_sql(query, db_connection)


def train_time_model(db_connection):
    print("ML (Horários): A iniciar TREINO...")
    try:
        setup_time_column(db_connection)
        df = get_time_data(db_connection)
        if df.empty: return

        features_df = df.drop('station_id', axis=1).fillna(0)
        scaler = StandardScaler()
        features_scaled = scaler.fit_transform(features_df)

        # 3 Clusters: Matinal, Noturno, Misto
        kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
        clusters = kmeans.fit_predict(features_scaled)

        with open(TIME_MODEL_FILE, "wb") as f: pickle.dump(kmeans, f)
        with open(TIME_SCALER_FILE, "wb") as f: pickle.dump(scaler, f)

        cursor = db_connection.cursor()
        update_query = "UPDATE ev_stations SET time_profile = %s WHERE station_id = %s"
        data = list(zip([int(c) for c in clusters], df['station_id']))
        cursor.executemany(update_query, data)
        db_connection.commit()
        cursor.close()
        print(f"ML (Horários): Feito.")
    except Exception as e: print(f"ML Erro: {e}")


def predict_time_updates(db_connection):
    if not os.path.exists(TIME_MODEL_FILE):
        train_time_model(db_connection)
        return
    try:
        with open(TIME_MODEL_FILE, "rb") as f: kmeans = pickle.load(f)
        with open(TIME_SCALER_FILE, "rb") as f: scaler = pickle.load(f)
        
        df = get_time_data(db_connection)
        if df.empty: return
        
        features_df = df.drop('station_id', axis=1).fillna(0)
        features_scaled = scaler.transform(features_df)
        predicted = kmeans.predict(features_scaled)
        
        cursor = db_connection.cursor()
        update_query = "UPDATE ev_stations SET time_profile = %s WHERE station_id = %s"
        data = list(zip([int(c) for c in predicted], df['station_id']))
        cursor.executemany(update_query, data)
        db_connection.commit()
        cursor.close()
        print("ML (Horários): Atualizado.")
    except Exception as e: print(f"ML Erro: {e}")


def connect_to_db():
    attempts = 0
    while attempts < 5:
        try:
            print(f"ML: A ligar à BD...")
            conn = mysql.connector.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME)
            if conn.is_connected(): return conn
        except Error:
            time.sleep(5)
            attempts += 1
    return None


def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        client.subscribe(MQTT_TRIGGER_TOPIC)
        print(f"ML: À escuta em {MQTT_TRIGGER_TOPIC}")


def on_message(client, userdata, msg):
    payload = msg.payload.decode()
    print(f"ML: Comando -> {payload}")
    
    db_conn = userdata
    if not db_conn or not db_conn.is_connected():
        db_conn = connect_to_db()
        client.user_data_set(db_conn)

    if db_conn:
        if payload == "run":
            train_model(db_conn)          
            train_session_model(db_conn)
            train_time_model(db_conn)
        elif payload == "update":
            predict_updates(db_conn)          
            predict_session_updates(db_conn)
            predict_time_updates(db_conn)


def main():
    db_connection = connect_to_db()
    if not db_connection: return

    client = mqtt.Client() 
    client.user_data_set(db_connection)
    
    client.tls_set(ca_certs="/app/certs/ca.crt", tls_version=ssl.PROTOCOL_TLSv1_2)
    client.tls_insecure_set(True)

    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, 60)
        print("ML Processor pronto (Seguro).")
        client.loop_forever()
    except Exception as e:
        print(f"Erro MQTT: {e}")

if __name__ == "__main__":
    main()