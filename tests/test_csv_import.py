"""药品 CSV 导入测试：编码、校验、去重、错误报告。"""
import pytest

from app import db
from app.services import csv_import
from app.services.errors import BusinessError

HEADER = "药品编码,通用名,规格,单价,医保类别,库存数量,效期\n"


def test_import_valid_and_invalid_rows(client):
    content = HEADER
    content += "CSV001,测试药品A,10mg*10片,9.90,甲类,30,2028-01-01\n"
    content += "CSV002,测试药品B,5mg*20片,12.50,乙类,20,2028-02-01\n"
    content += ",,10mg*10片,8.00,甲类,10,\n"
    content += "CSV003,错误单价,10mg*10片,abc,甲类,10,\n"
    content += "CSV004,错误数量,10mg*10片,8.00,甲类,-2,\n"
    raw = content.encode("utf-8-sig")
    result = csv_import.import_drugs(raw)
    assert result["success"] == 2
    assert result["failed"] == 3
    assert all("row" in error and "reason" in error for error in result["errors"])
    assert db.query_one("SELECT COUNT(*) AS c FROM drug WHERE drug_code IN ('CSV001','CSV002')")["c"] == 2


def test_import_gbk_encoding(client):
    content = HEADER + "CSV010,国标编码药品,10mg*10片,7.70,甲类,15,\n"
    result = csv_import.import_drugs(content.encode("gbk"))
    assert result["success"] == 1


def test_import_deduplicates_existing_and_in_file(client):
    db.execute(
        "INSERT INTO drug (drug_code, generic_name, spec, unit, price) "
        "VALUES ('DUP001','重复药品','10mg*10片','盒',5.00)"
    )
    content = HEADER
    content += "DUP001,重复药品,10mg*10片,5.00,甲类,10,\n"
    content += "CSV020,文件内重复,10mg*10片,5.00,甲类,10,\n"
    content += "CSV020,文件内重复,10mg*10片,5.00,甲类,10,\n"
    result = csv_import.import_drugs(content.encode("utf-8-sig"))
    assert result["success"] == 1
    assert result["failed"] == 2
    assert len([e for e in result["errors"] if "重复" in e["reason"]]) == 2


def test_import_missing_headers(client):
    with pytest.raises(BusinessError):
        csv_import.import_drugs("通用名,单价\n药,1\n".encode("utf-8"))


def test_import_empty_file(client):
    with pytest.raises(BusinessError):
        csv_import.import_drugs(b"")
