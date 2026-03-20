import os
import gridfs
from pymongo import MongoClient
from dotenv import load_dotenv

# Força a recarga do .env / Force reload of .env
load_dotenv(override=True)

class MongoDBConnection:
    """
    Classe para gerenciar a conexão com o MongoDB e GridFS.
    Class to manage MongoDB and GridFS connection.
    """
    def __init__(self):
        # Tenta ler do .env ou do st.secrets (Streamlit)
        # Tries to read from .env or st.secrets
        self.uri = os.getenv("MONGODB_URI")
        self.client = None
        self.db = None
        self.fs = None

    def connect(self):
        if not self.uri:
            print("ERRO: MONGODB_URI não encontrada! / ERROR: MONGODB_URI not found!")
            return None, None

        try:
            # Adicionamos um timeout curto para não travar o app por 30s
            # Short timeout to avoid freezing the app for 30s
            self.client = MongoClient(self.uri, serverSelectionTimeoutMS=5000)
            
            # Testa a conexão / Test connection
            self.client.admin.command('ping')
            
            self.db = self.client['anotai_db']
            self.fs = gridfs.GridFS(self.db)
            print("Conectado ao MongoDB Atlas! / Connected to MongoDB Atlas!")
            return self.db, self.fs
        except Exception as e:
            print(f"Falha crítica na conexão: {e} / Critical connection failure: {e}")
            return None, None

# Instâncias globais / Global instances
db_conn = MongoDBConnection()
db, fs = db_conn.connect()