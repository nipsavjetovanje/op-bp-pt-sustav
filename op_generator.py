"""OP modul: upitnik (slobodan tekst) + popis aktivnosti (fiksan) + PT sažetak -> strukturirani OP podaci."""
import json
import re

from anthropic import Anthropic
from config import ANTHROPIC_API_KEY, MODEL

SYSTEM_PROMPT = """Ti si asistent za izradu obrasca "Opis projekta" (OP) za hrvatske EU natječaje.
Dobivaš odgovore klijenta iz upitnika, fiksan popis aktivnosti iz natječaja i sažetak
projektnog tima (već izrađen u PT obrascu). Pravila (ne smiju se kršiti):

1. NE IZMIŠLJAJ ČINJENICE. Smiješ jezično doraditi i profesionalno uobličiti tekst iz
   upitnika (gramatika, stil, jasnoća), ali ne smiješ dodavati nove podatke, brojke,
   tvrdnje ili obećanja koja klijent nije naveo. Ako je neko polje upitnika prazno ili
   šturo, ostavi odgovarajuće polje OP-a kratkim — ne popunjavaj maštom.
2. Popis aktivnosti je FIKSAN. Prepiši ga u polje "aktivnosti_lista" TOČNO onako kako je
   dan — bez izmjene naziva, bez spajanja, dijeljenja, dodavanja ili izostavljanja ijedne
   aktivnosti. Redoslijed se čuva.
3. Polje "faze_i_aktivnosti_uvod" je kratak narativni uvod (2-5 rečenica) koji na temelju
   teksta o fazama projekta (iz upitnika) objašnjava kronologiju i logiku provedbe, i
   najavljuje da detaljan popis aktivnosti slijedi u nastavku. Ne nabrajaj ovdje aktivnosti
   pojedinačno (one idu u zaseban popis) — samo opiši tok/logiku faza.
4. Polje "projektni_tim_sazetak" je kratak narativni odlomak (3-6 rečenica) koji predstavlja
   tim na temelju dostavljenog PT sažetka — imena, uloge, ključne kompetencije relevantne za
   projekt. Ne izmišljaj članove tima ni kompetencije koje PT sažetak ne navodi.

Odgovori ISKLJUČIVO JSON objektom sljedeće strukture, bez popratnog teksta, bez markdown ograda:
{
  "naziv_projekta": "...",
  "opis_poslovanja": "...",
  "opis_buduceg_projekta": "...",
  "ciljano_trziste": "...",
  "faze_i_aktivnosti_uvod": "...",
  "aktivnosti_lista": ["...", "..."],
  "projektni_tim_sazetak": "...",
  "oprema": "..."
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


def _normalize_activity(s: str) -> str:
    s = re.sub(r"^\s*\d+[\.\)]\s*", "", s)  # makni vodeći broj "1." / "1)"
    return re.sub(r"\s+", " ", s).strip().lower()


def _pt_team_summary_text(pt_data: dict) -> str:
    if not pt_data or not pt_data.get("members"):
        return "(PT podaci nisu dostupni)"
    lines = []
    for m in pt_data["members"]:
        aktivnosti = ", ".join(a.get("aktivnost", "") for a in m.get("aktivnosti", []))
        lines.append(f"- {m.get('ime','')} ({m.get('uloga','')}): {m.get('kompetencije','')} "
                      f"[radi na: {aktivnosti}]")
    return "\n".join(lines)


def generate_op(upitnik: dict, aktivnosti_text: str, pt_data: dict | None) -> tuple[dict, list[str]]:
    """upitnik: dict s ključevima naziv_projekta, opis_poslovanja, opis_buduceg_projekta,
    ciljano_trziste, faze_projekta, oprema. Vraća (op_data, upozorenja)."""

    user_prompt = f"""UPITNIK (odgovori klijenta):
Naziv projekta: {upitnik.get('naziv_projekta','')}
Opis poslovanja / tržišta: {upitnik.get('opis_poslovanja','')}
Opis budućeg projekta: {upitnik.get('opis_buduceg_projekta','')}
Ciljano tržište: {upitnik.get('ciljano_trziste','')}
Faze projekta (slobodan tekst): {upitnik.get('faze_projekta','')}
Oprema prijavitelja: {upitnik.get('oprema','')}

POPIS AKTIVNOSTI (fiksan, iz natječaja — prepiši točno u aktivnosti_lista):
{aktivnosti_text}

SAŽETAK PROJEKTNOG TIMA (iz PT obrasca):
{_pt_team_summary_text(pt_data)}

Sastavi OP prema pravilima iz sistemskog prompta. Odgovori samo JSON-om."""

    client = _client()
    response = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    text_block = next((b.text for b in response.content if b.type == "text"), None)
    if not text_block:
        raise RuntimeError("Model nije vratio tekstualni odgovor.")

    op_data = _extract_json(text_block)

    warnings = []
    generated = [_normalize_activity(a) for a in op_data.get("aktivnosti_lista", [])]
    original_lines = [l for l in aktivnosti_text.splitlines() if l.strip()]
    original = [_normalize_activity(l) for l in original_lines]
    if generated != original:
        warnings.append(
            "UPOZORENJE: generirani popis aktivnosti odstupa od izvornog popisa (izmijenjen tekst, "
            "redoslijed, broj stavki). Aktivnosti moraju biti prepisane doslovno — provjeri ručno."
        )

    return op_data, warnings
