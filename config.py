import os

from mailjet_rest import Client
from pymongo import MongoClient

SECRET = "my_host_secret_key_7897"  
TOKEN_EXPIRY = 30 
ADMIN_EMAILS = {"admin@g-host.store"}

TEMPLATE_ROOT = "templates"
UPLOAD_ROOT = "sites"
LOG_ROOT = "logs"


MAILJET_API_KEY = ""
MAILJET_API_SECRET = ""
OTP_EXPIRY_MINUTES = 5
MONGO_URI = ""



ALLOWED_EXTENSIONS = {"html", "css", "js", "jpg", "jpeg", "png", "txt", "gif"}
MAX_FILE_MB = 5.0
USER_QUOTA_MB = 100.0
os.makedirs(UPLOAD_ROOT, exist_ok=True)
os.makedirs(LOG_ROOT, exist_ok=True)





client = MongoClient(MONGO_URI)
db = client["ghost_host"]
users = db["users"]
otp_col = db["otps"]
pending_users = db["pending_users"]
logs_col = db["logs"]
analytics_collection = db["analytics_collection"]
visitors_collection = db["visitors_collection"]


db_requests = db["db_requests"]
abuse_reports = db["abuse_reports"]

otp_col.create_index("created_at", expireAfterSeconds=OTP_EXPIRY_MINUTES*60)

mailjet = Client(auth=(MAILJET_API_KEY, MAILJET_API_SECRET), version='v3.1')
