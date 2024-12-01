worker_script = '''#!/bin/bash

# Mettre à jour et installer les paquets nécessaires
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y python3 python3-pip default-jdk wget scala git
sudo apt-get install -y mysql-server sysbench unzip
sudo apt-get install -y python3.12-venv
sudo apt-get install -y python3-full



# Créer un environnement virtuel Python pour FastAPI
cd /home/ubuntu
sudo -u ubuntu python3 -m venv fastapi_env
source fastapi_env/bin/activate

# Installer FastAPI et les dépendances nécessaires
pip install fastapi uvicorn pymysql

# Configurer MySQL
PASSWORD="password"
sudo mysql -e "ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY '$PASSWORD'; FLUSH PRIVILEGES;"

# Télécharger et importer les données Sakila
wget https://downloads.mysql.com/docs/sakila-db.zip
unzip sakila-db.zip

mysql -u root -p$PASSWORD -e "source /home/ubuntu/sakila-db/sakila-schema.sql; source /home/ubuntu/sakila-db/sakila-data.sql;"

# Configurer et exécuter un benchmark Sysbench
sudo sysbench /usr/share/sysbench/oltp_read_only.lua \
    --mysql-db=sakila \
    --mysql-user=root \
    --mysql-password=$PASSWORD \
    prepare

sudo sysbench /usr/share/sysbench/oltp_read_only.lua \
    --mysql-db=sakila \
    --mysql-user=root \
    --mysql-password=$PASSWORD \
    run

# Créer un fichier FastAPI pour servir l'API SQL
cat <<EOF > /home/ubuntu/app.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import pymysql

app = FastAPI()

# Configuration de la base de données
DB_HOST = "localhost"
DB_USER = "root"
DB_PASSWORD = "$PASSWORD"
DB_NAME = "sakila"

class SQLRequest(BaseModel):
    query: str

@app.post("/execute-sql")
async def execute_sql(request: SQLRequest):
    try:
        connection = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        cursor = connection.cursor()
        cursor.execute(request.query)
        result = cursor.fetchall()
        connection.commit()
        cursor.close()
        connection.close()
        return {"status": "success", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
EOF

# Configurer un service systemd pour exécuter l'application FastAPI
cat <<EOF | sudo tee /etc/systemd/system/fastapi.service
[Unit]
Description=FastAPI Service
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu
ExecStart=/home/ubuntu/fastapi_env/bin/uvicorn app:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Démarrer le service FastAPI
sudo systemctl daemon-reload
sudo systemctl start fastapi.service
sudo systemctl enable fastapi.service
'''

manager_script ='''#!/bin/bash

# Mettre à jour et installer les paquets nécessaires
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y python3 python3-pip default-jdk wget scala git
sudo apt-get install -y mysql-server sysbench unzip
sudo apt-get install -y python3.12-venv
sudo apt-get install -y python3-full

# Créer un environnement virtuel Python pour FastAPI
cd /home/ubuntu
sudo -u ubuntu python3 -m venv fastapi_env
source fastapi_env/bin/activate

# Installer FastAPI et les dépendances nécessaires
pip install fastapi uvicorn pymysql requests

# Configurer MySQL
PASSWORD="password"
sudo mysql -e "ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY '$PASSWORD'; FLUSH PRIVILEGES;"

# Télécharger et importer les données Sakila
wget https://downloads.mysql.com/docs/sakila-db.zip
unzip sakila-db.zip

mysql -u root -p$PASSWORD -e "source /home/ubuntu/sakila-db/sakila-schema.sql; source /home/ubuntu/sakila-db/sakila-data.sql;"

# Configurer et exécuter un benchmark Sysbench
sudo sysbench /usr/share/sysbench/oltp_read_only.lua \
    --mysql-db=sakila \
    --mysql-user=root \
    --mysql-password=$PASSWORD \
    prepare

sudo sysbench /usr/share/sysbench/oltp_read_only.lua \
    --mysql-db=sakila \
    --mysql-user=root \
    --mysql-password=$PASSWORD \
    run

# Enregistrer les adresses IP des instances t2.micro (workers et manager)
WORKER_IPS=("worker1_ip" "worker2_ip")
echo "Worker IPs: ${WORKER_IPS[@]}" > /home/ubuntu/worker_ips.txt

# Créer un fichier FastAPI pour servir l'API SQL
cat <<EOF > /home/ubuntu/app.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import pymysql
import requests
import json

app = FastAPI()

# Configuration de la base de données
DB_HOST = "localhost"
DB_USER = "root"
DB_PASSWORD = "$PASSWORD"
DB_NAME = "sakila"

WORKER_IPS = ["worker1_ip", "worker2_ip"]
WORKER_URLS = [f"http://{ip}:8000" for ip in WORKER_IPS]

def get_fastest_worker():
    response_times = {}
    for worker in WORKER_URLS:
        try:
            response = requests.get(worker + "/health", timeout=2)
            response_times[worker] = response.elapsed.total_seconds()
        except requests.exceptions.RequestException:
            response_times[worker] = float('inf')
    return min(response_times, key=response_times.get)

class SQLRequest(BaseModel):
    query: str

@app.get("/")
def health_check():
    return {"status": "Manager OK"}

@app.post("/")
async def handle_request(request: SQLRequest):
    fastest_worker = get_fastest_worker()
    try:
        response = requests.post(fastest_worker + "/execute-sql", json=request.dict())
        return response.json()
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=str(e))
EOF

# Configurer un service systemd pour exécuter l'application FastAPI
cat <<EOF | sudo tee /etc/systemd/system/fastapi.service
[Unit]
Description=FastAPI Service
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu
ExecStart=/home/ubuntu/fastapi_env/bin/uvicorn app:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Démarrer le service FastAPI
sudo systemctl daemon-reload
sudo systemctl start fastapi.service
sudo systemctl enable fastapi.service
'''

trust_host_script = '''#!/bin/bash

# Mise à jour des paquets
sudo apt-get update -y

# Installation de Python3 et de pip
sudo apt-get install -y python3 python3-pip

# Installation des dépendances nécessaires pour l'application
pip3 install fastapi uvicorn requests

# Création du fichier de l'application
cat <<EOF > /home/ubuntu/app.py
from fastapi import FastAPI, HTTPException, Request, status
import requests
import json

app = FastAPI()

PROXY_URL = f"http://proxy_ip:8000"

@app.get("/")
async def health_check():
    return "Trusted Host OK"

@app.get("/mode")
async def get_mode():
    try:
        response = requests.get(f"{PROXY_URL}/mode")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/mode")
async def post_mode(data: dict):
    try:
        response = requests.post(f"{PROXY_URL}/mode", json=data)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/query")
async def forward_query(data: dict):
    try:
        response = requests.post(PROXY_URL, json=data)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=str(e))
EOF

# Lancer l'application FastAPI avec Uvicorn
nohup uvicorn /home/ubuntu/app.py --host 0.0.0.0 --port 8000 > /home/ubuntu/fastapi.log 2>&1 &
'''
gatekeeper_script = '''#!/bin/bash

# Mettre à jour les paquets et installer les dépendances nécessaires
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y python3 python3-pip python3-venv git unzip curl

# Configurer l'environnement utilisateur
cd /home/ubuntu
sudo -u ubuntu mkdir -p gatekeeper
cd gatekeeper

# Créer un environnement virtuel pour Python
sudo -u ubuntu python3 -m venv venv
source venv/bin/activate

# Installer les dépendances Python
pip install --upgrade pip
pip install fastapi uvicorn requests pydantic

cat <<EOF > app.py
from fastapi import FastAPI, HTTPException, Request
import requests
import logging
import json
from pydantic import BaseModel

app = FastAPI()

# URL du Trusted Host
TRUSTED_HOST_URL = f"http://trust_host_ip:8000"

# Configuration des logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("GatekeeperApp")


class QueryRequest(BaseModel):
    query: str


@app.get("/")
def health_check():
    logger.info("Health check requested")
    return {"status": "Gatekeeper OK"}


@app.post("/")
async def validate_and_forward(request: QueryRequest):
    data = request.dict()
    logger.info(f"Received data: {data}")

    # Validation basique des données
    if "query" not in data:
        logger.warning("Invalid request format")
        raise HTTPException(status_code=400, detail="Invalid request format")

    # Transmettre les requêtes validées au Trusted Host
    try:
        response = requests.post(f"{TRUSTED_HOST_URL}/query", json=data)
        logger.info(f"Response from trusted host: {response.status_code}")
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error forwarding request: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
EOF

# Configurer le service systemd pour démarrer l'application FastAPI
cat <<EOF | sudo tee /etc/systemd/system/gatekeeper.service
[Unit]
Description=Gatekeeper Service
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/gatekeeper
ExecStart=/home/ubuntu/gatekeeper/venv/bin/uvicorn app:app --host 0.0.0.0 --port 5000
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Démarrer et activer le service
sudo systemctl daemon-reload
sudo systemctl start gatekeeper.service
sudo systemctl enable gatekeeper.service
'''