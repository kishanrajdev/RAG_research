# db.py
import os
from azure.cosmos import CosmosClient
from dotenv import load_dotenv

load_dotenv()

_cosmos_client = None
_database = None

def get_database():
    global _cosmos_client, _database

    if _cosmos_client is None:
        _cosmos_client = CosmosClient(
            os.environ["COSMOS_URI"],
            credential=os.environ["COSMOS_KEY"]
        )

        _database = _cosmos_client.get_database_client(
            os.environ["COSMOS_DB"]
        )

    return _database
