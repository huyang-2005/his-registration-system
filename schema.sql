-- ============================================================
-- 门诊挂号分系统 - SQLite 数据库结构
-- 依据：卫生部《医院信息系统基本功能规范》
-- ============================================================

PRAGMA foreign_keys = ON;

-- 按外键依赖逆序删除，便于重复初始化
DROP TABLE IF EXISTS operation_log;
DROP TABLE IF EXISTS payment;
DROP TABLE IF EXISTS registration;
DROP TABLE IF EXISTS doctor_schedule;
DROP TABLE IF EXISTS registration_level;
DROP TABLE IF EXISTS doctor;
DROP TABLE IF EXISTS department;
DROP TABLE IF EXISTS patient;
DROP TABLE IF EXISTS sys_user;

-- ------------------------------------------------------------
-- 系统用户（挂号员 / 收费员 / 管理员）
-- ------------------------------------------------------------
CREATE TABLE sys_user (
    user_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    username    TEXT NOT NULL UNIQUE,
    password    TEXT NOT NULL,
    real_name   TEXT NOT NULL,
    role        TEXT NOT NULL CHECK (role IN ('挂号员', '收费员', '管理员')),
    status      TEXT NOT NULL DEFAULT '启用' CHECK (status IN ('启用', '停用'))
);

-- ------------------------------------------------------------
-- 患者门诊档案（患者主索引）
-- ------------------------------------------------------------
CREATE TABLE patient (
    patient_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    medical_record_no TEXT NOT NULL UNIQUE,
    name              TEXT NOT NULL,
    gender            TEXT NOT NULL CHECK (gender IN ('男', '女')),
    birth_date        TEXT,
    id_card           TEXT UNIQUE,
    phone             TEXT,
    address           TEXT,
    patient_type      TEXT NOT NULL DEFAULT '自费'
                      CHECK (patient_type IN ('自费', '医保', '新农合')),
    insurance_no      TEXT,
    created_at        TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- ------------------------------------------------------------
-- 科室
-- ------------------------------------------------------------
CREATE TABLE department (
    dept_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    dept_code TEXT NOT NULL UNIQUE,
    dept_name TEXT NOT NULL,
    dept_type TEXT NOT NULL DEFAULT '门诊' CHECK (dept_type IN ('门诊', '急诊')),
    location  TEXT,
    status    TEXT NOT NULL DEFAULT '启用' CHECK (status IN ('启用', '停用'))
);

-- ------------------------------------------------------------
-- 医生
-- ------------------------------------------------------------
CREATE TABLE doctor (
    doctor_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    doctor_code TEXT NOT NULL UNIQUE,
    doctor_name TEXT NOT NULL,
    dept_id     INTEGER NOT NULL REFERENCES department (dept_id),
    title       TEXT,
    gender      TEXT CHECK (gender IN ('男', '女')),
    status      TEXT NOT NULL DEFAULT '在岗' CHECK (status IN ('在岗', '离岗'))
);

-- ------------------------------------------------------------
-- 挂号号别（普通 / 专家 / 急诊 / 专病）及价格
-- ------------------------------------------------------------
CREATE TABLE registration_level (
    level_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    level_code    TEXT NOT NULL UNIQUE,
    level_name    TEXT NOT NULL,
    reg_fee       REAL NOT NULL DEFAULT 0,
    diagnosis_fee REAL NOT NULL DEFAULT 0
);

-- ------------------------------------------------------------
-- 医生排班（号源）
-- ------------------------------------------------------------
CREATE TABLE doctor_schedule (
    schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
    doctor_id   INTEGER NOT NULL REFERENCES doctor (doctor_id),
    dept_id     INTEGER NOT NULL REFERENCES department (dept_id),
    work_date   TEXT NOT NULL,
    time_period TEXT NOT NULL CHECK (time_period IN ('上午', '下午', '夜班')),
    level_id    INTEGER NOT NULL REFERENCES registration_level (level_id),
    total_quota INTEGER NOT NULL DEFAULT 0,
    used_quota  INTEGER NOT NULL DEFAULT 0,
    status      TEXT NOT NULL DEFAULT '正常' CHECK (status IN ('正常', '停诊')),
    UNIQUE (doctor_id, work_date, time_period)
);

-- ------------------------------------------------------------
-- 挂号记录
-- ------------------------------------------------------------
CREATE TABLE registration (
    reg_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    reg_no      TEXT NOT NULL UNIQUE,
    patient_id  INTEGER NOT NULL REFERENCES patient (patient_id),
    dept_id     INTEGER NOT NULL REFERENCES department (dept_id),
    doctor_id   INTEGER NOT NULL REFERENCES doctor (doctor_id),
    schedule_id INTEGER NOT NULL REFERENCES doctor_schedule (schedule_id),
    level_id    INTEGER NOT NULL REFERENCES registration_level (level_id),
    reg_time    TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    reg_type    TEXT NOT NULL DEFAULT '现场' CHECK (reg_type IN ('现场', '预约')),
    queue_no    INTEGER NOT NULL,
    status      TEXT NOT NULL DEFAULT '已挂号'
                CHECK (status IN ('已挂号', '已就诊', '已退号')),
    fee         REAL NOT NULL DEFAULT 0,
    operator_id INTEGER REFERENCES sys_user (user_id)
);

-- ------------------------------------------------------------
-- 收费记录（与挂号单一对一）
-- ------------------------------------------------------------
CREATE TABLE payment (
    pay_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    reg_id      INTEGER NOT NULL UNIQUE REFERENCES registration (reg_id),
    amount      REAL NOT NULL,
    pay_type    TEXT NOT NULL CHECK (pay_type IN ('现金', '医保', '微信', '支付宝')),
    pay_time    TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    status      TEXT NOT NULL DEFAULT '已支付' CHECK (status IN ('已支付', '已退费')),
    operator_id INTEGER REFERENCES sys_user (user_id)
);

-- ------------------------------------------------------------
-- 操作日志
-- ------------------------------------------------------------
CREATE TABLE operation_log (
    log_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER REFERENCES sys_user (user_id),
    action     TEXT NOT NULL,
    target     TEXT,
    detail     TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- 常用查询索引
CREATE INDEX idx_doctor_dept        ON doctor (dept_id);
CREATE INDEX idx_schedule_date      ON doctor_schedule (work_date, dept_id);
CREATE INDEX idx_reg_time           ON registration (reg_time);
CREATE INDEX idx_reg_patient        ON registration (patient_id);
CREATE INDEX idx_reg_status         ON registration (status);
