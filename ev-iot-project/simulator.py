import pandas as pd
import paho.mqtt.client as mqtt
import time
import json
import os
import ssl

# configs
BROKER_ADDRESS = "localhost"
PORT = 8883 
TOPIC = "iot/ev-station"
CSV_FILE = "EVDataset/dataset-EV_with_stations_for_online_simulation.csv"
DELAY = 30
CA_CERT_PATH = "./Certificates/ca.crt" 

def run_simulator():
    if not os.path.exists(CSV_FILE):
        print(f"Error: {CSV_FILE} not found!")
        return

    df = pd.read_csv(CSV_FILE, sep=';')
    
    client = mqtt.Client()
    
    if os.path.exists(CA_CERT_PATH):
        client.tls_set(ca_certs=CA_CERT_PATH, tls_version=ssl.PROTOCOL_TLSv1_2)
        client.tls_insecure_set(True)
        print("TLS configured!")
    else:
        print(f"Certificate {CA_CERT_PATH} not found!")
    try:
        client.connect(BROKER_ADDRESS, PORT)
        print(f"Connected to MQTT in {BROKER_ADDRESS}:{PORT}")
    except Exception as e:
        print(f"Connection error: {e}")
        return

    client.loop_start()
    
    for index, row in df.iterrows():
        data = row.to_dict()
        message = json.dumps(data)
        client.publish(TOPIC, message)
        print(f"[Enviado] {data.get('Charging Station ID')}")
        time.sleep(DELAY)

    client.loop_stop()
    client.disconnect()

if __name__ == "__main__":
    run_simulator()