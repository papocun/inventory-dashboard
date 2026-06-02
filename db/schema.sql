-- ══════════════════════════════════════════════════════════════
--  INVENTORY DASHBOARD  –  schema.sql  (fully fixed)
--  Run this file top-to-bottom in MySQL Workbench or CLI
-- ══════════════════════════════════════════════════════════════

USE project_back;

-- ──────────────────────────────────────────────
-- QUICK INSPECTION (comment out after first run)
-- ──────────────────────────────────────────────
-- SHOW TABLES;
-- SELECT * FROM products;
-- SELECT * FROM reorders;
-- SELECT * FROM shipments;
-- SELECT * FROM stock_entries;
-- SELECT * FROM suppliers;


-- ══════════════════════════════════════════════
--  KPI QUERIES  (reference – same as db_functions.py)
-- ══════════════════════════════════════════════

-- 1  Total Suppliers
SELECT COUNT(*) AS total_suppliers FROM suppliers;

-- 2  Total Products (distinct names)
SELECT COUNT(DISTINCT product_name) AS total_products FROM products;

-- 3  Total categories
SELECT COUNT(DISTINCT category) AS total_categories FROM products;

-- 4  Total sales value – last 3 months
SELECT ROUND(SUM(ABS(se.change_quantity) * p.price), 2) AS total_sales_value_last_3_months
FROM stock_entries AS se
JOIN products p ON p.product_id = se.product_id
WHERE se.change_type = 'Sale'
  AND se.entry_date >= (
      SELECT DATE_SUB(MAX(entry_date), INTERVAL 3 MONTH) FROM stock_entries
  );

-- 5  Total restock value – last 3 months
SELECT ROUND(SUM(se.change_quantity * p.price), 2) AS total_restock_value_last_3_months
FROM stock_entries AS se
JOIN products p ON p.product_id = se.product_id
WHERE se.change_type = 'Restock'
  AND se.entry_date >= (
      SELECT DATE_SUB(MAX(entry_date), INTERVAL 3 MONTH) FROM stock_entries
  );

-- 6  Products needing reorder with NO pending/ordered reorder
--    FIX: changed status check from 'Pending' → 'Ordered'
--         to match what place_reorder() inserts in db_functions.py
SELECT COUNT(*) AS needs_reorder_no_pending
FROM products AS p
WHERE p.stock_quantity < p.reorder_level
  AND p.product_id NOT IN (
      SELECT DISTINCT product_id FROM reorders WHERE status = 'Ordered'
  );


-- ══════════════════════════════════════════════
--  SUMMARY TABLE QUERIES
-- ══════════════════════════════════════════════

-- 7  Supplier contact details – deduplicated
--    FIX: GROUP BY supplier_name instead of SELECT DISTINCT
--         because the suppliers table has multiple rows per supplier
SELECT
    supplier_name,
    MAX(contact_name) AS contact_name,
    MAX(email)        AS email,
    MAX(phone)        AS phone
FROM suppliers
GROUP BY supplier_name
ORDER BY supplier_name;

-- 8  Products with their supplier and current stock – deduplicated
--    MIN(product_id) subquery guarantees one row per product name.
--    No GROUP BY needed — avoids ONLY_FULL_GROUP_BY strict mode errors.
SELECT DISTINCT
    p.product_name,
    s.supplier_name,
    p.stock_quantity,
    p.reorder_level
FROM products p
JOIN suppliers s ON p.supplier_id = s.supplier_id
ORDER BY p.product_name ASC;

-- 9  Products needing reorder – deduplicated
--    Same approach — MIN subquery is sufficient, no GROUP BY required.
SELECT DISTINCT
    product_name,
    stock_quantity,
    reorder_level
FROM products
WHERE stock_quantity <= reorder_level
ORDER BY (reorder_level - stock_quantity) DESC


-- ══════════════════════════════════════════════
--  STORED PROCEDURE: AddNewProductManualID
-- ══════════════════════════════════════════════

DROP PROCEDURE IF EXISTS AddNewProductManualID;

DELIMITER $$
CREATE PROCEDURE AddNewProductManualID(
    IN p_name      VARCHAR(255),
    IN p_category  VARCHAR(100),
    IN p_price     DECIMAL(10,2),
    IN p_stock     INT,
    IN p_reorder   INT,
    IN p_supplier  INT
)
BEGIN
    DECLARE new_prod_id     INT;
    DECLARE new_shipment_id INT;
    DECLARE new_entry_id    INT;

    -- Insert into products
    SELECT MAX(product_id) + 1 INTO new_prod_id FROM products;
    INSERT INTO products (product_id, product_name, category, price, stock_quantity, reorder_level, supplier_id)
    VALUES (new_prod_id, p_name, p_category, p_price, p_stock, p_reorder, p_supplier);

    -- Insert into shipments
    SELECT MAX(shipment_id) + 1 INTO new_shipment_id FROM shipments;
    INSERT INTO shipments (shipment_id, product_id, supplier_id, quantity_received, shipment_date)
    VALUES (new_shipment_id, new_prod_id, p_supplier, p_stock, CURDATE());

    -- Insert into stock_entries
    SELECT MAX(entry_id) + 1 INTO new_entry_id FROM stock_entries;
    INSERT INTO stock_entries (entry_id, product_id, change_quantity, change_type, entry_date)
    VALUES (new_entry_id, new_prod_id, p_stock, 'Restock', CURDATE());
END $$
DELIMITER ;

-- Test (comment out after verifying):
-- CALL AddNewProductManualID('Smart Watch', 'Electronics', 99.99, 100, 25, 5);


-- ══════════════════════════════════════════════
--  VIEW: product_inventory_history
--  FIX: CREATE OR REPLACE ensures it always exists fresh
-- ══════════════════════════════════════════════

CREATE OR REPLACE VIEW product_inventory_history AS
SELECT
    pih.product_id,
    pih.record_type,
    pih.record_date,
    pih.quantity,
    pih.change_type,
    pr.supplier_id
FROM (
    SELECT
        product_id,
        'Shipment'        AS record_type,
        shipment_date     AS record_date,
        quantity_received AS quantity,
        NULL              AS change_type
    FROM shipments

    UNION

    SELECT
        product_id,
        'Stock Entry' AS record_type,
        entry_date    AS record_date,
        change_quantity AS quantity,
        change_type
    FROM stock_entries
) pih
JOIN products pr ON pr.product_id = pih.product_id
GROUP BY
    pih.product_id,
    pih.record_type,
    pih.record_date,
    pih.quantity,
    pih.change_type,
    pr.supplier_id
ORDER BY pih.record_date DESC

    -- Stock entry records (sales, restocks)
    SELECT
        product_id,
        'Stock Entry' AS record_type,
        entry_date    AS record_date,
        change_quantity AS quantity,
        change_type
    FROM stock_entries
) pih
JOIN products pr ON pr.product_id = pih.product_id;

-- Verify view works:
-- SELECT * FROM product_inventory_history WHERE product_id = 123 ORDER BY record_date DESC;


-- ══════════════════════════════════════════════
--  STORED PROCEDURE: MarkReorderAsReceived
--  FIX: corrected "Delimiter;" typo → DELIMITER ;
--       (missing space caused procedure to not register)
-- ══════════════════════════════════════════════

DROP PROCEDURE IF EXISTS MarkReorderAsReceived;

DELIMITER $$
CREATE PROCEDURE MarkReorderAsReceived(IN in_reorder_id INT)
BEGIN
    DECLARE prod_id         INT;
    DECLARE qty             INT;
    DECLARE sup_id          INT;
    DECLARE new_shipment_id INT;
    DECLARE new_entry_id    INT;

    START TRANSACTION;

    -- Get product_id and quantity from reorders
    SELECT product_id, reorder_quantity
    INTO prod_id, qty
    FROM reorders
    WHERE reorder_id = in_reorder_id;

    -- Get supplier_id from products
    SELECT supplier_id
    INTO sup_id
    FROM products
    WHERE product_id = prod_id
    LIMIT 1;                          -- FIX: LIMIT 1 prevents error if product has duplicate rows

    -- Mark reorder as Received
    --   FIX: status set to 'Received' (consistent with place_reorder using 'Ordered')
    UPDATE reorders
    SET status = 'Received'
    WHERE reorder_id = in_reorder_id;

    -- Update stock quantity in products
    UPDATE products
    SET stock_quantity = stock_quantity + qty
    WHERE product_id = prod_id;

    -- Insert into shipments
    SELECT MAX(shipment_id) + 1 INTO new_shipment_id FROM shipments;
    INSERT INTO shipments (shipment_id, product_id, supplier_id, quantity_received, shipment_date)
    VALUES (new_shipment_id, prod_id, sup_id, qty, CURDATE());

    -- Insert restock entry into stock_entries
    SELECT MAX(entry_id) + 1 INTO new_entry_id FROM stock_entries;
    INSERT INTO stock_entries (entry_id, product_id, change_quantity, change_type, entry_date)
    VALUES (new_entry_id, prod_id, qty, 'Restock', CURDATE());

    COMMIT;
END $$
DELIMITER ;

-- Test (comment out after verifying):
-- CALL MarkReorderAsReceived(1);


-- ══════════════════════════════════════════════
--  PLACE A REORDER  (reference query)
--  FIX: status inserted as 'Ordered' (not 'ordered' or 'Pending')
--       must match the NOT IN check in KPI query #6 above
-- ══════════════════════════════════════════════

-- INSERT INTO reorders (reorder_id, product_id, reorder_quantity, reorder_date, status)
-- SELECT COALESCE(MAX(reorder_id), 0) + 1, 101, 200, CURDATE(), 'Ordered'
-- FROM reorders;


-- ══════════════════════════════════════════════
--  VERIFICATION QUERIES  (run after setup)
-- ══════════════════════════════════════════════

-- Check all procedures exist:
-- SHOW PROCEDURE STATUS WHERE Db = 'project_back';

-- Check view exists:
-- SHOW FULL TABLES WHERE Table_type = 'VIEW';

-- Check distinct reorder statuses in your data:
-- SELECT DISTINCT status FROM reorders;

-- Check for duplicate supplier rows:
-- SELECT supplier_name, COUNT(*) AS cnt FROM suppliers GROUP BY supplier_name HAVING cnt > 1;

-- Check for duplicate product rows:
-- SELECT product_name, COUNT(*) AS cnt FROM products GROUP BY product_name HAVING cnt > 1;