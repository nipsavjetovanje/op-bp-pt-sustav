import streamlit as st
from pathlib import Path

from extract import extract_text
from pt_generator import generate_pt
from pt_docx import render_pt_docx
from op_generator import generate_op
from op_docx import render_op_docx
from bp_generator import generate_bp
from bp_xlsx import render_bp_xlsx
from budget_fit import uskladi_s_budzetom

OUTPUTS_DIR = Path(__file__).resolve().parent.parent / "outputs"
OUTPUTS_DIR.mkdir(exist_ok=True)

st.set_page_config(page_title="Pred-proces OP/BP/PT — Nikolić i partneri", page_icon="📋", layout="centered")

if "data" not in st.session_state:
    st.session_state.data = {
        "naziv_projekta": "",
        "opis_poslovanja": "",
        "opis_buduceg_projekta": "",
        "ciljano_trziste": "",
        "faze_projekta": "",
        "oprema": "",
        "trajanje_projekta_mjeseci": 0.0,
        "aktivnosti_tekst": "",
        "cv_files": [],
        "platna_lista_file": None,
        "satnica_metodologija_file": None,
        "bl_file": None,
        "up_file": None,
    }

st.title("📋 Pred-proces: OP, BP, PT")
st.caption("Nikolić i partneri — generiranje ulaznih dokumenata prije glavnog programa")

tab1, tab2, tab3, tab4 = st.tabs(["1. Upitnik OP", "2. Popis aktivnosti", "3. Tim i natječaj", "4. Generiraj"])

with tab1:
    st.subheader("Upitnik za izradu Opisa projekta (OP)")
    d = st.session_state.data
    d["naziv_projekta"] = st.text_input("Naziv projekta", d["naziv_projekta"])
    d["opis_poslovanja"] = st.text_area("Opis poslovanja / tržišta", d["opis_poslovanja"], height=120)
    d["opis_buduceg_projekta"] = st.text_area("Opis budućeg projekta (djelatnost, proširenje)", d["opis_buduceg_projekta"], height=120)
    d["ciljano_trziste"] = st.text_area("Ciljano tržište", d["ciljano_trziste"], height=100)
    d["faze_projekta"] = st.text_area("Faze projekta (slobodan tekst, kronologija)", d["faze_projekta"], height=150)
    d["oprema"] = st.text_area("Oprema prijavitelja (postojeća)", d["oprema"], height=100)
    d["trajanje_projekta_mjeseci"] = st.number_input(
        "Trajanje projekta (mjeseci)", min_value=0.0, value=float(d["trajanje_projekta_mjeseci"]), step=1.0,
        help="Iz natječaja. Koristi se za izračun % rada na projektu (FTE) po članu tima u PT obrascu.",
    )

with tab2:
    st.subheader("Popis aktivnosti (fiksan, iz natječaja)")
    st.caption("Taksativno — jedna aktivnost po retku. Ovaj popis se ne mijenja, izmišlja ni spaja kasnije u procesu.")
    st.session_state.data["aktivnosti_tekst"] = st.text_area(
        "Aktivnosti projekta", st.session_state.data["aktivnosti_tekst"], height=200,
        placeholder="1. Izrada prototipa (...)\n2. Demonstracija tehničke izvedivosti (...)\n..."
    )

with tab3:
    st.subheader("Projektni tim i natječajni prilozi")
    st.session_state.data["cv_files"] = st.file_uploader(
        "CV djelatnika (po članu tima)", type=["pdf", "docx"], accept_multiple_files=True
    )
    st.session_state.data["platna_lista_file"] = st.file_uploader("Platna lista", type=["pdf", "xlsx", "docx"])
    st.session_state.data["satnica_metodologija_file"] = st.file_uploader(
        "Metodologija izračuna satnice (prilog natječaja)", type=["pdf", "docx"]
    )
    st.session_state.data["bl_file"] = st.file_uploader("BL (bodovna lista)", type=["pdf"])
    st.session_state.data["up_file"] = st.file_uploader("UP (upute za prijavitelje)", type=["pdf"])

with tab4:
    st.subheader("Generiranje OP / BP / PT")
    d = st.session_state.data
    missing = []
    if not d["naziv_projekta"]:
        missing.append("Naziv projekta")
    if not d["aktivnosti_tekst"].strip():
        missing.append("Popis aktivnosti")
    if not d["cv_files"]:
        missing.append("CV djelatnika")
    if not d["satnica_metodologija_file"]:
        missing.append("Metodologija izračuna satnice")

    if missing:
        st.warning("Nedostaje prije generiranja: " + ", ".join(missing))

    if st.button("Generiraj PT", type="primary", disabled=bool(missing)):
        with st.spinner("Čitam dokumente i generiram PT (ovo može potrajati do minute)..."):
            try:
                cv_items = [(f.name, extract_text(f.name, f.read())) for f in d["cv_files"]]
                platna_lista_text = (
                    extract_text(d["platna_lista_file"].name, d["platna_lista_file"].read())
                    if d["platna_lista_file"] else ""
                )
                satnica_text = extract_text(
                    d["satnica_metodologija_file"].name, d["satnica_metodologija_file"].read()
                )
                uloga_vok = ""
                if d["bl_file"]:
                    uloga_vok += extract_text(d["bl_file"].name, d["bl_file"].read()) + "\n"
                if d["up_file"]:
                    uloga_vok += extract_text(d["up_file"].name, d["up_file"].read())

                pt_data, warnings = generate_pt(
                    aktivnosti_text=d["aktivnosti_tekst"],
                    cv_items=cv_items,
                    platna_lista_text=platna_lista_text,
                    satnica_metodologija_text=satnica_text,
                    uloga_vokabular_text=uloga_vok,
                )

                out_path = OUTPUTS_DIR / "PT_obrazac.docx"
                summary = render_pt_docx(
                    pt_data, str(out_path),
                    trajanje_mjeseci=d["trajanje_projekta_mjeseci"] or None,
                )

                st.session_state["pt_result"] = {
                    "path": str(out_path),
                    "warnings": warnings,
                    "summary": summary,
                    "n_members": len(pt_data.get("members", [])),
                    "pt_data": pt_data,
                }
            except Exception as e:
                st.error(f"Greška pri generiranju: {e}")

    pt_result = st.session_state.get("pt_result")
    if pt_result:
        for w in pt_result["warnings"]:
            st.warning(w)
        st.success(
            f"PT generiran — {pt_result['n_members']} članova tima, "
            f"ukupno {pt_result['summary']['ukupno_sati']} sati, "
            f"{pt_result['summary']['ukupan_trosak']:.2f} EUR."
        )
        with open(pt_result["path"], "rb") as f:
            st.download_button("⬇ Preuzmi PT_obrazac.docx", f, file_name="PT_obrazac.docx")

    st.divider()
    st.subheader("Korak 2 — OP")
    if not pt_result:
        st.info("Prvo generiraj PT (korak 1) — OP koristi sažetak tima iz PT-a.")
    if st.button("Generiraj OP", type="primary", disabled=not pt_result):
        with st.spinner("Generiram OP..."):
            try:
                op_data, op_warnings = generate_op(
                    upitnik=d,
                    aktivnosti_text=d["aktivnosti_tekst"],
                    pt_data=pt_result["pt_data"],
                )
                op_path = OUTPUTS_DIR / "OP_obrazac.docx"
                render_op_docx(op_data, str(op_path))
                st.session_state["op_result"] = {"path": str(op_path), "warnings": op_warnings}
            except Exception as e:
                st.error(f"Greška pri generiranju OP-a: {e}")

    op_result = st.session_state.get("op_result")
    if op_result:
        for w in op_result["warnings"]:
            st.warning(w)
        if not op_result["warnings"]:
            st.success("OP generiran — popis aktivnosti potvrđeno identičan izvornom.")
        with open(op_result["path"], "rb") as f:
            st.download_button("⬇ Preuzmi OP_obrazac.docx", f, file_name="OP_obrazac.docx")

    st.divider()
    st.subheader("Korak 3 — BP")
    if not pt_result:
        st.info("Prvo generiraj PT (korak 1) — BP koristi troškove tima iz PT-a.")
    st.caption("Ostale stavke troška (oprema, usluge, materijal...) — slobodan unos naziva i iznosa, sustav ih automatski razvrstava u kategoriju prema UP-u.")

    if "ostale_stavke_df" not in st.session_state:
        import pandas as pd
        st.session_state.ostale_stavke_df = pd.DataFrame(
            [{"Naziv": "", "Iznos (EUR)": 0.0}]
        )
    st.session_state.ostale_stavke_df = st.data_editor(
        st.session_state.ostale_stavke_df, num_rows="dynamic", key="ostale_stavke_editor",
        use_container_width=True,
    )

    if st.button("Generiraj BP", type="primary", disabled=not pt_result):
        with st.spinner("Klasificiram troškove i generiram BP..."):
            try:
                up_text = extract_text(d["up_file"].name, d["up_file"].read()) if d["up_file"] else ""
                rows = st.session_state.ostale_stavke_df.to_dict("records")
                ostale_stavke = [
                    {"naziv": r["Naziv"], "iznos": r["Iznos (EUR)"]}
                    for r in rows if str(r.get("Naziv", "")).strip() and r.get("Iznos (EUR)", 0)
                ]
                bp_data, bp_warnings = generate_bp(pt_result["pt_data"], ostale_stavke, up_text)
                bp_path = OUTPUTS_DIR / "BP_obrazac.xlsx"
                render_bp_xlsx(bp_data, str(bp_path), bp_warnings)
                st.session_state["bp_result"] = {"path": str(bp_path), "warnings": bp_warnings, "bp_data": bp_data}
            except Exception as e:
                st.error(f"Greška pri generiranju BP-a: {e}")

    bp_result = st.session_state.get("bp_result")
    if bp_result:
        for w in bp_result["warnings"]:
            if w.startswith("UPOZORENJE"):
                st.warning(w)
            else:
                st.caption(w)
        with open(bp_result["path"], "rb") as f:
            st.download_button("⬇ Preuzmi BP_obrazac.xlsx", f, file_name="BP_obrazac.xlsx")

    st.divider()
    st.subheader("Korak 4 — Uskladi trošak osoblja s budžetom")
    st.caption(
        "Proporcionalno skalira sve satove tima (satnice ostaju fiksne) tako da trošak osoblja + "
        "neizravni troškovi stanu u max. iznos potpore iz UP-a, umanjen za sigurnosnu marginu. "
        "Dodaje i % rada na projektu (FTE) po članu tima."
    )
    col1, col2 = st.columns(2)
    with col1:
        postotak_neizravnih = st.number_input(
            "Postotak neizravnih troškova (%)", min_value=0.0, max_value=100.0, value=15.0, step=1.0,
        )
    with col2:
        margina = st.number_input("Sigurnosna margina (EUR)", min_value=0.0, value=60.0, step=10.0)

    uskladi_disabled = not bp_result or not (d["trajanje_projekta_mjeseci"] or 0) > 0
    if not bp_result:
        st.info("Prvo generiraj BP (korak 3).")
    elif not (d["trajanje_projekta_mjeseci"] or 0) > 0:
        st.info("Upiši trajanje projekta (mjeseci) u Tab 1 — potrebno za izračun % rada po članu.")

    if st.button("⚖️ Uskladi s budžetom", disabled=uskladi_disabled):
        with st.spinner("Preračunavam satove i troškove..."):
            try:
                novi_pt, novi_bp, uskladi_warnings = uskladi_s_budzetom(
                    pt_result["pt_data"], bp_result["bp_data"],
                    trajanje_mjeseci=d["trajanje_projekta_mjeseci"],
                    postotak_neizravnih=postotak_neizravnih,
                    margina=margina,
                )
                pt_path = OUTPUTS_DIR / "PT_obrazac.docx"
                pt_summary = render_pt_docx(novi_pt, str(pt_path), trajanje_mjeseci=d["trajanje_projekta_mjeseci"])
                bp_path = OUTPUTS_DIR / "BP_obrazac.xlsx"
                render_bp_xlsx(novi_bp, str(bp_path), uskladi_warnings)

                pt_result["pt_data"] = novi_pt
                pt_result["summary"] = pt_summary
                pt_result["path"] = str(pt_path)
                bp_result["bp_data"] = novi_bp
                bp_result["warnings"] = uskladi_warnings
                bp_result["path"] = str(bp_path)
                st.session_state["pt_result"] = pt_result
                st.session_state["bp_result"] = bp_result
                st.success("Satovi i troškovi usklađeni s budžetom — PT i BP su regenerirani (preuzmi ponovno gore).")
            except Exception as e:
                st.error(f"Greška pri usklađivanju s budžetom: {e}")

st.divider()
st.caption("Verzija u izradi — PT, OP i BP moduli rade. Slijedi spajanje u cjelinu i Streamlit Cloud deployment.")
