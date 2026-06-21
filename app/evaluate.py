"""Évaluation du lendemain : que sont devenues les actions achetées la veille ?

Pour chaque position, on fige le prix d'entrée (= clôture de la séance d'achat,
soit l'achat « 5 min avant la clôture ») puis on calcule le gain/perte théorique
selon 4 scénarios de revente pendant la séance suivante :
  - première demi-heure (09:30)
  - ouverture (09:00)
  - mi-journée (13:00)
  - 17h
"""
from __future__ import annotations

import datetime as dt

from app import benchmark, ledger, market


def _gain(entree: float | None, sortie: float | None, allocation: float) -> dict | None:
    if not entree or not sortie:
        return None
    parts = allocation / entree
    pnl = parts * (sortie - entree)
    return {
        "prix": round(sortie, 4),
        "pnl_eur": round(pnl, 2),
        "pnl_pct": round((sortie / entree - 1) * 100, 2),
    }


def evaluer_positions(aujourd_hui: dt.date) -> list[dict]:
    """Évalue toutes les positions en attente. Retourne les résultats."""
    a_evaluer = ledger.positions_a_evaluer(aujourd_hui)
    resultats = []

    for p in a_evaluer:
        date_achat = dt.date.fromisoformat(p["date_achat"])
        ticker = p["ticker"]

        # Prix d'entrée = clôture de la séance d'achat (achat près de la clôture)
        entree = p.get("prix_entree") or market.cloture_du_jour(ticker, date_achat)

        # Séance suivante = aujourd'hui (jour de l'évaluation)
        prix = market.prix_intraday(ticker, aujourd_hui)

        evaluation = {
            "date_evaluation": aujourd_hui.isoformat(),
            "prix_entree": round(entree, 4) if entree else None,
            "scenarios": {
                "ouverture": _gain(entree, prix["ouverture"], p["allocation_eur"]),
                "premiere_demi_heure": _gain(entree, prix["demi_heure"], p["allocation_eur"]),
                "mi_journee": _gain(entree, prix["mi_journee"], p["allocation_eur"]),
                "h17": _gain(entree, prix["h17"], p["allocation_eur"]),
            },
        }

        ledger.mettre_a_jour_position(
            p["id"], {"prix_entree": evaluation["prix_entree"], "evaluation": evaluation}
        )
        resultats.append({**p, "evaluation": evaluation})

        # Benchmark CAC 40 pour ce jour évalué (calculé une fois, mis en cache).
        benchmark.assurer(aujourd_hui, date_achat)

    return resultats
