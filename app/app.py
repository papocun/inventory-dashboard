import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from db_functions import (
    connect_to_db,
    get_basic_info,
    get_additional_tables,
    get_categories,
    get_suppliers,
    add_new_manual_id,
    get_all_products,
    get_product_history,
    place_reorder,
    get_pending_reorders,
    mark_reorder_as_received,
    get_abc_analysis,
    get_monthly_sales_trend,
    get_category_stock_summary,
    get_advanced_product_insights,
)

# ──────────────────────────────────────────────
# PAGE CONFIG
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="Inventory Dashboard",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────
# DARK THEME CSS
# ──────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

    html, body, [class*="css"], .stApp {
        font-family: 'Space Grotesk', sans-serif !important;
        background-color: #0d1117 !important;
        color: #e6edf3 !important;
    }
    .main .block-container {
        background-color: #0d1117 !important;
        padding-top: 2rem;
    }

    /* ── Sidebar ── */
    [data-testid="stSidebar"] {
        background: #161b22 !important;
        border-right: 1px solid #30363d !important;
    }
    [data-testid="stSidebar"] * { color: #c9d1d9 !important; }
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 { color: #58a6ff !important; }
    [data-testid="stSidebar"] .stRadio label {
        padding: 8px 14px !important;
        border-radius: 8px !important;
        border: 1px solid transparent !important;
        transition: all 0.2s !important;
        color: #8b949e !important;
    }
    [data-testid="stSidebar"] .stRadio label:hover {
        background: #21262d !important;
        border-color: #30363d !important;
        color: #e6edf3 !important;
    }

    /* ── Headers ── */
    h1 { color: #f0f6fc !important; font-weight: 700 !important; letter-spacing: -0.02em; }
    h2 { color: #e6edf3 !important; font-weight: 600 !important; }
    h3 { color: #c9d1d9 !important; font-weight: 500 !important; }
    p, li, span, label { color: #8b949e !important; }

    /* ── Metric cards ── */
    [data-testid="stMetric"] {
        background: #161b22 !important;
        border: 1px solid #30363d !important;
        border-radius: 12px !important;
        padding: 20px 22px !important;
        transition: border-color 0.2s;
    }
    [data-testid="stMetric"]:hover { border-color: #58a6ff !important; }
    [data-testid="stMetricLabel"] p {
        font-size: 0.72rem !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
        letter-spacing: .07em !important;
        color: #8b949e !important;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.85rem !important;
        font-weight: 700 !important;
        color: #f0f6fc !important;
        font-family: 'JetBrains Mono', monospace !important;
    }

    /* ── Buttons ── */
    .stButton > button {
        background: #238636 !important;
        color: #ffffff !important;
        border: 1px solid #2ea043 !important;
        border-radius: 8px !important;
        padding: 10px 22px !important;
        font-weight: 600 !important;
        transition: all 0.2s !important;
    }
    .stButton > button:hover {
        background: #2ea043 !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 12px rgba(46,160,67,0.3) !important;
    }

    /* ── Inputs ── */
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input,
    .stSelectbox > div > div {
        background-color: #161b22 !important;
        border: 1px solid #30363d !important;
        color: #e6edf3 !important;
        border-radius: 8px !important;
    }
    .stTextInput > div > div > input:focus,
    .stNumberInput > div > div > input:focus {
        border-color: #58a6ff !important;
        box-shadow: 0 0 0 3px rgba(88,166,255,0.15) !important;
    }

    /* ── HTML Table (our custom render_table) ── */
    .dark-table {
        width: 100%;
        border-collapse: collapse;
        font-family: 'Space Grotesk', sans-serif;
        font-size: 0.875rem;
        border-radius: 10px;
        overflow: hidden;
        border: 1px solid #30363d;
    }
    .dark-table thead tr {
        background: #21262d;
    }
    .dark-table thead th {
        color: #8b949e !important;
        font-weight: 600;
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        padding: 12px 16px;
        text-align: left;
        border-bottom: 1px solid #30363d;
    }
    .dark-table tbody tr {
        background: #161b22;
        border-bottom: 1px solid #21262d;
        transition: background 0.15s;
    }
    .dark-table tbody tr:hover {
        background: #1c2128;
    }
    .dark-table tbody tr:last-child {
        border-bottom: none;
    }
    .dark-table tbody td {
        color: #e6edf3 !important;
        padding: 11px 16px;
        vertical-align: middle;
    }
    .dark-table tbody td:first-child {
        color: #8b949e !important;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.78rem;
    }
    .table-wrap {
        border-radius: 10px;
        overflow-y: auto;
        max-height: 420px;
        border: 1px solid #30363d;
        margin-bottom: 8px;
    }

    /* ── Divider ── */
    hr { border-color: #21262d !important; }

    /* ── Form ── */
    [data-testid="stForm"] {
        background: #161b22 !important;
        border: 1px solid #30363d !important;
        border-radius: 12px !important;
        padding: 24px !important;
    }

    /* ── Alerts ── */
    .stSuccess { background: #0d1f12 !important; color: #3fb950 !important; border-color: #238636 !important; }
    .stError   { background: #1a0f0f !important; color: #f85149 !important; border-color: #da3633 !important; }
    .stWarning { background: #1a160a !important; color: #d29922 !important; border-color: #9e6a03 !important; }
    .stInfo    { background: #0d1a2e !important; color: #58a6ff !important; border-color: #1f3558 !important; }

    /* ── Status banners ── */
    .status-critical {
        background: #1a0f0f; border-left: 4px solid #f85149;
        padding: 14px 18px; border-radius: 8px;
        color: #f85149; font-weight: 600; margin-bottom: 16px;
    }
    .status-warning {
        background: #1a160a; border-left: 4px solid #d29922;
        padding: 14px 18px; border-radius: 8px;
        color: #d29922; font-weight: 600; margin-bottom: 16px;
    }
    .status-healthy {
        background: #0d1f12; border-left: 4px solid #3fb950;
        padding: 14px 18px; border-radius: 8px;
        color: #3fb950; font-weight: 600; margin-bottom: 16px;
    }
    .insight-box {
        background: #0d1a2e; border: 1px solid #1f3558;
        padding: 16px 20px; border-radius: 10px;
        color: #58a6ff; font-size: 0.95rem; margin-top: 12px; line-height: 1.6;
    }
    .insight-box strong { color: #79c0ff !important; }
    .insight-box em     { color: #a5d6ff !important; }
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────
# HELPER — renders any list-of-dicts as a dark HTML table
# ──────────────────────────────────────────────
def render_table(data, max_rows=None):
    if not data:
        st.info("No data available.")
        return
    df = pd.DataFrame(data)
    if max_rows:
        df = df.head(max_rows)

    headers = "".join(f"<th>{col}</th>" for col in df.columns)
    rows = ""
    for i, row in df.iterrows():
        cells = "".join(f"<td>{val}</td>" for val in row.values)
        rows += f"<tr>{cells}</tr>"

    html = f"""
    <div class="table-wrap">
      <table class="dark-table">
        <thead><tr>{headers}</tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


# ──────────────────────────────────────────────
# Plotly dark theme helper
# ──────────────────────────────────────────────
PLOT_BG  = "#161b22"
PAPER_BG = "#161b22"
FONT_CLR = "#c9d1d9"
GRID_CLR = "#21262d"
ACCENT   = "#58a6ff"
GREEN    = "#3fb950"
ORANGE   = "#d29922"
RED      = "#f85149"

def dark_layout(fig, height=380):
    fig.update_layout(
        paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG,
        font=dict(family="Space Grotesk", color=FONT_CLR),
        height=height,
        margin=dict(t=36, b=24, l=8, r=8),
        xaxis=dict(showgrid=False, color=FONT_CLR, linecolor=GRID_CLR),
        yaxis=dict(gridcolor=GRID_CLR, color=FONT_CLR, linecolor=GRID_CLR),
        legend=dict(bgcolor="rgba(0,0,0,0)", font_color=FONT_CLR),
    )
    return fig


# ──────────────────────────────────────────────
# SIDEBAR
# ──────────────────────────────────────────────
with st.sidebar:
    st.markdown("## Inventory Dashboard ")
    st.markdown("---")
    option = st.radio(
        "nav",
        ["📊  Basic Information", "⚙️  Operational Tasks", "🔬  Advanced Insights"],
        label_visibility="collapsed"
    )
    st.markdown("---")
    st.caption("Made by Divyanshu :)")


# ──────────────────────────────────────────────
# DB CONNECTION
# ──────────────────────────────────────────────
st.title("Inventory & Supply Chain Dashboard")

try:
    db     = connect_to_db()
    cursor = db.cursor(dictionary=True)
except Exception as e:
    st.error(f"❌ Cannot connect to database: {e}")
    st.stop()

try:

    # ════════════════════════════════════════════
    # PAGE 1 — BASIC INFORMATION
    # ════════════════════════════════════════════
    if option == "📊  Basic Information":
        st.header("Key Metrics")

        basic_info = get_basic_info(cursor)
        keys       = list(basic_info.keys())

        cols = st.columns(3)
        for i in range(min(3, len(keys))):
            cols[i].metric(keys[i], basic_info[keys[i]])

        if len(keys) > 3:
            cols2 = st.columns(3)
            for i in range(3, min(6, len(keys))):
                cols2[i - 3].metric(keys[i], basic_info[keys[i]])

        st.divider()

        # ── ABC Analysis ──────────────────────────
        st.header("ABC Inventory Analysis")
        abc_data = get_abc_analysis(cursor)

        if abc_data:
            df_abc      = pd.DataFrame(abc_data)
            class_count = df_abc["abc_class"].value_counts()

            c1, c2, c3 = st.columns(3)
            c1.metric("Class A — High Value",   class_count.get("A – High Value",   0))
            c2.metric("Class B — Medium Value", class_count.get("B – Medium Value", 0))
            c3.metric("Class C — Low Value",    class_count.get("C – Low Value",    0))

            col_chart, col_table = st.columns([1, 1])
            with col_chart:
                fig = px.pie(
                    df_abc, names="abc_class", values="revenue",
                    hole=0.48,
                    color_discrete_sequence=[ACCENT, GREEN, ORANGE],
                )
                fig.update_traces(textfont_color=FONT_CLR)
                fig = dark_layout(fig, height=340)
                fig.update_layout(
                    title=dict(text="Revenue by ABC Class", font_color=FONT_CLR),
                    legend=dict(orientation="h", yanchor="bottom", y=-0.25, font_color=FONT_CLR)
                )
                st.plotly_chart(fig, use_container_width=True)

            with col_table:
                render_table(abc_data)

        st.divider()

        # ── Monthly Sales Trend ────────────────────
        st.header("Monthly Sales Trend")
        trend_data = get_monthly_sales_trend(cursor)
        if trend_data:
            df_trend = pd.DataFrame(trend_data)
            fig2 = px.area(
                df_trend, x="month", y="sales_value",
                labels={"month": "Month", "sales_value": "Sales Value (₹)"},
                color_discrete_sequence=[ACCENT],
            )
            fig2.update_traces(line_width=2.5, fillcolor="rgba(88,166,255,0.15)")
            fig2 = dark_layout(fig2)
            st.plotly_chart(fig2, use_container_width=True)

        st.divider()

        # ── Category Stock ─────────────────────────
        st.header("Stock by Category")
        cat_data = get_category_stock_summary(cursor)
        if cat_data:
            df_cat = pd.DataFrame(cat_data)
            fig3 = px.bar(
                df_cat, x="category", y="total_stock",
                color="below_reorder",
                color_continuous_scale=[[0, GREEN], [1, RED]],
                labels={"category": "Category", "total_stock": "Total Stock",
                        "below_reorder": "Below Reorder"},
            )
            fig3 = dark_layout(fig3)
            fig3.update_layout(coloraxis_colorbar=dict(
                tickfont_color=FONT_CLR, title_font_color=FONT_CLR
            ))
            st.plotly_chart(fig3, use_container_width=True)

        st.divider()

        # ── Detailed Tables ────────────────────────
        tables = get_additional_tables(cursor)
        for label, data in tables.items():
            st.subheader(label)
            render_table(data)
            st.divider()


    # ════════════════════════════════════════════
    # PAGE 2 — OPERATIONAL TASKS
    # ════════════════════════════════════════════
    elif option == "⚙️  Operational Tasks":
        st.header("Operational Tasks")

        task = st.selectbox(
            "Choose a task",
            ["Add New Product", "Product History", "Place Reorder", "Receive Reorder"]
        )

        # ── Add New Product ────────────────────────
        if task == "Add New Product":
            st.subheader("Add New Product")
            categories = get_categories(cursor)
            suppliers  = get_suppliers(cursor)

            with st.form("add_product_form", clear_on_submit=True):
                col1, col2 = st.columns(2)
                with col1:
                    product_name     = st.text_input("Product Name *")
                    product_category = st.selectbox("Category", categories)
                    product_price    = st.number_input("Price (₹)", min_value=0.0, format="%.2f")
                with col2:
                    product_stock = st.number_input("Stock Quantity", min_value=0, step=1)
                    product_level = st.number_input("Reorder Level",  min_value=0, step=1)
                    supplier_ids   = [s["supplier_id"]   for s in suppliers]
                    supplier_names = [s["supplier_name"] for s in suppliers]
                    supplier_id    = st.selectbox(
                        "Supplier",
                        options=supplier_ids,
                        format_func=lambda x: supplier_names[supplier_ids.index(x)]
                    )

                submitted = st.form_submit_button("➕ Add Product")
                if submitted:
                    if not product_name.strip():
                        st.error("Product name is required.")
                    else:
                        try:
                            add_new_manual_id(
                                cursor, db,
                                product_name, product_category,
                                product_price, product_stock,
                                product_level, supplier_id
                            )
                            st.success(f"✅ Product **{product_name}** added successfully!")
                        except Exception as e:
                            st.error(f"Error: {e}")

        # ── Product History ────────────────────────
        elif task == "Product History":
            st.subheader("Product Inventory History")
            products      = get_all_products(cursor)
            product_names = [p["product_name"] for p in products]
            product_ids   = [p["product_id"]   for p in products]

            selected_name = st.selectbox("Select Product", product_names)
            if selected_name:
                pid  = product_ids[product_names.index(selected_name)]
                rows = get_product_history(cursor, pid)
                if rows:
                    render_table(rows)
                else:
                    st.info("No history found for this product.")

        # ── Place Reorder ──────────────────────────
        elif task == "Place Reorder":
            st.subheader("Place a Reorder")
            products      = get_all_products(cursor)
            product_names = [p["product_name"] for p in products]
            product_ids   = [p["product_id"]   for p in products]

            selected_name = st.selectbox("Select Product", product_names)
            reorder_qty   = st.number_input("Reorder Quantity", min_value=1, step=1)

            if st.button("Place Reorder"):
                pid = product_ids[product_names.index(selected_name)]
                try:
                    place_reorder(cursor, db, pid, reorder_qty)
                    st.success(f"✅ Reorder placed for **{selected_name}** — Qty: {reorder_qty}")
                except Exception as e:
                    st.error(f"Error: {e}")

        # ── Receive Reorder ────────────────────────
        elif task == "Receive Reorder":
            st.subheader("Mark Reorder as Received")
            pending = get_pending_reorders(cursor)

            if not pending:
                st.info("No pending reorders at the moment.")
            else:
                reorder_ids    = [r["reorder_id"]   for r in pending]
                reorder_labels = [f"ID {r['reorder_id']} — {r['product_name']}" for r in pending]

                selected_label = st.selectbox("Select Reorder", reorder_labels)
                selected_rid   = reorder_ids[reorder_labels.index(selected_label)]

                if st.button("✅ Mark as Received"):
                    try:
                        mark_reorder_as_received(cursor, db, selected_rid)
                        st.success(f"Reorder **{selected_rid}** marked as received!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")


    # ════════════════════════════════════════════
    # PAGE 3 — ADVANCED INSIGHTS
    # ════════════════════════════════════════════
    elif option == "🔬  Advanced Insights":
        st.header("Supply Chain Optimization Engine")
        st.caption("Operations Research models: Safety Stock · ROP · EOQ")
        st.divider()

        products      = get_all_products(cursor)
        product_names = [p["product_name"] for p in products]
        product_ids   = [p["product_id"]   for p in products]

        selected_name = st.selectbox("Select a product to analyse:", product_names)

        if selected_name:
            pid      = product_ids[product_names.index(selected_name)]
            insights = get_advanced_product_insights(cursor, pid)

            if not insights:
                st.warning("Could not load data for this product.")
            else:
                status = insights["status"]
                if "CRITICAL" in status:
                    st.markdown(f'<div class="status-critical">🚨 {status}</div>', unsafe_allow_html=True)
                elif "WARNING" in status:
                    st.markdown(f'<div class="status-warning">⚠️ {status}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="status-healthy">✅ {status}</div>', unsafe_allow_html=True)

                st.subheader("Inventory Parameters")
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Current Stock",        f"{insights['current_stock']} units")
                m2.metric("Avg Daily Demand",      f"{insights['avg_daily_demand']} units/day")
                m3.metric("Demand Volatility (σ)", f"{insights['volatility']} units")
                m4.metric("EOQ (Optimal Batch)",   f"{insights['eoq']} units")

                st.divider()

                st.subheader("Reorder Thresholds")
                col_rop, col_ss = st.columns(2)
                with col_rop:
                    st.metric("Reorder Point (ROP)", f"{insights['rop']} units")
                    st.caption("When stock hits this level, place a new order to cover 5-day lead time.")
                with col_ss:
                    st.metric("Safety Stock", f"{insights['safety_stock']} units")
                    st.caption("Buffer at 95% service level to absorb demand spikes.")

                st.divider()

                max_range = max(insights["current_stock"] * 1.5, insights["rop"] * 2)
                fig_gauge = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=insights["current_stock"],
                    number={"font": {"color": FONT_CLR, "family": "JetBrains Mono"}},
                    title={"text": f"Stock Level — {insights['product_name']}",
                           "font": {"size": 15, "color": FONT_CLR}},
                    gauge={
                        "axis": {"range": [0, max_range],
                                 "tickcolor": FONT_CLR,
                                 "tickfont": {"color": FONT_CLR}},
                        "bar":  {"color": ACCENT},
                        "bgcolor": PLOT_BG,
                        "bordercolor": GRID_CLR,
                        "steps": [
                            {"range": [0, insights["safety_stock"]],              "color": "#1a0f0f"},
                            {"range": [insights["safety_stock"], insights["rop"]], "color": "#1a160a"},
                            {"range": [insights["rop"], max_range],               "color": "#0d1f12"},
                        ],
                        "threshold": {
                            "line": {"color": RED, "width": 3},
                            "thickness": 0.8,
                            "value": insights["rop"]
                        }
                    }
                ))
                fig_gauge.update_layout(
                    paper_bgcolor=PAPER_BG,
                    font=dict(family="Space Grotesk", color=FONT_CLR),
                    height=300,
                    margin=dict(t=50, b=20, l=30, r=30)
                )
                st.plotly_chart(fig_gauge, use_container_width=True)

                st.markdown(
                    f'<div class="insight-box">'
                    f'💡 <strong>Recommendation:</strong> For <em>{insights["product_name"]}</em>, '
                    f'order <strong>{insights["eoq"]} units</strong> (EOQ) whenever stock drops to '
                    f'<strong>{insights["rop"]} units</strong> (ROP). '
                    f'Keep at least <strong>{insights["safety_stock"]} units</strong> as a safety buffer.'
                    f'</div>',
                    unsafe_allow_html=True
                )

finally:
    cursor.close()
    db.close()