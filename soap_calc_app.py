import streamlit as st
import pandas as pd

# Typical SAP values (NaOH) in grams NaOH per gram oil.
# Sources vary slightly by reference; always validate against your preferred SAP table.
SAP_NAOH = {
    "Olive Oil": 0.134,
    "Coconut Oil 76°": 0.183,
    "Palm Oil": 0.142,
    "Castor Oil": 0.128,
    "Shea Butter": 0.128,
    "Cocoa Butter": 0.137,
    "Avocado Oil": 0.133,
    "Sunflower Oil (high linoleic)": 0.135,
    "Sweet Almond Oil": 0.136,
    "Grapeseed Oil": 0.135,
    "Rice Bran Oil": 0.128,
    "Canola Oil": 0.133,
    "Lard": 0.138,
    "Tallow": 0.141,
}

# KOH SAP is typically ~1.403x NaOH SAP (because molecular weights differ)
KOH_FACTOR = 1.403

def calc_lye_required(oils: list[dict], alkali: str, superfat_pct: float) -> tuple[float, pd.DataFrame]:
    """
    oils: [{"name": str, "weight_g": float, "sap_naoh": float}, ...]
    alkali: "NaOH" or "KOH"
    superfat_pct: e.g., 5.0 for 5%
    """
    rows = []
    total_lye_0sf = 0.0

    for oil in oils:
        w = float(oil["weight_g"])
        sap_naoh = float(oil["sap_naoh"])
        if alkali == "NaOH":
            sap = sap_naoh
        else:
            sap = sap_naoh * KOH_FACTOR

        lye_for_oil_0sf = w * sap
        total_lye_0sf += lye_for_oil_0sf

        rows.append({
            "Oil": oil["name"],
            "Weight (g)": w,
            f"SAP ({alkali})": sap,
            f"Lye @0% SF (g) [{alkali}]": lye_for_oil_0sf
        })

    df = pd.DataFrame(rows)
    lye_discount = (1.0 - superfat_pct / 100.0)
    total_lye = total_lye_0sf * lye_discount

    df[f"Lye @ {superfat_pct:.1f}% SF (g) [{alkali}]"] = df[f"Lye @0% SF (g) [{alkali}]"] * lye_discount
    return total_lye, df

def water_from_lye_concentration(lye_g: float, concentration_pct: float) -> float:
    """
    Lye concentration = lye / (lye + water)
    So water = lye*(1-c)/c
    """
    c = concentration_pct / 100.0
    if c <= 0 or c >= 1:
        raise ValueError("Lye concentration must be between 1 and 99.")
    return lye_g * (1 - c) / c

def water_from_water_lye_ratio(lye_g: float, water_to_lye_ratio: float) -> float:
    """
    water = ratio * lye
    Example: 2.0 means 2:1 water:lye by weight
    """
    if water_to_lye_ratio <= 0:
        raise ValueError("Water:lye ratio must be > 0.")
    return lye_g * water_to_lye_ratio

st.set_page_config(page_title="Soap / Lye Calculator", layout="wide")
st.title("Soap Lye Calculator")
st.caption("Calm, accurate lye and water calculations for cold process soap.")


st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Source+Serif+4:wght@400;600&family=Inter:wght@400;500&display=swap');

/* Page width + breathing room */
.block-container {
    max-width: 1040px;
    padding-top: 2.5rem;
    padding-bottom: 3rem;
}

/* Global text */
html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
    color: #2B2B2B;
}

/* Headings */
h1, h2, h3 {
    font-family: 'Source Serif 4', serif;
    letter-spacing: -0.01em;
}

/* Subtle panels / cards */
[data-testid="stMetric"],
[data-testid="stContainer"] {
    background: #F7F6F3;
    border: 1px solid #E4E1DA;
    border-radius: 18px;
    padding: 16px 18px;
}

/* Metric numbers */
[data-testid="stMetricValue"] {
    font-family: 'Inter', sans-serif;
    font-weight: 500;
    font-size: 28px;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background-color: #F3F2EE;
}

/* Buttons */
.stButton button {
    border-radius: 14px;
    background-color: #2F4F4F;
    color: #FFFFFF;
    border: none;
    padding: 0.6rem 0.9rem;
}
.stButton button:hover {
    background-color: #3E6B6B;
}
</style>
""", unsafe_allow_html=True)


st.caption(
    "*CAUTION*: lye is caustic. Always add lye to water, *not water to lye*, wear eye/skin protection, and verify SAP values with your trusted reference."
)

# Sidebar controls
# Sidebar controls
with st.sidebar:
    st.header("Batch Settings")

    ALKALI_OPTIONS = {
        "Sodium Hydroxide (NaOH)": "NaOH",
        "Potassium Hydroxide (KOH)": "KOH",
    }

    alkali_label = st.selectbox("Lye type", list(ALKALI_OPTIONS.keys()))
    alkali = ALKALI_OPTIONS[alkali_label]

    unit = st.selectbox("Input units", ["grams", "ounces"], index=0)

    superfat = st.slider(
        "Superfat (%)",
        min_value=0.0,
        max_value=20.0,
        value=5.0,
        step=0.5,
    )

    st.subheader("Water Calculation Mode")
    water_mode = st.radio(
        "Choose one",
        ["Lye concentration (%)", "Water : lye ratio"],
        index=0,
    )

    if water_mode == "Lye concentration (%)":
        lye_conc = st.slider(
            "Lye concentration (%)",
            min_value=20,
            max_value=45,
            value=33,
            step=1,
        )
        water_ratio = None
    else:
        water_ratio = st.number_input(
            "Water : Lye ratio (by weight)",
            min_value=0.5,
            max_value=5.0,
            value=2.0,
            step=0.1,
        )
        lye_conc = None

    st.subheader("Add Oils")
    st.write("Select oils and weights below.")


# Oil entries
if "oil_rows" not in st.session_state:
    st.session_state.oil_rows = []


colA, colB, colC = st.columns([2, 1, 1])
with colA:
    if st.button("➕ Add another oil"):
    st.session_state.oil_rows.append({"name": None, "weight": 0.0, "search": ""})

with colB:
    if st.button("🧹 Clear oils"):
        st.session_state.oil_rows = []
with colC:
    st.write("")

st.subheader("Oil List")

oil_names = list(SAP_NAOH.keys())
edited_rows = []

for i, row in enumerate(st.session_state.oil_rows):
    c1, c2, c3 = st.columns([2, 1, 1])

    with c1:
        search = st.text_input(
            "Find oil",
            value=row.get("search", ""),
            key=f"search_{i}",
            placeholder="Type to search oils…",
            label_visibility="collapsed",
        )

        filtered = [o for o in oil_names if search.lower() in o.lower()]
        options = ["— Select an oil —"] + (filtered if filtered else oil_names)

        current_name = row.get("name")
        index = options.index(current_name) if current_name in options else 0

        selected = st.selectbox(
            f"Oil #{i+1}",
            options,
            index=index,
            key=f"oil_{i}",
            label_visibility="collapsed",
        )

        name = None if selected == "— Select an oil —" else selected

    with c2:
        w = st.number_input(
            "Weight",
            min_value=0.0,
            value=float(row.get("weight", 0.0)),
            step=10.0,
            key=f"wt_{i}",
            label_visibility="collapsed",
        )

    with c3:
        if st.button("Remove", key=f"rm_{i}"):
            st.session_state.oil_rows.pop(i)
            st.rerun()

    edited_rows.append({"name": name, "weight": w, "search": search})

st.session_state.oil_rows = edited_rows


# Convert input to grams
OZ_TO_G = 28.349523125

oils = []
total_oils_g = 0.0
for r in st.session_state.oil_rows:
    w_in = float(r["weight"])
    w_g = w_in if unit == "grams" else w_in * OZ_TO_G
    sap_naoh = SAP_NAOH[r["name"]]
    oils.append({"name": r["name"], "weight_g": w_g, "sap_naoh": sap_naoh})
    total_oils_g += w_g

if total_oils_g <= 0:
    st.warning("Add at least one oil with a weight greater than 0.")
    st.stop()

# Calculate lye
total_lye_g, breakdown_df = calc_lye_required(oils, alkali=alkali, superfat_pct=superfat)

# Calculate water
try:
    if water_mode == "Lye concentration (%)":
        water_g = water_from_lye_concentration(total_lye_g, float(lye_conc))
        water_label = f"Water (g) @ {lye_conc}% lye concentration"
    else:
        water_g = water_from_water_lye_ratio(total_lye_g, float(water_ratio))
        water_label = f"Water (g) @ {water_ratio}:1 water:lye"
except ValueError as e:
    st.error(str(e))
    st.stop()

# Totals
total_batch_g = total_oils_g + total_lye_g + water_g

# Display results
st.header("Results")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Total oils (g)", f"{total_oils_g:,.1f}")
m2.metric(f"Total {alkali} (g)", f"{total_lye_g:,.1f}")
m3.metric("Water (g)", f"{water_g:,.1f}")
m4.metric("Total batch (g)", f"{total_batch_g:,.1f}")

# Optional conversions display
with st.expander("Show results in ounces too"):
    st.write(f"Total oils: {total_oils_g / OZ_TO_G:,.2f} oz")
    st.write(f"Total {alkali}: {total_lye_g / OZ_TO_G:,.2f} oz")
    st.write(f"Water: {water_g / OZ_TO_G:,.2f} oz")
    st.write(f"Total batch: {total_batch_g / OZ_TO_G:,.2f} oz")

st.subheader("Batch Instructions")

st.markdown("### 1. Measure your oils")

for oil in oils:
    st.markdown(
        f"- **{oil['weight_g']:.1f} g** {oil['name']}"
    )

st.markdown(
    f"\n**Total oils:** {total_oils_g:.1f} g"
)

st.markdown("### 2. Prepare the lye solution")

lye_name = "sodium hydroxide (NaOH)" if alkali == "NaOH" else "potassium hydroxide (KOH)"

st.markdown(
    f"""
In a heat-safe container, slowly add  
**{total_lye_g:.1f} g {lye_name}**  
to  
**{water_g:.1f} g water**.

Stir until fully dissolved.  
Set aside to cool.
"""
)

st.markdown("### 3. Combine and soap")

st.markdown(
    """
- Gently melt and combine your oils.
- Allow oils and lye solution to cool to similar temperatures.
- Slowly combine and blend to light trace.
- Pour into mold and proceed with your normal process.
"""
)



st.subheader("Notes")
st.markdown(
    f"""
- **Superfat {superfat:.1f}%** means we discounted the calculated 0% SF lye by **{superfat:.1f}%**.
- **Water mode**: {water_mode}  
  - This app computed: **{water_label}**
- “Total batch” is **oils + lye + water** (doesn’t include fragrance, additives, or water evaporation during cure).
"""
)
