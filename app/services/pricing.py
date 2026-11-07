"""划价服务：金额一律由后端按药品档案单价计算，不信任前端。"""
from decimal import Decimal, ROUND_HALF_UP


def to_money(value) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def item_amount(unit_price, quantity) -> float:
    if quantity <= 0:
        raise ValueError("药品数量必须大于 0")
    if float(unit_price) < 0:
        raise ValueError("药品单价不能为负数")
    return to_money(Decimal(str(unit_price)) * Decimal(int(quantity)))


def prescription_total(items) -> float:
    total = Decimal("0")
    for item in items:
        total += Decimal(str(item_amount(item["unit_price"], item["quantity"])))
    return float(total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
