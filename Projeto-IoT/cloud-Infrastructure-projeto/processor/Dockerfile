FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    default-libmysqlclient-dev gcc && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY processor.py .
COPY load_db.py .
COPY EV-session.csv .
COPY EV-stations.csv .
COPY ca.crt .
COPY client.crt .
COPY client.key .

CMD ["python", "-u", "processor.py"]