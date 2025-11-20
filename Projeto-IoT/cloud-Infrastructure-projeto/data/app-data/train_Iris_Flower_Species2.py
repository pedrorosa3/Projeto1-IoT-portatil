import pandas as pd
from sklearn.cluster import KMeans
import joblib
import gzip
import os

print("📘 Training KMeans clustering model...")

# Garantir diretoria models
os.makedirs("model", exist_ok=True)

df = pd.read_csv("../EV-session.csv", sep=";")

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

# Converter valores com vírgula
df["energy_consumed"] = df["energy_consumed"].astype(str).str.replace(",", ".")
df["energy_consumed"] = df["energy_consumed"].astype(float)

X = df[["energy_consumed"]]


'''
models = [
    ('KMEANS', KMeans(n_clusters=3, random_state=42)),
    ('KMEANS_SOC', KMeans(n_clusters=3, random_state=42)),
    # etc...
]

for name, model in models:
    model.fit(X)
    joblib.dump(model, gzip.open(f"models/ev-{name}.dat.gz", "wb"))
'''


# Treinar com 3 clusters (depois de usares o elbow method)
kmeans = KMeans(n_clusters=3, random_state=42)
kmeans.fit(X)

# Guardar em gzip (igual ao exemplo da professora)
filename = "model/energy-kmeans.dat.gz"
joblib.dump(kmeans, gzip.open(filename, "wb"))

print(f"✅ Modelo guardado em {filename}")



