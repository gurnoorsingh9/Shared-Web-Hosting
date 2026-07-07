import os
import re

from flask import Blueprint, jsonify, request

from config import users
from routes.utils import calc_usage, current_user, log_action, site_path

site_bp = Blueprint("site", __name__)


@site_bp.route("/api/site/add", methods=["POST"])
@log_action("Site_Created")
def add_site():
    u = current_user()
    if not u:
        return jsonify({"error": "not_authenticated"}), 401
    if u.get("site_name"):
        return jsonify({"success": False, "message": "You already have a site"}), 400
    d = request.get_json()
    name = d.get("name", "").strip()
    if not name or len(name) < 3:
        return jsonify({"success": False, "message": "Invalid name"}), 400
    path = site_path(name)
    if os.path.exists(path):
        return jsonify({"success": False, "message": "Folder exists"}), 400
    os.makedirs(path)
    users.update_one({"email": u["email"]}, {"$set": {"site_name": name, "uploaded_files": [], "usage.used_mb": 0.0}})
    return jsonify({"success": True, "site_name": name})


@site_bp.route("/api/site/delete", methods=["POST"])
@log_action("Site_Deleted")
def del_site():
    u = current_user()
    if not u:
        return jsonify({"error": "not_authenticated"}), 401
    site = u.get("site_name")
    if not site:
        return jsonify({"success": False, "message": "No site"}), 400
    path = site_path(site)
    if os.path.exists(path):
        for f in os.listdir(path):
            os.remove(os.path.join(path, f))
        os.rmdir(path)
    users.update_one({"email": u["email"]}, {"$set": {"site_name": None, "uploaded_files": [], "usage.used_mb": 0.0}})
    return jsonify({"success": True})


@site_bp.route("/api/check-site", methods=["POST"])
def check_site():
    data = request.get_json()
    name = data.get("name", "").lower()
    if not re.match(r"^[a-z0-9]([a-z0-9-]{1,30})[a-z0-9]$", name):
        return jsonify({"available": False, "message": "Invalid domain"}), 400
    existing = users.find_one({"site_name": name})
    return jsonify({"available": existing is None})


@site_bp.route("/api/track-visit", methods=["POST"])
def track_visit():
    data = request.get_json() or {}
    site_name = (data.get("site_name") or "").strip().lower()
    if not site_name:
        return jsonify({"success": False, "message": "site_name required"}), 400
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    ua = request.headers.get("User-Agent", "")
    return jsonify({"success": True})



import os
import json
import shutil
from flask import Blueprint, jsonify, request



PRETEMPLATE_DIR = "pretemp"


# =========================
# GET ALL TEMPLATES
# =========================
@site_bp.route("/api/templates", methods=["GET"])
def get_templates():

    templates = []

    if not os.path.exists(PRETEMPLATE_DIR):
        return jsonify({
            "success": True,
            "templates": []
        })

    for folder in os.listdir(PRETEMPLATE_DIR):

        folder_path = os.path.join(PRETEMPLATE_DIR, folder)

        if not os.path.isdir(folder_path):
            continue

        meta_path = os.path.join(folder_path, "metadata.json")

        if not os.path.exists(meta_path):
            continue

        try:

            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)

            templates.append({
                "id": meta.get("id"),
                "name": meta.get("name"),
                "preview": meta.get("preview")
            })

        except Exception:
            continue

    return jsonify({
        "success": True,
        "templates": templates
    })


# =========================
# GET SINGLE TEMPLATE
# =========================
@site_bp.route("/api/template/<template_id>", methods=["GET"])
def get_single_template(template_id):

    template_id = template_id.strip().lower()

    template_path = os.path.join(
        PRETEMPLATE_DIR,
        template_id
    )

    meta_path = os.path.join(
        template_path,
        "metadata.json"
    )

    if not os.path.exists(meta_path):
        return jsonify({
            "success": False,
            "message": "Template not found"
        }), 404

    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    return jsonify({
        "success": True,
        "template": {
            "id": meta.get("id"),
            "name": meta.get("name"),
            "preview": meta.get("preview")
        }
    })


# =========================
# APPLY TEMPLATE
# =========================
@site_bp.route("/api/template/apply", methods=["POST"])
@log_action("Template_Applied")
def apply_template():

    u = current_user()

    if not u:
        return jsonify({
            "error": "not_authenticated"
        }), 401

    site = u.get("site_name")

    if not site:
        return jsonify({
            "success": False,
            "message": "No site found"
        }), 400

    data = request.get_json()

    template = data.get(
        "template",
        ""
    ).strip().lower()

    if not template:
        return jsonify({
            "success": False,
            "message": "Template required"
        }), 400

    template_path = os.path.join(
        PRETEMPLATE_DIR,
        template
    )

    if not os.path.exists(template_path):
        return jsonify({
            "success": False,
            "message": "Invalid template"
        }), 400

    src = os.path.join(
        template_path,
        "files"
    )

    if not os.path.exists(src):
        return jsonify({
            "success": False,
            "message": "Template files missing"
        }), 500

    dst = site_path(site)

    try:

        shutil.copytree(
            src,
            dst,
            dirs_exist_ok=True
        )

        return jsonify({
            "success": True,
            "message": "Template applied successfully"
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500
