import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "voters.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()

    # ── Constituencies ────────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS constituencies (
            id   INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
    """)

    # ── Blocks (Blockchain Persistence) ───────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS blocks (
            hash          TEXT PRIMARY KEY,
            block_index   INTEGER NOT NULL,
            election_id   TEXT NOT NULL,
            voter_id      TEXT NOT NULL,
            candidate     TEXT NOT NULL,
            constituency  TEXT NOT NULL,
            timestamp     TEXT NOT NULL,
            previous_hash TEXT NOT NULL
        )
    """)
    # Migration for election_id
    bcols = [r[1] for r in c.execute("PRAGMA table_info(blocks)").fetchall()]
    if "election_id" not in bcols:
        c.execute("ALTER TABLE blocks RENAME TO blocks_old")
        c.execute("""
            CREATE TABLE blocks (
                hash          TEXT PRIMARY KEY,
                block_index   INTEGER NOT NULL,
                election_id   TEXT NOT NULL,
                voter_id      TEXT NOT NULL,
                candidate     TEXT NOT NULL,
                constituency  TEXT NOT NULL,
                timestamp     TEXT NOT NULL,
                previous_hash TEXT NOT NULL
            )
        """)
        c.execute("INSERT INTO blocks (hash, block_index, election_id, voter_id, candidate, constituency, timestamp, previous_hash) SELECT hash, block_index, 'ELECTION_1', voter_id, candidate, constituency, timestamp, previous_hash FROM blocks_old")
        c.execute("DROP TABLE blocks_old")

    # ── Voters ────────────────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS voters (
            voter_id      TEXT PRIMARY KEY,
            name          TEXT NOT NULL,
            face_path     TEXT NOT NULL,
            encoding      TEXT NOT NULL,
            constituency  TEXT NOT NULL,
            booth         TEXT DEFAULT ''
        )
    """)
    vcols = [r[1] for r in c.execute("PRAGMA table_info(voters)").fetchall()]
    if "booth" not in vcols:
        c.execute("ALTER TABLE voters ADD COLUMN booth TEXT DEFAULT ''")

    # ── Candidates ────────────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS candidates (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT NOT NULL,
            party         TEXT NOT NULL,
            symbol        TEXT NOT NULL,
            constituency  TEXT NOT NULL,
            photo_path    TEXT,
            ward          TEXT DEFAULT '',
            area          TEXT DEFAULT '',
            booth         TEXT DEFAULT ''
        )
    """)
    ccols = [r[1] for r in c.execute("PRAGMA table_info(candidates)").fetchall()]
    if "ward" not in ccols:
        c.execute("ALTER TABLE candidates ADD COLUMN ward TEXT DEFAULT ''")
        c.execute("ALTER TABLE candidates ADD COLUMN area TEXT DEFAULT ''")
        c.execute("ALTER TABLE candidates ADD COLUMN booth TEXT DEFAULT ''")

    # ── Audit Logs ────────────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp  TEXT NOT NULL,
            voter_id   TEXT,
            action     TEXT NOT NULL,
            detail     TEXT
        )
    """)

    # ── Election Settings ─────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS election_settings (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)

    # ── Seed constituencies ───────────────────────────────────────────────────
    c.execute("SELECT COUNT(*) FROM constituencies")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT OR IGNORE INTO constituencies (name) VALUES (?)",
                      [("North District",), ("South District",), ("Central District",)])

    # ── Seed default candidates ───────────────────────────────────────────────
    c.execute("SELECT COUNT(*) FROM candidates")
    if c.fetchone()[0] == 0:
        c.executemany(
            "INSERT OR IGNORE INTO candidates (name, party, symbol, constituency) VALUES (?,?,?,?)",
            [
                ("Alice Johnson",  "Progressive Party", "🌿", "North District"),
                ("Bob Martinez",   "Unity Alliance",    "⚡", "North District"),
                ("Carol Lee",      "Future Forward",    "🚀", "South District"),
                ("David Singh",    "People's Voice",    "🏛️", "South District"),
                ("Elena Ramos",    "Green Future",      "🌱", "Central District"),
                ("Frank Zhang",    "Tech Democracy",    "💻", "Central District"),
            ]
        )

    # ── Seed default settings ─────────────────────────────────────────────────
    c.execute("INSERT OR IGNORE INTO election_settings (key, value) VALUES ('results_locked','0')")

    conn.commit()
    conn.close()


# ── Voter helpers ──────────────────────────────────────────────────────────────

def get_all_voters(conn):
    return conn.execute(
        "SELECT voter_id, name, constituency FROM voters ORDER BY constituency, name"
    ).fetchall()


def get_voter(conn, voter_id):
    return conn.execute("SELECT * FROM voters WHERE voter_id=?", (voter_id,)).fetchone()


def add_voter(conn, voter_id, name, face_path, encoding_json, constituency="General", booth=""):
    conn.execute(
        "INSERT OR REPLACE INTO voters (voter_id, name, face_path, encoding, constituency, booth) VALUES (?,?,?,?,?,?)",
        (voter_id, name, face_path, encoding_json, constituency, booth)
    )
    conn.commit()

# ── Candidate helpers ──────────────────────────────────────────────────────────

def get_candidates(conn):
    return conn.execute("SELECT * FROM candidates ORDER BY constituency, id").fetchall()


def get_candidates_by_constituency(conn, constituency):
    return conn.execute(
        "SELECT * FROM candidates WHERE constituency=? ORDER BY id", (constituency,)
    ).fetchall()


def add_candidate(conn, name, party, symbol, constituency="General", photo_path=None, ward="", area="", booth=""):
    conn.execute(
        "INSERT INTO candidates (name, party, symbol, constituency, photo_path, ward, area, booth) VALUES (?,?,?,?,?,?,?,?)",
        (name, party, symbol, constituency, photo_path, ward, area, booth)
    )
    conn.commit()


# ── Constituency helpers ───────────────────────────────────────────────────────

def get_all_constituencies():
    # Returning 39 Lok Sabha Constituencies of Tamil Nadu unconditionally
    return sorted(["Arakkonam", "Arani", "Chennai Central", "Chennai North", 
                   "Chennai South", "Chidambaram", "Coimbatore", "Cuddalore", 
                   "Dharmapuri", "Dindigul", "Erode", "Kallakurichi", "Kancheepuram", 
                   "Kanniyakumari", "Karur", "Krishnagiri", "Madurai", "Mayiladuthurai", 
                   "Nagapattinam", "Namakkal", "Nilgiris", "Perambalur", "Pollachi", 
                   "Ramanathapuram", "Salem", "Sivaganga", "Sriperumbudur", "Tenkasi", 
                   "Thanjavur", "Theni", "Thoothukkudi", "Tiruchirappalli", "Tirunelveli", 
                   "Tiruppur", "Tiruvallur", "Tiruvannamalai", "Vellore", "Viluppuram", 
                   "Virudhunagar"])


def get_constituency_stats(conn):
    """Returns list of dicts: constituency, total_registered, total_voted."""
    rows = conn.execute("""
        SELECT constituency,
               COUNT(*) AS total_registered,
               SUM(has_voted) AS total_voted
        FROM voters
        GROUP BY constituency
        ORDER BY constituency
    """).fetchall()
    return [dict(r) for r in rows]


# ── Audit log helpers ──────────────────────────────────────────────────────────

def add_audit_log(conn, voter_id, action, detail=""):
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    conn.execute(
        "INSERT INTO audit_logs (timestamp, voter_id, action, detail) VALUES (?,?,?,?)",
        (ts, voter_id or "SYSTEM", action, detail)
    )
    conn.commit()


def get_audit_logs(conn, limit=200):
    return conn.execute(
        "SELECT * FROM audit_logs ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()


# ── Settings helpers ───────────────────────────────────────────────────────────

def get_setting(conn, key, default="0"):
    row = conn.execute("SELECT value FROM election_settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(conn, key, value):
    conn.execute("INSERT OR REPLACE INTO election_settings (key, value) VALUES (?,?)", (key, value))
    conn.commit()


# ── Block Persistence helpers ──────────────────────────────────────────────────

def add_block(conn, b, election_id="ELECTION_1"):
    conn.execute(
        "INSERT INTO blocks (hash, block_index, election_id, voter_id, candidate, constituency, timestamp, previous_hash) VALUES (?,?,?,?,?,?,?,?)",
        (b.hash, b.index, election_id, b.voter_id, b.candidate, b.constituency, b.timestamp, b.previous_hash)
    )
    conn.commit()


def get_all_blocks(conn, election_id="ELECTION_1"):
    return conn.execute("SELECT * FROM blocks WHERE election_id=? ORDER BY block_index ASC", (election_id,)).fetchall()
