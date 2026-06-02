import streamlit as st
import pandas as pd
from db_functions import (
    connect_to_db,
    get_basic_info,
    get_additional_tables,  # Fixed spelling matching db_functions
    get_categories,
    get_suppliers,
    add_new_manual_id, 
    get_all_products, 
    get_product_history, 
    place_reorder,
    get_pending_reorders,
    mark_reorder_as_received
)

# 1. Sidebar Setup
st.sidebar.title("Inventory Management Dashboard")
option = st.sidebar.radio("Select Option:", ["Basic Information", "Operational Tasks"])

# 2. Main Space Header
st.title("Inventory and Supply Chain Dashboard")

# 3. Secure Connection Lifecycle (Safely handled inside a try/finally block)
db = connect_to_db()
cursor = db.cursor(dictionary=True)

try:
    # --------------------- BASIC INFORMATION PAGE ---------------------
    if option == "Basic Information":
        st.header("Basic Metrics")

        # Get basic information from DB
        basic_info = get_basic_info(cursor)
        keys = list(basic_info.keys())

        # Render first row of metrics safely
        cols1 = st.columns(3)
        for i in range(min(3, len(keys))):
            cols1[i].metric(label=keys[i], value=basic_info[keys[i]])

        # Render second row of metrics safely
        if len(keys) > 3:
            cols2 = st.columns(3)
            for i in range(3, min(6, len(keys))):
                cols2[i-3].metric(label=keys[i], value=basic_info[keys[i]])

        st.divider()

        # Fetch and display detailed tables
        tables = get_additional_tables(cursor)
        for labels, data in tables.items():
            st.header(labels)
            df = pd.DataFrame(data)
            st.dataframe(df, use_container_width=True)
            st.divider()

    # --------------------- OPERATIONAL TASKS PAGE ---------------------
    elif option == "Operational Tasks":
        st.header("Operational Tasks")
        selected_task = st.selectbox("Choose a Task", ["Add New Product", "Product History", "Place Reorder", "Receive Reorder"])
        
        # Task A: Add New Product
        if selected_task == "Add New Product":
            st.subheader("Add New Product")
            categories = get_categories(cursor)
            suppliers = get_suppliers(cursor)

            with st.form("Add_Product_Form", clear_on_submit=True):
                product_name = st.text_input("Product Name")
                product_category = st.selectbox("Category", categories)
                product_price = st.number_input("Price", min_value=0.00, format="%.2f")
                product_stock = st.number_input("Stock Quantity", min_value=0, step=1)
                product_level = st.number_input("Reorder Level", min_value=0, step=1)

                supplier_ids = [s["supplier_id"] for s in suppliers]
                supplier_names = [s["supplier_name"] for s in suppliers]

                supplier_id = st.selectbox(
                    "Supplier",
                    options=supplier_ids,
                    format_func=lambda x: supplier_names[supplier_ids.index(x)] if x in supplier_ids else ""
                )

                submitted = st.form_submit_button("Add Product")

                if submitted:
                    if not product_name.strip():
                        st.error("Please Enter the Product Name.")
                    else:
                        try:
                            add_new_manual_id(
                                cursor,
                                db,
                                product_name,
                                product_category,
                                product_price,
                                product_stock,
                                product_level,
                                supplier_id
                            )
                            st.success(f"Product '{product_name}' added successfully!")
                        except Exception as e:
                            st.error(f"Error adding the Product: {e}")

        # Task B: Product History (Fixed indentation alignment to clean up branch scopes)
        elif selected_task == "Product History":
            st.subheader("Product Inventory History")

            products = get_all_products(cursor)
            product_names = [p['product_name'] for p in products]
            product_ids = [p['product_id'] for p in products]

            selected_product_name = st.selectbox("Select a Product", options=product_names)

            if selected_product_name:
                selected_product_id = product_ids[product_names.index(selected_product_name)]
                history_data = get_product_history(cursor, selected_product_id)

                if history_data:
                    df = pd.DataFrame(history_data)
                    st.dataframe(df, use_container_width=True)
                else:
                    st.info("No history found for the selected product.")

        # Task C: Place Reorder
        elif selected_task == "Place Reorder":
            st.subheader("Place a Reorder")

            products = get_all_products(cursor)
            product_names = [p['product_name'] for p in products]
            product_ids = [p['product_id'] for p in products]

            selected_product_name = st.selectbox("Select a Product", options=product_names)
            reorder_qty = st.number_input("Reorder Quantity", min_value=1, step=1)

            if st.button("Place Reorder"):
                if not selected_product_name:
                    st.error("Please select a product.")
                else:
                    selected_product_id = product_ids[product_names.index(selected_product_name)]
                    try:
                        place_reorder(cursor, db, selected_product_id, reorder_qty)
                        st.success(f"Order placed for {selected_product_name} (Quantity: {reorder_qty})")
                    except Exception as e:
                        st.error(f"Error placing reorder: {e}")

        # Task D: Receive Reorder
        elif selected_task == "Receive Reorder":
            st.subheader("Mark Reorder as Received")
            
            pending_reorders = get_pending_reorders(cursor)
            if not pending_reorders:
                st.info("No pending orders to receive.")
            else:
                reorder_ids = [r['reorder_id'] for r in pending_reorders]
                reorder_labels = [f"ID {r['reorder_id']} - {r['product_name']}" for r in pending_reorders]

                selected_label = st.selectbox("Select Reorder to Mark As Received", options=reorder_labels)

                if selected_label:
                    selected_reorder_id = reorder_ids[reorder_labels.index(selected_label)]

                    if st.button("Mark as Received"):
                        try:
                            mark_reorder_as_received(cursor, db, selected_reorder_id)
                            st.success(f"Reorder ID {selected_reorder_id} marked as received successfully!")
                            st.rerun()  # Forces interface state synchronization immediately
                        except Exception as e:
                            st.error(f"Error updating order state: {e}")

finally:
    # 4. Guarantee Clean Connection Closures to MySQL Instance
    cursor.close()
    db.close()