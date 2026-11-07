"""002 为药品表追加医保类别字段（实验六迁移练习）。"""
VERSION = 2
NAME = "drug_insurance_category"


def up(conn):
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(drug)")}
    if "insurance_category" not in cols:
        conn.execute(
            "ALTER TABLE drug ADD COLUMN insurance_category TEXT NOT NULL DEFAULT '甲类'"
        )
