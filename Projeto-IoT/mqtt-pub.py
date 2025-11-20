import pandas as pd
import json
import time
import paho.mqtt.client as mqtt

MQTT_BROKER = "mosquitto"
MQTT_PORT = 8883
MQTT_TOPIC = "idc/iris"

filename = "../EV-simulation.csv"

df = pd.read_csv(filename,sep=";")

df.columns = [
    "vehicle_model",
    "battery_capacity",
    "station_id",
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



client = mqtt.Client()

client.tls_set(ca_certs="ca.crt",
certfile="client.crt",
keyfile="client.key",
)

client.tls_insecure_set(True)


client.connect(MQTT_BROKER, MQTT_PORT)

for i, row in df.iterrows():
    message = row.to_dict()
    payload = json.dumps(message)
    print("Enviando:", payload)

    client.publish(MQTT_TOPIC, payload)
    
    time.sleep(1)  # intervalo para simular sensor

client.disconnect()
print("Todos os dados foram enviados.")