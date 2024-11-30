Micros_script = '''#!/bin/bash

# Mettre à jour et installer les paquets nécessaires
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y python3 python3-pip default-jdk wget scala git
sudo apt-get install -y mysql-server sysbench unzip

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