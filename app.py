import streamlit as st
import pandas as pd
import datetime
from st_supabase_connection import SupabaseConnection

st.set_page_config(page_title="Sales Order Tracker", layout="wide", page_icon="🚚")
st.title("🚚 Sales Order Tracking Dashboard")

# ====================== SUPABASE CONNECTION ======================
conn = st.connection("supabase", type=SupabaseConnection)

# Create table if not exists
@st.cache_resource
def init_table():
    conn.query("""
        CREATE TABLE IF NOT EXISTS orders (
            id TEXT PRIMARY KEY,
            product TEXT,
            qty INTEGER,
            expected_dispatch TEXT,
            customer TEXT,
            tech_req TEXT,
            additional TEXT,
            status TEXT DEFAULT 'Pending',
            last_updated TEXT,
            updated_by TEXT,
            is_deleted INTEGER DEFAULT 0
        )
    """).execute()

init_table()

# ====================== HELPER FUNCTIONS ======================
def load_orders(include_deleted=False):
    query = "SELECT * FROM orders ORDER BY id DESC"
    response = conn.query(query).execute()
    df = pd.DataFrame(response.data) if response.data else pd.DataFrame()
    
    if df.empty:
        return pd.DataFrame()
    
    if 'is_deleted' not in df.columns:
        df['is_deleted'] = 0
    if not include_deleted:
        df = df[df['is_deleted'] == 0]
    return df

def get_next_order_id():
    response = conn.query("SELECT id FROM orders ORDER BY id DESC LIMIT 1").execute()
    last = response.data[0] if response.data else None
    
    if not last:
        return "2026-27/ORD/1"
    try:
        last_num = int(last['id'].split('/')[-1])
        return f"2026-27/ORD/{last_num + 1}"
    except:
        return "2026-27/ORD/1"

def save_order(order_dict):
    conn.table("orders").insert(order_dict).execute()

def update_order_status(order_id, new_status, updated_by):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    conn.table("orders").update({
        "status": new_status,
        "last_updated": now,
        "updated_by": updated_by
    }).eq("id", order_id).execute()

def soft_delete_order(order_id, deleted_by):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    conn.table("orders").update({
        "is_deleted": 1,
        "last_updated": now,
        "updated_by": deleted_by
    }).eq("id", order_id).execute()

# ====================== LOGIN ======================
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.role = None
    st.session_state.name = None

if not st.session_state.authenticated:
    st.subheader("🔐 Login")
    username = st.text_input("Username", placeholder="admin / production / logistics")
    password = st.text_input("Password", type="password")
    
    if st.button("Login", type="primary"):
        users = {
            "admin": {"password": "admin123", "role": "Admin", "name": "Admin"},
            "production": {"password": "prod123", "role": "Production", "name": "Production Head"},
            "logistics": {"password": "logi123", "role": "Logistics", "name": "Logistics Team"}
        }
        if username in users and users[username]["password"] == password:
            st.session_state.authenticated = True
            st.session_state.role = users[username]["role"]
            st.session_state.name = users[username]["name"]
            st.rerun()
        else:
            st.error("Incorrect credentials")
    st.stop()

st.sidebar.success(f"✅ {st.session_state.name} ({st.session_state.role})")

if st.sidebar.button("Logout"):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

role = st.session_state.role

# ====================== MAIN APP ======================
tab1, tab2 = st.tabs(["📋 Dashboard", "➕ New Order"])

with tab1:
    st.subheader("All Sales Orders")
    df = load_orders(include_deleted=True)
    
    if df.empty:
        st.info("No orders yet. Create your first one!")
    else:
        status_filter = st.selectbox("Filter by Status", ["All", "Pending", "In Production", "Ready for Dispatch", "Invoiced", "Shipped"])
        if status_filter != "All":
            df = df[df['status'] == status_filter]

        for _, row in df.iterrows():
            is_deleted = row.get('is_deleted', 0) == 1
            
            with st.container(border=True):
                col1, col2, col3 = st.columns([3.5, 2, 2.5])
                
                with col1:
                    if is_deleted:
                        st.write(f"~~**{row['id']}** — {row['product']}~~ 🗑️")
                    else:
                        st.write(f"**{row['id']}** — {row['product']}")
                    st.caption(f"👤 {row.get('customer', '—')} | Qty: **{row['qty']}**")
                    
                    if row.get('tech_req'):
                        st.markdown("**🔧 Technical Requirements:**")
                        st.info(row['tech_req'])
                    if row.get('additional'):
                        st.markdown("**📋 Additional Information:**")
                        st.info(row['additional'])
                
                with col2:
                    st.metric("Expected Dispatch", row['expected_dispatch'])
                    colors = {"Pending":"orange", "In Production":"blue", "Ready for Dispatch":"green", 
                             "Invoiced":"purple", "Shipped":"gray"}
                    color = colors.get(row['status'], "gray")
                    status_text = f"~~{row['status']}~~" if is_deleted else row['status']
                    st.markdown(f"**Status:** <span style='color:{color}'>{status_text}</span>", unsafe_allow_html=True)
                
                with col3:
                    if is_deleted:
                        st.markdown("**🗑️ Deleted**", unsafe_allow_html=True)
                    else:
                        if role == "Production":
                            if row['status'] == "Pending":
                                if st.button("▶️ Start Production", key=f"start_{row['id']}"):
                                    update_order_status(row['id'], "In Production", st.session_state.name)
                                    st.rerun()
                            elif row['status'] == "In Production":
                                if st.button("✅ Mark Ready", key=f"ready_{row['id']}"):
                                    update_order_status(row['id'], "Ready for Dispatch", st.session_state.name)
                                    st.rerun()
                        
                        elif role == "Logistics":
                            if row['status'] == "Ready for Dispatch":
                                if st.button("📄 Generate Invoice", key=f"inv_{row['id']}"):
                                    update_order_status(row['id'], "Invoiced", st.session_state.name)
                                    st.success("✅ Invoice Generated!")
                                    st.rerun()
                            elif row['status'] == "Invoiced":
                                if st.button("🚚 Mark Shipped", key=f"ship_{row['id']}"):
                                    update_order_status(row['id'], "Shipped", st.session_state.name)
                                    st.success("✅ Shipped!")
                                    st.rerun()
                        
                        if role == "Admin":
                            if st.button("🗑️ Delete Order", key=f"del_{row['id']}", type="secondary"):
                                soft_delete_order(row['id'], st.session_state.name)
                                st.success(f"Order {row['id']} deleted!")
                                st.rerun()

with tab2:
    if role == "Admin":
        st.subheader("Create New Sales Order")
        with st.form("new_order_form", clear_on_submit=True):
            product = st.text_input("Product Name *")
            qty = st.number_input("Quantity *", min_value=1, value=10)
            exp_date = st.date_input("Expected Dispatch Date", datetime.date.today() + datetime.timedelta(days=15))
            customer = st.text_input("Customer Name")
            tech_req = st.text_area("Technical Requirements", height=120)
            additional = st.text_area("Additional Information", height=100)
            
            if st.form_submit_button("Create Order", type="primary") and product:
                new_id = get_next_order_id()
                order = {
                    "id": new_id,
                    "product": product,
                    "qty": int(qty),
                    "expected_dispatch": str(exp_date),
                    "customer": customer or "—",
                    "tech_req": tech_req,
                    "additional": additional,
                    "status": "Pending",
                    "last_updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "updated_by": st.session_state.name,
                    "is_deleted": 0
                }
                save_order(order)
                st.success(f"🎉 Order **{new_id}** created successfully!")
    else:
        st.warning("Only Admin can create orders.")

st.sidebar.info("Data is now stored in Supabase (persistent & reliable)")
