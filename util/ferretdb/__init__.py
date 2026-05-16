import threading
from django.conf import settings
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

class MongoDBClient:
    _client = None
    _lock = threading.Lock()

    @classmethod
    def get_db(cls):
        if cls._client is None:
            with cls._lock:
                if cls._client is None:  # Double-check pattern for thread safety
                    cls._client = MongoClient(
                        settings.MONGODB_URI,
                        serverSelectionTimeoutMS=5000  # Fail fast if FerretDB is down
                    )
                    
                    # Proactively verify the FerretDB connection handshake
                    try:
                        cls._client.admin.command('ping')
                    except ConnectionFailure as e:
                        cls._client = None
                        raise ConnectionFailure(f"Could not connect to FerretDB: {e}")

        return cls._client[settings.MONGODB_DB_NAME]

# Helper function for easy importing
def get_mongo_db():
    return MongoDBClient.get_db()
