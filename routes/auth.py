import datetime
import os
import random

from flask import Blueprint, jsonify, request, session
from mailjet_rest import Client
from werkzeug.security import check_password_hash, generate_password_hash

from config import MAILJET_API_KEY, MAILJET_API_SECRET, OTP_EXPIRY_MINUTES, USER_QUOTA_MB, otp_col, pending_users, users,mailjet
from routes.utils import calc_usage, current_user, log_action, log_manual, make_token, site_path,generate_device

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/api/signup", methods=["POST"])
def signup():
    d = request.get_json()
    mail, pwd = d.get("email", "").lower(), d.get("password", "")
    if not mail or not pwd:
        return jsonify({"success": False, "message": "Missing fields"}), 400
    if users.find_one({"email": mail}):
        return jsonify({"success": False, "message": "Email exists"}), 400

    otp = str(random.randint(100000, 999999))
    now = datetime.datetime.utcnow()

    # Store OTP
    otp_col.update_one(
        {"email": mail},
        {"$set": {"otp": otp, "created_at": now}},
        upsert=True
    )

    pending_users.update_one(
        {"email": mail},
        {"$set": {"email": mail, "password_hash": generate_password_hash(pwd), "created_at": now}},
        upsert=True
    )
    mailjet = Client(auth=(MAILJET_API_KEY, MAILJET_API_SECRET), version='v3.1')
    text_part = f"""
    Welcome to G Host!

    Your OTP for completing the signup is: {otp}

    This OTP is valid for {OTP_EXPIRY_MINUTES} minutes.

    If you did not request this, please ignore this email.

    Thank you,
    G Host Team
    """
    html_part = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <style>
        body {{ font-family: 'Poppins', sans-serif; background: #f5f7fb; color: #2c3e50; padding: 20px; }}
        .container {{ max-width: 600px; margin: auto; background: #fff; padding: 30px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); }}
        .otp {{ font-size: 24px; font-weight: bold; color: #1565c0; }}
        .footer {{ margin-top: 20px; font-size: 14px; color: #546e7a; }}
      </style>
    </head>
    <body>
      <div class="container">
        <h2>Welcome to G Host!</h2>
        <p>Your OTP to complete the signup is:</p>
        <p class="otp">{otp}</p>
        <p>This OTP will expire in {OTP_EXPIRY_MINUTES} minutes.</p>
        <p class="footer">If you did not request this, simply ignore this email.<br>Thank you, <br>G Host Team</p>
      </div>
    </body>
    </html>
    """
    message = {
        'Messages': [
            {
                "From": {"Email": "otp@g-host.store", "Name": "G Host"},
                "To": [{"Email": mail}],
                "Subject": "OTP Verification",
                "TextPart": text_part,
                "HTMLPart": html_part
            }
        ]
    }
    result = mailjet.send.create(data=message)
    print(otp)
    result = mailjet.send.create(data=message)

    if result.status_code == 200:
        return jsonify({"success": True, "message": "OTP sent. Verify to complete signup."})
    else:
        return jsonify({"success": False, "message": "Failed to send OTP"}), 500


@auth_bp.route("/api/ver-otp", methods=["POST"])
def verify_otp():
    data = request.get_json()
    email = data.get("email", "").lower()
    otp = data.get("otp", "")
    if not email or not otp:
        return jsonify({"success": False, "message": "Missing fields"}), 400
    record = otp_col.find_one({"email": email})
    if not record:
        return jsonify({"success": False, "message": "OTP expired or not sent"}), 400
    if record["otp"] != otp:
        return jsonify({"success": False, "message": "Invalid OTP"}), 400

    otp_col.delete_one({"email": email})
    pending = pending_users.find_one({"email": email})
    if not pending:
        return jsonify({"success": False, "message": "Signup record not found"}), 400

    now = datetime.datetime.utcnow()

    users.insert_one({
        "email": pending["email"],
        "password": pending["password_hash"],
        "user_plan": "free",
        "trusted_device_id": None,
        "site_name": None,
        "uploaded_files": [],
        "usage": {"used_mb": 0.0, "total_mb": USER_QUOTA_MB},
        "MemberSince" : now
    })
    pending_users.delete_one({"email": email})
    session["email"] = email
    return jsonify({"success": True, "message": "OTP verified. Signup complete."})





#@auth_bp.route("/api/login", methods=["POST"])
'''
def login():
    d = request.get_json()
    mail, pwd = d.get("email", "").lower(), d.get("password", "")
    u = users.find_one({"email": mail})
    if not u or not check_password_hash(u["password"], pwd):
        return jsonify({"success": False, "message": "Invalid credentials"}), 401
    if u.get("blocked"):
        return jsonify({"success": False, "message": "Account is blocked"}), 403
    session["email"] = mail
    users.update_one({"email": mail}, {"$set": {"last_login_at": datetime.datetime.utcnow()}})
    token = make_token(mail)
    return jsonify({"success": True, "token": token})


@auth_bp.route("/api/login", methods=["POST"])
def login():
    d = request.get_json()
    mail = d.get("email", "").lower()
    pwd = d.get("password", "")

    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    ua = request.headers.get("User-Agent", "")

    u = users.find_one({"email": mail})
    device_id = get_device_id(ip, ua)
    now = datetime.datetime.utcnow()
    # user not found
    if not u:
        log_manual("system", "Login_Attempt", {
            "email": mail,
            "success": False,
            "reason": "user_not_found",
            "ip": ip,
            "ua": ua
        })
        return jsonify({"success": False, "message": "Invalid credentials"}), 401

    # wrong password
    if not check_password_hash(u["password"], pwd):
        log_manual(u.get("site_name") or "system", "Login_Attempt", {
            "email": mail,
            "success": False,
            "reason": "wrong_password",
            "ip": ip,
            "ua": ua
        })
        return jsonify({"success": False, "message": "Invalid credentials"}), 401

    # blocked account
    if u.get("blocked"):
        log_manual(u.get("site_name") or "system", "Login_Attempt", {
            "email": mail,
            "success": False,
            "reason": "blocked_account",
            "ip": ip,
            "ua": ua
        })
        return jsonify({"success": False, "message": "Account blocked"}), 403

    # success
    session["email"] = mail
    session.permanent = True
    users.update_one(
        {"email": mail},
        {"$set": {"last_login_at": datetime.datetime.utcnow()}}
    )

    token = make_token(mail)

    log_manual(u.get("site_name") or "system", "Login_Attempt", {
        "email": mail,
        "success": True,
        "reason": "login_success",
        "ip": ip,
        "ua": ua
    })

    return jsonify({"success": True, "token": token})
'''

@auth_bp.route("/api/login/verify-otp/v2", methods=["POST"])
def verify_login_otp():
    data = request.get_json()

    mail = data.get("email", "").lower()
    otp = data.get("otp", "")
    trust_device = data.get("trust_device", False)
    device_id = data.get("device_id")

    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    ua = request.headers.get("User-Agent", "")
    now = datetime.datetime.utcnow()

    u = users.find_one({"email": mail})

    if not u:
        return jsonify({"success": False, "message": "User not found"}), 404

    record = otp_col.find_one({"email": mail, "type": "login"})

    if not record or record.get("otp") != otp:
        log_manual(u.get("site_name") or "system", "OTP_Verify", {
            "email": mail,
            "success": False,
            "reason": "invalid_otp",
            "ip": ip,
            "ua": ua
        })
        return jsonify({"success": False, "message": "Invalid OTP"}), 400

    otp_col.delete_one({"_id": record["_id"]})

    # =========================
    # TRUST DEVICE (7 DAYS)
    # =========================
    if trust_device and device_id:
        users.update_one(
            {"email": mail},
            {"$set": {
                "trusted_device_id": {
                    "device_id": device_id,
                    "created_at": now,
                    "expires_at": now + datetime.timedelta(days=7)
                }
            }}
        )

    session["email"] = mail
    session.permanent = True

    users.update_one(
        {"email": mail},
        {"$set": {"last_login_at": now}}
    )

    token = make_token(mail)

    log_manual(u.get("site_name") or "system", "OTP_Verify", {
        "email": mail,
        "success": True,
        "reason": "otp_verified_login_success",
        "ip": ip,
        "ua": ua
    })

    return jsonify({
        "success": True,
        "token": token
    })



@auth_bp.route("/api/login/send-otp", methods=["POST"])
def send_login_otp():
    data = request.get_json()

    mail = data.get("email", "").lower()
    device_id = data.get("device_id")

    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    ua = request.headers.get("User-Agent", "")
    now = datetime.datetime.utcnow()

    u = users.find_one({"email": mail})

    if not u:
        return jsonify({"success": False, "message": "User not found"}), 404

    otp = str(random.randint(100000, 999999))

    otp_col.update_one(
        {"email": mail, "type": "login"},
        {"$set": {
            "otp": otp,
            "created_at": now,
            "device_id": device_id
        }},
        upsert=True
    )

    mailjet = Client(auth=(MAILJET_API_KEY, MAILJET_API_SECRET), version='v3.1')
    text_part = f"""
    Welcome to G Host!

    Your OTP for completing the Verification is: {otp}

    This OTP is valid for {OTP_EXPIRY_MINUTES} minutes.

    If you did not request this, please ignore this email.

    Thank you,
    G Host Team
    """
    html_part = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <style>
        body {{ font-family: 'Poppins', sans-serif; background: #f5f7fb; color: #2c3e50; padding: 20px; }}
        .container {{ max-width: 600px; margin: auto; background: #fff; padding: 30px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); }}
        .otp {{ font-size: 24px; font-weight: bold; color: #1565c0; }}
        .footer {{ margin-top: 20px; font-size: 14px; color: #546e7a; }}
      </style>
    </head>
    <body>
      <div class="container">
        <h2>Welcome to G Host!</h2>
        <p>Your OTP For Verification Is :</p>
        <p class="otp">{otp}</p>
        <p>This OTP will expire in {OTP_EXPIRY_MINUTES} minutes.</p>
        <p class="footer">If you did not request this, simply ignore this email.<br>Thank you, <br>G Host Team</p>
      </div>
    </body>
    </html>
    """
    message = {
        'Messages': [
            {
                "From": {"Email": "otp@g-host.store", "Name": "G Host"},
                "To": [{"Email": mail}],
                "Subject": "OTP Verification",
                "TextPart": text_part,
                "HTMLPart": html_part
            }
        ]
    }
    result = mailjet.send.create(data=message)
    print(otp)
    result = mailjet.send.create(data=message)

    return jsonify({
        "success": True,
        "message": "OTP sent",
        "device_id": device_id
    })

@auth_bp.route("/api/login", methods=["POST"])
def login():
    d = request.get_json()
    mail = d.get("email", "").lower()
    pwd = d.get("password", "")
    device_id = d.get("device_id")

    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    ua = request.headers.get("User-Agent", "")
    now = datetime.datetime.utcnow()

    u = users.find_one({"email": mail})

    # =========================
    # USER NOT FOUND
    # =========================
    if not u:
        log_manual("system", "Login_Attempt", {
            "email": mail,
            "success": False,
            "reason": "user_not_found",
            "ip": ip,
            "ua": ua
        })
        return jsonify({"success": False, "message": "Invalid credentials"}), 401

    # =========================
    # WRONG PASSWORD
    # =========================
    if not check_password_hash(u["password"], pwd):
        log_manual(u.get("site_name") or "system", "Login_Attempt", {
            "email": mail,
            "success": False,
            "reason": "wrong_password",
            "ip": ip,
            "ua": ua
        })
        return jsonify({"success": False, "message": "Invalid credentials"}), 401

    # =========================
    # BLOCKED ACCOUNT
    # =========================
    if u.get("blocked"):
        log_manual(u.get("site_name") or "system", "Login_Attempt", {
            "email": mail,
            "success": False,
            "reason": "blocked_account",
            "ip": ip,
            "ua": ua
        })
        return jsonify({"success": False, "message": "Account blocked"}), 403

    # =========================
    # TRUSTED DEVICE PARSE
    # =========================
    trusted = u.get("trusted_device_id")

    trusted_device_id = None
    trusted_expires = None

    if isinstance(trusted, dict):
        trusted_device_id = trusted.get("device_id")
        trusted_expires = trusted.get("expires_at")
    else:
        trusted_device_id = trusted

    # =========================
    # CASE 1: NO DEVICE SENT → GENERATE DEVICE ID
    # =========================
    if not device_id:
        device_id = str(uuid.uuid4())  # ✅ ADDED ONLY

        log_manual(u.get("site_name") or "system", "Login_Attempt", {
            "email": mail,
            "success": False,
            "reason": "otp_required_no_device",
            "ip": ip,
            "ua": ua
        })

        return jsonify({
            "action": "require_otp",
            "require_otp": True,
            "device_id": device_id
        })

    # =========================
    # CASE 2: TRUSTED DEVICE LOGIN
    # =========================
    is_trusted_valid = False

    if trusted_device_id == device_id:
        if trusted_expires and now <= trusted_expires:
            is_trusted_valid = True

    if is_trusted_valid:
        session["email"] = mail
        session.permanent = True

        users.update_one(
            {"email": mail},
            {"$set": {"last_login_at": now}}
        )

        token = make_token(mail)

        log_manual(u.get("site_name") or "system", "Login_Attempt", {
            "email": mail,
            "success": True,
            "reason": "login_success_trusted_device",
            "ip": ip,
            "ua": ua
        })

        return jsonify({
            "success": True,
            "token": token,
            "device_id": device_id
        })

    # =========================
    # CASE 3: NEW DEVICE → OTP REQUIRED (NO GENERATION HERE NOW)
    # =========================
    log_manual(u.get("site_name") or "system", "Login_Attempt", {
        "email": mail,
        "success": False,
        "reason": "otp_required_new_device",
        "ip": ip,
        "ua": ua
    })

    return jsonify({
        "action": "require_otp",
        "require_otp": True,
        "device_id": device_id
    })

@auth_bp.route("/api/dashboard")
def api_dash():
    u = current_user()
    if not u:
        return jsonify({"error": "not_authenticated"}), 401
    site = u.get("site_name")
    user_plan = u.get("user_plan")
    files, used = [], 0.0
    last_login_at = u.get("last_login_at")
    MemberSince = u.get("MemberSince")
    if site:
        path = site_path(site)
        used = calc_usage(path)
        if os.path.exists(path):
            for f in sorted(os.listdir(path)):
                fp = os.path.join(path, f)
                if os.path.isfile(fp):
                    files.append({"name": f, "size": round(os.path.getsize(fp)/(1024*1024), 2)})
    users.update_one({"email": u["email"]}, {"$set": {"usage.used_mb": used}})
    return jsonify({
        "email": u["email"],
        "site_name": site,
        "user_plan": user_plan,
        "usage": {"used_mb": used, "total_mb": USER_QUOTA_MB},
        "uploaded_files": files,
        "last_login_at": last_login_at,
        "MemberSince": MemberSince
    })


# For Request To Change Password And Genrate Otp For Forgot Password
@auth_bp.route("/api/forgot-password/request", methods=["POST"])
@log_action("forgot-password")
def forgot_password_request():
    data = request.get_json()
    email = data.get("email", "").lower()
    if not email:
        return jsonify({"success": False, "message": "Email required"}), 400
    user = users.find_one({"email": email})
    if not user:
        return jsonify({"success": False, "message": "Email not found"}), 404
    otp = str(random.randint(100000, 999999))
    now = datetime.datetime.utcnow()
    otp_col.update_one(
        {"email": email, "type": "forgot"},
        {"$set": {"otp": otp, "created_at": now, "verified": False}},
        upsert=True
    )
    mailjet = Client(auth=(MAILJET_API_KEY, MAILJET_API_SECRET), version='v3.1')
    text_part = f"""
    Welcome Back to G Host!

    Your OTP for Reset Password is : {otp}

    This OTP is valid for {OTP_EXPIRY_MINUTES} minutes.

    If you did not request this, please ignore this email.

    Thank you,
    G Host Team
    """
    html_part = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <style>
        body {{ font-family: 'Poppins', sans-serif; background: #f5f7fb; color: #2c3e50; padding: 20px; }}
        .container {{ max-width: 600px; margin: auto; background: #fff; padding: 30px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); }}
        .otp {{ font-size: 24px; font-weight: bold; color: #1565c0; }}
        .footer {{ margin-top: 20px; font-size: 14px; color: #546e7a; }}
      </style>
    </head>
    <body>
      <div class="container">
        <h2>Welcome Back to G Host!</h2>
        <p>Your OTP for Reset Password is:</p>
        <p class="otp">{otp}</p>
        <p>This OTP will expire in {OTP_EXPIRY_MINUTES} minutes.</p>
        <p class="footer">If you did not request this, simply ignore this email.<br>Thank you, <br>GhostHost Team</p>
      </div>
    </body>
    </html>
    """
    message = {
        'Messages': [
            {
                "From": {"Email": "otp@g-host.store", "Name": "G Host"},
                "To": [{"Email": email}],
                "Subject": "Your OTP for Password Reset",
                "TextPart": text_part,
                "HTMLPart": html_part
            }
        ]
    }
    result = mailjet.send.create(data=message)
    if result.status_code == 200:
        return jsonify({"success": True, "message": "OTP sent to your email."})
    else:
        return jsonify({"success": False, "message": "Failed to send OTP."}), 500


@auth_bp.route("/api/forgot-password/verify-otp", methods=["POST"])
def forgot_password_verify_otp():
    data = request.get_json()
    email = data.get("email", "").lower()
    otp = data.get("otp", "")

    if not email or not otp:
        return jsonify({"success": False, "message": "Missing fields"}), 400

    record = otp_col.find_one({"email": email, "type": "forgot"})
    if not record:
        return jsonify({"success": False, "message": "OTP expired or not sent"}), 400

    if record["otp"] != otp:
        return jsonify({"success": False, "message": "Invalid OTP"}), 400

    # Mark OTP as verified
    otp_col.update_one({"email": email, "type": "forgot"}, {"$set": {"verified": True}})

    return jsonify({"success": True, "message": "OTP verified. You can now reset your password."})


@auth_bp.route("/api/forgot-password/reset", methods=["POST"])
def forgot_password_reset():
    data = request.get_json()
    email = data.get("email", "").lower()
    new_password = data.get("password", "")

    if not email or not new_password:
        return jsonify({"success": False, "message": "Missing fields"}), 400

    # Check OTP verified
    record = otp_col.find_one({"email": email, "type": "forgot", "verified": True})
    if not record:
        return jsonify({"success": False, "message": "OTP not verified"}), 400

    # Update password
    users.update_one({"email": email}, {"$set": {"password": generate_password_hash(new_password)}})

    # Remove OTP record
    otp_col.delete_one({"email": email, "type": "forgot"})

    return jsonify({"success": True, "message": "Password updated successfully."})
