"""Calendrier quotidien + tableau de bord mensuel.

- journal_quotidien.csv : une ligne par jour de résultat, somme gain/perte aux
  4 moments de revente (ouverture, 9h30, midi, 17h). Ouvrable dans Excel/Sheets.
- bilan_mensuel.md : récap par mois (brut ET net de frais), taux de réussite,
  meilleur/pire jour, cumul. Mis à jour à chaque exécution.
- historique_recent_texte() : track record réinjecté dans le prompt Claude.

Les résultats sont indexés par DATE D'ÉVALUATION (le jour où la position aurait
été revendue), pas par date d'achat.
"""
from __future__ import annotations

import csv
import datetime as dt
from collections import OrderedDict

import config
from app import ledger

SCENARIOS = ["ouverture", "premiere_demi_heure", "mi_journee", "h17"]
LIBELLES = {
    "ouverture": "Ouverture",
    "premiere_demi_heure": "9h30",
    "mi_journee": "Midi",
    "h17": "17h",
}


def _jours() -> "OrderedDict[str, dict]":
    """Agrège les positions évaluées par date d'évaluation.

    Retourne {date_eval: {tickers, n, sommes{scenario: pnl_eur}}} trié par date.
    """
    jours: dict[str, dict] = {}
    for p in ledger.toutes_positions():
        ev = p.get("evaluation")
        if not ev:
            continue
        date = ev.get("date_evaluation")
        if not date:
            continue
        bloc = jours.setdefault(
            date, {"tickers": [], "n": 0, "sommes": {s: None for s in SCENARIOS}}
        )
        bloc["tickers"].append(p["ticker"])
        bloc["n"] += 1
        for s in SCENARIOS:
            cell = ev["scenarios"].get(s)
            if cell:
                base = bloc["sommes"][s] or 0.0
                bloc["sommes"][s] = base + cell["pnl_eur"]
    return OrderedDict(sorted(jours.items()))


def _cout_jour(n: int) -> float:
    """Frais estimés d'aller-retour pour n positions (P&L net)."""
    return n * config.ALLOCATION_PAR_ACTION * config.COUT_TRANSACTION_PCT / 100


# --- Calendrier CSV --------------------------------------------------------
def ecrire_csv() -> str:
    chemin = config.DOSSIER_RAPPORTS / "journal_quotidien.csv"
    jours = _jours()
    with open(chemin, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["date", "nb_actions", "actions",
                    "pnl_ouverture_eur", "pnl_9h30_eur", "pnl_midi_eur",
                    "pnl_17h_eur", "frais_estimes_eur", "pnl_17h_net_eur"])
        for date, b in jours.items():
            s = b["sommes"]
            cout = _cout_jour(b["n"])
            net17 = (s["h17"] - cout) if s["h17"] is not None else None
            w.writerow([
                date, b["n"], "+".join(b["tickers"]),
                _r(s["ouverture"]), _r(s["premiere_demi_heure"]),
                _r(s["mi_journee"]), _r(s["h17"]),
                _r(cout), _r(net17),
            ])
    return str(chemin)


def _r(x: float | None) -> str:
    return f"{x:.2f}".replace(".", ",") if x is not None else ""


# --- Tableau de bord mensuel ----------------------------------------------
def _bilan_par_mois() -> "OrderedDict[str, dict]":
    mois: dict[str, dict] = {}
    for date, b in _jours().items():
        cle = date[:7]  # AAAA-MM
        m = mois.setdefault(cle, {
            "jours": 0, "positions": 0,
            "sommes": {s: 0.0 for s in SCENARIOS},
            "frais": 0.0, "jours_gagnants_17h": 0,
            "meilleur": None, "pire": None,
        })
        m["jours"] += 1
        m["positions"] += b["n"]
        m["frais"] += _cout_jour(b["n"])
        for s in SCENARIOS:
            if b["sommes"][s] is not None:
                m["sommes"][s] += b["sommes"][s]
        pnl17 = b["sommes"]["h17"]
        if pnl17 is not None:
            if pnl17 > 0:
                m["jours_gagnants_17h"] += 1
            jour_info = {"date": date, "pnl": pnl17, "tickers": b["tickers"]}
            if m["meilleur"] is None or pnl17 > m["meilleur"]["pnl"]:
                m["meilleur"] = jour_info
            if m["pire"] is None or pnl17 < m["pire"]["pnl"]:
                m["pire"] = jour_info
    return OrderedDict(sorted(mois.items(), reverse=True))


def _signe(x: float) -> str:
    return "🟢" if x >= 0 else "🔴"


def rendu_mensuel() -> str:
    mois = _bilan_par_mois()
    if not mois:
        return ("## Tableau de bord mensuel\n\n_Aucun résultat évalué pour "
                "l'instant. Reviens après quelques séances._\n")

    lignes = ["## Tableau de bord mensuel\n"]
    lignes.append(f"_Frais d'aller-retour estimés : {config.COUT_TRANSACTION_PCT:.2f}% "
                  f"par position (P&L net au 17h)._\n")

    # Synthèse multi-mois
    lignes.append("| Mois | Jours | Ouverture | 9h30 | Midi | 17h (brut) | 17h (net) | Réussite 17h |")
    lignes.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for cle, m in mois.items():
        s = m["sommes"]
        net = s["h17"] - m["frais"]
        taux = m["jours_gagnants_17h"] / m["jours"] * 100 if m["jours"] else 0
        lignes.append(
            f"| {cle} | {m['jours']} "
            f"| {_signe(s['ouverture'])} {s['ouverture']:+.2f}€ "
            f"| {_signe(s['premiere_demi_heure'])} {s['premiere_demi_heure']:+.2f}€ "
            f"| {_signe(s['mi_journee'])} {s['mi_journee']:+.2f}€ "
            f"| {_signe(s['h17'])} {s['h17']:+.2f}€ "
            f"| {_signe(net)} {net:+.2f}€ "
            f"| {taux:.0f}% |"
        )
    lignes.append("")

    # Détail du mois en cours (calendrier jour par jour)
    cle_courant = next(iter(mois))
    m = mois[cle_courant]
    lignes.append(f"### Détail du mois {cle_courant} (jour par jour)\n")
    if m["meilleur"]:
        lignes.append(f"- Meilleur jour : **{m['meilleur']['date']}** "
                      f"{m['meilleur']['pnl']:+.2f}€ ({'+'.join(m['meilleur']['tickers'])})")
    if m["pire"]:
        lignes.append(f"- Pire jour : **{m['pire']['date']}** "
                      f"{m['pire']['pnl']:+.2f}€ ({'+'.join(m['pire']['tickers'])})")
    lignes.append("")
    lignes.append("| Date | Actions | Ouverture | 9h30 | Midi | 17h |")
    lignes.append("|---|---|---:|---:|---:|---:|")
    for date, b in _jours().items():
        if not date.startswith(cle_courant):
            continue
        s = b["sommes"]
        def c(x):
            return f"{_signe(x)} {x:+.2f}€" if x is not None else "n/d"
        lignes.append(
            f"| {date} | {'+'.join(b['tickers'])} "
            f"| {c(s['ouverture'])} | {c(s['premiere_demi_heure'])} "
            f"| {c(s['mi_journee'])} | {c(s['h17'])} |"
        )
    lignes.append("")
    return "\n".join(lignes)


def ecrire_bilan_mensuel() -> str:
    chemin = config.DOSSIER_RAPPORTS / "bilan_mensuel.md"
    entete = (f"# Bilan mensuel — mis à jour le "
              f"{dt.datetime.now(config.FUSEAU_PARIS):%Y-%m-%d %H:%M}\n\n")
    chemin.write_text(entete + rendu_mensuel(), encoding="utf-8")
    return str(chemin)


# --- Feedback réinjecté dans le prompt Claude ------------------------------
def historique_recent_texte(n: int = 10) -> str:
    """Résumé des n dernières positions évaluées, pour auto-correction de Claude."""
    evaluees = [p for p in ledger.toutes_positions() if p.get("evaluation")]
    if not evaluees:
        return ""
    evaluees.sort(key=lambda p: p["evaluation"]["date_evaluation"], reverse=True)
    recent = evaluees[:n]

    gagnants = 0
    lignes = []
    for p in recent:
        h17 = p["evaluation"]["scenarios"].get("h17")
        if not h17:
            continue
        if h17["pnl_pct"] > 0:
            gagnants += 1
        lignes.append(
            f"- {p['date_achat']} {p['ticker']} ({p.get('nom', '')}): "
            f"{h17['pnl_pct']:+.2f}% au 17h (conviction {p.get('conviction', '?')})"
        )
    if not lignes:
        return ""
    taux = gagnants / len(lignes) * 100
    entete = (f"Sur tes {len(lignes)} derniers paris évalués : {gagnants} gagnants "
              f"au 17h ({taux:.0f}%). Détail :\n")
    return entete + "\n".join(lignes)
