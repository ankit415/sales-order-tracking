import streamlit as st
import pandas as pd
import sqlite3
import datetime
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader

st.set_page_config(page_title="Sales Order Tracker", layout="wide")
st.title("🚚 Sales Order Tracking Dashboard")

# ====================== DATABASE SETUP ======================
def init_db():
    conn = sqlite3.connect('sales_orders.db')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id TEXT PRIMARY KEY,
            product TEXT,
            qty INTEGER,
            expected_dispatch TEXT,
            customer TEXT,
            tech_req TEXT,
            additional TEXT,
            status TEXT,
            last_updated TEXT,
            updated_by TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def get_db():
    return sqlite3.connect('sales_orders.db')

# ====================== SIMPLE AUTH (Free & Easy) ======================
# Change these credentials as per your team
credentials = {
    "usernames": {
        "admin": {"name": "Admin", "password": "admin123", "role": "Admin"},
        "production": {"name": "Production Head", "password": "prod123", "role": "Production"},
        "logistics": {"name": "Logistics", "password": "logi123", "role": "Logistics"}
    }
}

authenticator = stauth.Authenticate(
    credentials,
    cookie_name="sales_order_cookie",
    cookie_key="random_key_123",   # Change this in production
    cookie_expiry_days=30
)

name, authentication_status, username = authenticator.login()

if not authentication_status:
    st.stop()

st.sidebar.success(f"Logged in as **{name}** ({credentials['usernames'][username]['role']})")
role = credentials['usernames'][username]['role']

if st.sidebar.button("Logout"):
    authenticator.logout()
    st.rerun()

# ====================== LOAD / SAVE ORDERS ======================
def load_orders():
    conn = get_db()
    df = pd.read_sql_query("SELECT * FROM orders ORDER BY id DESC", conn)
    conn.close()
    return df

def save_order(order_dict):
    conn = get_db()
    df = pd.DataFrame([order_dict])
    df.to_sql('orders', conn, if_exists='append', index=False)
    conn.commit()
    conn.close()

def update_order_status(order_id, new_status, updated_by):
    conn = get_db()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    conn.execute("""
        UPDATE orders 
        SET status = ?, last_updated = ?, updated_by = ?
        WHERE id = ?
    """, (new_status, now, updated_by, order_id))
    conn.commit()
    conn.close()

# ====================== MAIN APP ======================
tab1, tab2 = st.tabs(["📋 Dashboard", "➕ New Order"])

with tab1:
    st.subheader("All Sales Orders")
    
    df = load_orders()
    if df.empty:
        st.info("No orders yet. Create your first order.")
    else:
        # Status filters
        status_filter = st.selectbox("Filter by Status", 
                                   ["All", "Pending", "In Production", "Ready for Dispatch", "Invoiced", "Shipped"],
                                   index=0)
        
        if status_filter != "All":
            df = df[df['status'] == status_filter]
        
        # Display table
        for _, row in df.iterrows():
            col1, col2, col3, col4 = st.columns([3, 1.5, 2, 2])
            
            with col1:
                st.write(f"**{row['id']}** — {row['product']}")
                st.caption(f"Customer: {row.get('customer', '—')} | Qty: {row['qty']}")
            
            with col2:
                st.metric("Expected", row['expected_dispatch'])
            
            with col3:
                color = {"Pending":"orange", "In Production":"blue", 
                        "Ready for Dispatch":"green", "Invoiced":"purple", 
                        "Shipped":"gray"}.get(row['status'], "gray")
                st.markdown(f"**Status:** <span style='color:{color}'>{row['status']}</span>", unsafe_allow_html=True)
            
            with col4:
                if role == "Production":
                    if row['status'] == "Pending":
                        if st.button("Start Production", key=f"prod_{row['id']}"):
                            update_order_status(row['id'], "In Production", name)
                            st.rerun()
                    elif row['status'] == "In Production":
                        if st.button("Mark Ready", key=f"ready_{row['id']}"):
                            update_order_status(row['id'], "Ready for Dispatch", name)
                            st.rerun()
                
                elif role == "Logistics":
                    if row['status'] == "Ready for Dispatch":
                        if st.button("Generate Invoice & Ship", key=f"ship_{row['id']}"):
                            invoice = f"INV-{datetime.date.today().strftime('%Y%m')}-{row['id'][-3:]}"
                            update_order_status(row['id'], "Invoiced", name)
                            st.success(f"Invoice {invoice} generated!")
                            st.rerun()
                    elif row['status'] == "Invoiced":
                        if st.button("Mark Shipped", key=f"shipped_{row['id']}"):
                            update_order_status(row['id'], "Shipped", name)
                            st.rerun()
            
            st.divider()

with tab2:
    if role == "Admin":
        st.subheader("Create New Sales Order")
        with st.form("new_order"):
            product = st.text_input("Product Name *")
            qty = st.number_input("Quantity *", min_value=1, value=10)
            exp_date = st.date_input("Expected Dispatch Date", 
                                   datetime.date.today() + datetime.timedelta(days=15))
            customer = st.text_input("Customer Name")
            tech_req = st.text_area("Technical Requirements")
            additional = st.text_area("Additional Information")
            
            submitted = st.form_submit_button("Create Order")
            if submitted and product:
                new_id = f"ORD-{datetime.datetime.now().strftime('%y%m%d')}-{len(df)+1001}"
                order = {
                    "id": new_id,
                    "product": product,
                    "qty": qty,
                    "expected_dispatch": str(exp_date),
                    "customer": customer or "—",
                    "tech_req": tech_req,
                    "additional": additional,
                    "status": "Pending",
                    "last_updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "updated_by": name
                }
                save_order(order)
                st.success(f"Order {new_id} created successfully!")
                st.rerun()
    else:
        st.warning("Only Admin can create new orders.")

# Sidebar Info
st.sidebar.info("**Workflow:**\n"
                "Admin → Creates Order\n"
                "Production → Updates to Ready\n"
                "Logistics → Invoices & Ships")
