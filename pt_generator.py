"""PT modul: CV + platna lista + metodologija satnice + popis aktivnosti -> strukturirani PT podaci."""
import json
import re
import difflib

from anthropic import Anthropic
from config import ANTHROPIC_API_KEY, MODEL

SYSTEM_PROMPT = """Ti si asistent za izradu obrasca "Projektni tim" (PT) za hrvatske EU natječaje.
Tvoj zadatak je, isključivo na temelju dostavljenih dokumenata, sastaviti strukturirani opis
projektnog tima. Pravila (ne smiju se kršiti):

1. Popis aktivnosti je FIKSAN i dolazi iz natječaja — ne smiješ izmišljati, spajati, dijeliti
   niti preimenovati aktivnosti. Svaki član tima mora raditi samo na aktivnostima iz tog popisa.
2. Kompetencije članova tima smiju dolaziti ISKLJUČIVO iz dostavljenih CV-ova — ne izmišljaj
   iskustvo ili kvalifikacije koje CV ne navodi.
3. Uloga člana tima (npr. "Voditelj projekta", "Koordinator aktivnosti"): prvo provjeri
   sadrži li dostavljeni tekst natječaja (UP/BL) propisani vokabular uloga. Ako da, koristi
   isključivo te nazive. Ako ne, imenuj ulogu slobodno, ali usklađeno sa stvarnom ulogom člana
   u aktivnostima.
4. Satnica se računa isključivo prema priloženoj metodologiji izračuna satnice i platnoj listi.
   Zaokruži je na točno 2 decimale.
5. Sat rada po aktivnosti procjenjuje se prema opsegu i prirodi aktivnosti (opis rada), a NE
   prema bilo kakvom budžetu — budžet u ovoj fazi ne postoji.
6. KLJUČNO: polje "methodology_quote" mora biti DOSLOVAN, nepromijenjen citat (verbatim
   copy-paste) iz dostavljenog teksta metodologije izračuna satnice — ne smiješ parafrazirati,
   skraćivati sa značenjskim izmjenama niti preformulirati. Prepiši točan odlomak/odlomke koji
   definiraju izračun satnice.

Odgovori ISKLJUČIVO JSON objektom sljedeće strukture, bez popratnog teksta, bez markdown ograda:
{
  "methodology_quote": "<doslovan citat>",
  "role_vocabulary_used": true/false,
  "members": [
    {
      "ime": "<ime i prezime iz CV-a>",
      "uloga": "<uloga>",
      "kompetencije": "<sažetak relevantnih kompetencija iz CV-a>",
      "aktivnosti": [
        {"aktivnost": "<točan naziv iz popisa aktivnosti>", "opis_rada": "<opis>", "sat_rada": <broj>, "satnica": <broj, 2 decimale>}
      ]
    }
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


def generate_pt(
    aktivnosti_text: str,
    cv_items: list[tuple[str, str]],  # [(filename, text), ...]
    platna_lista_text: str,
    satnica_metodologija_text: str,
    uloga_vokabular_text: str = "",
) -> tuple[dict, list[str]]:
    """Vraća (pt_data, upozorenja)."""
    cv_block = "\n\n".join(f"### CV: {fn}\n{txt}" for fn, txt in cv_items)

    user_prompt = f"""POPIS AKTIVNOSTI (fiksan, iz natječaja):
{aktivnosti_text}

CV DJELATNIKA:
{cv_block}

PLATNA LISTA:
{platna_lista_text}

METODOLOGIJA IZRAČUNA SATNICE (prilog natječaja — izvor za methodology_quote i izračun satnice):
{satnica_metodologija_text}

VOKABULAR ULOGA (UP/BL, ako postoji):
{uloga_vokabular_text or "(nije dostavljeno — slobodno imenovanje uloga)"}

Sastavi PT prema pravilima iz sistemskog prompta. Odgovori samo JSON-om."""

    client = _client()
    response = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    text_block = next((b.text for b in response.content if b.type == "text"), None)
    if not text_block:
        raise RuntimeError("Model nije vratio tekstualni odgovor (provjeri max_tokens / thinking budžet).")

    if response.stop_reason == "max_tokens":
        raise RuntimeError(
            "Odgovor modela je prekinut na pola (previše teksta za zadani limit odgovora). "
            "Pokušaj ponovno — ako se greška ponavlja, pošalji mi kraće/sažetije CV-eve ili manje aktivnosti odjednom."
        )

    try:
        pt_data = _extract_json(text_block)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Model nije vratio ispravan JSON (greška pri parsiranju: {e}). "
            "Pokušaj ponovno generirati PT — ako se ponavlja, javi mi."
        ) from e

    warnings = []
    quote = pt_data.get("methodology_quote", "")
    if quote and satnica_metodologija_text:
        warnings.extend(_verify_verbatim(quote, satnica_metodologija_text))
    if not pt_data.get("members"):
        warnings.append("Nijedan član tima nije generiran — provjeri CV i popis aktivnosti.")

    return pt_data, warnings


def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def _verify_verbatim(quote: str, source: str) -> list[str]:
    """Deterministička provjera da je methodology_quote stvarno doslovan citat izvora."""
    nq, ns = _normalize(quote), _normalize(source)
    if nq in ns:
        return []
    # Fuzzy fallback — nađi najsličniji odsječak izvora i izmjeri sličnost
    matcher = difflib.SequenceMatcher(None, nq, ns)
    match = matcher.find_longest_match(0, len(nq), 0, len(ns))
    ratio = match.size / max(len(nq), 1)
    if ratio < 0.85:
        return [
            "UPOZORENJE: 'Metodologija izračuna satnice' ne odgovara doslovno izvornom dokumentu "
            f"(podudarnost ~{ratio:.0%}). Provjeri i ručno ispravi prije korištenja — citat mora biti "
            "doslovan, ne parafraziran."
        ]
    return [
        "Napomena: citat metodologije je gotovo doslovan (manja razlika u bjelini/formatiranju) — "
        "preporučena ručna provjera."
    ]
