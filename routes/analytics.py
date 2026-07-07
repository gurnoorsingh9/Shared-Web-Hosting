from flask import Blueprint, request, jsonify
from datetime import datetime
from user_agents import parse
from flask import Blueprint, jsonify, session
from config import analytics_collection, users
from datetime import datetime
from config import analytics_collection, visitors_collection

analytics_bp = Blueprint("analytics", __name__)


@analytics_bp.route("/api/track", methods=["POST"])
def track():
    try:

        # =========================
        # GET REQUEST DATA
        # =========================

        data = request.get_json()

        if not data:
            return jsonify({
                "success": False,
                "message": "No data received"
            }), 400

        visitor_id = data.get("visitor_id")
        path = data.get("path")
        screen_size = data.get("screen_size")

        if not visitor_id or not path:
            return jsonify({
                "success": False,
                "message": "Missing required fields"
            }), 400


        # =========================
        # REQUEST INFO
        # =========================

        ip_address = request.remote_addr
        user_agent = request.headers.get("User-Agent")
        host = request.host


        # =========================
        # SITE NAME
        # =========================

        if host.startswith("127.") or host.startswith("localhost"):
            site_name = "testsite"
        else:
            site_name = host.split(".")[0]


        # =========================
        # USER AGENT PARSE
        # =========================

        ua = parse(user_agent)

        browser = ua.browser.family
        os_name = ua.os.family

        if ua.is_mobile:
            device = "Mobile"

        elif ua.is_tablet:
            device = "Tablet"

        else:
            device = "Desktop"


        # =========================
        # TODAY DATE
        # =========================

        today = datetime.now().strftime("%Y-%m-%d")


        # =========================
        # FIND ANALYTICS DOCUMENT
        # =========================

        analytics = analytics_collection.find_one({
            "site": site_name
        })


        # =========================
        # CREATE ANALYTICS DOCUMENT
        # =========================

        if not analytics:

            analytics = {
                "site": site_name,

                "total_views": 0,
                "unique_visitors": 0,

                "pages": {},

                "countries": {},
                "browsers": {},
                "devices": {},
                "operating_systems": {},

                "daily_views": {},

                "last_visit": None
            }

            analytics_collection.insert_one(analytics)


        # =========================
        # TOTAL VIEWS
        # =========================

        analytics["total_views"] += 1


        # =========================
        # UNIQUE VISITOR CHECK
        # =========================

        existing_visitor = visitors_collection.find_one({
            "site": site_name,
            "visitor_id": visitor_id
        })

        if not existing_visitor:

            analytics["unique_visitors"] += 1

            visitors_collection.insert_one({
                "site": site_name,
                "visitor_id": visitor_id,
                "created_at": datetime.utcnow()
            })


        # =========================
        # PAGE VIEWS
        # =========================

        if path not in analytics["pages"]:

            analytics["pages"][path] = {
                "views": 0
            }

        analytics["pages"][path]["views"] += 1


        # =========================
        # BROWSER STATS
        # =========================

        if browser not in analytics["browsers"]:
            analytics["browsers"][browser] = 0

        analytics["browsers"][browser] += 1


        # =========================
        # DEVICE STATS
        # =========================

        if device not in analytics["devices"]:
            analytics["devices"][device] = 0

        analytics["devices"][device] += 1


        # =========================
        # OS STATS
        # =========================

        if os_name not in analytics["operating_systems"]:
            analytics["operating_systems"][os_name] = 0

        analytics["operating_systems"][os_name] += 1


        # =========================
        # DAILY VIEWS
        # =========================

        if today not in analytics["daily_views"]:
            analytics["daily_views"][today] = 0

        analytics["daily_views"][today] += 1


        # =========================
        # LAST VISIT
        # =========================

        analytics["last_visit"] = datetime.utcnow()


        # =========================
        # UPDATE DATABASE
        # =========================

        analytics_collection.update_one(
            {
                "site": site_name
            },
            {
                "$set": analytics
            }
        )


        # =========================
        # DEBUG LOG
        # =========================

        print("\n===== ANALYTICS TRACK =====")
        print(f"Site            : {site_name}")
        print(f"Visitor ID      : {visitor_id}")
        print(f"Path            : {path}")
        print(f"IP              : {ip_address}")
        print(f"Browser         : {browser}")
        print(f"Device          : {device}")
        print(f"Operating System: {os_name}")
        print(f"Screen Size     : {screen_size}")
        print("===========================\n")


        return jsonify({
            "success": True,
            "message": "Analytics tracked successfully"
        }), 200


    except Exception as e:

        print(f"Analytics Error: {e}")

        return jsonify({
            "success": False,
            "message": "Internal server error"
        }), 500





@analytics_bp.route("/api/analytics", methods=["GET"])
def get_analytics():

    try:

        # =========================
        # CHECK LOGIN
        # =========================

        if "email" not in session:

            return jsonify({
                "success": False,
                "message": "Unauthorized"
            }), 401


        # =========================
        # GET USER
        # =========================

        user = users.find_one({
            "email": session["email"]
        })

        if not user:

            return jsonify({
                "success": False,
                "message": "User not found"
            }), 404


        # =========================
        # GET SITE NAME
        # =========================

        #site_name = user.get("site_name")
        site_name = "testsite"

        if not site_name:

            return jsonify({
                "success": False,
                "message": "No site found"
            }), 404


        # =========================
        # GET ANALYTICS DATA
        # =========================

        analytics = analytics_collection.find_one({
            "site": site_name
        })


        # =========================
        # NO ANALYTICS YET
        # =========================

        if not analytics:

            return jsonify({
                "success": True,
                "analytics": {
                    "site": site_name,
                    "total_views": 0,
                    "unique_visitors": 0,
                    "pages": {},
                    "countries": {},
                    "browsers": {},
                    "devices": {},
                    "operating_systems": {},
                    "daily_views": {}
                }
            })


        # =========================
        # REMOVE OBJECT ID
        # =========================

        analytics.pop("_id", None)


        # =========================
        # TODAY VIEWS
        # =========================

        today = datetime.now().strftime("%Y-%m-%d")

        today_views = analytics.get(
            "daily_views",
            {}
        ).get(today, 0)


        analytics["today_views"] = today_views


        # =========================
        # TOTAL PAGES
        # =========================

        analytics["total_pages"] = len(
            analytics.get("pages", {})
        )


        # =========================
        # RETURN RESPONSE
        # =========================

        return jsonify({
            "success": True,
            "analytics": analytics
        })


    except Exception as e:

        print(f"Analytics API Error: {e}")

        return jsonify({
            "success": False,
            "message": "Internal server error"
        }), 500
