import mysql.connector
import os
import numpy as np
from dotenv import load_dotenv

load_dotenv()

# ──────────────────────────────────────────────
# CONNECTION
# ──────────────────────────────────────────────

def connect_to_db():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "project_back"),
        port=int(os.getenv("DB_PORT", 3306))
    )


# ──────────────────────────────────────────────
# BASIC INFO  (6 KPI cards)
# ──────────────────────────────────────────────

def get_basic_info(cursor):
    queries = {
        "Total Suppliers": "SELECT COUNT(*) AS v FROM suppliers",
        "Total Products":  "SELECT COUNT(DISTINCT product_name) AS v FROM products",
        "Total Categories": "SELECT COUNT(DISTINCT category) AS v FROM products",

        "Sale Value - Last 3 Months": """
            SELECT ROUND(SUM(ABS(se.change_quantity) * p.price), 2) AS v
            FROM stock_entries se
            JOIN products p ON se.product_id = p.product_id
            WHERE se.change_type = 'Sale'
              AND se.entry_date >= (
                  SELECT DATE_SUB(MAX(entry_date), INTERVAL 3 MONTH)
                  FROM stock_entries)
        """,

        "Restock Value - Last 3 Months": """
            SELECT ROUND(SUM(se.change_quantity * p.price), 2) AS v
            FROM stock_entries se
            JOIN products p ON se.product_id = p.product_id
            WHERE se.change_type = 'Restock'
              AND se.entry_date >= (
                  SELECT DATE_SUB(MAX(entry_date), INTERVAL 3 MONTH)
                  FROM stock_entries)
        """,

        "Needs Reorder (No Pending)": """
            SELECT COUNT(*) AS v
            FROM (
                SELECT DISTINCT product_name
                FROM products
                WHERE stock_quantity < reorder_level
                  AND product_name NOT IN (
                      SELECT DISTINCT p2.product_name
                      FROM reorders r
                      JOIN products p2 ON r.product_id = p2.product_id
                      WHERE r.status = 'Ordered'
                  )
            ) AS t
        """
    }

    result = {}
    for label, query in queries.items():
        cursor.execute(query)
        row = cursor.fetchone()
        result[label] = list(row.values())[0] if row else 0
    return result


# ──────────────────────────────────────────────
# SUMMARY TABLES
# ──────────────────────────────────────────────

def get_additional_tables(cursor):
    queries = {
        # Suppliers: GROUP BY with MAX() — safe for ONLY_FULL_GROUP_BY
        "Supplier Contact Details": """
            SELECT
                supplier_name,
                MAX(contact_name) AS contact_name,
                MAX(email)        AS email,
                MAX(phone)        AS phone
            FROM suppliers
            GROUP BY supplier_name
            ORDER BY supplier_name
        """,

        # Products with Supplier & Stock:
        # Use a derived table that picks one row per product_name first,
        # then join — this is the only reliable way when product_id itself
        # has duplicates in the products table.
        "Products with Supplier & Stock": """
            SELECT
                d.product_name,
                s.supplier_name,
                d.stock_quantity,
                d.reorder_level
            FROM (
                SELECT
                    product_name,
                    MAX(supplier_id)    AS supplier_id,
                    MAX(stock_quantity) AS stock_quantity,
                    MAX(reorder_level)  AS reorder_level
                FROM products
                GROUP BY product_name
            ) AS d
            JOIN (
                SELECT supplier_id, MAX(supplier_name) AS supplier_name
                FROM suppliers
                GROUP BY supplier_id
            ) AS s ON d.supplier_id = s.supplier_id
            ORDER BY d.product_name
        """,

        # Products Needing Reorder: same derived-table approach
        "Products Needing Reorder": """
            SELECT
                product_name,
                MAX(stock_quantity) AS stock_quantity,
                MAX(reorder_level)  AS reorder_level
            FROM products
            WHERE stock_quantity <= reorder_level
            GROUP BY product_name
            ORDER BY (MAX(reorder_level) - MAX(stock_quantity)) DESC
        """
    }

    tables = {}
    for label, query in queries.items():
        cursor.execute(query)
        rows = cursor.fetchall()
        # Python-level deduplication — guaranteed to work regardless of DB duplicates
        seen = set()
        deduped = []
        for row in rows:
            key = list(row.values())[0]  # first column (product_name or supplier_name)
            if key not in seen:
                seen.add(key)
                deduped.append(row)
        tables[label] = deduped
    return tables


# ──────────────────────────────────────────────
# HELPERS FOR FORMS
# ──────────────────────────────────────────────

def get_categories(cursor):
    cursor.execute("SELECT DISTINCT category FROM products ORDER BY category ASC")
    return [row["category"] for row in cursor.fetchall()]


def get_suppliers(cursor):
    cursor.execute("""
        SELECT supplier_id, MAX(supplier_name) AS supplier_name
        FROM suppliers
        GROUP BY supplier_id
        ORDER BY supplier_name ASC
    """)
    return cursor.fetchall()


def get_all_products(cursor):
    cursor.execute("""
        SELECT MAX(product_id) AS product_id, product_name
        FROM products
        GROUP BY product_name
        ORDER BY product_name
    """)
    return cursor.fetchall()


# ──────────────────────────────────────────────
# OPERATIONAL TASKS
# ──────────────────────────────────────────────

def add_new_manual_id(cursor, db, p_name, p_category, p_price, p_stock, p_reorder, p_supplier):
    cursor.execute(
        "CALL AddNewProductManualID(%s, %s, %s, %s, %s, %s)",
        (p_name, p_category, p_price, p_stock, p_reorder, p_supplier)
    )
    db.commit()


def get_product_history(cursor, product_id):
    cursor.execute(
        "SELECT * FROM product_inventory_history WHERE product_id = %s ORDER BY record_date DESC",
        (product_id,)
    )
    return cursor.fetchall()


def place_reorder(cursor, db, product_id, reorder_quantity):
    cursor.execute("""
        INSERT INTO reorders (reorder_id, product_id, reorder_quantity, reorder_date, status)
        SELECT COALESCE(MAX(reorder_id), 0) + 1, %s, %s, CURDATE(), 'Ordered'
        FROM reorders
    """, (product_id, reorder_quantity))
    db.commit()


def get_pending_reorders(cursor):
    cursor.execute("""
        SELECT r.reorder_id, p.product_name
        FROM reorders r
        JOIN products p ON r.product_id = p.product_id
        WHERE r.status = 'Ordered'
        ORDER BY r.reorder_id
    """)
    return cursor.fetchall()


def mark_reorder_as_received(cursor, db, reorder_id):
    cursor.callproc("MarkReorderAsReceived", [reorder_id])
    db.commit()


# ──────────────────────────────────────────────
# ADVANCED ANALYTICS
# ──────────────────────────────────────────────

def get_abc_analysis(cursor):
    cursor.execute("""
        WITH DeduplicatedProducts AS (
            SELECT MIN(product_id) AS product_id, product_name
            FROM products
            GROUP BY product_name
        ),
        ProductRevenue AS (
            SELECT
                dp.product_id,
                dp.product_name,
                SUM(ABS(se.change_quantity) * p.price) AS revenue
            FROM stock_entries se
            JOIN DeduplicatedProducts dp ON se.product_id = dp.product_id
            JOIN products p ON p.product_id = dp.product_id
            WHERE se.change_type = 'Sale'
            GROUP BY dp.product_id, dp.product_name
        ),
        Ranked AS (
            SELECT
                product_name,
                revenue,
                SUM(revenue) OVER () AS total_revenue,
                SUM(revenue) OVER (ORDER BY revenue DESC) /
                    SUM(revenue) OVER () * 100 AS cum_pct
            FROM ProductRevenue
        )
        SELECT
            product_name,
            ROUND(revenue, 2) AS revenue,
            CASE
                WHEN cum_pct <= 80 THEN 'A – High Value'
                WHEN cum_pct <= 95 THEN 'B – Medium Value'
                ELSE 'C – Low Value'
            END AS abc_class
        FROM Ranked
        ORDER BY revenue DESC
    """)
    return cursor.fetchall()


def get_monthly_sales_trend(cursor):
    # GROUP BY and ORDER BY use full expression — alias not allowed in strict mode
    cursor.execute("""
        SELECT
            DATE_FORMAT(se.entry_date, '%Y-%m') AS month,
            ROUND(SUM(ABS(se.change_quantity) * p.price), 2) AS sales_value
        FROM stock_entries se
        JOIN products p ON se.product_id = p.product_id
        WHERE se.change_type = 'Sale'
        GROUP BY DATE_FORMAT(se.entry_date, '%Y-%m')
        ORDER BY DATE_FORMAT(se.entry_date, '%Y-%m')
    """)
    return cursor.fetchall()


def get_category_stock_summary(cursor):
    cursor.execute("""
        SELECT
            category,
            COUNT(DISTINCT product_name)  AS total_products,
            SUM(max_stock)                AS total_stock,
            SUM(needs_reorder)            AS below_reorder
        FROM (
            SELECT
                category,
                product_name,
                MAX(stock_quantity) AS max_stock,
                MAX(CASE WHEN stock_quantity <= reorder_level THEN 1 ELSE 0 END) AS needs_reorder
            FROM products
            GROUP BY category, product_name
        ) AS deduped
        GROUP BY category
        ORDER BY total_stock DESC
    """)
    return cursor.fetchall()


def get_advanced_product_insights(cursor, product_id):
    cursor.execute("""
        SELECT entry_date, SUM(ABS(change_quantity)) AS daily_sales
        FROM stock_entries
        WHERE product_id = %s AND change_type = 'Sale'
        GROUP BY entry_date
    """, (product_id,))
    sales_data = cursor.fetchall()

    cursor.execute(
        "SELECT product_name, stock_quantity, price FROM products WHERE product_id = %s LIMIT 1",
        (product_id,)
    )
    meta = cursor.fetchone()
    if not meta:
        return None

    name          = meta["product_name"]
    current_stock = float(meta["stock_quantity"])   # cast — DB may return string
    price         = float(meta["price"])

    if not sales_data:
        return {
            "product_name": name, "current_stock": current_stock,
            "avg_daily_demand": 0, "volatility": 0,
            "safety_stock": 0, "eoq": 0, "rop": 0,
            "status": "No sales history available for this product."
        }

    volumes          = [float(r["daily_sales"]) for r in sales_data]
    avg_daily_demand = np.mean(volumes)
    volatility       = np.std(volumes)
    lead_time        = 5

    safety_stock  = 1.65 * volatility * (lead_time ** 0.5)
    rop           = (avg_daily_demand * lead_time) + safety_stock
    annual_demand = avg_daily_demand * 365
    order_cost    = 50.0
    holding_cost  = price * 0.20
    eoq           = ((2 * annual_demand * order_cost) / holding_cost) ** 0.5 if holding_cost > 0 else 0

    if current_stock <= safety_stock:
        status = "CRITICAL: Stock has breached the safety buffer. Immediate reorder required."
    elif current_stock <= rop:
        status = "WARNING: Stock is below Reorder Point. Place a replenishment order now."
    else:
        status = "HEALTHY: Inventory levels are well within safe boundaries."

    return {
        "product_name":     name,
        "current_stock":    current_stock,
        "avg_daily_demand": round(avg_daily_demand, 2),
        "volatility":       round(volatility, 2),
        "safety_stock":     round(safety_stock, 1),
        "eoq":              int(round(eoq)),
        "rop":              round(rop, 1),
        "status":           status
    }