import pandas as pd
import streamlit as st
from io import BytesIO

st.set_page_config(page_title="Batch → Profile Converter", page_icon="🔄", layout="centered")

# ---------------------
# Transformation logic
# ---------------------
def transform_batch_to_profile(src_df: pd.DataFrame) -> pd.DataFrame:
    df = src_df.copy()
    df.columns = [c.strip().lower() for c in df.columns]
    df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)

    def find_col(*names):
        for n in names:
            if n in df.columns:
                return n
        return None

    col_group    = find_col("group")
    col_material = find_col("material")
    col_length   = find_col("length")
    col_qty      = find_col("qty")
    col_itemid   = find_col("itemid", "item_id", "item id")

    # Default single group if no 'group' col
    if not col_group:
        df["_group"] = "1"
        col_group = "_group"

    # Preserve group order as first occurrence
    first_rows = df.groupby(col_group).head(1).reset_index()
    group_order = list(first_rows[col_group].astype(str))

    # Stop BEFORE first group whose first row material starts with FCTSM-26
    stop_at_idx = None
    if col_material:
        for idx, g in enumerate(group_order):
            gdf = df[df[col_group] == g]
            if not gdf.empty:
                mat = (gdf.iloc[0][col_material] or "").upper()
                if mat.startswith("FCT"):
                    stop_at_idx = idx
                    break
    kept_groups = group_order[:stop_at_idx] if stop_at_idx is not None else group_order

    # Organize rows by group
    group_rows = {str(g): df[df[col_group] == g].reset_index(drop=True) for g in kept_groups}
    num_pages = len(kept_groups)
    max_items = max((len(gdf) for gdf in group_rows.values()), default=0)

    def get_val(g, idx, col, default=""):
        gdf = group_rows[str(g)]
        if idx < len(gdf) and col and col in gdf.columns:
            v = gdf.iloc[idx][col]
            return "" if pd.isna(v) else str(v)
        return default

    rows = []
    # Header rows
    rows.append(["List separator=", "Decimal symbol=."] + [""] * max(0, num_pages - 2))
    rows.append(["Scheme Scheme"] + [""] * num_pages)
    page_labels = [f"Page_{i+1}" for i in range(num_pages)]
    rows.append(["LANGID_804"] + page_labels)
    rows.append(["LANGID_404"] + page_labels)
    rows.append(["1"] + [str(i+1) for i in range(num_pages)])

    # Static rows
    rows.append(["204_HMI_Scheme_ProjectData_BarchCode"] + ["1"] * num_pages)
    rows.append(["204_HMI_Scheme_ProjectData_EngInfo"] + ["1"] * num_pages)
    rows.append(["204_HMI_Scheme_ProjectData_ProfileName"] + [get_val(g, 0, col_material, "") for g in kept_groups])
    rows.append(["204_HMI_Scheme_ProjectData_ProfileCode"] + ["0"] * num_pages)
    rows.append(["204_HMI_Scheme_ProjectData_RawLength"] + ["4870"] * num_pages)
    rows.append(["204_HMI_Scheme_ProjectData_RawHeight"] + ["0"] * num_pages)
    rows.append(["204_HMI_Scheme_ProjectData_RawWidth"] + ["0"] * num_pages)
    rows.append(["204_HMI_Scheme_ProjectData_Amount"] + ["0"] * num_pages)

    # PerformData (dynamic)
    for k in range(1, max_items + 1):
        idx = k - 1
        rows.append([f"204_HMI_Scheme_ProjectData_PerformData{{{k}}}.length"]
                    + [(get_val(g, idx, col_length, "0") or "0") for g in kept_groups])
        rows.append([f"204_HMI_Scheme_ProjectData_PerformData{{{k}}}.angle2"] + ["0"] * num_pages)
        rows.append([f"204_HMI_Scheme_ProjectData_PerformData{{{k}}}.angle1"] + ["0"] * num_pages)
        rows.append([f"204_HMI_Scheme_ProjectData_PerformData{{{k}}}.quantity"]
                    + [(get_val(g, idx, col_qty, "0") or "0") for g in kept_groups])

    # Barcodes
    for k in range(1, max_items + 1):
        idx = k - 1
        rows.append([f"204_HMI_Scheme_ProjectData_PerformData{{{k}}}.barcode"]
                    + [get_val(g, idx, col_itemid, "") for g in kept_groups])

    return pd.DataFrame(rows).fillna("")

# ---------------------
# Streamlit UI
# ---------------------
st.title("🔄 Batch → Profile Converter")
st.write("Upload your **Batch CSV** (semicolon-separated) and I’ll generate the profile-cut file automatically.")

uploaded_file = st.file_uploader("📤 Upload your Batch CSV", type=["csv"])

if uploaded_file:
    try:
        src = pd.read_csv(uploaded_file, sep=";", dtype=str, engine="python")
        converted = transform_batch_to_profile(src)
        buffer = BytesIO()
        converted.to_csv(buffer, index=False, header=False, encoding="utf-8")
        buffer.seek(0)

        st.success(f"✅ Converted successfully! Pages generated: {converted.shape[1] - 1}")
        st.download_button("⬇️ Download converted file", buffer, file_name="converted_profile.csv", mime="text/csv")

        st.dataframe(src.head(10))
    except Exception as e:
        st.error(f"Error: {e}")
else:
    st.info("👆 Upload a file to begin.")
