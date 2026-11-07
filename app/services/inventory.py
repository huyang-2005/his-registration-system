"""库存服务：按效期先进先出扣减，必须在外层事务中调用。"""
from app.services.errors import BusinessError


def available_stock(conn, drug_id: int) -> int:
    row = conn.execute(
        "SELECT COALESCE(SUM(quantity), 0) AS q FROM drug_inventory WHERE drug_id = ?",
        (drug_id,),
    ).fetchone()
    return int(row["q"])


def deduct_stock(conn, drug_id: int, quantity: int, drug_name: str = ""):
    """按效期升序扣减；不足则抛 400，调用方负责回滚。"""
    if quantity <= 0:
        raise BusinessError("扣减数量必须大于 0", 400)

    available = available_stock(conn, drug_id)
    if available < quantity:
        raise BusinessError(
            "药品「%s」库存不足：需要 %d，可用 %d" % (drug_name or drug_id, quantity, available),
            400,
        )

    rows = conn.execute(
        "SELECT inventory_id, batch_no, quantity, expiry_date FROM drug_inventory "
        "WHERE drug_id = ? AND quantity > 0 "
        "ORDER BY CASE WHEN expiry_date IS NULL OR expiry_date = '' THEN 1 ELSE 0 END, "
        "         expiry_date, inventory_id",
        (drug_id,),
    ).fetchall()

    remain = quantity
    allocations = []
    for row in rows:
        if remain <= 0:
            break
        take = min(remain, int(row["quantity"]))
        conn.execute(
            "UPDATE drug_inventory SET quantity = quantity - ? WHERE inventory_id = ?",
            (take, row["inventory_id"]),
        )
        allocations.append({"batch_no": row["batch_no"], "quantity": take})
        remain -= take
    return allocations
