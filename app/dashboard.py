"""Tableau de bord récapitulatif sur tout l'historique du portefeuille papier.

Pour chacun des 4 scénarios de revente (ouverture, 1re demi-heure, mi-journée,
17h), calcule sur l'ensemble des positions évaluées :
  - le P&L cumulé (€),
  - le rendement moyen (%),
  - le taux de réussite (part des positions gagnantes),
  - le meilleur et le pire trade.

Permet d'identifier la « meilleure stratégie de sortie » a posteriori.
"""
from __future__ import annotations

from app import ledger

SCENARIOS = {
    "ouverture": "Ouverture (09:00)",
    "premiere_demi_heure": "1re demi-heure (09:30)",
    "mi_journee": "Mi-journée (13:00)",
    "h17": "17h",
}


def calculer_stats() -> dict:
    """Agrège les statistiques sur toutes les positions évaluées."""
    positions = [p for p in ledger.toutes_positions() if p.get("evaluation")]

    stats = {
        cle: {"pnl_total": 0.0, "rendements": [], "gagnants": 0, "evalues": 0,
              "meilleur": None, "pire": None}
        for cle in SCENARIOS
    }

    for p in positions:
        scenarios = p["evaluation"]["scenarios"]
        for cle in SCENARIOS:
            s = scenarios.get(cle)
            if not s:
                continue
            bloc = stats[cle]
            bloc["evalues"] += 1
            bloc["pnl_total"] += s["pnl_eur"]
            bloc["rendements"].append(s["pnl_pct"])
            if s["pnl_eur"] > 0:
                bloc["gagnants"] += 1
            trade = {"ticker": p["ticker"], "date": p["date_achat"],
                     "pnl_eur": s["pnl_eur"], "pnl_pct": s["pnl_pct"]}
            if bloc["meilleur"] is None or s["pnl_eur"] > bloc["meilleur"]["pnl_eur"]:
                bloc["meilleur"] = trade
            if bloc["pire"] is None or s["pnl_eur"] < bloc["pire"]["pnl_eur"]:
                bloc["pire"] = trade

    return {
        "nb_positions": len(positions),
        "nb_total": len(ledger.toutes_positions()),
        "scenarios": stats,
    }


def _moyenne(xs: list[float]) -> float | None:
    return sum(xs) / len(xs) if xs else None


def rendu_texte(stats: dict) -> str:
    n = stats["nb_positions"]
    if n == 0:
        return ("### Tableau de bord\n\n"
                "_Aucune position évaluée pour l'instant. Reviens après quelques "
                "séances pour voir les statistiques._\n")

    lignes = ["### Tableau de bord — synthèse sur tout l'historique\n"]
    lignes.append(f"Positions évaluées : **{n}** "
                  f"(sur {stats['nb_total']} enregistrées)\n")

    lignes.append("| Scénario de sortie | P&L cumulé | Rendement moyen | Taux de réussite |")
    lignes.append("|---|---:|---:|---:|")

    meilleur_scenario = None
    for cle, libelle in SCENARIOS.items():
        b = stats["scenarios"][cle]
        if b["evalues"] == 0:
            lignes.append(f"| {libelle} | n/d | n/d | n/d |")
            continue
        moy = _moyenne(b["rendements"])
        taux = b["gagnants"] / b["evalues"] * 100
        signe = "🟢" if b["pnl_total"] >= 0 else "🔴"
        lignes.append(
            f"| {libelle} | {signe} {b['pnl_total']:+.2f}€ | {moy:+.2f}% "
            f"| {taux:.0f}% ({b['gagnants']}/{b['evalues']}) |"
        )
        if meilleur_scenario is None or b["pnl_total"] > meilleur_scenario[1]:
            meilleur_scenario = (libelle, b["pnl_total"])

    lignes.append("")
    if meilleur_scenario:
        lignes.append(
            f"**Meilleure stratégie de sortie a posteriori : {meilleur_scenario[0]}** "
            f"({meilleur_scenario[1]:+.2f}€ cumulés).\n"
        )

    # Détail meilleur/pire trade par scénario
    lignes.append("Détail par scénario :")
    for cle, libelle in SCENARIOS.items():
        b = stats["scenarios"][cle]
        if b["evalues"] == 0:
            continue
        m, pr = b["meilleur"], b["pire"]
        lignes.append(
            f"- {libelle} — meilleur : {m['ticker']} ({m['pnl_pct']:+.2f}%, "
            f"{m['date']}) | pire : {pr['ticker']} ({pr['pnl_pct']:+.2f}%, {pr['date']})"
        )
    lignes.append("")
    return "\n".join(lignes)


def afficher() -> str:
    texte = rendu_texte(calculer_stats())
    print(texte)
    return texte
