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

        "Sale Value – Last 3 Months": """
            SELECT ROUND(SUM(ABS(se.change_quantity) * p.price), 2) AS v
            FROM stock_entries se
            JOIN products p ON se.product_id = p.product_id
            WHERE se.change_type = 'Sale'
              AND se.entry_date >= (
                  SELECT DATE_SUB(MAX(entry_date), INTERVAL 3 MONTH)
                  FROM stock_entries)
        """,

        "Restock Value – Last 3 Months": """
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
            FROM products p
            WHERE p.stock_quantity < p.reorder_level
              AND p.product_id NOT IN (
                  SELECT DISTINCT product_id FROM reorders WHERE status = 'Ordered')
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
        "Supplier Contact Details": """
            SELECT DISTINCT supplier_name, contact_name, email, phone
            FROM suppliers
            ORDER BY supplier_name
        """,

        # Use GROUP BY product_id (the true unique key) to eliminate
        # duplicate product_name rows that exist in the products table
        "Products with Supplier & Stock": """
            SELECT p.product_name, s.supplier_name,
                   p.stock_quantity, p.reorder_level
            FROM products p
            JOIN suppliers s ON p.supplier_id = s.supplier_id
            WHERE p.product_id = (
                SELECT MIN(p2.product_id)
                FROM products p2
                WHERE p2.product_name = p.product_name
            )
            ORDER BY p.product_name
        """,

        "Products Needing Reorder": """
            SELECT product_name, stock_quantity, reorder_level
            FROM products
            WHERE stock_quantity <= reorder_level
              AND product_id = (
                  SELECT MIN(p2.product_id)
                  FROM products p2
                  WHERE p2.product_name = products.product_name
              )
            ORDER BY (reorder_level - stock_quantity) DESC
        """
    }
    tables = {}
    for label, query in queries.items():
        cursor.execute(query)
        tables[label] = cursor.fetchall()
    return tables


# ──────────────────────────────────────────────
# HELPERS FOR FORMS
# ──────────────────────────────────────────────

def get_categories(cursor):
    cursor.execute("SELECT DISTINCT category FROM products ORDER BY category ASC")
    return [row["category"] for row in cursor.fetchall()]


def get_suppliers(cursor):
    cursor.execute("SELECT supplier_id, supplier_name FROM suppliers ORDER BY supplier_name ASC")
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
            -- Pick only the canonical (lowest) product_id per name
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
    cursor.execute("""
        SELECT
            DATE_FORMAT(se.entry_date, '%Y-%m') AS month,
            ROUND(SUM(ABS(se.change_quantity) * p.price), 2) AS sales_value
        FROM stock_entries se
        JOIN products p ON se.product_id = p.product_id
        WHERE se.change_type = 'Sale'
        GROUP BY month
        ORDER BY month
    """)
    return cursor.fetchall()


def get_category_stock_summary(cursor):
    cursor.execute("""
        SELECT category,
               COUNT(*)            AS total_products,
               SUM(stock_quantity)  AS total_stock,
               SUM(CASE WHEN stock_quantity <= reorder_level THEN 1 ELSE 0 END) AS below_reorder
        FROM products
        WHERE product_id = (
            SELECT MIN(p2.product_id)
            FROM products p2
            WHERE p2.product_name = products.product_name
        )
        GROUP BY category
        ORDER BY total_stock DESC
    """)
    return cursor.fetchall()


def get_advanced_product_insights(cursor, product_id):
    # Daily sales volumes
    cursor.execute("""
        SELECT entry_date, SUM(ABS(change_quantity)) AS daily_sales
        FROM stock_entries
        WHERE product_id = %s AND change_type = 'Sale'
        GROUP BY entry_date
    """, (product_id,))
    sales_data = cursor.fetchall()

    # Product metadata
    cursor.execute(
        "SELECT product_name, stock_quantity, price FROM products WHERE product_id = %s",
        (product_id,)
    )
    meta = cursor.fetchone()
    if not meta:
        return None

    name          = meta["product_name"]
    current_stock = meta["stock_quantity"]
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
    lead_time        = 5          # days

    safety_stock      = 1.65 * volatility * (lead_time ** 0.5)
    rop               = (avg_daily_demand * lead_time) + safety_stock
    annual_demand     = avg_daily_demand * 365
    order_cost        = 50.0
    holding_cost      = price * 0.20
    eoq               = ((2 * annual_demand * order_cost) / holding_cost) ** 0.5 if holding_cost > 0 else 0

    if current_stock <= safety_stock:
        status = "CRITICAL: Stock has breached the safety buffer. Immediate reorder required."
    elif current_stock <= rop:
        status = "WARNING: Stock is below Reorder Point. Place a replenishment order now."
    else:
        status = "HEALTHY: Inventory levels are well within safe boundaries."

    return {
        "product_name":    name,
        "current_stock":   current_stock,
        "avg_daily_demand": round(avg_daily_demand, 2),
        "volatility":      round(volatility, 2),
        "safety_stock":    round(safety_stock, 1),
        "eoq":             int(round(eoq)),
        "rop":             round(rop, 1),
        "status":          status
    }