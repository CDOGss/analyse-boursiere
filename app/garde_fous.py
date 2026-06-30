"""Garde-fous de bon sens appliqués à la sélection finale de Claude.

Indépendants du P&L récent (donc pas de sur-optimisation) : ils corrigent trois
travers classiques du momentum :
  1. volume insuffisant (flux acheteur non confirmé),
  2. hausse parabolique déjà trop tendue (prise de bénéfices probable),
  3. concentration sectorielle (deux paris corrélés le même soir).

Les points 1 et 2 sont déjà filtrés en amont dans la shortlist (market.preselection) ;
on les revérifie ici comme filet de sécurité (au cas où Claude choisit hors shortlist),
et on applique le point 3 qui dépend de la combinaison des deux choix.
"""
from __future__ import annotations

import config
from app.market import Instantane


def secteur(ticker: str) -> str | None:
    """Secteur d'un ticker selon les groupes à forte corrélation (ou None)."""
    for nom, tickers in config.GROUPES_SECTEURS.items():
        if ticker in tickers:
            return nom
    return None


def appliquer(selection: list[dict], instantanes: list[Instantane],
              nb_max: int) -> tuple[list[dict], list[str]]:
    """Filtre la sélection de Claude selon les garde-fous.

    Retourne (sélection retenue, notes expliquant les éventuels rejets).
    """
    par_ticker = {i.ticker: i for i in instantanes}
    retenus: list[dict] = []
    secteurs_pris: set[str] = set()
    notes: list[str] = []

    for choix in selection:
        if len(retenus) >= nb_max:
            break
        t = choix.get("ticker", "")
        inst = par_ticker.get(t)

        if inst is not None:
            vr = inst.volume_ratio
            if (vr or 0) < config.VOLUME_MIN_RATIO:
                vr_txt = f"{vr:.2f}x" if vr is not None else "n/d"
                notes.append(f"{t} écarté : volume {vr_txt} < "
                             f"{config.VOLUME_MIN_RATIO:.2f}x (titre délaissé, volume anormalement faible).")
                continue
            if inst.variation_1j is not None and inst.variation_1j > config.HAUSSE_MAX_1J_PCT:
                notes.append(f"{t} écarté : +{inst.variation_1j:.1f}% sur la séance "
                             f"(> {config.HAUSSE_MAX_1J_PCT:.0f}%, sur-étendu).")
                continue

        sect = secteur(t)
        if sect is not None and sect in secteurs_pris:
            notes.append(f"{t} écarté : 2e valeur du secteur « {sect} » "
                         f"(diversification obligatoire).")
            continue

        retenus.append(choix)
        if sect is not None:
            secteurs_pris.add(sect)

    return retenus, notes
