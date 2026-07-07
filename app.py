import os,datetime

from flask import Flask

import config

app = Flask(__name__, template_folder=config.TEMPLATE_ROOT)
app.secret_key = "ghost-secret"
app.permanent_session_lifetime = datetime.timedelta(minutes=30)

# BLUEPRINT REGISTRATION 
from routes.pages import pages_bp
from routes.auth import auth_bp
from routes.site import site_bp
from routes.filemanager import file_bp
from routes.log import log_bp
from routes.analytics import analytics_bp


app.register_blueprint(pages_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(site_bp)
app.register_blueprint(file_bp)
app.register_blueprint(log_bp)
app.register_blueprint(analytics_bp)

@app.route("/test")
def test():
    return """
    <html>
    <body>

        <h1>Analytics Test</h1>

        <script src="/static/js/tracker.js"></script>

    </body>
    </html>
    """
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9000, debug=True)
