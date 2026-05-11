from flask import Flask, render_template, request, redirect, session, jsonify, url_for
import sqlite3
import json
import os
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")

# On Render, mount a disk at /data and set DB_PATH=/data/flowchart.db
DB_PATH = os.environ.get("DB_PATH", "flowchart.db")


def get_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


def init_db():
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            preferences TEXT DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS flowcharts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            nodes TEXT DEFAULT '[]',
            connections TEXT DEFAULT '[]',
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)
    try:
        db.execute("ALTER TABLE users ADD COLUMN preferences TEXT DEFAULT '{}'")
    except Exception:
        pass
    db.commit()
    db.close()


def get_user_prefs():
    db = get_db()
    row = db.execute("SELECT preferences FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    db.close()
    try:
        return json.loads(row["preferences"]) if row and row["preferences"] else {}
    except Exception:
        return {}


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        if not username or not email or not password:
            return render_template("register.html", error="All fields are required.")

        db = get_db()
        try:
            db.execute(
                "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                (username, email, generate_password_hash(password))
            )
            db.commit()
            user = db.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
            session["user_id"] = user["id"]
            session["username"] = username
            db.close()
            return redirect(url_for("dashboard"))
        except sqlite3.IntegrityError:
            db.close()
            return render_template("register.html", error="Username or email already taken.")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        db.close()

        if not user or not check_password_hash(user["password_hash"], password):
            return render_template("login.html", error="Invalid username or password.")

        session["user_id"] = user["id"]
        session["username"] = user["username"]
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    flowcharts = db.execute(
        "SELECT id, name FROM flowcharts WHERE user_id = ? ORDER BY id DESC",
        (session["user_id"],)
    ).fetchall()
    db.close()
    return render_template("dashboard.html", flowcharts=flowcharts, username=session["username"], user_prefs=get_user_prefs())


@app.route("/new_flowchart")
@login_required
def new_flowchart():
    return render_template("new_flowchart.html")


@app.route("/create_flowchart", methods=["POST"])
@login_required
def create_flowchart():
    name = request.form["flowchart_name"].strip()
    if not name:
        return redirect(url_for("new_flowchart"))
    db = get_db()
    cursor = db.execute(
        "INSERT INTO flowcharts (user_id, name) VALUES (?, ?)",
        (session["user_id"], name)
    )
    flowchart_id = cursor.lastrowid
    db.commit()
    db.close()
    return redirect(url_for("canvas", flowchart_id=flowchart_id))


@app.route("/canvas/<int:flowchart_id>")
@login_required
def canvas(flowchart_id):
    db = get_db()
    fc = db.execute(
        "SELECT * FROM flowcharts WHERE id = ? AND user_id = ?",
        (flowchart_id, session["user_id"])
    ).fetchone()
    db.close()
    if not fc:
        return redirect(url_for("dashboard"))
    saved_data = {
        "nodes": json.loads(fc["nodes"]) if fc["nodes"] else [],
        "connections": json.loads(fc["connections"]) if fc["connections"] else []
    }
    return render_template("canvas.html", flowchart_name=fc["name"], flowchart_id=flowchart_id, saved_data=saved_data, user_prefs=get_user_prefs())


@app.route("/rename_flowchart", methods=["POST"])
@login_required
def rename_flowchart():
    data = request.get_json()
    db = get_db()
    fc = db.execute("SELECT id FROM flowcharts WHERE id = ? AND user_id = ?",
                    (data.get("id"), session["user_id"])).fetchone()
    if not fc:
        db.close()
        return jsonify({"error": "Not found"}), 404
    name = data.get("name", "").strip()
    if not name:
        db.close()
        return jsonify({"error": "Name cannot be empty"}), 400
    db.execute("UPDATE flowcharts SET name = ? WHERE id = ?", (name, data.get("id")))
    db.commit()
    db.close()
    return jsonify({"ok": True})


@app.route("/delete_flowchart", methods=["POST"])
@login_required
def delete_flowchart():
    data = request.get_json()
    db = get_db()
    fc = db.execute("SELECT id FROM flowcharts WHERE id = ? AND user_id = ?",
                    (data.get("id"), session["user_id"])).fetchone()
    if not fc:
        db.close()
        return jsonify({"error": "Not found"}), 404
    db.execute("DELETE FROM flowcharts WHERE id = ?", (data.get("id"),))
    db.commit()
    db.close()
    return jsonify({"ok": True})


@app.route("/update_account", methods=["POST"])
@login_required
def update_account():
    data = request.get_json()
    action = data.get("action")
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()

    if action == "change_password":
        if not check_password_hash(user["password_hash"], data.get("current_password", "")):
            db.close()
            return jsonify({"error": "Current password is incorrect."}), 400
        new_pw = data.get("new_password", "")
        if len(new_pw) < 6:
            db.close()
            return jsonify({"error": "New password must be at least 6 characters."}), 400
        db.execute("UPDATE users SET password_hash = ? WHERE id = ?",
                   (generate_password_hash(new_pw), session["user_id"]))
        db.commit()
        db.close()
        return jsonify({"ok": True, "message": "Password updated."})

    if action == "change_email":
        if not check_password_hash(user["password_hash"], data.get("password", "")):
            db.close()
            return jsonify({"error": "Password is incorrect."}), 400
        new_email = data.get("new_email", "").strip().lower()
        if not new_email or "@" not in new_email:
            db.close()
            return jsonify({"error": "Invalid email address."}), 400
        try:
            db.execute("UPDATE users SET email = ? WHERE id = ?", (new_email, session["user_id"]))
            db.commit()
            db.close()
            return jsonify({"ok": True, "message": "Email updated."})
        except Exception:
            db.close()
            return jsonify({"error": "Email already in use."}), 400

    db.close()
    return jsonify({"error": "Unknown action."}), 400


@app.route("/delete_account", methods=["POST"])
@login_required
def delete_account():
    db = get_db()
    db.execute("DELETE FROM flowcharts WHERE user_id = ?", (session["user_id"],))
    db.execute("DELETE FROM users WHERE id = ?", (session["user_id"],))
    db.commit()
    db.close()
    session.clear()
    return jsonify({"ok": True})


@app.route("/save_preferences", methods=["POST"])
@login_required
def save_preferences():
    data = request.get_json()
    db = get_db()
    db.execute("UPDATE users SET preferences = ? WHERE id = ?",
               (json.dumps(data), session["user_id"]))
    db.commit()
    db.close()
    return jsonify({"ok": True})


@app.route("/save_flowchart", methods=["POST"])
@login_required
def save_flowchart():
    data = request.get_json()
    flowchart_id = data.get("id")
    db = get_db()
    fc = db.execute(
        "SELECT id FROM flowcharts WHERE id = ? AND user_id = ?",
        (flowchart_id, session["user_id"])
    ).fetchone()
    if not fc:
        db.close()
        return jsonify({"error": "Not found"}), 404
    db.execute(
        "UPDATE flowcharts SET nodes = ?, connections = ? WHERE id = ?",
        (json.dumps(data.get("nodes", [])), json.dumps(data.get("connections", [])), flowchart_id)
    )
    db.commit()
    db.close()
    return jsonify({"message": "Saved!"})


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
