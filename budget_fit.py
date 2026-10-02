"""Deterministički modul (bez AI-ja): usklađivanje troška osoblja (satova iz PT-a) s maksimalnim
iznosom bespovratne potpore iz UP-a, uz zadani postotak neizravnih troškova.

Logika:
1. raspoloživo za (osoblje + neizravni) = max_iznos_potpore - margina - bespovratna već upisanih
   "ostalih" BP stavki
2. to se pretvara u ukupan prihvatljiv trošak preko intenziteta financiranja za trošak osoblja
3. ciljani_trošak = osoblje + neizravni, gdje je neizravni = postotak_neizravnih % od osoblja
4. satovi svakog člana tima skaliraju se proporcionalno (isti faktor za sve) - satnice se NE mijenjaju
   (fiksne prema metodologiji, propisano u PT modulu)
5. % rada na projektu po članu = novi sati / (trajanje_mjeseci x sati_mjesecno) x 100
"""
import copy

from bp_generator import build_team_rows, _validate


def _ukupno_osoblje(pt_data: dict) -> float:
    total = 0.0
    for m in pt_data.get("members", []):
        for a in m.get("aktivnosti", []):
            sat = float(a.get("sat_rada", 0) or 0)
            satnica = round(float(a.get("satnica", 0) or 0), 2)
            total += sat * satnica
    return round(total, 2)


def _postotak_financiranja_osoblje(bp_data: dict) -> float:
    """Postotak financiranja timskih redova iz već generiranog BP-a. Ako se razlikuju po članu
    (ne bi smjelo, isti intenzitet vrijedi za cijelu kategoriju), uzima se najniži - konzervativno."""
    postoci = [s["postotak_financiranja"] for s in bp_data.get("stavke", []) if s.get("izvor") == "tim"]
    return min(postoci) if postoci else 0.0


def uskladi_s_budzetom(
    pt_data: dict,
    bp_data: dict,
    trajanje_mjeseci: float,
    postotak_neizravnih: float = 15.0,
    margina: float = 60.0,
    sati_mjesecno: float = 169.0,
) -> tuple[dict, dict, list[str]]:
    """Vraća (novi_pt_data, novi_bp_data, upozorenja). Ne mijenja ulazne pt_data/bp_data (kopira ih)."""
    warnings: list[str] = []

    max_iznos = bp_data.get("max_iznos_potpore")
    if max_iznos is None:
        return pt_data, bp_data, [
            "Ne mogu uskladiti s budžetom: UP ne sadrži prepoznat max. iznos potpore — provjeri UP tekst."
        ]

    intenzitet = _postotak_financiranja_osoblje(bp_data)
    if intenzitet <= 0:
        return pt_data, bp_data, [
            "Ne mogu uskladiti s budžetom: postotak financiranja za trošak osoblja nije prepoznat (ili je 0)."
        ]

    bespovratna_ostalo = sum(
        s["bespovratna_sredstva"] for s in bp_data.get("stavke", []) if s.get("izvor") not in ("tim", "neizravno")
    )
    raspolozivo = max_iznos - margina - bespovratna_ostalo
    if raspolozivo <= 0:
        return pt_data, bp_data, [
            f"UPOZORENJE: 'ostale stavke' troška + margina ({margina:.2f} EUR) same dosežu/prelaze max. "
            f"iznos potpore ({max_iznos:.2f} EUR) — za trošak osoblja ne preostaje budžet. Smanji ostale stavke."
        ]

    ciljani_trosak = raspolozivo / (intenzitet / 100)
    osoblje_target = round(ciljani_trosak / (1 + postotak_neizravnih / 100), 2)
    neizravni_target = round(ciljani_trosak - osoblje_target, 2)

    osoblje_trenutno = _ukupno_osoblje(pt_data)
    if osoblje_trenutno <= 0:
        return pt_data, bp_data, ["Ne mogu uskladiti s budžetom: trenutni trošak osoblja je 0."]

    faktor = osoblje_target / osoblje_trenutno
    if trajanje_mjeseci is None or trajanje_mjeseci <= 0:
        warnings.append(
            "Napomena: trajanje projekta nije uneseno (ili je 0) — % rada po članu nije izračunat."
        )
    raspoloziv_sati_clan = (trajanje_mjeseci or 0) * sati_mjesecno

    novi_pt = copy.deepcopy(pt_data)
    for m in novi_pt.get("members", []):
        ukupno_sati_clana = 0.0
        for a in m.get("aktivnosti", []):
            novi_sat = round(float(a.get("sat_rada", 0) or 0) * faktor, 2)
            a["sat_rada"] = novi_sat
            ukupno_sati_clana += novi_sat
        if raspoloziv_sati_clan > 0:
            postotak_rada = round(ukupno_sati_clana / raspoloziv_sati_clan * 100, 1)
            m["postotak_rada"] = postotak_rada
            if postotak_rada > 100:
                warnings.append(
                    f"UPOZORENJE: prema uskladbi s budžetom, {m.get('ime','')} bi trebao/la raditi "
                    f"{postotak_rada:.0f}% radnog vremena (preko 100%) — nerealno, provjeri ručno "
                    "(premalo članova tima za ovaj budžet, ili je trajanje projekta prekratko)."
                )
            elif postotak_rada < 5:
                warnings.append(
                    f"Napomena: {m.get('ime','')} ima nizak postotak rada na projektu "
                    f"({postotak_rada:.1f}%) nakon uskladbe s budžetom — provjeri je li realno."
                )

    # Rebuild BP stavke: tim (iz novog PT-a), ostale (nepromijenjene), + neizravni (novi red)
    klasifikacija_tim = next(
        (s["kategorija"] for s in bp_data.get("stavke", []) if s.get("izvor") == "tim"),
        "Trošak rada projektnog tima",
    )
    team_rows = build_team_rows(novi_pt)
    nove_stavke = []
    for r in team_rows:
        bespovratna = round(r["ukupno"] * intenzitet / 100, 2)
        nove_stavke.append({
            "kategorija": klasifikacija_tim,
            "opis_naziv": r["opis_naziv"],
            "kolicina": r["kolicina"],
            "jedinicna_cijena": r["jedinicna_cijena"],
            "ukupno": r["ukupno"],
            "postotak_financiranja": intenzitet,
            "bespovratna_sredstva": bespovratna,
            "vlastito_ucesce": round(r["ukupno"] - bespovratna, 2),
            "izvor": "tim",
        })

    ostale_nepromijenjene = [
        s for s in bp_data.get("stavke", []) if s.get("izvor") not in ("tim", "neizravno")
    ]
    nove_stavke.extend(ostale_nepromijenjene)

    bespovratna_neizravni = round(neizravni_target * intenzitet / 100, 2)
    nove_stavke.append({
        "kategorija": f"Neizravni troškovi ({postotak_neizravnih:.0f}% od troška osoblja)",
        "opis_naziv": "Neizravni troškovi (flat rate)",
        "kolicina": 1,
        "jedinicna_cijena": neizravni_target,
        "ukupno": neizravni_target,
        "postotak_financiranja": intenzitet,
        "bespovratna_sredstva": bespovratna_neizravni,
        "vlastito_ucesce": round(neizravni_target - bespovratna_neizravni, 2),
        "izvor": "neizravno",
    })

    novi_bp = copy.deepcopy(bp_data)
    novi_bp["stavke"] = nove_stavke

    warnings.append(
        "Napomena: neizravni troškovi dodani kao zaseban red u BP-u, financirani istim postotkom kao "
        "trošak osoblja — provjeri odgovara li to pravilima ovog natječaja (neki natječaji propisuju "
        "drugačiji intenzitet financiranja za flat-rate neizravne troškove)."
    )
    warnings.extend(_validate(novi_bp))

    return novi_pt, novi_bp, warnings
