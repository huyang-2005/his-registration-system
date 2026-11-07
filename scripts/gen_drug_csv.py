"""生成 100 条药品导入演示 CSV（含 5 条故意错误行，用于展示错误报告）。

用法：python scripts/gen_drug_csv.py
输出：static/drug_import_demo.csv（UTF-8 BOM，可直接被系统识别）
"""
import csv
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT = os.path.join(BASE_DIR, "static", "drug_import_demo.csv")

HEADERS = ["药品编码", "通用名", "商品名", "规格", "剂型", "单位", "单价", "医保类别", "库存数量", "效期"]
FORMS = ["片剂", "胶囊", "颗粒剂", "口服液", "软膏剂"]
CATEGORIES = ["甲类", "乙类", "丙类", "自费"]


def main():
    rows = []
    for i in range(1, 101):
        rows.append(
            [
                "CSV%04d" % i,
                "演示药品%03d" % i,
                "演示商品名%03d" % i,
                "%dmg*%d片" % (5 + i % 20, 10 + i % 20),
                FORMS[i % len(FORMS)],
                "盒",
                "%.2f" % (5 + i * 0.8),
                CATEGORIES[i % len(CATEGORIES)],
                str(20 + i),
                "2028-%02d-28" % (1 + i % 12),
            ]
        )
    # 故意错误行：验证逐行校验与错误报告
    rows.append(["CSV0101", "", "缺通用名", "10mg*10片", "片剂", "盒", "9.90", "甲类", "30", "2028-06-30"])
    rows.append(["CSV0102", "错误单价药品", "测试", "10mg*10片", "片剂", "盒", "abc", "甲类", "30", "2028-06-30"])
    rows.append(["CSV0103", "错误库存药品", "测试", "10mg*10片", "片剂", "盒", "8.80", "甲类", "-5", "2028-06-30"])
    rows.append(["CSV0104", "错误医保类别", "测试", "10mg*10片", "片剂", "盒", "8.80", "未知", "30", "2028-06-30"])
    rows.append(["CSV0001", "文件内重复药品", "测试", "5mg*10片", "片剂", "盒", "8.80", "甲类", "30", "2028-06-30"])

    with open(OUTPUT, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(HEADERS)
        writer.writerows(rows)
    print("已生成：%s（合法 %d 行，错误 %d 行）" % (OUTPUT, 100, len(rows) - 100))


if __name__ == "__main__":
    sys.exit(main())
