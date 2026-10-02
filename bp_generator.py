"""BP modul: PT troškovi tima + slobodno unesene ostale stavke -> strukturirani BP (auto-klasifikacija
po kategorijama iz UP-a) + deterministička post-validacija (% po kategoriji, max iznos potpore)."""
import json
import re

from anthropic import Anthropic
from config import ANTHROPIC_API_KEY, MODEL

SYSTEM_PROMPT = """Ti si asistent za klasifikaciju troškova u obrascu BP (proračun/troškovnik) za
hrvatske EU natječaje. Dobivaš tekst natječajnih Uputa za prijavitelje (UP) te popis stavki troška
(troškovi tima iz PT obrasca + ostale stavke koje je konzultant slobodno unio). Tvoj zadatak:

1. Iz UP teksta izvuci popis DOPUŠTENIH KATEGORIJA TROŠKA. Za svaku kategoriju, ako je UP eksplicitno
   navodi, izvuci: maksimalni dopušteni udio te kategorije u ukupnom proračunu (u %, ako je propisan)
   i intenzitet potpore / postotak financiranja za tu kategoriju (u %, ako je propisan — ako UP
   propisuje jedinstven postotak financiranja za cijeli projekt, primijeni ga na sve kategorije).
   Ako UP ne propisuje neki od ovih podataka, stavi null — NE IZMIŠLJAJ brojke.
2. Izvuci MAKSIMALNI UKUPNI IZNOS POTPORE (bespovratnih sredstava) za cijeli projekt, ako je naveden
   u UP-u. Ako nije, stavi null.
3. Za SVAKU dostavljenu stavku (i troškove tima i ostale stavke) odredi kojoj kategoriji iz popisa
   pripada (najbliže po sadržaju/opisu), i naznači koji postotak financiranja se na nju primjenjuje.
   Ne mijenjaj iznose stavki — samo ih klasificiraj.

Odgovori ISKLJUČIVO JSON objektom sljedeće strukture, bez popratnog teksta, bez markdown ograda:
{
  "kategorije": [
    {"naziv": "...", "max_udio_posto": <broj ili null>, "postotak_financiranja": <broj ili null>}
  ],
  "max_iznos_potpore": <broj ili null>,
  "klasifikacija": [
    {"stavka_id": "<id kako je dan u ulazu>", "kategorija": "<točan naziv iz popisa kategorija>", "postotak_financiranja": <broj>}
  ]
}
"""


def _client() -> Anthropic:
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY nije postavljen.")
    return Anthropic(api_key=ANTHROPIC_API_KEY)


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n", "", text)
        text = re.sub(r"\n```$", "", text)
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        text = match.group(0)
    return json.loads(text)


def build_team_rows(pt_data: dict) -> list[dict]:
    """Agregira PT podatke po članu tima (satnica je konstantna po članu)."""
    per_member = {}
    for m in pt_data.get("members", []):
        ime = m.get("ime", "")
        uloga = m.get("uloga", "")
        satnice = set()
        sati = 0.0
        for a in m.get("aktivnosti", []):
            sat = float(a.get("sat_rada", 0) or 0)
            satnica = round(float(a.get("satnica", 0) or 0), 2)
            sati += sat
            satnice.add(satnica)
        d = per_member.setdefault(ime, {"uloga": uloga, "sati": 0.0, "satnice": set()})
        d["sati"] += sati
        d["satnice"] |= satnice

    rows = []
    for ime, d in per_member.items():
        satnica = max(d["satnice"]) if d["satnice"] else 0.0  # konstantna po članu; max kao sigurnosna mjera
        ukupno = round(d["sati"] * satnica, 2)
        rows.append({
            "id": f"tim:{ime}",
            "opis_naziv": f"Trošak rada — {ime} ({d['uloga']})",
            "kolicina": d["sati"],
            "jedinicna_cijena": satnica,
            "ukupno": ukupno,
            "izvor": "tim",
        })
    return rows


def generate_bp(pt_data: dict, ostale_stavke: list[dict], up_text: str) -> tuple[dict, list[str]]:
    """ostale_stavke: [{"naziv": str, "iznos": float}, ...]. Vraća (bp_data, upozorenja)."""
    team_rows = build_team_rows(pt_data)

    ostale_rows = []
    for i, s in enumerate(ostale_stavke):
        ostale_rows.append({
            "id": f"ostalo:{i}",
            "opis_naziv": s["naziv"],
            "kolicina": 1,
            "jedinicna_cijena": round(float(s["iznos"]), 2),
            "ukupno": round(float(s["iznos"]), 2),
            "izvor": "ostalo",
        })

    all_rows = team_rows + ostale_rows
    if not all_rows:
        return {"kategorije": [], "max_iznos_potpore": None, "stavke": []}, ["Nema unesenih stavki troška."]

    stavke_za_klasifikaciju = "\n".join(
        f"- id={r['id']}: {r['opis_naziv']} (ukupno {r['ukupno']} EUR)" for r in all_rows
    )

    user_prompt = f"""TEKST UP-a (natječajne Upute za prijavitelje):
{up_text or "(nije dostavljeno)"}

STAVKE ZA KLASIFIKACIJU:
{stavke_za_klasifikaciju}

Izvuci kategorije i klasificiraj stavke prema pravilima iz sistemskog prompta. Odgovori samo JSON-om."""

    client = _client()
    response = client.messages.create(
        model=MODEL,
        max_tokens=6000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    text_block = next((b.text for b in response.content if b.type == "text"), None)
    if not text_block:
        raise RuntimeError("Model nije vratio tekstualni odgovor.")

    if response.stop_reason == "max_tokens":
        raise RuntimeError(
            "Odgovor modela je prekinut na pola (previše teksta za zadani limit odgovora). "
            "Pokušaj ponovno — ako se greška ponavlja, pošalji mi kraći UP tekst ili manje stavki odjednom."
        )

    try:
        result = _extract_json(text_block)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Model nije vratio ispravan JSON (greška pri parsiranju: {e}). "
            "Pokušaj ponovno generirati BP — ako se ponavlja, javi mi."
        ) from e
    kategorije = result.get("kategorije", [])
    max_iznos_potpore = result.get("max_iznos_potpore")
    klasifikacija = {k["stavka_id"]: k for k in result.get("klasifikacija", [])}

    stavke = []
    for r in all_rows:
        kl = klasifikacija.get(r["id"], {})
        postotak = kl.get("postotak_financiranja")
        postotak = float(postotak) if postotak is not None else 0.0
        bespovratna = round(r["ukupno"] * postotak / 100, 2)
        vlastito = round(r["ukupno"] - bespovratna, 2)
        stavke.append({
            "kategorija": kl.get("kategorija", "(nerazvrstano)"),
            "opis_naziv": r["opis_naziv"],
            "kolicina": r["kolicina"],
            "jedinicna_cijena": r["jedinicna_cijena"],
            "ukupno": r["ukupno"],
            "postotak_financiranja": postotak,
            "bespovratna_sredstva": bespovratna,
            "vlastito_ucesce": vlastito,
            "izvor": r["izvor"],
        })

    bp_data = {"kategorije": kategorije, "max_iznos_potpore": max_iznos_potpore, "stavke": stavke}
    warnings = _validate(bp_data)
    return bp_data, warnings


def _validate(bp_data: dict) -> list[str]:
    warnings = []
    stavke = bp_data["stavke"]
    total = sum(s["ukupno"] for s in stavke)
    total_bespovratna = sum(s["bespovratna_sredstva"] for s in stavke)

    by_category = {}
    for s in stavke:
        by_category.setdefault(s["kategorija"], 0.0)
        by_category[s["kategorija"]] += s["ukupno"]

    limits = {k["naziv"]: k.get("max_udio_posto") for k in bp_data.get("kategorije", [])}
    for kat, iznos in by_category.items():
        limit = limits.get(kat)
        if limit is not None and total > 0:
            udio = iznos / total * 100
            if udio > limit + 0.01:
                warnings.append(
                    f"UPOZORENJE: kategorija '{kat}' čini {udio:.1f}% proračuna, "
                    f"a dopušteni limit prema UP-u je {limit:.1f}%."
                )

    max_iznos = bp_data.get("max_iznos_potpore")
    if max_iznos is not None and total_bespovratna > max_iznos + 0.01:
        warnings.append(
            f"UPOZORENJE: ukupna tražena bespovratna sredstva ({total_bespovratna:.2f} EUR) "
            f"prelaze max. iznos potpore iz UP-a ({max_iznos:.2f} EUR)."
        )

    if not limits or all(v is None for v in limits.values()):
        warnings.append("Napomena: UP ne sadrži (prepoznate) % limite po kategoriji — provjeri ručno.")
    if max_iznos is None:
        warnings.append("Napomena: UP ne sadrži (prepoznat) max. iznos potpore — provjeri ručno.")

    return warnings
