import glob
import html
import os
import tempfile
import time

import altair as alt
import pandas as pd
import streamlit as st

from engine import normalize, partition, reduce_fn, run_mappers, shuffle_and_sort

st.set_page_config(page_title="map() → reduce()", page_icon="⚡", layout="wide")

LIME, PINK, CYAN, AMBER = "#C6F432", "#FF4F9A", "#3DD6F5", "#FFB547"
REDUCER_COLORS = [CYAN, PINK, AMBER, LIME]
DIM = "#8B95B0"
CHIP_LIMIT = 36


def esc(text) -> str:
    return html.escape(str(text))


def render(markup: str) -> None:
    """Render HTML compactly so Markdown never treats indentation as code."""
    st.markdown(
        " ".join(line.strip() for line in markup.splitlines() if line.strip()),
        unsafe_allow_html=True,
    )


def rcolor(rid: int) -> str:
    return REDUCER_COLORS[rid % len(REDUCER_COLORS)]


def chips(items, num_reducers, limit=CHIP_LIMIT, color_of=None) -> str:
    """items: list of (label, value). Chip colour = destination reducer."""
    out = []
    for word, value in items[:limit]:
        color = color_of(word) if color_of else rcolor(partition(word, num_reducers))
        out.append(f'<span class="chip" style="--c:{color}">{esc(word)}<b>{esc(value)}</b></span>')
    if len(items) > limit:
        out.append(f'<span class="chip more">+{len(items) - limit} more</span>')
    return "".join(out)


# ── Styles ────────────────────────────────────────────────────────────────────
render(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=JetBrains+Mono:wght@400;600;800&display=swap');
.stApp {{
    background-color: #0B0F1A;
    background-image:
        radial-gradient(ellipse at 10% -10%, rgba(198,244,50,.13), transparent 45%),
        radial-gradient(ellipse at 100% 0%, rgba(255,79,154,.12), transparent 40%),
        linear-gradient(rgba(255,255,255,.035) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,.035) 1px, transparent 1px);
    background-size: auto, auto, 34px 34px, 34px 34px;
}}
.stApp, .stMarkdown, p, label, input, button {{ font-family: 'Space Grotesk', sans-serif; }}
[data-testid="stHeader"] {{ background: transparent; }}
.stAppDeployButton {{ display: none; }}
.block-container {{ padding-top: 2.2rem; max-width: 1480px; }}
.stButton button[kind="primary"], .stDownloadButton button {{ font-family: 'JetBrains Mono', monospace; font-weight: 800; border-radius: 0; letter-spacing: .04em; }}
.stButton button[kind="primary"] {{ background: {LIME}; color: #0B0F1A; border: none; box-shadow: 4px 4px 0 {PINK}; }}
.stButton button[kind="primary"]:hover {{ background: #E2FF7A; color: #0B0F1A; }}
.stButton button[kind="secondary"] {{ border-radius: 0; font-family: 'JetBrains Mono', monospace; }}
[class*="st-key-box"] {{ background: rgba(20,27,45,.82); border: 1px solid #222C47 !important; border-radius: 4px; backdrop-filter: blur(6px); }}

.top {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 2rem; }}
.tag {{ font-family: 'JetBrains Mono', monospace; font-size: .75rem; color: #0B0F1A; background: {LIME}; display: inline-block; padding: 2px 8px; letter-spacing: .12em; }}
.title {{ font-family: 'Space Grotesk', sans-serif; font-weight: 700; font-size: clamp(3rem, 7vw, 6.2rem); line-height: .95; letter-spacing: -.04em; margin: .8rem 0 .6rem; color: #F4F6FB; }}
.title .m {{ color: {LIME}; }}
.title .r {{ color: transparent; -webkit-text-stroke: 2px {PINK}; }}
.title .paren {{ font-family: 'JetBrains Mono', monospace; font-weight: 400; font-size: .55em; color: {DIM}; letter-spacing: 0; }}
.title .arrow {{ font-weight: 400; color: {DIM}; padding: 0 .15em; }}
.lede {{ color: #B9C1D6; font-size: 1.08rem; max-width: 640px; }}
.prompt {{ font-family: 'JetBrains Mono', monospace; font-size: .95rem; color: #D7DDEA; margin-top: 1.1rem; background: #070A12; border: 1px solid #222C47; padding: 10px 14px; display: inline-block; }}
.prompt .dollar {{ color: {LIME}; }}
.prompt .flag {{ color: {CYAN}; }}
.cursor {{ display: inline-block; width: 9px; height: 1.05em; background: {LIME}; vertical-align: -2px; margin-left: 4px; animation: blink 1s steps(1) infinite; }}
@keyframes blink {{ 50% {{ opacity: 0; }} }}
.author {{ font-family: 'JetBrains Mono', monospace; font-size: .8rem; color: {DIM}; text-align: right; line-height: 1.7; border-right: 3px solid {PINK}; padding-right: 12px; white-space: nowrap; }}
.author b {{ color: #F4F6FB; font-weight: 600; }}

.section {{ font-family: 'JetBrains Mono', monospace; font-size: .78rem; letter-spacing: .18em; text-transform: uppercase; color: {DIM}; margin: 1.6rem 0 .6rem; display: flex; align-items: center; gap: 12px; }}
.section:after {{ content: ""; flex: 1; height: 1px; background: linear-gradient(90deg, #2A3557, transparent); }}
.section b {{ color: {LIME}; font-weight: 800; }}

.ticker {{ display: flex; border: 1px solid #222C47; background: rgba(7,10,18,.85); overflow-x: auto; }}
.tick {{ flex: 1; padding: 14px 18px; border-right: 1px dashed #26314F; min-width: 140px; }}
.tick:last-child {{ border-right: none; }}
.tick span {{ font-family: 'JetBrains Mono', monospace; font-size: .68rem; letter-spacing: .14em; color: {DIM}; text-transform: uppercase; }}
.tick div {{ font-family: 'JetBrains Mono', monospace; font-weight: 800; font-size: 1.9rem; color: #F4F6FB; line-height: 1.2; }}
.tick div small {{ font-size: .9rem; color: {DIM}; font-weight: 400; }}

.board-wrap {{ overflow-x: auto; }}
.board {{ display: grid; grid-template-columns: 1.25fr 1fr 1fr 1fr 1fr; gap: 0; min-width: 1150px; border: 1px solid #222C47; background: rgba(7,10,18,.7); }}
.col {{ border-right: 1px solid #1C2540; padding: 0 0 14px; position: relative; }}
.col:last-child {{ border-right: none; }}
.col-head {{ padding: 12px 14px; border-bottom: 1px solid #1C2540; font-family: 'JetBrains Mono', monospace; display: flex; align-items: baseline; gap: 10px; background: rgba(20,27,45,.6); }}
.col-head .n {{ color: {LIME}; font-weight: 800; font-size: 1.15rem; }}
.col-head .t {{ color: #F4F6FB; font-weight: 600; letter-spacing: .08em; }}
.col-head .s {{ color: {DIM}; font-size: .72rem; margin-left: auto; }}
.col:not(:last-child) .col-head:after {{ content: "▶"; position: absolute; right: -8px; top: 13px; color: {LIME}; font-size: .7rem; z-index: 2; }}
.grp {{ padding: 10px 12px 2px; }}
.grp-label {{ font-family: 'JetBrains Mono', monospace; font-size: .7rem; color: {DIM}; margin-bottom: 6px; }}
.grp-label i {{ font-style: normal; display: inline-block; width: 8px; height: 8px; margin-right: 6px; background: var(--c); }}
.raw {{ font-family: 'JetBrains Mono', monospace; font-size: .8rem; color: #C9D1E4; background: #0E1424; border-left: 2px solid {LIME}; padding: 8px 10px; white-space: pre-wrap; word-break: break-word; max-height: 120px; overflow: hidden; }}
.chip {{ display: inline-flex; align-items: center; gap: 6px; font-family: 'JetBrains Mono', monospace; font-size: .76rem; color: #E6EAF2; border: 1px solid var(--c); background: color-mix(in srgb, var(--c) 12%, transparent); padding: 2px 7px; margin: 0 5px 6px 0; }}
.chip b {{ color: var(--c); font-weight: 800; }}
.chip.more {{ --c: #3A4566; color: {DIM}; }}
.chip.big {{ font-size: .9rem; padding: 4px 10px; }}
.ghost {{ font-family: 'JetBrains Mono', monospace; color: #3F4A6B; font-size: .8rem; padding: 14px; }}
.legend {{ font-family: 'JetBrains Mono', monospace; font-size: .74rem; color: {DIM}; margin-top: 8px; display: flex; gap: 16px; flex-wrap: wrap; }}
.legend i {{ display: inline-block; width: 10px; height: 10px; margin-right: 6px; background: var(--c); vertical-align: -1px; }}

.lane {{ margin: 10px 0 16px; }}
.lane-top {{ display: flex; justify-content: space-between; font-family: 'JetBrains Mono', monospace; font-size: .8rem; color: #D7DDEA; margin-bottom: 6px; }}
.lane-top span:last-child {{ color: {DIM}; }}
.lane-bar {{ height: 14px; background: #0E1424; border: 1px solid #222C47; }}
.lane-bar div {{ height: 100%; background: repeating-linear-gradient(135deg, var(--c) 0 8px, color-mix(in srgb, var(--c) 70%, #000) 8px 16px); }}

.ascii {{ display: flex; flex-wrap: wrap; gap: 6px; margin: 10px 0; }}
.ascii div {{ border: 1px solid #2A3557; background: #0E1424; text-align: center; min-width: 44px; padding: 4px 6px; font-family: 'JetBrains Mono', monospace; }}
.ascii div b {{ display: block; color: #F4F6FB; font-size: 1.1rem; }}
.ascii div span {{ color: {DIM}; font-size: .72rem; }}
.verdict {{ font-family: 'JetBrains Mono', monospace; font-size: .92rem; color: #D7DDEA; }}
.verdict b {{ color: var(--c); }}

.log {{ font-family: 'JetBrains Mono', monospace; font-size: .8rem; background: #070A12; border: 1px solid #222C47; padding: 12px 14px; line-height: 1.75; color: #C9D1E4; }}
.log .ts {{ color: {DIM}; }}
.log .ok {{ color: {LIME}; }}
.log .k {{ color: {CYAN}; }}
</style>
""")


# ── Pipeline execution (timed per stage) ──────────────────────────────────────
def execute(input_dir: str, output_dir: str, num_reducers: int) -> dict:
    paths = sorted(
        os.path.join(input_dir, f) for f in os.listdir(input_dir) if f.endswith(".txt")
    )
    if not paths:
        raise FileNotFoundError(f"No .txt files found in '{input_dir}'")

    raw = {}
    for p in paths:
        with open(p, encoding="utf-8") as f:
            raw[os.path.basename(p)] = f.read()

    os.makedirs(output_dir, exist_ok=True)
    for old in glob.glob(os.path.join(output_dir, "reducer_*.txt")):
        os.remove(old)

    timings = {}
    t = time.perf_counter()
    map_outputs = run_mappers(paths)
    timings["map + combine"] = time.perf_counter() - t

    t = time.perf_counter()
    reducer_inputs = shuffle_and_sort(map_outputs, num_reducers)
    timings["partition + shuffle"] = time.perf_counter() - t

    t = time.perf_counter()
    results = {rid: reduce_fn(g, rid, output_dir) for rid, g in enumerate(reducer_inputs)}
    timings["reduce"] = time.perf_counter() - t

    return {
        "splits": list(raw),
        "raw": raw,
        "map_outputs": map_outputs,
        "reducer_inputs": reducer_inputs,
        "results": results,
        "timings": timings,
        "num_reducers": num_reducers,
        "source": input_dir if input_dir == "input" else "uploads",
    }


# ── Header ────────────────────────────────────────────────────────────────────
num_reducers = st.session_state.get("reducers") or 2
input_flag = "uploads/" if str(st.session_state.get("source", "")).startswith("upload") else "input/"
render(f"""
<div class="top">
    <div>
        <span class="tag">CIS4103 // BONUS LAB</span>
        <div class="title"><span class="m">map</span><span class="paren">()</span><span class="arrow">→</span><span class="r">reduce</span><span class="paren">()</span></div>
        <div class="lede">A word-count engine hand-built in Python. No Hadoop, no Spark:
        just threads, a hash function and a lot of counting. Run it and follow every
        word from raw text to final tally.</div>
        <div class="prompt"><span class="dollar">$</span> python main.py <span class="flag">--input</span> {input_flag}
        <span class="flag">--reducers</span> {num_reducers}<span class="cursor"></span></div>
    </div>
    <div class="author"><b>Farida Obied</b><br>Big Data Analytics<br>Lecture 06 · MapReduce</div>
</div>
""")


# ── Controls ──────────────────────────────────────────────────────────────────
render('<div class="section"><b>00</b> configure</div>')
with st.container(border=True, key="box_controls"):
    c_src, c_red, c_run, c_clear = st.columns([2.2, 1.6, 1, 0.8], vertical_alignment="bottom")
    with c_src:
        source = st.segmented_control(
            "Input", ["sample claim notes", "upload .txt files"], default="sample claim notes", key="source"
        ) or "sample claim notes"
    with c_red:
        st.segmented_control("Reducers", [1, 2, 3, 4], default=2, key="reducers")
    with c_run:
        run_clicked = st.button("▶ RUN", type="primary", width="stretch")
    with c_clear:
        if st.button("reset", width="stretch"):
            st.session_state.pop("data", None)
    uploaded = None
    if source.startswith("upload"):
        uploaded = st.file_uploader(
            "Each file becomes one split", type=["txt"], accept_multiple_files=True
        )

if run_clicked:
    input_dir = None
    if uploaded:
        input_dir = tempfile.mkdtemp()
        for uf in uploaded:
            with open(os.path.join(input_dir, os.path.basename(uf.name)), "wb") as out:
                out.write(uf.getvalue())
    elif source.startswith("upload"):
        st.warning("Upload at least one .txt file first.")
    else:
        input_dir = "input"
    if input_dir:
        try:
            st.session_state["data"] = execute(input_dir, "output", num_reducers)
        except FileNotFoundError as e:
            st.error(str(e))

data = st.session_state.get("data")


# ── Ticker ────────────────────────────────────────────────────────────────────
if data:
    n = data["num_reducers"]
    tokens = sum(c for pairs in data["map_outputs"] for _, c in pairs)
    pairs_after = sum(len(p) for p in data["map_outputs"])
    unique = sum(len(r) for r in data["results"].values())
    ms = sum(data["timings"].values()) * 1000
    saved = (1 - pairs_after / tokens) * 100 if tokens else 0
    ticks = [
        ("splits", len(data["splits"]), "files"),
        ("tokens", f"{tokens:,}", "emitted"),
        ("after combine", f"{pairs_after:,}", f"−{saved:.0f}%"),
        ("unique keys", f"{unique:,}", ""),
        ("reducers", n, ""),
        ("wall time", f"{ms:.2f}", "ms"),
    ]
else:
    ticks = [(k, "—", "") for k in ["splits", "tokens", "after combine", "unique keys", "reducers", "wall time"]]
render(
    '<div class="ticker">'
    + "".join(f'<div class="tick"><span>{k}</span><div>{v} <small>{s}</small></div></div>' for k, v, s in ticks)
    + "</div>"
)


# ── Trace board ───────────────────────────────────────────────────────────────
render('<div class="section"><b>01</b> trace every word</div>')

heads = [
    ("01", "SPLIT", "raw text"),
    ("02", "MAP", "(word, 1)"),
    ("03", "COMBINE", "local sums"),
    ("04", "SHUFFLE", "grouped by key"),
    ("05", "REDUCE", "final counts"),
]


def col(i, body):
    num, title, sub = heads[i]
    return (
        f'<div class="col"><div class="col-head"><span class="n">{num}</span>'
        f'<span class="t">{title}</span><span class="s">{sub}</span></div>{body}</div>'
    )


if data:
    n = data["num_reducers"]
    split_html, map_html, comb_html = "", "", ""
    for name, pairs in zip(data["splits"], data["map_outputs"]):
        text = data["raw"][name]
        preview = text if len(text) <= 260 else text[:260] + " …"
        emitted = [(w, 1) for w in (normalize(t) for t in text.split()) if w]
        split_html += f'<div class="grp"><div class="grp-label">{esc(name)}</div><div class="raw">{esc(preview)}</div></div>'
        map_html += f'<div class="grp"><div class="grp-label">mapper ← {esc(name)}</div>{chips(emitted, n)}</div>'
        comb = sorted(pairs, key=lambda p: (-p[1], p[0]))
        comb_html += f'<div class="grp"><div class="grp-label">{len(emitted)} → {len(pairs)} pairs</div>{chips(comb, n)}</div>'

    shuf_html, red_html = "", ""
    for rid, groups in enumerate(data["reducer_inputs"]):
        label = f'<i style="--c:{rcolor(rid)}"></i>reducer {rid}'
        grouped = [(w, "[" + ",".join(map(str, c)) + "]") for w, c in groups]
        shuf_html += f'<div class="grp"><div class="grp-label">{label} · {len(groups)} keys</div>{chips(grouped, n, color_of=lambda _w, r=rid: rcolor(r))}</div>'
        final = data["results"][rid]
        red_html += (
            f'<div class="grp"><div class="grp-label">{label} → output/reducer_{rid}.txt</div>'
            + chips(final, n, color_of=lambda _w, r=rid: rcolor(r)).replace('class="chip"', 'class="chip big"')
            + "</div>"
        )
    body = [split_html, map_html, comb_html, shuf_html, red_html]
else:
    body = ['<div class="ghost">waiting for ▶ RUN …</div>'] * 5

render(f'<div class="board-wrap"><div class="board">{"".join(col(i, b) for i, b in enumerate(body))}</div></div>')
legend_n = data["num_reducers"] if data else num_reducers
render(
    '<div class="legend">chip colour = destination reducer:'
    + "".join(f'<span><i style="--c:{rcolor(r)}"></i>reducer {r}</span>' for r in range(legend_n))
    + "</div>"
)

if not data:
    st.stop()


# ── Analysis row ──────────────────────────────────────────────────────────────
render('<div class="section"><b>02</b> what came out</div>')
n = data["num_reducers"]
all_results = [(w, c, rid) for rid, r in data["results"].items() for w, c in r]
counts = {w: c for w, c, _ in all_results}

c_freq, c_load = st.columns([1.4, 1])
with c_freq:
    with st.container(border=True, key="box_freq"):
        st.markdown("**Frequency leaderboard**")
        top = sorted(all_results, key=lambda x: (-x[1], x[0]))[:15]
        df = pd.DataFrame(top, columns=["word", "count", "reducer"])
        df["reducer"] = "reducer " + df["reducer"].astype(str)
        domain = [f"reducer {r}" for r in range(n)]
        base = alt.Chart(df).encode(
            y=alt.Y("word:N", sort=None, title=None,
                    axis=alt.Axis(labelFont="JetBrains Mono", labelColor="#D7DDEA", labelFontSize=12, ticks=False, domain=False)),
            x=alt.X("count:Q", title=None, axis=None),
        )
        bars = base.mark_bar(height=16).encode(
            color=alt.Color("reducer:N", scale=alt.Scale(domain=domain, range=[rcolor(r) for r in range(n)]), legend=None),
            tooltip=["word", "count", "reducer"],
        )
        labels = base.mark_text(align="left", dx=6, font="JetBrains Mono", color="#F4F6FB", fontWeight="bold").encode(text="count:Q")
        st.altair_chart(
            (bars + labels).properties(height=max(26 * len(df), 120))
            .configure_view(strokeWidth=0).configure(background="transparent"),
            width="stretch",
        )

with c_load:
    with st.container(border=True, key="box_load"):
        st.markdown("**Reducer load**")
        total = sum(c for _, c, _ in all_results) or 1
        lanes = ""
        for rid, r in data["results"].items():
            share = sum(c for _, c in r) / total * 100
            lanes += f"""
            <div class="lane">
                <div class="lane-top"><span>reducer_{rid}.txt</span><span>{len(r)} keys · {sum(c for _, c in r)} words · {share:.0f}%</span></div>
                <div class="lane-bar"><div style="--c:{rcolor(rid)};width:{share:.1f}%"></div></div>
            </div>
            """
        render(lanes)
        dl_cols = st.columns(n)
        for rid, dc in enumerate(dl_cols):
            with dc:
                content = "".join(f"{w}\t{c}\n" for w, c in data["results"][rid])
                st.download_button(f"↓ reducer_{rid}", content, file_name=f"reducer_{rid}.txt", width="stretch")


# ── Partition lab + run log ───────────────────────────────────────────────────
render('<div class="section"><b>03</b> under the hood</div>')
c_lab, c_log = st.columns([1.4, 1])

with c_lab:
    with st.container(border=True, key="box_lab"):
        st.markdown("**Partition lab:** why does a word land where it does?")
        q = st.text_input("word", placeholder="type any word, e.g. water", label_visibility="collapsed")
        word = normalize(q) if q else ""
        if word:
            codes = [ord(ch) for ch in word]
            total_ascii = sum(codes)
            rid = partition(word, n)
            boxes = "".join(f"<div><b>{esc(ch)}</b><span>{code}</span></div>" for ch, code in zip(word[:24], codes[:24]))
            more = f"<div><b>…</b><span>+{len(word) - 24}</span></div>" if len(word) > 24 else ""
            seen = f"seen <b>{counts[word]}×</b> in this run" if word in counts else "not in this run's data"
            render(f"""
            <div class="ascii">{boxes}{more}</div>
            <div class="verdict" style="--c:{rcolor(rid)}">
                Σ ascii = {total_ascii} &nbsp;→&nbsp; {total_ascii} mod {n} = <b>{total_ascii % n}</b>
                &nbsp;→&nbsp; <b>reducer {rid}</b> &nbsp;·&nbsp; {seen}
            </div>
            """)

with c_log:
    with st.container(border=True, key="box_log"):
        st.markdown("**Run log**")
        elapsed = 0.0
        lines = [f'<span class="ts">[  0.000 ms]</span> <span class="k">start</span> source={esc(data["source"])} splits={len(data["splits"])} reducers={n}']
        notes = {
            "map + combine": f"{len(data['splits'])} threads → {sum(len(p) for p in data['map_outputs'])} local pairs",
            "partition + shuffle": "keys routed by Σascii mod " + str(n),
            "reduce": f"{sum(len(r) for r in data['results'].values())} keys summed",
        }
        for stage, secs in data["timings"].items():
            elapsed += secs * 1000
            lines.append(f'<span class="ts">[{elapsed:7.3f} ms]</span> <span class="k">{stage}</span> {notes[stage]}')
        for rid, r in data["results"].items():
            lines.append(f'<span class="ts">[{elapsed:7.3f} ms]</span> wrote output/reducer_{rid}.txt ({len(r)} keys)')
        lines.append(f'<span class="ts">[{elapsed:7.3f} ms]</span> <span class="ok">✔ done</span>')
        render('<div class="log">' + "<br>".join(lines).replace("  ", "&nbsp;&nbsp;") + "</div>")
