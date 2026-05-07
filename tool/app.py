import io
import warnings

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from chatbot import GTMChatbot
from gtm_engine import ColumnMap, GTMEngine

warnings.filterwarnings("ignore")

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="GTM Analysis Tool",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; }
    .metric-label { font-size: 0.8rem; color: #666; }
    .metric-value { font-size: 1.8rem; font-weight: 700; }
    .stTabs [data-baseweb="tab"] { font-size: 0.95rem; }
    div[data-testid="stSidebarContent"] { padding-top: 1rem; }
</style>
""", unsafe_allow_html=True)


# ── Helpers ────────────────────────────────────────────────────────────────────

def auto_detect(df: pd.DataFrame) -> dict:
    detected = {}
    for col in df.select_dtypes(include="object").columns:
        try:
            vals = set(df[col].dropna().str.lower().unique())
            if vals & {"view", "cart", "purchase", "add_to_cart", "buy", "add", "pageview"}:
                detected["event_type"] = col
                break
        except Exception:
            pass

    for col in df.columns:
        cl = col.lower()
        if any(k in cl for k in ["user_id", "userid", "user", "customer_id", "visitor_id"]):
            detected["user_id"] = col
            break

    for col in df.select_dtypes(include="number").columns:
        if any(k in col.lower() for k in ["price", "amount", "value", "revenue", "cost"]):
            detected["price"] = col
            break

    for col in df.columns:
        if any(k in col.lower() for k in ["time", "date", "timestamp", "created"]):
            detected["timestamp"] = col
            break

    for col in df.columns:
        if any(k in col.lower() for k in ["category", "cat", "category_code"]):
            detected["category"] = col
            break

    for col in df.columns:
        if "brand" in col.lower():
            detected["brand"] = col
            break

    return detected


@st.cache_data(show_spinner="Loading data...")
def load_csv(file_bytes: bytes) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(file_bytes))
    return df


@st.cache_data(show_spinner="Sampling by user...")
def sample_by_user(df: pd.DataFrame, uid_col: str, n_users: int = 50_000) -> pd.DataFrame:
    all_users = df[uid_col].unique()
    if len(all_users) <= n_users:
        return df
    sampled = pd.Series(all_users).sample(n=n_users, random_state=42)
    return df[df[uid_col].isin(sampled)].copy()


# ── Charts ─────────────────────────────────────────────────────────────────────

def funnel_chart(f: dict) -> go.Figure:
    fig = go.Figure(go.Funnel(
        y=["Views", "Add to Cart", "Purchase"],
        x=[f["views"], f["carts"], f["purchases"]],
        textinfo="value+percent initial",
        marker={"color": ["#4C9BE8", "#F5A623", "#7ED321"]},
        connector={"line": {"color": "#ccc", "dash": "dot", "width": 2}},
    ))
    fig.update_layout(
        title="Conversion Funnel", height=340,
        margin=dict(l=10, r=10, t=40, b=10),
    )
    return fig


def price_comparison_chart(price_data: dict) -> go.Figure:
    abn = price_data["abandoned_prices"]
    pur = price_data["purchased_prices"]
    cap = max(abn.quantile(0.95), pur.quantile(0.95))

    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=abn[abn <= cap], name="Abandoned", opacity=0.65, nbinsx=40,
        marker_color="#F5A623",
    ))
    fig.add_trace(go.Histogram(
        x=pur[pur <= cap], name="Purchased", opacity=0.65, nbinsx=40,
        marker_color="#7ED321",
    ))
    fig.add_vline(
        x=price_data["abandoned_median"], line_dash="dash", line_color="#E85A4F",
        annotation_text=f"Abandoned ${price_data['abandoned_median']:.0f}",
        annotation_position="top right",
    )
    fig.add_vline(
        x=price_data["purchased_median"], line_dash="dash", line_color="#2E7D32",
        annotation_text=f"Purchased ${price_data['purchased_median']:.0f}",
        annotation_position="top left",
    )
    fig.update_layout(
        title="Price: Abandoned vs Purchased Carts", barmode="overlay",
        xaxis_title="Price ($)", yaxis_title="Count",
        height=340, margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(orientation="h", y=1.1),
    )
    return fig


def category_chart(cat_data: pd.DataFrame) -> go.Figure:
    top = cat_data.head(15).reset_index()
    avg = cat_data["conversion_rate"].mean()

    fig = px.bar(
        top, x=top.columns[0], y="conversion_rate",
        color="conversion_rate",
        color_continuous_scale=["#F5A623", "#7ED321"],
        title="Conversion Rate by Category (%)",
        labels={"conversion_rate": "Rate (%)", top.columns[0]: "Category"},
    )
    fig.add_hline(y=avg, line_dash="dash", line_color="red",
                  annotation_text=f"Avg {avg:.1f}%")
    fig.update_layout(height=380, margin=dict(l=10, r=10, t=40, b=80),
                      coloraxis_showscale=False)
    fig.update_xaxes(tickangle=40)
    return fig


def hourly_chart(hourly: pd.Series) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=list(hourly.index), y=hourly.values,
        mode="lines+markers",
        fill="tozeroy",
        fillcolor="rgba(76,155,232,0.12)",
        line=dict(color="#4C9BE8", width=2),
        marker=dict(size=5),
    ))
    peak = int(hourly.idxmax())
    fig.add_vline(x=peak, line_dash="dash", line_color="#F5A623",
                  annotation_text=f"Peak {peak}:00")
    fig.update_layout(
        title="Purchase Conversion Rate by Hour (UTC)",
        xaxis_title="Hour", yaxis_title="Rate (%)",
        height=320, margin=dict(l=10, r=10, t=40, b=10),
        xaxis=dict(tickmode="linear", tick0=0, dtick=2),
    )
    return fig


def day_of_week_chart(day_data: pd.Series) -> go.Figure:
    colors = ["#7ED321" if v == day_data.max() else "#4C9BE8" for v in day_data.values]
    fig = go.Figure(go.Bar(
        x=list(day_data.index), y=day_data.values,
        marker_color=colors, text=[f"{v:.1f}%" for v in day_data.values],
        textposition="outside",
    ))
    fig.update_layout(
        title="Conversion Rate by Day of Week",
        yaxis_title="Rate (%)",
        height=300, margin=dict(l=10, r=10, t=40, b=10),
    )
    return fig


def price_tier_chart(tier_data: pd.DataFrame) -> go.Figure:
    tiers = tier_data.index.tolist()
    v2c = tier_data["view_to_cart"].values
    c2p = [v if v <= 100 else 0 for v in tier_data["cart_to_purchase"].values]

    fig = go.Figure()
    fig.add_trace(go.Bar(name="View→Cart %", x=tiers, y=v2c, marker_color="#4C9BE8"))
    fig.add_trace(go.Bar(name="Cart→Purchase %", x=tiers, y=c2p, marker_color="#F5A623"))
    fig.update_layout(
        title="Conversion Rates by Price Tier",
        barmode="group", yaxis_title="Rate (%)",
        height=340, margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(orientation="h", y=1.1),
    )
    return fig


def brand_chart(brand_data: pd.DataFrame) -> go.Figure:
    top = brand_data.head(12).reset_index()
    fig = px.bar(
        top, x="conversion_rate", y=top.columns[0],
        orientation="h", color="conversion_rate",
        color_continuous_scale=["#F5A623", "#7ED321"],
        title="Top Brands by Conversion Rate",
        labels={"conversion_rate": "Rate (%)", top.columns[0]: "Brand"},
    )
    fig.update_layout(height=400, margin=dict(l=10, r=10, t=40, b=10),
                      coloraxis_showscale=False, yaxis=dict(autorange="reversed"))
    return fig


def render_chart(key: str, engine: GTMEngine):
    if key == "funnel":
        st.plotly_chart(funnel_chart(engine.funnel), use_container_width=True)
    elif key == "price_comparison":
        d = engine.get_price_analysis()
        if d:
            st.plotly_chart(price_comparison_chart(d), use_container_width=True)
    elif key == "category":
        d = engine.get_category_funnel()
        if d is not None:
            st.plotly_chart(category_chart(d), use_container_width=True)
    elif key == "hourly":
        d = engine.get_hourly_analysis()
        if d is not None:
            st.plotly_chart(hourly_chart(d), use_container_width=True)
    elif key == "day_of_week":
        d = engine.get_day_of_week_analysis()
        if d is not None:
            st.plotly_chart(day_of_week_chart(d), use_container_width=True)
    elif key == "price_tier":
        d = engine.get_price_tier_funnel()
        if d is not None:
            st.plotly_chart(price_tier_chart(d), use_container_width=True)
    elif key == "brand":
        d = engine.get_brand_funnel()
        if d is not None:
            st.plotly_chart(brand_chart(d), use_container_width=True)
    elif key == "price_dist":
        d = engine.get_price_analysis()
        if d:
            st.plotly_chart(price_comparison_chart(d), use_container_width=True)


# ── Landing page ───────────────────────────────────────────────────────────────

def show_landing():
    st.title("📊 GTM Analysis Tool")
    st.subheader("Upload any e-commerce event CSV and get instant GTM insights — no code required.")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("### 📥 Upload\nDrop in any CSV with event data (view / cart / purchase).")
    with col2:
        st.markdown("### 🗂️ Map\nTell the tool which columns are events, users, prices, etc.")
    with col3:
        st.markdown("### 💬 Explore\nAsk questions in plain English or click preset questions.")

    st.markdown("---")
    st.markdown("""
**What you can ask:**
- *"What is my funnel conversion rate?"*
- *"Which category converts best?"*
- *"How many users abandoned their cart?"*
- *"What should I fix first?"*
- *"What is the peak purchase hour?"*

**Expected CSV columns:** `event_type`, `user_id`, `price`, `event_time`, `category_code`, `brand`
(Column names can differ — you'll map them after upload.)
""")


# ── Sidebar ────────────────────────────────────────────────────────────────────

def sidebar() -> tuple:
    with st.sidebar:
        st.markdown("## 📊 GTM Analysis Tool")
        st.markdown("---")

        uploaded = st.file_uploader(
            "Upload CSV", type=["csv"],
            help="E-commerce event data with view / cart / purchase events.",
        )

        if uploaded is None:
            return None, None, None

        df_raw = load_csv(uploaded.read())
        st.success(f"Loaded {len(df_raw):,} rows · {df_raw.shape[1]} columns")

        st.markdown("### Column Mapping")
        st.caption("Auto-detected — override if wrong.")

        detected = auto_detect(df_raw)
        cols = ["(none)"] + list(df_raw.columns)

        def pick(label, key, required=True):
            default = detected.get(key, "(none)")
            idx = cols.index(default) if default in cols else 0
            val = st.selectbox(label, cols, index=idx, key=f"col_{key}")
            return None if val == "(none)" else val

        et  = pick("Event type column *", "event_type")
        uid = pick("User ID column *", "user_id")
        price = pick("Price column", "price", required=False)
        ts    = pick("Timestamp column", "timestamp", required=False)
        cat   = pick("Category column", "category", required=False)
        brand = pick("Brand column", "brand", required=False)

        if not et or not uid:
            st.warning("⚠️ Event type and User ID columns are required.")
            return df_raw, None, None

        st.markdown("### Sample Size")
        max_users = df_raw[uid].nunique()
        slider_max = min(max_users, 100_000)
        slider_min = min(1_000, slider_max)
        slider_val = max(min(max_users, 50_000), slider_min)

        if slider_max <= slider_min:
            n_users = slider_max
            st.caption(f"Using all {max_users:,} users.")
        else:
            n_users = st.slider(
                "Max unique users",
                min_value=slider_min,
                max_value=slider_max,
                value=slider_val,
                step=min(1_000, slider_max - slider_min),
                help="Larger = more accurate but slower.",
            )

        df = sample_by_user(df_raw, uid, n_users)

        col_map = ColumnMap(
            event_type=et, user_id=uid,
            price=price, timestamp=ts,
            category=cat, brand=brand,
        )

        st.caption(f"Working with {df[uid].nunique():,} users · {len(df):,} events")
        return df, col_map, uploaded.name

    return None, None, None


# ── Tabs ───────────────────────────────────────────────────────────────────────

def tab_funnel(engine: GTMEngine):
    f = engine.funnel
    v2c = f["view_to_cart"] * 100
    c2p = f["cart_to_purchase"] * 100
    e2e = f["end_to_end"] * 100

    # Metrics row
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("👀 Viewers", f"{f['views']:,}")
    c2.metric("🛒 Carted", f"{f['carts']:,}")
    c3.metric("✅ Purchased", f"{f['purchases']:,}")
    c4.metric("View → Cart", f"{v2c:.1f}%", delta=f"{v2c - 10:.1f}pp vs 10% mid", delta_color="normal")
    c5.metric("Cart → Purchase", f"{c2p:.1f}%", delta=f"{c2p - 30:.1f}pp vs 30% mid", delta_color="normal")

    st.markdown("---")

    col_left, col_right = st.columns([1, 1])
    with col_left:
        st.plotly_chart(funnel_chart(f), use_container_width=True)
    with col_right:
        st.markdown("#### Interpretation")
        st.markdown(f"""
| Stage | Rate | Benchmark | Status |
|---|---|---|---|
| View → Cart | {v2c:.1f}% | 5–15% | {"⚠️ Below" if v2c < 5 else "✅ Above" if v2c > 15 else "→ Normal"} |
| Cart → Purchase | {c2p:.1f}% | 20–40% | {"⚠️ Below" if c2p < 20 else "✅ Above" if c2p > 40 else "→ Normal"} |
| End-to-end | {e2e:.1f}% | — | — |
""")
        st.markdown("#### Funnel Leverage")
        imp_v2c = int(f["views"] * 0.01 * f["cart_to_purchase"])
        imp_c2p = int(f["carts"] * 0.01)
        st.markdown(f"""
Every **+1pp on View→Cart** → ~**{imp_v2c:,} more purchases**
Every **+1pp on Cart→Purchase** → ~**{imp_c2p:,} more purchases**

{"🔴 **Fix the top of funnel first** — it has more leverage." if imp_v2c > imp_c2p else "🔴 **Fix checkout first** — it has more leverage."}
""")


def tab_dropoff(engine: GTMEngine):
    f = engine.funnel
    st.markdown(f"#### 🛒 {f['cart_abandoned']:,} users added to cart but did not purchase")

    price_data = engine.get_price_analysis()
    hourly = engine.get_hourly_analysis()
    day_data = engine.get_day_of_week_analysis()
    cat_data = engine.get_category_funnel()

    if price_data:
        col1, col2 = st.columns(2)
        with col1:
            st.plotly_chart(price_comparison_chart(price_data), use_container_width=True)
        with col2:
            abn = price_data["abandoned_median"]
            pur = price_data["purchased_median"]
            st.markdown("#### Price Abandonment Insight")
            st.markdown(f"""
- Abandoned cart median: **${abn:.2f}**
- Completed purchase median: **${pur:.2f}**
""")
            if abn > pur * 1.1:
                st.warning("Abandoned carts are priced higher. Price sensitivity is a factor.")
                st.markdown("**Action:** Show installment options or free shipping threshold at checkout.")
            elif abn < pur * 0.9:
                st.info("Abandoned carts are priced lower. Price is NOT the main issue.")
                st.markdown("**Action:** Focus on purchase intent signals — reviews, urgency cues on product pages.")
            else:
                st.info("Minimal price difference. Abandonment is likely UX friction.")
                st.markdown("**Action:** Audit checkout flow for unnecessary steps or trust issues.")

    if hourly is not None or day_data is not None:
        cols = st.columns(2)
        if hourly is not None:
            with cols[0]:
                st.plotly_chart(hourly_chart(hourly), use_container_width=True)
        if day_data is not None:
            with cols[1]:
                st.plotly_chart(day_of_week_chart(day_data), use_container_width=True)

    if cat_data is not None:
        st.plotly_chart(category_chart(cat_data), use_container_width=True)


def tab_segmentation(engine: GTMEngine):
    tier_data = engine.get_price_tier_funnel()
    brand_data = engine.get_brand_funnel()
    rfm = engine.get_rfm_segments()

    if tier_data is not None:
        st.plotly_chart(price_tier_chart(tier_data), use_container_width=True)

    if brand_data is not None:
        col1, col2 = st.columns([2, 1])
        with col1:
            st.plotly_chart(brand_chart(brand_data), use_container_width=True)
        with col2:
            st.markdown("#### Bottom Brands")
            st.dataframe(
                brand_data.tail(8)[["views", "purchases", "conversion_rate"]].reset_index(),
                hide_index=True, use_container_width=True,
            )

    if rfm is not None:
        st.markdown("#### RFM Spend Segments")
        summary = rfm.groupby("spend_tier").agg(
            users=("user_id", "count"),
            avg_spend=("total_spend", "mean"),
            avg_orders=("total_purchases", "mean"),
        ).round(2)
        st.dataframe(summary, use_container_width=True)

        st.markdown("""
| Segment | GTM Strategy |
|---|---|
| 🟢 High Spender | Loyalty program, early access, VIP support |
| 🟡 Mid Spender | Upsell campaigns, bundles — **highest re-engagement ROI** |
| 🔵 Low Spender | First-time buyer follow-up, category intro emails |
""")


def tab_recommendations(engine: GTMEngine):
    recs = engine.generate_recommendations()

    if not recs:
        st.success("✅ All funnel metrics are within or above benchmarks. Focus on driving more traffic.")
        return

    impact_color = {"High": "🔴", "Medium": "🟡", "Low": "🟢"}

    for i, rec in enumerate(recs, 1):
        with st.expander(f"{impact_color.get(rec['impact'],'•')} **{i}. {rec['title']}** — Impact: {rec['impact']} | Effort: {rec['effort']}", expanded=(i == 1)):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Finding:** {rec['finding']}")
                st.markdown(f"**So what:** {rec['so_what']}")
            with col2:
                st.markdown(f"**Action:** {rec['action']}")
                st.markdown(f"**Metric:** {rec['metric']}")


def tab_chat(engine: GTMEngine):
    from chatbot import GTMChatbot, PRESET_QUESTIONS

    bot = GTMChatbot(engine)

    st.markdown("#### Ask anything about your data")
    st.caption("Type a question or click a preset button below.")

    # Preset question buttons
    cols = st.columns(2)
    for i, q in enumerate(PRESET_QUESTIONS):
        if cols[i % 2].button(q, key=f"preset_{i}", use_container_width=True):
            st.session_state["chat_input"] = q

    st.markdown("---")

    user_input = st.text_input(
        "Your question",
        value=st.session_state.get("chat_input", ""),
        placeholder="e.g. What is my cart abandonment rate?",
        key="chat_text_input",
    )

    if user_input:
        st.session_state["chat_input"] = ""
        result = bot.answer(user_input)

        st.markdown("**Answer:**")
        st.markdown(result["text"])

        if result["chart"]:
            render_chart(result["chart"], engine)

        # Chat history
        if "chat_history" not in st.session_state:
            st.session_state["chat_history"] = []
        st.session_state["chat_history"].insert(0, (user_input, result["text"]))

    if st.session_state.get("chat_history"):
        with st.expander("Chat history", expanded=False):
            for q, a in st.session_state["chat_history"][:10]:
                st.markdown(f"**Q:** {q}")
                st.markdown(f"**A:** {a}")
                st.markdown("---")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    if "chat_input" not in st.session_state:
        st.session_state["chat_input"] = ""

    df, col_map, filename = sidebar()

    if df is None or col_map is None:
        show_landing()
        return

    engine = GTMEngine(df, col_map)

    st.title(f"📊 GTM Analysis — {filename}")

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📈 Funnel Overview",
        "🔍 Drop-off Analysis",
        "👥 Segmentation",
        "💡 Recommendations",
        "💬 Chat",
    ])

    with tab1:
        tab_funnel(engine)
    with tab2:
        tab_dropoff(engine)
    with tab3:
        tab_segmentation(engine)
    with tab4:
        tab_recommendations(engine)
    with tab5:
        tab_chat(engine)


if __name__ == "__main__":
    main()
