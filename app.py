import os
import io
import json
from datetime import datetime
from flask import (Flask, render_template, request, redirect,
                   url_for, session, jsonify, flash, send_file)
from werkzeug.utils import secure_filename

from blockchain import Blockchain
from database import (
    init_db, get_db, get_voter, get_all_voters,
    get_candidates, get_candidates_by_constituency,
    add_voter, add_candidate,
    get_all_constituencies, get_constituency_stats,
    add_audit_log, get_audit_logs,
    get_setting, set_setting
)
from face_auth import encode_face_from_path, encode_face_from_b64, verify_face
from pdf_gen import generate_receipt

app = Flask(__name__)
app.secret_key = "blockchain_voting_secret_2024"
app.config["UPLOAD_FOLDER"]       = os.path.join("static", "voter_faces")
app.config["CANDIDATE_FOLDER"]    = os.path.join("static", "candidate_photos")
app.config["MAX_CONTENT_LENGTH"]  = 10 * 1024 * 1024  # 10 MB

os.makedirs(app.config["UPLOAD_FOLDER"],    exist_ok=True)
os.makedirs(app.config["CANDIDATE_FOLDER"], exist_ok=True)

# ── Global blockchain instance ────────────────────────────────────────────────
voting_chain = None

# ── Init DB on startup ────────────────────────────────────────────────────────
with app.app_context():
    init_db()
    conn = get_db()
    current_elec = get_setting(conn, "current_election", "ELECTION_1")
    conn.close()
    voting_chain = Blockchain(current_elec)

ADMIN_PASSWORD = "admin@2024"

# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def require_admin():
    """Return True if admin, else redirect to admin login."""
    return session.get("is_admin", False)


# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/")
def index():
    return render_template("index.html")


# ── Step 1 : voter enters their Voter ID ──────────────────────────────────────
@app.route("/verify-voter-id", methods=["POST"])
def verify_voter_id():
    voter_id = request.form.get("voter_id", "").strip().upper()
    conn = get_db()
    voter = get_voter(conn, voter_id)

    if not voter:
        add_audit_log(conn, voter_id, "LOGIN_FAILED", "Voter ID not found")
        conn.close()
        flash("❌ Voter ID not found. Please check and try again.", "danger")
        return redirect(url_for("index"))

    if voting_chain.has_voted(voter_id):
        add_audit_log(conn, voter_id, "DUPLICATE_ATTEMPT", "Voter already cast a vote")
        conn.close()
        flash("⚠️ You have already cast your vote in the current election.", "warning")
        return redirect(url_for("index"))

    add_audit_log(conn, voter_id, "VOTER_ID_ENTERED", f"Constituency: {voter['constituency']}")
    conn.close()

    session["pending_voter_id"]    = voter_id
    session["voter_name"]          = voter["name"]
    session["voter_constituency"]  = voter["constituency"]
    return render_template("face_scan.html", voter_name=voter["name"], voter_id=voter_id)


# ── Step 2 : face verification via webcam ────────────────────────────────────
@app.route("/api/verify-face", methods=["POST"])
def api_verify_face():
    pending = session.get("pending_voter_id")
    if not pending:
        return jsonify({"success": False, "message": "Session expired. Please log in again."}), 403

    data     = request.get_json(force=True)
    b64_image = data.get("image", "")

    conn  = get_db()
    voter = get_voter(conn, pending)

    if not voter:
        conn.close()
        return jsonify({"success": False, "message": "Voter not found."}), 404

    live_enc = encode_face_from_b64(b64_image)
    if live_enc is None:
        add_audit_log(conn, pending, "FACE_SCAN_FAILED", "No face detected in frame")
        conn.close()
        return jsonify({"success": False, "message": "No face detected. Please look at the camera."}), 200

    matched, confidence = verify_face(voter["encoding"], live_enc)
    if matched:
        add_audit_log(conn, pending, "FACE_VERIFIED", f"Confidence: {confidence*100:.1f}%")
        conn.close()
        session["authenticated_voter"] = pending
        session.pop("pending_voter_id", None)
        return jsonify({"success": True, "confidence": confidence,
                        "message": f"Face verified! Confidence: {confidence*100:.1f}%"})
    else:
        add_audit_log(conn, pending, "FACE_MISMATCH", f"Confidence: {confidence*100:.1f}%")
        conn.close()
        return jsonify({"success": False, "confidence": confidence,
                        "message": f"Face mismatch. Confidence: {confidence*100:.1f}%"})


# ── Step 3 : voting booth ────────────────────────────────────────────────────
@app.route("/vote")
def vote():
    voter_id = session.get("authenticated_voter")
    if not voter_id:
        flash("Please authenticate first.", "danger")
        return redirect(url_for("index"))

    conn  = get_db()
    
    # Check election time window
    start_at = get_setting(conn, "election_start", "")
    end_at = get_setting(conn, "election_end", "")
    now = datetime.utcnow().isoformat()
    if start_at and now < start_at:
        flash("Election has not started yet.", "warning")
        return redirect(url_for("index"))
    if end_at and now > end_at:
        flash("Election has already ended.", "warning")
        return redirect(url_for("index"))

    voter = get_voter(conn, voter_id)

    if not voter or voting_chain.has_voted(voter_id):
        conn.close()
        flash("⚠️ You have already voted in this election.", "warning")
        session.clear()
        return redirect(url_for("index"))

    constituency = voter["constituency"]
    candidates   = get_candidates_by_constituency(conn, constituency)
    conn.close()

    return render_template("vote.html",
                           voter_name=session.get("voter_name", voter_id),
                           constituency=constituency,
                           candidates=candidates)


@app.route("/cast-vote", methods=["POST"])
def cast_vote():
    voter_id = session.get("authenticated_voter")
    if not voter_id:
        flash("Session expired. Please log in again.", "danger")
        return redirect(url_for("index"))

    candidate    = request.form.get("candidate", "").strip()
    constituency = session.get("voter_constituency", "General")
    voter_name   = session.get("voter_name", voter_id)

    if not candidate:
        flash("Please select a candidate.", "warning")
        return redirect(url_for("vote"))

    # Write to blockchain
    block = voting_chain.add_vote(voter_id, candidate, constituency)

    # Mark as voted in audit log
    conn = get_db()
    add_audit_log(conn, voter_id, "VOTE_CAST",
                  f"Constituency: {constituency} | Block #{block.index}")
    conn.close()

    # Generate PDF receipt
    pdf_bytes = generate_receipt(
        voter_id=voter_id,
        voter_name=voter_name,
        constituency=constituency,
        block_hash=block.hash,
        block_index=block.index,
        timestamp=block.timestamp
    )
    # Store in session (base64) so user can download from success page
    import base64
    session["receipt_b64"]    = base64.b64encode(pdf_bytes).decode()
    session["receipt_vid"]    = voter_id
    session.pop("authenticated_voter", None)

    return render_template("success.html",
                           voter_name=voter_name,
                           candidate=candidate,
                           constituency=constituency,
                           block=block.to_dict())


@app.route("/download-receipt")
def download_receipt():
    b64 = session.get("receipt_b64")
    vid = session.get("receipt_vid", "voter")
    if not b64:
        flash("Receipt not available. Please vote first.", "warning")
        return redirect(url_for("index"))
    import base64
    pdf_bytes = base64.b64decode(b64)
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"vote_receipt_{vid}.pdf"
    )


# ══════════════════════════════════════════════════════════════════════════════
# RESULTS (public, but can be locked by admin)
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/results")
def results():
    conn   = get_db()
    locked = get_setting(conn, "results_locked", "0") == "1"
    conn.close()
    chain_valid = voting_chain.is_chain_valid()
    return render_template("results.html", chain_valid=chain_valid, locked=locked,
                           is_admin=session.get("is_admin", False))


@app.route("/api/results")
def api_results():
    conn   = get_db()
    locked = get_setting(conn, "results_locked", "0") == "1"
    stats  = get_constituency_stats(conn)
    conn.close()

    if locked and not session.get("is_admin"):
        return jsonify({"locked": True, "total_votes": 0, "results": {}, "by_constituency": {}})

    return jsonify({
        "locked":           False,
        "results":          voting_chain.get_results(),
        "by_constituency":  voting_chain.get_results_by_constituency(),
        "total_votes":      len(voting_chain.chain) - 1,
        "chain_valid":      voting_chain.is_chain_valid(),
        "turnout_stats":    stats,
    })


# ══════════════════════════════════════════════════════════════════════════════
# BLOCKCHAIN EXPLORER  (admin only)
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/blockchain")
def blockchain_explorer():
    if not require_admin():
        flash("🔒 Blockchain access is restricted to administrators.", "warning")
        return redirect(url_for("admin"))
    chain_data  = voting_chain.get_chain_data()
    chain_valid = voting_chain.is_chain_valid()
    return render_template("blockchain.html", chain=chain_data, chain_valid=chain_valid)


# ══════════════════════════════════════════════════════════════════════════════
# ADMIN PANEL
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/admin", methods=["GET", "POST"], strict_slashes=False)
def admin():
    if request.method == "POST":
        pwd = request.form.get("password", "")
        if pwd == ADMIN_PASSWORD:
            session["is_admin"] = True
            conn = get_db()
            add_audit_log(conn, "ADMIN", "ADMIN_LOGIN", "Admin logged in")
            conn.close()
        else:
            flash("Invalid admin password.", "danger")

    if not session.get("is_admin"):
        return render_template("admin_login.html")

    conn          = get_db()
    voters        = get_all_voters(conn)
    candidates    = get_candidates(conn)
    constituencies = get_all_constituencies()
    stats         = get_constituency_stats(conn)
    locked        = get_setting(conn, "results_locked", "0") == "1"
    election_start = get_setting(conn, "election_start", "")
    election_end = get_setting(conn, "election_end", "")
    current_elec  = get_setting(conn, "current_election", "ELECTION_1")
    audit_logs    = get_audit_logs(conn, limit=50)
    conn.close()

    return render_template("admin.html",
                           voters=voters,
                           candidates=candidates,
                           constituencies=constituencies,
                           stats=stats,
                           locked=locked,
                           election_start=election_start,
                           election_end=election_end,
                           current_elec=current_elec,
                           audit_logs=audit_logs,
                           total_votes=len(voting_chain.chain)-1,
                           chain_valid=voting_chain.is_chain_valid())


# ── Register Voter ─────────────────────────────────────────────────────────────
@app.route("/admin/register-voter", methods=["POST"])
def admin_register_voter():
    if not require_admin():
        return redirect(url_for("admin"))

    voter_id     = request.form.get("voter_id", "").strip().upper()
    name         = request.form.get("name", "").strip()
    constituency = request.form.get("constituency", "General").strip()
    booth        = request.form.get("booth", "").strip()
    file         = request.files.get("face_image")

    if not voter_id or not name or not file:
        flash("All fields are required.", "danger")
        return redirect(url_for("admin"))

    filename  = secure_filename(f"{voter_id}.jpg")
    face_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(face_path)

    encoding_json = encode_face_from_path(face_path)
    if encoding_json is None:
        os.remove(face_path)
        flash("❌ No face detected in uploaded image. Please use a clear frontal face photo.", "danger")
        return redirect(url_for("admin"))

    conn = get_db()
    add_voter(conn, voter_id, name, face_path, encoding_json, constituency, booth)
    add_audit_log(conn, "ADMIN", "VOTER_REGISTERED",
                  f"Voter {voter_id} ({name}) constituency: {constituency}, booth: {booth}")
    conn.close()
    flash(f"✅ Voter '{name}' registered. ID: {voter_id} | Constituency: {constituency}", "success")
    return redirect(url_for("admin"))


# ── Register Candidate ─────────────────────────────────────────────────────────
@app.route("/admin/register-candidate", methods=["POST"])
def admin_register_candidate():
    if not require_admin():
        return redirect(url_for("admin"))

    name         = request.form.get("c_name", "").strip()
    party        = request.form.get("c_party", "").strip()
    symbol       = request.form.get("c_symbol", "🗳️").strip() or "🗳️"
    constituency = request.form.get("c_constituency", "General").strip()
    ward         = request.form.get("c_ward", "").strip()
    area         = request.form.get("c_area", "").strip()
    booth        = request.form.get("c_booth", "").strip()
    file         = request.files.get("c_photo")

    if not name or not party or not constituency:
        flash("Candidate name, party, and constituency are required.", "danger")
        return redirect(url_for("admin"))

    photo_path = None
    if file and file.filename:
        filename   = secure_filename(f"{name.replace(' ','_')}_{constituency.replace(' ','_')}.jpg")
        photo_path = os.path.join(app.config["CANDIDATE_FOLDER"], filename)
        file.save(photo_path)
        photo_path = photo_path.replace("\\", "/")   # normalize for HTML

    conn = get_db()
    add_candidate(conn, name, party, symbol, constituency, photo_path, ward, area, booth)
    add_audit_log(conn, "ADMIN", "CANDIDATE_REGISTERED",
                  f"{name} ({party}) – {constituency}")
    conn.close()
    flash(f"✅ Candidate '{name}' added to '{constituency}'.", "success")
    return redirect(url_for("admin"))


# ── Toggle Result Lock ─────────────────────────────────────────────────────────
@app.route("/admin/toggle-results-lock")
def toggle_results_lock():
    if not require_admin():
        return redirect(url_for("admin"))
    conn    = get_db()
    current = get_setting(conn, "results_locked", "0")
    new_val = "0" if current == "1" else "1"
    set_setting(conn, "results_locked", new_val)
    add_audit_log(conn, "ADMIN", "RESULTS_LOCK_TOGGLED",
                  f"Results {'LOCKED' if new_val=='1' else 'UNLOCKED'}")
    conn.close()
    status = "locked 🔒" if new_val == "1" else "unlocked 🔓"
    flash(f"Results are now {status}.", "success")
    return redirect(url_for("admin"))


# ── Audit Log View ─────────────────────────────────────────────────────────────
@app.route("/admin/audit-log")
def admin_audit_log():
    if not require_admin():
        return redirect(url_for("admin"))
    conn   = get_db()
    logs   = get_audit_logs(conn, limit=500)
    conn.close()
    return render_template("audit_log.html", logs=logs)

# ── Start New Election ─────────────────────────────────────────────────────────
@app.route("/admin/new-election", methods=["POST"])
def admin_new_election():
    if not require_admin():
        return redirect(url_for("admin"))
    
    conn = get_db()
    current = get_setting(conn, "current_election", "ELECTION_1")
    try:
        num = int(current.split("_")[1])
    except:
        num = 1
    new_election_id = f"ELECTION_{num + 1}"
    
    set_setting(conn, "current_election", new_election_id)
    add_audit_log(conn, "ADMIN", "NEW_ELECTION_STARTED", f"Transitioned from {current} to {new_election_id}")
    conn.close()
    
    global voting_chain
    voting_chain = Blockchain(new_election_id)
    
    flash(f"New election '{new_election_id}' successfully started. Previous blockchain records are strictly preserved.", "success")
    return redirect(url_for("admin"))


# ── Save Settings ──────────────────────────────────────────────────────────────
@app.route("/admin/save-settings", methods=["POST"])
def admin_save_settings():
    if not require_admin():
        return redirect(url_for("admin"))
    
    start = request.form.get("election_start", "")
    end   = request.form.get("election_end", "")
    
    conn = get_db()
    set_setting(conn, "election_start", start)
    set_setting(conn, "election_end", end)
    add_audit_log(conn, "ADMIN", "SETTINGS_UPDATED", "Updated election datetime configuration")
    conn.close()
    
    flash("Election settings saved successfully.", "success")
    return redirect(url_for("admin"))


@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True, port=5000)
