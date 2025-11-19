import pandas as pd
from sklearn.cluster import KMeans
import joblib

print("📘 Training KMeans clustering model...")

df = pd.read_csv("EV-session.csv")

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

X = df[["energy_consumed"]]

# Treinar com 3 clusters
kmeans = KMeans(n_clusters=3, random_state=42)
kmeans.fit(X)

joblib.dump(kmeans, "energy_cluster_kmeans.pkl")

print("✅ Modelo treinado e guardado como energy_cluster_kmeans.pkl")




