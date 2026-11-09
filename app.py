"""Online Shop Sales Dashboard (2025)

Goal: help the online shop's sales manager see when revenue peaks, which
categories earn and which get returned, and whether discounts grow orders.
Audience: e-commerce sales manager, reviewed weekly.
Data: data/online_orders.csv (synthetic, generated for class).
"""

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Online Shop Sales 2025", layout="wide")

DATA_PATH = "data/online_orders.csv"


# ------------------------------------------------------------------ load
@st.cache_data
def load_data(path: str) -> pd.DataFrame:
    """Read the CSV and add helper columns."""
    df = pd.read_csv(path, parse_dates=["order_date"])
    # Blank values: this file has none, but to be safe we drop rows missing the
    # columns every chart depends on (a caption in the app says so).
    df = df.dropna(subset=["order_date", "category", "revenue", "units"])
    df["month_num"] = df["order_date"].dt.month
    df["month"] = df["order_date"].dt.strftime("%b")
    df["is_returned"] = df["returned"].eq("Yes")
    df["discount_label"] = (df["discount_pct"] * 100).round().astype(int).astype(str) + "%"
    return df


df = load_data(DATA_PATH)


# --------------------------------------------------------------- filters
def sidebar_filters(data: pd.DataFrame) -> pd.DataFrame:
    """Draw the sidebar controls and return the filtered dataframe."""
    st.sidebar.header("Filters")

    d_min, d_max = data["order_date"].min().date(), data["order_date"].max().date()
    date_range = st.sidebar.date_input(
        "Order date range", value=(d_min, d_max), min_value=d_min, max_value=d_max
    )
    categories = st.sidebar.multiselect(
        "Category", sorted(data["category"].unique()),
        default=sorted(data["category"].unique()),
    )
    regions = st.sidebar.multiselect(
        "Region", sorted(data["region"].unique()),
        default=sorted(data["region"].unique()),
    )
    devices = st.sidebar.multiselect(
        "Device", sorted(data["device"].unique()),
        default=sorted(data["device"].unique()),
    )
    customer = st.sidebar.selectbox(
        "Customer type", ["All customers", "New", "Returning"]
    )
    max_disc = st.sidebar.slider(
        "Maximum discount (%)", 0, 30, 30, step=10,
        help="Keeps only orders with a discount at or below this value.",
    )

    # date_input returns a 1-tuple while the user is mid-selection
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start, end = date_range
    else:
        start, end = d_min, d_max

    mask = (
        data["order_date"].between(pd.Timestamp(start), pd.Timestamp(end))
        & data["category"].isin(categories)
        & data["region"].isin(regions)
        & data["device"].isin(devices)
        & (data["discount_pct"] <= max_disc / 100 + 1e-9)
    )
    if customer != "All customers":
        mask &= data["customer_type"] == customer
    return data[mask]


f = sidebar_filters(df)

# ----------------------------------------------------------------- header
st.title("Online Shop Sales Dashboard, 2025")
st.markdown(
    "**Goal:** help the sales manager see when revenue peaks, which categories "
    "earn and get returned, and whether discounts grow orders.  \n"
    "**Audience:** e-commerce sales manager, checked weekly."
)

if f.empty:
    st.warning("No orders match the current filters. Widen the date range or "
               "select more categories, regions or devices in the sidebar.")
    st.stop()

st.caption(
    "Data handling: this dataset has no blank values, but any order missing a "
    "date, category, revenue or units would be dropped. Revenue is gross "
    "(returned orders are still counted; returns are shown separately)."
)

# ------------------------------------------------------------------- KPIs
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Total revenue (USD)", f"${f['revenue'].sum():,.0f}")
k2.metric("Orders", f"{len(f):,}")
k3.metric("Avg order value (USD)", f"${f['revenue'].mean():,.2f}")
k4.metric("Return rate (%)", f"{f['is_returned'].mean() * 100:.1f}%")
k5.metric("Avg rating (1-5)", f"{f['rating_1to5'].mean():.2f}")

st.divider()

# ----------------------------------------------------------------- charts
# Chart 1 (Q1): monthly revenue
monthly = (f.groupby(["month_num", "month"], as_index=False)["revenue"].sum()
           .sort_values("month_num"))
fig1 = px.line(monthly, x="month", y="revenue", markers=True,
               text=monthly["revenue"].map(lambda v: f"${v / 1000:,.1f}k"),
               labels={"month": "Month (2025)", "revenue": "Revenue (USD)"},
               title="Monthly revenue")
fig1.update_traces(textposition="top center")
fig1.update_layout(font_size=14, yaxis_tickprefix="$")
st.plotly_chart(fig1, width="stretch")
st.caption("Line chart of total revenue per month. Each point is labelled with "
           "its value in thousands of USD; hover for exact figures.")

left, right = st.columns(2)

# Chart 2 (Q2): revenue by category
with left:
    cat = (f.groupby("category", as_index=False)
           .agg(revenue=("revenue", "sum"), return_rate=("is_returned", "mean"))
           .sort_values("revenue", ascending=False))
    cat["return_pct"] = cat["return_rate"] * 100
    fig2 = px.bar(cat, x="category", y="revenue",
                  text=cat["revenue"].map(lambda v: f"${v:,.0f}"),
                  labels={"category": "Category", "revenue": "Revenue (USD)"},
                  title="Revenue by category")
    fig2.update_traces(textposition="outside")
    fig2.update_layout(font_size=14, yaxis_tickprefix="$")
    st.plotly_chart(fig2, width="stretch")
    st.caption("Bar chart of total revenue per category, with dollar values "
               "printed on each bar.")

# Chart 3 (Q2): return rate by category
with right:
    fig3 = px.bar(cat.sort_values("return_pct", ascending=False),
                  x="category", y="return_pct",
                  text=cat.sort_values("return_pct", ascending=False)["return_pct"]
                  .map(lambda v: f"{v:.1f}%"),
                  labels={"category": "Category", "return_pct": "Return rate (%)"},
                  title="Return rate by category")
    fig3.update_traces(textposition="outside")
    fig3.update_layout(font_size=14, yaxis_ticksuffix="%")
    st.plotly_chart(fig3, width="stretch")
    st.caption("Bar chart of the share of orders returned in each category "
               "(percent, labelled on the bars).")

left2, right2 = st.columns(2)

# Chart 4 (Q3): discount vs order size
with left2:
    disc = (f.groupby(["discount_pct", "discount_label"], as_index=False)
            .agg(avg_units=("units", "mean"), avg_order=("revenue", "mean"),
                 orders=("order_id", "count"))
            .sort_values("discount_pct"))
    fig4 = px.bar(disc, x="discount_label", y="avg_units",
                  text=disc["avg_units"].map(lambda v: f"{v:.2f}"),
                  hover_data={"avg_order": ":$.2f", "orders": True},
                  labels={"discount_label": "Discount applied",
                          "avg_units": "Average units per order"},
                  title="Order size by discount level")
    fig4.update_traces(textposition="outside")
    fig4.update_layout(font_size=14)
    st.plotly_chart(fig4, width="stretch")
    st.caption("Bar chart of average units per order at each discount level; "
               "hover to also see average order value (USD) and order counts.")

# Chart 5 (Q4): revenue by region and device
with right2:
    rd = f.groupby(["region", "device"], as_index=False)["revenue"].sum()
    fig5 = px.bar(rd, x="region", y="revenue", color="device", barmode="group",
                  pattern_shape="device",  # pattern so color is not the only cue
                  labels={"region": "Region", "revenue": "Revenue (USD)",
                          "device": "Device"},
                  title="Revenue by region and device")
    fig5.update_layout(font_size=14, yaxis_tickprefix="$")
    st.plotly_chart(fig5, width="stretch")
    st.caption("Grouped bars of revenue per region, split by device. Devices "
               "differ by both color and fill pattern; hover for exact values.")

# --------------------------------------------------------------- insights
st.subheader("Key insights")

peak = monthly.loc[monthly["revenue"].idxmax()]
low = monthly.loc[monthly["revenue"].idxmin()]
m = monthly.set_index("month")["revenue"]
if {"Jun", "Jul"} <= set(m.index):
    jul_text = f" July revenue was ${m['Jul']:,.0f} versus ${m['Jun']:,.0f} in June ({(m['Jul'] / m['Jun'] - 1) * 100:+.0f}%)."
else:
    jul_text = ""
q1 = (f"{peak['month']} is the peak month at ${peak['revenue']:,.0f}, and "
      f"{low['month']} is the lowest at ${low['revenue']:,.0f}.{jul_text}")

top_cat = cat.iloc[0]
top_ret = cat.sort_values("return_pct", ascending=False).iloc[0]
q2 = (f"{top_cat['category']} earns the most (${top_cat['revenue']:,.0f}, "
      f"{top_cat['revenue'] / cat['revenue'].sum() * 100:.0f}% of revenue), while "
      f"{top_ret['category']} has the highest return rate ({top_ret['return_pct']:.1f}%).")

if len(disc) >= 2:
    lo, hi = disc.iloc[0], disc.iloc[-1]
    q3 = (f"Orders at {lo['discount_label']} discount average {lo['avg_units']:.2f} units "
          f"(${lo['avg_order']:,.2f}), versus {hi['avg_units']:.2f} units "
          f"(${hi['avg_order']:,.2f}) at {hi['discount_label']}.")
else:
    q3 = "Only one discount level is in the current selection, so no comparison is possible."

reg = f.groupby("region")["revenue"].sum().sort_values(ascending=False)
dev = f.groupby("device")["revenue"].sum().sort_values(ascending=False)
q4 = (f"{reg.index[0]} is the top region (${reg.iloc[0]:,.0f}), and {dev.index[0]} "
      f"drives the most revenue by device ({dev.iloc[0] / dev.sum() * 100:.0f}% of the total).")

st.markdown(f"""
1. **Sales over the year:** {q1}
2. **Categories and returns:** {q2}
3. **Discounts and order size:** {q3}
4. **Where orders come from:** {q4}
""")
