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
proxy_script = '''#!/bin/bash

# Update and install required packages
sudo apt-get update -y
sudo apt-get upgrade -y
sudo apt-get install -y python3 python3-venv python3-pip curl

# Create and activate a virtual environment
cd /home/ubuntu
python3 -m venv api_env
source api_env/bin/activate

# Install Python dependencies
pip install fastapi uvicorn requests

# Create the FastAPI application
cat <<EOF > server.py
from fastapi import FastAPI, Request, HTTPException
import requests
import random
import json
import logging

service = FastAPI()

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("proxy")

workers = ["worker1_ip", "worker2_ip"]

MANAGER_NODE_URL = f"http://manager_ip:8000"
WORKER_NODE_URLS = [f"http://{ip}:8000" for ip in workers]

def select_fastest_node():
    response_times = {}
    for node in WORKER_NODE_URLS:
        try:
            response = requests.get(node, timeout=2)
            response_times[node] = response.elapsed.total_seconds()
        except requests.exceptions.RequestException:
            response_times[node] = float("inf")
    return min(response_times, key=response_times.get)

@service.get("/")
def health_status():
    return {"status": "Service is operational"}

@service.post("/")
async def handle_request(req: Request):
    payload = await req.json()
    log.info(f"Incoming request: {payload}")
    
    # Extract and validate fields
    action_type = payload.get("action", "").lower()
    query = payload.get("query")
    mode = payload.get("mode")

    # Validate required fields
    if not query or not action_type or not mode:
        log.error("Missing required fields in the payload")
        raise HTTPException(status_code=400, detail="Missing required fields in the payload")
    
    # Handle write actions
    if action_type == "write":
        try:
            response = requests.post(MANAGER_NODE_URL, json=payload)
            return response.json()
        except requests.exceptions.RequestException as e:
            log.error(f"Error forwarding request: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    # Handle read actions
    elif action_type == "read":
        target_node = None
        
        # Determine target node based on mode
        if mode == "direct_hit":
            target_node = MANAGER_NODE_URL
        elif mode == "random":
            target_node = random.choice(WORKER_NODE_URLS)
        elif mode == "customized":
            target_node = select_fastest_node()

        if target_node:
            try:
                response = requests.post(target_node, json=payload)
                return response.json()
            except requests.exceptions.RequestException as e:
                log.error(f"Error forwarding request: {str(e)}")
                raise HTTPException(status_code=501, detail=str(e))
        else:
            log.error("Invalid mode specified")
            raise HTTPException(status_code=400, detail="Invalid mode specified")
    
    # Handle invalid action types
    else:
        log.error("Invalid action type")
        raise HTTPException(status_code=400, detail="Invalid action type")
EOF

# Create a systemd service file
cat <<EOF | sudo tee /etc/systemd/system/api_service.service
[Unit]
Description=FastAPI Service Node
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu
ExecStart=/home/ubuntu/api_env/bin/uvicorn server:service --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and start the service
sudo systemctl daemon-reload
sudo systemctl enable api_service.service
sudo systemctl start api_service.service

# Verify the service status
sudo systemctl status api_service.service
'''

trust_host_script = '''#!/bin/bash

sudo apt-get update -y

# Installation de Python3, pip et venv
sudo apt-get install -y python3 python3-pip python3.12-venv

# Création de l'environnement virtuel
sudo -u ubuntu python3 -m venv /home/ubuntu/venv

# Installation des dépendances
source /home/ubuntu/venv/bin/activate
pip install fastapi uvicorn requests

# Création de l'application
cat <<EOF > /home/ubuntu/app.py
from fastapi import FastAPI, HTTPException, Request, status
import requests
import json
import logging



app = FastAPI()

PROXY_URL = f"http://proxy_ip:8000"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TrustHostApp")

@app.get("/")
async def health_check():
    return "Trust Host OK"

@app.post("/query")
async def forward_query(data: dict):
    try:
        response = requests.post(PROXY_URL, json=data)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error forwarding request: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
EOF

# Création du fichier de service systemd pour FastAPI
cat <<EOF > /etc/systemd/system/trust_host.service
[Unit]
Description=Trust Host FastAPI Service
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu
Environment="PATH=/home/ubuntu/venv/bin"
ExecStart=/home/ubuntu/venv/bin/uvicorn app:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Recharger systemd, démarrer et activer le service
sudo systemctl daemon-reload
sudo systemctl start trust_host.service
sudo systemctl enable trust_host.service
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

# URL du Trust Host
TRUST_HOST_URL = f"http://trust_host_ip:8000"

# Configuration des logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("GatekeeperApp")


class QueryRequest(BaseModel):
    action: str
    query: str
    mode: str    


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

    # Transmettre les requêtes validées au Trust Host
    try:
        response = requests.post(f"{TRUST_HOST_URL}/query", json=data)
        logger.info(f"Response from trust host: {response.status_code}")
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