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
MQTT_BROKER_PORT = int(os.getenv("MQTT_BROKER_PORT", 8883)) # Porta Segura
MQTT_TRIGGER_TOPIC = "iot/ev-station/ml/run" 

# config da db
DB_HOST = os.getenv("DB_HOST", "database")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "evdatasetpassword")
DB_NAME = os.getenv("DB_NAME", "ev_charging_db")

# ficheiros para modelo de estacoes 
# treino offline
MODEL_FILE = "kmeans_model.pkl"
SCALER_FILE = "scaler.pkl"

# treino online
SESSION_MODEL_FILE = "kmeans_sessions.pkl"
SESSION_SCALER_FILE = "scaler_sessions.pkl"


def get_training_data(db_connection):
    query = """
        SELECT 
            station_id,get_training_data
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


def setup_db_column(conn):
    try:
        cursor = conn.cursor()
        cursor.execute("ALTER TABLE ev_stations ADD COLUMN cluster_profile INT DEFAULT NULL")
        cursor.close()
    except Error as e:
        if e.errno != 1060: print(f"Erro SQL (Estações): {e}")


def train_model(db_connection):
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
    except Exception as e:
        print(f"ML Error: {e}")


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
        predicted_clusters = kmeans.predict(features_scaled)

        update_db_clusters(db_connection, df['station_id'], predicted_clusters)
    except Exception as e:
        print(f"ML Error: {e}")
        

def setup_session_column(conn):
    try:
        cursor = conn.cursor()
        cursor.execute("ALTER TABLE charging ADD COLUMN session_profile INT DEFAULT NULL")
        cursor.close()
    except Error as e:
        if e.errno != 1060: print(f"SQL Error: {e}")


def get_session_data(db_connection):
    query = """
        SELECT session_id, state_of_charge_start, state_of_charge_end, duration
        FROM charging
        WHERE state_of_charge_start IS NOT NULL AND state_of_charge_end IS NOT NULL;
    """
    return pd.read_sql(query, db_connection)


def train_session_model(db_connection):
    try:
        setup_session_column(db_connection)
        df = get_session_data(db_connection)
        
        if df.empty or len(df) < 50:
            return

        # Feature Engineering: Delta SOC (Quanto carregou?)
        df['delta_soc'] = df['state_of_charge_end'] - df['state_of_charge_start']
        features = df[['state_of_charge_start', 'delta_soc', 'duration']]
        
        scaler = StandardScaler()
        features_scaled = scaler.fit_transform(features)

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
    except Exception as e:
        print(f"ML Error: {e}")


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
            WHERE session_profile IS NULL 
              AND state_of_charge_start IS NOT NULL
              AND state_of_charge_end IS NOT NULL
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
        print(f"ML (Sessões): {len(df)} novas sessões atualizadas.")
    except Exception as e:
        print(f"ML (Sessões) Erro: {e}")


def connect_to_db():
    attempts = 0
    while attempts < 5:
        try:
            print(f"ML Connecting to DB...")
            conn = mysql.connector.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME)
            if conn.is_connected(): return conn
        except Error:
            time.sleep(5)
            attempts += 1
    return None


def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        client.subscribe(MQTT_TRIGGER_TOPIC)
        print(f"ML listening in {MQTT_TRIGGER_TOPIC}")


def on_message(client, userdata, msg):
    payload = msg.payload.decode()
    print(f"ML {payload}")
    
    db_conn = userdata
    if not db_conn or not db_conn.is_connected():
        db_conn = connect_to_db()
        client.user_data_set(db_conn)

    if db_conn:
        if payload == "run":
            train_model(db_conn)          
            train_session_model(db_conn)  
        elif payload == "update":
            predict_updates(db_conn)          
            predict_session_updates(db_conn)  


def main():
    db_connection = connect_to_db()
    if not db_connection: return
    client = mqtt.Client() 
    client.user_data_set(db_connection)
    
    # config tls
    client.tls_set(ca_certs="/app/certs/ca.crt", tls_version=ssl.PROTOCOL_TLSv1_2)
    client.tls_insecure_set(True)
    client.on_connect = on_connect
    client.on_message = on_message
    try:
        client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, 60)
        print("ML ready")
        client.loop_forever()
    except Exception as e:
        print(f"MQTT Error: {e}")

if __name__ == "__main__":
    main()