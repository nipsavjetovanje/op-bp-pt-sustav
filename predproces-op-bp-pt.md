# Pred-proces: generiranje OP, BP i PT prije glavnog programa

Rješenje bermudskog trokuta (aktivnosti-budžet-tim) na ulazu, ne naknadnom
validacijom.

---

## 1. Ideja

Umjesto da OP.docx i BP.xlsx budu ručno pisani, fiksni ulazni predlošci koje
glavni program (6 faza) samo čita, uvodi se **zaseban pred-korak** koji te tri
DP datoteke (OP, BP) plus novu PT (projektni tim) **generira** iz egzaktnih
izvora — CV, platna lista, natječajni prilozi. Time su OP/BP/PT međusobno
usklađeni po konstrukciji, ne po naknadnoj provjeri.

## 2. Ulazni dokumenti pred-procesa

| Oznaka | Dokument | Format | Napomena |
|---|---|---|---|
| A | Upitnik OP | Word/web, slobodan tekst (popunjava klijent) | Naziv, Opis poslovanja/tržišta, Opis budućeg projekta, Ciljano tržište, Faze projekta (slobodan tekst), Oprema prijavitelja. Bez aktivnosti i tima — ti su zasebno. |
| B | Popis aktivnosti | Fiksan, taksativan | Konzultant unosi iz UP/natječaja. Mora postojati prije pokretanja PT modula. |
| C | CV djelatnika | Po članu tima | Izvor kompetencija |
| D | Platna lista | — | Izvor bruto plaće |
| E | Metodologija izračuna satnice | Prilog natječaja (propisan) | Jedini izvor formule za satnicu |
| F | BL + UP | — | Vokabular uloga + dopuštene kategorije troška s % limitima + max iznos potpore |

## 3. Tok obrade

1. **PT** — CV kompetencije matchaju na aktivnosti → član + uloga + opis rada
   po aktivnosti + sat rada (iz opsega, ne iz budžeta) × satnica (2 decimale)
   = trošak. Obavezna sekcija: doslovan citat metodologije satnice
   (deterministički provjeren).
2. **OP** — upitnik + taksativne aktivnosti (deterministički provjerene) +
   sažetak tima iz PT-a → koherentan narativ.
3. **BP** — timski redovi iz PT-a (deterministički agregirani) + slobodno
   unesene ostale stavke (AI klasificira u kategoriju iz UP-a).
4. **Post-validacija** — % po kategoriji i max iznos potpore, oboje
   deterministički izračunato, samo upozorenje bez auto-ispravka.
5. **Izlaz** — OP.docx + BP.xlsx + PT.docx.

## 4. Implementacija

Streamlit web aplikacija (`app/main.py`), AI logika preko Anthropic API-ja
(`pt_generator.py`, `op_generator.py`, `bp_generator.py`), renderiranje
izlaznih datoteka (`pt_docx.py`, `op_docx.py`, `bp_xlsx.py`). Sve kritične
provjere (verbatim citat, identičnost popisa aktivnosti, % limiti, max iznos
potpore) su deterministički Python kod, ne AI.
