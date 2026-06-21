"""Génération des rapports lisibles (console + fichier markdown)."""
from __future__ import annotations

import datetime as dt

import config


def _fmt_scenario(s: dict | None) -> str:
    if not s:
        return "n/d"
    signe = "🟢" if s["pnl_eur"] >= 0 else "🔴"
    return f"{signe} {s['prix']:.2f}€  ({s['pnl_pct']:+.2f}%  soit {s['pnl_eur']:+.2f}€)"


def rapport_evaluation(resultats: list[dict]) -> str:
    if not resultats:
        return "### Évaluation de la veille\n\n_Aucune position à évaluer aujourd'hui._\n"

    lignes = ["### Évaluation des achats de la séance précédente\n"]
    total = {"ouverture": 0.0, "premiere_demi_heure": 0.0, "mi_journee": 0.0, "h17": 0.0}
    compte = {k: 0 for k in total}

    for r in resultats:
        ev = r["evaluation"]
        sc = ev["scenarios"]
        lignes.append(f"**{r['ticker']} — {r['nom']}**  (acheté le {r['date_achat']})")
        lignes.append(f"- Prix d'entrée (clôture veille) : "
                      f"{ev['prix_entree']:.2f}€" if ev["prix_entree"] else "- Prix d'entrée : n/d")
        lignes.append(f"- Revente à l'ouverture (09:00) : {_fmt_scenario(sc['ouverture'])}")
        lignes.append(f"- Revente 1re demi-heure (09:30) : {_fmt_scenario(sc['premiere_demi_heure'])}")
        lignes.append(f"- Revente mi-journée (13:00) : {_fmt_scenario(sc['mi_journee'])}")
        lignes.append(f"- Revente à 17h : {_fmt_scenario(sc['h17'])}")
        lignes.append("")

        for k in total:
            if sc[k]:
                total[k] += sc[k]["pnl_eur"]
                compte[k] += 1

    lignes.append("**Total du portefeuille (somme des positions évaluées) :**")
    libelles = {
        "ouverture": "Ouverture",
        "premiere_demi_heure": "1re demi-heure",
        "mi_journee": "Mi-journée",
        "h17": "17h",
    }
    for k, lib in libelles.items():
        if compte[k]:
            signe = "🟢" if total[k] >= 0 else "🔴"
            lignes.append(f"- {lib} : {signe} {total[k]:+.2f}€")
    lignes.append("")
    return "\n".join(lignes)


def rapport_selection(analyse: dict, positions: list[dict]) -> str:
    lignes = ["### Sélection du soir (marche à blanc)\n"]
    lignes.append(f"_{analyse.get('synthese_marche', '')}_\n")
    for p in positions:
        prix = p.get("prix_decision_17h")
        prix_txt = f"{prix:.2f}€" if prix else "n/d"
        lignes.append(f"**{p['ticker']} — {p['nom']}**  "
                      f"(conviction {p.get('conviction', '?')}/100)")
        lignes.append(f"- Achat papier : {config.ALLOCATION_PAR_ACTION:.0f}€ "
                      f"au cours ~17h de {prix_txt}")
        lignes.append(f"- Catalyseur : {p.get('catalyseur', '')}")
        lignes.append(f"- Raisonnement : {p.get('raisonnement', '')}")
        lignes.append("")
    lignes.append("_Aucun ordre réel n'a été passé. Simulation uniquement._\n")
    return "\n".join(lignes)


def ecrire_rapport(jour: dt.date, contenu: str) -> str:
    chemin = config.DOSSIER_RAPPORTS / f"rapport_{jour.isoformat()}.md"
    entete = f"# Rapport du {jour.strftime('%A %d %B %Y')}\n\n"
    chemin.write_text(entete + contenu, encoding="utf-8")
    return str(chemin)
