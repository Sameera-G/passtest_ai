import firebase_admin
from firebase_admin import credentials, auth, firestore
import json
import os
from dotenv import load_dotenv

load_dotenv()  # Load env variables from .env

firebase_json = os.environ.get("FIREBASE_CREDENTIALS_JSON")
cred_dict = json.loads(firebase_json)
cred = credentials.Certificate(cred_dict)

firebase_admin.initialize_app(cred)
db = firestore.client()
