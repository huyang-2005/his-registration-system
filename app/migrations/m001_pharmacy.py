"""001 建立药品、库存、处方、处方收费与发药相关表。"""
VERSION = 1
NAME = "pharmacy_tables"

DDL = """
CREATE TABLE IF NOT EXISTS drug (
    drug_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    drug_code     TEXT NOT NULL UNIQUE,
    generic_name  TEXT NOT NULL,
    trade_name    TEXT,
    spec          TEXT NOT NULL,
    dosage_form   TEXT,
    unit          TEXT NOT NULL DEFAULT '盒',
    price         REAL NOT NULL CHECK (price >= 0),
    manufacturer  TEXT,
    status        TEXT NOT NULL DEFAULT '启用' CHECK (status IN ('启用', '停用')),
    created_at    TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS drug_inventory (
    inventory_id INTEGER PRIMARY KEY AUTOINCREMENT,
    drug_id      INTEGER NOT NULL REFERENCES drug (drug_id),
    batch_no     TEXT NOT NULL,
    quantity     INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    expiry_date  TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE (drug_id, batch_no)
);

CREATE TABLE IF NOT EXISTS prescription (
    presc_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    presc_no     TEXT NOT NULL UNIQUE,
    reg_id       INTEGER NOT NULL REFERENCES registration (reg_id),
    patient_id   INTEGER NOT NULL REFERENCES patient (patient_id),
    doctor_id    INTEGER NOT NULL REFERENCES doctor (doctor_id),
    diagnosis    TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT '待收费'
                 CHECK (status IN ('待收费', '已收费', '已发药', '已作废')),
    total_amount REAL NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    operator_id  INTEGER REFERENCES sys_user (user_id)
);

CREATE TABLE IF NOT EXISTS prescription_item (
    item_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    presc_id   INTEGER NOT NULL REFERENCES prescription (presc_id) ON DELETE CASCADE,
    drug_id    INTEGER NOT NULL REFERENCES drug (drug_id),
    drug_name  TEXT NOT NULL,
    spec       TEXT,
    quantity   INTEGER NOT NULL CHECK (quantity > 0),
    unit_price REAL NOT NULL CHECK (unit_price >= 0),
    amount     REAL NOT NULL CHECK (amount >= 0)
);

CREATE TABLE IF NOT EXISTS presc_payment (
    pay_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    presc_id    INTEGER NOT NULL UNIQUE REFERENCES prescription (presc_id),
    amount      REAL NOT NULL CHECK (amount >= 0),
    pay_type    TEXT NOT NULL CHECK (pay_type IN ('现金', '医保', '微信', '支付宝')),
    pay_time    TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    status      TEXT NOT NULL DEFAULT '已支付' CHECK (status IN ('已支付', '已退费')),
    operator_id INTEGER REFERENCES sys_user (user_id)
);

CREATE TABLE IF NOT EXISTS dispense_record (
    dispense_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    presc_id     INTEGER NOT NULL UNIQUE REFERENCES prescription (presc_id),
    operator_id  INTEGER REFERENCES sys_user (user_id),
    dispensed_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_drug_generic ON drug (generic_name);
CREATE INDEX IF NOT EXISTS idx_inventory_drug ON drug_inventory (drug_id);
CREATE INDEX IF NOT EXISTS idx_presc_reg ON prescription (reg_id);
CREATE INDEX IF NOT EXISTS idx_presc_status ON prescription (status);
"""


def up(conn):
    conn.executescript(DDL)
