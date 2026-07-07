import datetime
import json
import os
import time
from functools import wraps
import hashlib
import random
import jwt
from flask import jsonify, request, session

from config import ADMIN_EMAILS, LOG_ROOT, SECRET, TOKEN_EXPIRY, UPLOAD_ROOT, users


import uuid

def generate_device():
    return str(uuid.uuid4())

def current_user():
    mail = session.get("email")
    return users.find_one({"email": mail}) if mail else None


def log_manual(site, action_name, data=None):
    import datetime, os, json
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    ua = request.headers.get("User-Agent", "")
    endpoint = request.path
    method = request.method
    timestamp = datetime.datetime.utcnow().isoformat() + "Z"
    data = data or {}

    site_log_dir = os.path.join(LOG_ROOT, site)
    os.makedirs(site_log_dir, exist_ok=True)

    month_file = datetime.datetime.utcnow().strftime("%Y-%m") + ".json"
    log_file_path = os.path.join(site_log_dir, month_file)

    log_entry = {
        "timestamp": timestamp,
        "endpoint": endpoint,
        "method": method,
        "ip": ip,
        "user_agent": ua,
        "action": action_name,
        "details": data
    }

    # Load existing logs safely
    logs = []
    if os.path.exists(log_file_path):
        try:
            with open(log_file_path, "r", encoding="utf-8") as f:
                logs = json.load(f)
                if not isinstance(logs, list):
                    logs = []
        except Exception:
            # if JSON corrupted, keep existing file by renaming
            os.rename(log_file_path, log_file_path + ".bak")
            logs = []

    logs.append(log_entry)

    # Save back without overwriting previous valid logs
    with open(log_file_path, "w", encoding="utf-8") as f:
        json.dump(logs, f, indent=2)




def make_tokenn(email):
    payload = {
        "email": email,
        "exp": time.time() + TOKEN_EXPIRY
    }
    return jwt.encode(payload, SECRET, algorithm="HS256")

import datetime

def make_token(email):
    payload = {
        "email": email,
        "iat": datetime.datetime.utcnow(),
        "exp": datetime.datetime.utcnow() + datetime.timedelta(seconds=TOKEN_EXPIRY)
    }
    return jwt.encode(payload, SECRET, algorithm="HS256")

def site_path(name):
    return os.path.join(UPLOAD_ROOT, name)


def calc_usage(folder):
    if not os.path.exists(folder):
        return 0.0
    total = 0
    for r, _, fs in os.walk(folder):
        for f in fs:
            total += os.path.getsize(os.path.join(r, f))
    return round(total / (1024*1024), 2)


def log_action(action_name):
    """
    Decorator to log user actions automatically.
    """
    def decorator(f):  # f is the original function
        @wraps(f)
        def wrapper(*args, **kwargs):
            # Pre-processing: capture info
            try:
                u = current_user()
                site = u.get("site_name") if u else "unknown"
                ip = request.headers.get("X-Forwarded-For", request.remote_addr)
                ua = request.headers.get("User-Agent", "")
                endpoint = request.path
                method = request.method
                timestamp = datetime.datetime.utcnow().isoformat() + "Z"

                # Call the original endpoint
                resp = f(*args, **kwargs)

                # Get JSON response if possible
                try:
                    data = resp.get_json() if hasattr(resp, "get_json") else {}
                except:
                    data = {}

                # Write log
                if site:
                    site_log_dir = os.path.join(LOG_ROOT, site)
                    os.makedirs(site_log_dir, exist_ok=True)

                    month_file = datetime.datetime.utcnow().strftime("%Y-%m") + ".json"
                    log_file_path = os.path.join(site_log_dir, month_file)

                    log_entry = {
                        "timestamp": timestamp,
                        "endpoint": endpoint,
                        "method": method,
                        "ip": ip,
                        "user_agent": ua,
                        "action": action_name,
                        "details": data
                    }

                    # Append to existing JSON
                    if os.path.exists(log_file_path):
                        try:
                            with open(log_file_path, "r", encoding="utf-8") as f_log:
                                logs = json.load(f_log)
                        except:
                            logs = []
                    else:
                        logs = []

                    logs.append(log_entry)

                    with open(log_file_path, "w", encoding="utf-8") as f_log:
                        json.dump(logs, f_log, indent=2)

            except Exception as e:
                print("Logging error:", e)

            return resp
        return wrapper
    return decorator


def allowed_ext1(filename, plan="free"):
    filename = filename.lower()
    ext = filename.rsplit(".", 1)[-1]
    base_allowed = {"jpg", "jpeg", "png", "txt","html", "css", "js", "gif"}
    if plan == "free":
        return ext in base_allowed
    if plan == "standard":
        return ext in base_allowed or ext == "php"
    return False


def allowed_ext(filename, plan="free"):
    filename = filename.lower()

    # block double extensions like shell.php.jpg
    if ".php." in filename or ".phtml." in filename:
        return False

    if "." not in filename:
        return False

    ext = filename.rsplit(".", 1)[-1]

    base_allowed = {"jpg","jpeg","png","txt","html","css","js","gif"}

    if plan == "free":
        return ext in base_allowed

    if plan == "standard":
        return ext in base_allowed or ext == "php"

    return False


def require_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        token = request.headers.get("Authorization")
        if not token:
            return jsonify({"error": "missing_token"}), 401
        token = token.replace("Bearer ", "")
        try:
            data = jwt.decode(token, SECRET, algorithms=["HS256"])
        except Exception:
            return jsonify({"error": "invalid_or_expired_token"}), 401
        request.user = data
        return f(*args, **kwargs)
    return wrapper


def require_admin(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        email = session.get("email")
        if not email:
            return jsonify({"error": "not_authenticated"}), 401
        if email not in ADMIN_EMAILS:
            return jsonify({"error": "forbidden", "message": "Admin only"}), 403
        return f(*args, **kwargs)
    return wrapper
