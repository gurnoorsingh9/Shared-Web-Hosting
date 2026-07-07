import io
import os
import re
import shutil
import zipfile

from flask import Blueprint, abort, jsonify, redirect, render_template, request, send_file, session
from werkzeug.utils import secure_filename

from config import MAX_FILE_MB, USER_QUOTA_MB, users
from routes.utils import allowed_ext, calc_usage, current_user, log_action, site_path

file_bp = Blueprint("filemanager", __name__)


@file_bp.route("/api/upload", methods=["POST"])
@log_action("files_uploaded")
def upload():
    u = current_user()
    if not u:
        return jsonify({"error": "not_authenticated"}), 401
    site = u.get("site_name")
    plan = u.get("user_plan")
    if not site:
        return jsonify({"success": False, "message": "Create site first"}), 400
    if "file" in request.files:
        files = [request.files["file"]]
    elif "files" in request.files:
        files = request.files.getlist("files")
    else:
        return jsonify({"success": False, "message": "No files uploaded"}), 400
    path = site_path(site)
    used = calc_usage(path)
    saved = []
    for f in files:
        if not allowed_ext(f.filename, plan):
            return jsonify({"success": False, "message": f"{f.filename} not allowed"}), 400
        f.seek(0, os.SEEK_END)
        size = f.tell() / (1024*1024)
        f.seek(0)
        if size > MAX_FILE_MB:
            return jsonify({"success": False, "message": f"{f.filename} >5MB"}), 400
        if used + size > USER_QUOTA_MB:
            return jsonify({"success": False, "message": "Quota exceeded"}), 400
        safe_name = secure_filename(f.filename)
        dest = os.path.join(path, safe_name)
        f.save(dest)
        saved.append(safe_name)
        used += size
    users.update_one({"email": u["email"]}, {"$set": {"usage.used_mb": used}})
    return jsonify({"success": True, "message": f"Uploaded {len(saved)} file(s)", "files": saved})

'''
@file_bp.route("/api/delete-file", methods=["POST"])
@log_action("delete-file")
def del_file():
    u = current_user()
    if not u:
        return jsonify({"error": "not_authenticated"}), 401
    d = request.get_json() or {}
    name = (d.get("filename") or "").strip()
    site = u.get("site_name")
    if not site or not name:
        return jsonify({"success": False, "message": "Missing"}), 400
    try:
        safe_name = secure_filename(name)
        fp = safe_join(safe_name)
        if not os.path.exists(fp):
            return jsonify({"success": False, "message": "File not found"}), 404
        os.remove(fp)
    except PermissionError:
        return jsonify({"success": False, "message": "Access denied"}), 403
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    used = calc_usage(site_path(site))
    users.update_one({"email": u["email"]}, {"$set": {"usage.used_mb": used}})
    return jsonify({"success": True})
'''
@file_bp.route("/api/delete-file", methods=["POST"])
@log_action("delete-file")
def del_file():
    u = current_user()
    if not u:
        return jsonify({"error": "not_authenticated"}), 401

    d = request.get_json() or {}
    name = (d.get("filename") or "").strip()
    site = u.get("site_name")

    if not site or not name:
        return jsonify({"success": False, "message": "Missing parameters"}), 400

    try:
        safe_name = secure_filename(name)
        fp = safe_join(safe_name)

        # Prevent deleting user root folder accidentally
        user_root = get_user_root()
        if os.path.abspath(fp) == user_root:
            return jsonify({"success": False, "message": "Cannot delete root folder"}), 403

        if not os.path.exists(fp):
            return jsonify({"success": False, "message": "File not found"}), 404

        os.remove(fp)

    except PermissionError:
        return jsonify({"success": False, "message": "Access denied"}), 403
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

    used = calc_usage(user_root)
    users.update_one({"email": u["email"]}, {"$set": {"usage.used_mb": used}})
    return jsonify({"success": True})



@file_bp.route("/filemanager")
def file_manager():
    if "email" not in session:
        return redirect("/")
    return render_template("filemanager.html")


import shutil
import zipfile
import tempfile
from flask import send_file, request, jsonify

import zipfile
import io
from flask import send_file, request, jsonify, abort

import re
from werkzeug.utils import secure_filename

ALLOWED_EXT = {"jpg","jpeg","png","gif","txt","html","css","js"}

DANGEROUS_EXT = {
    "php","phtml","phar","cgi","pl","py","sh","bash",
    "exe","dll","so","bin","cmd","bat"
}


def allowed_file(filename):
    if not filename:
        return False

    # Step 1: sanitize and lowercase
    filename = secure_filename(filename).strip()
    filename_lower = filename.lower()

    # Step 2: block hidden files
    if filename_lower.startswith("."):
        return False

    # Step 3: must contain at least one dot
    if "." not in filename_lower:
        return False

    # Step 4: check allowed characters (letters, numbers, _ - .)
    if not re.fullmatch(r"[a-z0-9._-]+", filename_lower):
        return False

    # Step 5: split all parts by dot and check each extension
    parts = filename_lower.split(".")
    name_parts = parts[:-1]  # everything except last extension
    ext = parts[-1]

    # Block dangerous extensions anywhere in filename
    for p in name_parts + [ext]:
        if p in DANGEROUS_EXT:
            return False

    # Step 6: check final extension is allowed
    if ext not in ALLOWED_EXT:
        return False

    return True
'''
def allowed_file(filename):
    if not filename:
        return False

    # sanitize filename
    filename = secure_filename(filename)
    filename = filename.lower().strip()

    # block hidden files (.env, .htaccess etc)
    if filename.startswith("."):
        return False

    # allow only safe characters
    if not re.fullmatch(r"[a-z0-9._-]+", filename):
        return False

    # must contain extension
    if "." not in filename:
        return False

    parts = filename.split(".")

    # block double extension like shell.php.jpg
    if len(parts) > 2:
        for p in parts[:-1]:
            if p in DANGEROUS_EXT:
                return False

    name = parts[0]
    ext = parts[-1]

    if not name:
        return False

    # block dangerous extensions anywhere
    if ext in DANGEROUS_EXT:
        return False

    # allow only whitelisted extensions
    if ext not in ALLOWED_EXT:
        return False

    return True
'''


# CONFIGURATION
BASE_DIR = os.path.abspath("sites")  # All user folders live here
              # Hardcoded for demo. In a real app, use session/login.

def get_user_root():
    """Returns the absolute path to the current user's root folder."""
    CURRENT_USER = current_user()
    CURRENT_USER = CURRENT_USER.get("site_name")

    user_path = os.path.join(BASE_DIR, CURRENT_USER)
    if not os.path.exists(user_path):
        os.makedirs(user_path)
    return user_path

def safe_join(path):
    """
    Security Barrier: Ensures the requested path is inside the user's root.
    Prevents '../' traversal attacks.
    """
    root = get_user_root()
    # Remove leading slash to treat path as relative to root
    
    if path.startswith('/'):
        path = path[1:]
    
    target_path = os.path.abspath(os.path.join(root, path))
    
    # Check if the target path starts with the user root path
    if not os.path.commonpath([root, target_path]) == root:
        raise PermissionError("Access denied")
    
    return target_path

'''
@file_bp.route('/')
def index():
    return render_template('index.html')
'''

@file_bp.route('/api/list')
def list_files():
    u = current_user()
    if not u:
        return jsonify({"error":"not_authenticated"}), 401
    req_path = request.args.get('path', '')
    try:
        abs_path = safe_join(req_path)
        
        items = []
        if os.path.isdir(abs_path):
            for entry in os.scandir(abs_path):
                items.append({
                    'name': entry.name,
                    'type': 'folder' if entry.is_dir() else 'file',
                    'path': os.path.join(req_path, entry.name).replace('\\', '/')
                })
        # Sort: Folders first, then files
        items.sort(key=lambda x: (x['type'] != 'folder', x['name'].lower()))
        
        return jsonify({'current_path': req_path, 'items': items})
    except Exception as e:
        return jsonify({'error': str(e)}), 403

'''#OLD FUNC
@file_bp.route('/api/create', methods=['POST'])
def create_item():
    data = request.json
    try:
        path = safe_join(data['path'])
        is_folder = data.get('is_folder', False)
        
        if is_folder:
            os.makedirs(path, exist_ok=True)
        else:
            with open(path, 'w') as f:
                f.write("") # Create empty file
                
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

'''

@file_bp.route('/api/create', methods=['POST'])
def create_item():
    u = current_user()
    if not u:
        return jsonify({"error":"not_authenticated"}), 401    
    data = request.json
    try:
        is_folder = data.get("is_folder", False)
        name = os.path.basename(data["path"])

        # If it's a folder, only sanitize name, do not enforce file extensions
        if is_folder:
            safe_name = secure_filename(name)
            if not safe_name:  # prevent empty names
                return jsonify({"error":"Invalid folder name"}), 400
        else:
            # For files, validate using allowed_file
            if not allowed_file(name):
                return jsonify({"error": "File type not allowed"}), 400
            safe_name = secure_filename(name)

        # Compute full path safely
        full_path = safe_join(os.path.join(os.path.dirname(data["path"]), safe_name))

        if is_folder:
            os.makedirs(full_path, exist_ok=True)
        else:
            with open(full_path, "w") as f:
                f.write("")

        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

'''
@file_bp.route('/api/delete', methods=['POST'])
def delete_item():
    u = current_user()
    if not u:
        return jsonify({"error":"not_authenticated"}), 401
    data = request.json
    try:
        path = safe_join(data['path'])
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            if not os.path.exists(path):
                return jsonify({"error":"Not found"}),404
            os.remove(path)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

'''
''' old func
@file_bp.route('/api/rename', methods=['POST'])
def rename_item():
    data = request.json
    try:
        old_path = safe_join(data['old_path'])
        new_path = safe_join(data['new_path'])
        
        os.rename(old_path, new_path)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
'''


@file_bp.route('/api/delete', methods=['POST'])
def delete_item():
    u = current_user()
    if not u:
        return jsonify({"error":"not_authenticated"}), 401

    data = request.json
    try:
        path = safe_join(data['path'])
        user_root = get_user_root()

        # Prevent deleting user root folder accidentally
        if os.path.abspath(path) == user_root:
            return jsonify({"error":"Cannot delete root folder"}), 403

        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            if not os.path.exists(path):
                return jsonify({"error":"Not found"}),404
            os.remove(path)

    except PermissionError:
        return jsonify({"error":"Access denied"}), 403
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    # Update usage
    used = calc_usage(user_root)
    users.update_one({"email": u["email"]}, {"$set": {"usage.used_mb": used}})

    return jsonify({'success': True})


@file_bp.route('/api/rename', methods=['POST'])
def rename_item():
    u = current_user()
    if not u:
        return jsonify({"error":"not_authenticated"}), 401
    data = request.json

    try:
        old_path = safe_join(data["old_path"])
        new_name = secure_filename(os.path.basename(data["new_path"]))

        new_path = os.path.join(os.path.dirname(old_path), new_name)

        if not allowed_file(new_name):
            return jsonify({"error":"Invalid filename"}),400

        if os.path.exists(new_path):
            return jsonify({"error":"File exists"}),400
        
        os.rename(old_path, new_path)

        return jsonify({"success":True})

    except Exception as e:
        return jsonify({"error":str(e)}),500



MAX_READ = 1024*1024  # 1MB

@file_bp.route('/api/read')
def read_file():
    u = current_user()
    if not u:
        return jsonify({"error":"not_authenticated"}), 401
    path = request.args.get("path")

    try:
        abs_path = safe_join(path)

        if os.path.getsize(abs_path) > MAX_READ:
            return jsonify({"error":"File too large"}),400

        with open(abs_path,"r",encoding="utf-8") as f:
            content = f.read()

        return jsonify({"content":content})

    except Exception as e:
        return jsonify({"error":str(e)}),500



MAX_SAVE = 5*1024*1024

@file_bp.route('/api/save', methods=['POST'])
def save_file():
    u = current_user()
    if not u:
        return jsonify({"error":"not_authenticated"}), 401
    data = request.json

    try:
        abs_path = safe_join(data["path"])

        content = data["content"]

        if len(content.encode("utf-8")) > MAX_SAVE:
            return jsonify({"error":"File too large"}),400

        with open(abs_path,"w",encoding="utf-8") as f:
            f.write(content)

        return jsonify({"success":True})

    except Exception as e:
        return jsonify({"error":str(e)}),500


def zip_folder(folder_path, user_root):
    """
    Create a zip file of the folder in memory
    """
    u = current_user()
    if not u:
        return jsonify({"error":"not_authenticated"}), 401
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                # Calculate the relative path to maintain folder structure in the zip
                arcname = os.path.relpath(file_path, user_root)
                zip_file.write(file_path, arcname)
    
    zip_buffer.seek(0)
    return zip_buffer

@file_bp.route("/api/downloadzip")
def download_zip():
    u = current_user()
    if not u:
        return jsonify({"error":"not_authenticated"}), 401    
    try:
        CURRENT_USER = current_user()
        CURRENT_USER = CURRENT_USER.get("site_name")
        # Get the path from query parameters
        path = request.args.get("path", "")
        
        # Get the safe, absolute path using your existing safe_join function
        safe_folder_path = safe_join(path)
        
        # Check if the path exists and is a directory
        if not os.path.exists(safe_folder_path):
            return jsonify({"error": "Folder not found"}), 404
        
        if not os.path.isdir(safe_folder_path):
            return jsonify({"error": "Path is not a folder"}), 400
        
        # Create zip file in memory
        user_root = get_user_root()
        zip_memory = zip_folder(safe_folder_path, user_root)
        
        # Generate download name
        download_name = os.path.basename(safe_folder_path) + ".zip"
        if download_name == ".zip":  # If it's the root directory
            download_name = f"{CURRENT_USER}.zip"
        
        return send_file(
            zip_memory,
            as_attachment=True,
            download_name=download_name,
            mimetype='application/zip'
        )
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
from flask import send_file
import os
from werkzeug.utils import secure_filename

@file_bp.route('/api/file')
def serve_file():
    u = current_user()
    if not u:
        return jsonify({"error":"not_authenticated"}), 401    
    try:
        abs_path = safe_join(request.args.get("path", ""))
    except PermissionError:
        return jsonify({"error": "Access denied"}), 403
    if not path:
        return jsonify({'error': 'Path parameter is required'}), 400
    
    try:
        # Security: Validate and sanitize the path
        if '..' in path or path.startswith('/'):
            return jsonify({'error': 'Invalid path'}), 400
        
        # Construct the full file path (adjust this to your actual file structure)
        file_path = os.path.join('uploads', path)  # Change 'uploads' to your actual upload directory
        
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404
        
        # Determine content type based on file extension
        ext = os.path.splitext(file_path)[1].lower()
        content_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.bmp': 'image/bmp',
            '.webp': 'image/webp',
            '.svg': 'image/svg+xml',
            '.ico': 'image/x-icon'
        }
        
        content_type = content_types.get(ext, 'application/octet-stream')
        
        return send_file(file_path, mimetype=content_type)
        
    except Exception as e:
        print(f"Error serving file: {e}")
        return jsonify({'error': 'Failed to serve file'}), 500
