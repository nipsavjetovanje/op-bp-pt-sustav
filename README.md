# Pred-proces OP/BP/PT — Nikolić i partneri

Web aplikacija koja generira obrasce OP (Opis projekta), BP (proračun) i PT
(projektni tim) prije glavnog sustava za pisanje EU prijava. Umjesto ručnog
pisanja, ovi se dokumenti generiraju iz CV-a, platne liste i natječajnih
priloga — pa su međusobno usklađeni ("bermudski trokut" aktivnosti-budžet-tim
riješen na ulazu).

## Kako se koristi (bez terminala, bez kodiranja)

1. Otvori link aplikacije (Streamlit Cloud)
2. Tab 1: popuni upitnik (naziv, opis, tržište, faze projekta...)
3. Tab 2: zalijepi taksativan popis aktivnosti iz natječaja
4. Tab 3: učitaj CV-eve, platnu listu, metodologiju satnice, BL, UP
5. Tab 4: klikni redom "Generiraj PT" → "Generiraj OP" → "Generiraj BP",
   preuzmi gotove datoteke

## Tehnički detalji (za buduće održavanje)

- `app/main.py` — Streamlit sučelje
- `app/extract.py` — čitanje PDF/DOCX/XLSX uploada
- `app/pt_generator.py`, `app/op_generator.py`, `app/bp_generator.py` — AI
  logika (Anthropic API), svaka s determinističkom post-validacijom
  (doslovnost citata, identičnost popisa aktivnosti, % limiti troška, max
  iznos potpore — sve provjereno u Pythonu, ne prepušteno modelu)
- `app/pt_docx.py`, `app/op_docx.py`, `app/bp_xlsx.py` — generiranje izlaznih
  datoteka
- `app/config.py` — API ključ se čita iz Streamlit Cloud "Secrets" (`st.secrets`)
  u produkciji, ili lokalnog `.env` (nikad u repozitoriju — vidi `.gitignore`)

### Secrets (Streamlit Cloud → App settings → Secrets)

```
ANTHROPIC_API_KEY = "sk-ant-..."
```

### Arhitektura i dizajnerske odluke

Vidi `docs/predproces-op-bp-pt.md` (puna arhitektura, pravila i rationale).
