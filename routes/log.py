import json
import os

from flask import Blueprint, jsonify, request

from config import LOG_ROOT

log_bp = Blueprint("logs", __name__)


@log_bp.route("/api/logs/<site_name>/<year_month>")
def get_logs(site_name, year_month):
    file_path = os.path.join(LOG_ROOT, site_name, f"{year_month}.json")

    if not os.path.exists(file_path):
        return jsonify({"logs": []})

    with open(file_path, "r", encoding="utf-8") as f:
        logs = json.load(f)

    # filter by day
    day = request.args.get("day")
    if day:
        logs = [l for l in logs if l["timestamp"].startswith(f"{year_month}-{int(day):02d}")]

    # filter by action
    action = request.args.get("action")
    if action:
        logs = [l for l in logs if l.get("action") == action]

    return jsonify({"logs": logs})
