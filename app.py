import os
import tempfile
import pandas as pd
import streamlit as st
from engine import run, partition

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Mini MapReduce Engine",
    page_icon="⚙️",
    layout="wide",
)

# ── Minimal custom style ──────────────────────────────────────────────────────
st.markdown("""
<style>
    .phase-card {
        background: #f0fdf8;
        border-left: 4px solid #00a382;
        border-radius: 4px;
        padding: 0.65rem 1rem;
        margin-bottom: 0.5rem;
        font-size: 0.93rem;
    }
    .phase-card b { color: #006655; }
    .phase-detail { color: #444; font-size: 0.86rem; margin-top: 2px; }
</style>
""", unsafe_allow_html=True)


# ── Header ────────────────────────────────────────────────────────────────────
st.title("⚙️ Mini MapReduce Engine")
st.caption("Word count across distributed text splits — built from scratch · no Hadoop · no Spark")
st.divider()


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Settings")

    use_default = st.toggle("Use ETI claim notes (default)", value=True)

    uploaded_files = None
    if not use_default:
        uploaded_files = st.file_uploader(
            "Upload your own .txt splits",
            type=["txt"],
            accept_multiple_files=True,
        )

    st.divider()
    run_clicked = st.button("▶  Run MapReduce", use_container_width=True, type="primary")
    st.caption("Each .txt file is treated as one split.")


# ── Run on button click ───────────────────────────────────────────────────────
if run_clicked:

    # Resolve input directory
    if use_default or not uploaded_files:
        input_dir = "input"
    else:
        input_dir = tempfile.mkdtemp()
        for uf in uploaded_files:
            with open(os.path.join(input_dir, uf.name), "wb") as out:
                out.write(uf.read())

    # Run the pipeline
    with st.spinner("Running pipeline..."):
        try:
            data = run(input_dir, output_dir="output")
        except FileNotFoundError as e:
            st.error(str(e))
            st.stop()

    # ── Pipeline phases ───────────────────────────────────────────────────────
    st.subheader("Pipeline")

    total_before_combine = sum(
        sum(c for _, c in pairs) for pairs in data["map_outputs"]
    )
    total_after_combine = sum(len(pairs) for pairs in data["map_outputs"])
    r0_words = len(data["reducer_inputs"][0])
    r1_words = len(data["reducer_inputs"][1])

    phases = [
        (
            "1 · Map",
            f"{len(data['splits'])} mappers ran in parallel "
            f"({', '.join(data['splits'])}) — "
            f"{total_before_combine} total word occurrences found"
        ),
        (
            "2 · Combine",
            f"Each mapper reduced its own pairs locally: "
            f"{total_before_combine} occurrences → {total_after_combine} unique (word, count) pairs"
        ),
        (
            "3 · Partition",
            "Each word assigned to a reducer via: "
            "<code>sum(ord(c) for c in word) % 2</code> — deterministic every run"
        ),
        (
            "4 · Shuffle &amp; Sort",
            f"Reducer 0 received {r0_words} distinct words — "
            f"Reducer 1 received {r1_words} distinct words — sorted alphabetically"
        ),
        (
            "5 · Reduce",
            f"Counts summed per word — written to "
            f"<code>output/reducer_0.txt</code> and <code>output/reducer_1.txt</code>"
        ),
    ]

    for label, detail in phases:
        st.markdown(
            f'<div class="phase-card">'
            f'<b>{label}</b>'
            f'<div class="phase-detail">{detail}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.divider()

    # ── Results ───────────────────────────────────────────────────────────────
    st.subheader("Results")

    col_r0, col_r1 = st.columns(2)

    for col, rid in zip([col_r0, col_r1], [0, 1]):
        with col:
            st.markdown(f"**Reducer {rid}** — `output/reducer_{rid}.txt`")
            df = pd.DataFrame(data["results"][rid], columns=["word", "count"])
            st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()

    # ── Bar chart ─────────────────────────────────────────────────────────────
    st.subheader("Word Frequencies")

    all_words = [
        pair for results in data["results"].values() for pair in results
    ]
    df_chart = (
        pd.DataFrame(all_words, columns=["word", "count"])
        .sort_values("count", ascending=False)
        .head(10)
        .set_index("word")
    )
    st.bar_chart(df_chart["count"])

    st.divider()

    # ── Partition inspector ───────────────────────────────────────────────────
    st.subheader("🔍 Partition Inspector")
    st.caption("Type any word to see which reducer it maps to and why.")

    word_query = st.text_input("Word:", placeholder="e.g. fire")
    if word_query:
        w = word_query.lower().strip(".,!?;:")
        ascii_sum = sum(ord(c) for c in w)
        rid = partition(w)
        st.info(
            f"**'{w}'** → ASCII sum = **{ascii_sum}** "
            f"→ {ascii_sum} % 2 = **{ascii_sum % 2}** "
            f"→ **Reducer {rid}**"
        )