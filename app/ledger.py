"""Registre du portefeuille en marche à blanc (aucun ordre réel n'est passé)."""
from __future__ import annotations

import datetime as dt
import json
import math
from typing import Any

import config


def _charger() -> dict[str, Any]:
    if config.FICHIER_PORTEFEUILLE.exists():
        with open(config.FICHIER_PORTEFEUILLE, encoding="utf-8") as f:
            return json.load(f)
    return {"positions": []}


def _assainir(x: Any) -> Any:
    """Remplace récursivement NaN/Infini par None.

    `json.dump` écrit sinon les littéraux `NaN`/`Infinity`, que Python relit
    mais qui sont INVALIDES en JSON : tout autre consommateur (la page web,
    `JSON.parse`) échoue sur la totalité du fichier. Dernier rempart : le
    portefeuille reste lisible par tous, même si un NaN a franchi les filtres.
    """
    if isinstance(x, float):
        return None if math.isnan(x) or math.isinf(x) else x
    if isinstance(x, dict):
        return {k: _assainir(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_assainir(v) for v in x]
    return x


def _sauver(donnees: dict[str, Any]) -> None:
    with open(config.FICHIER_PORTEFEUILLE, "w", encoding="utf-8") as f:
        json.dump(_assainir(donnees), f, ensure_ascii=False, indent=2,
                  allow_nan=False)


def enregistrer_achats(jour: dt.date, selection: list[dict], prix_decision: dict[str, float | None]) -> list[dict]:
    """Crée des positions "papier" pour la sélection du jour.

    prix_decision : {ticker: cours observé à ~17h} (référence indicative).
    L'entrée réelle (clôture de la séance) sera figée lors de l'évaluation.
    """
    donnees = _charger()
    nouvelles = []
    for choix in selection:
        ticker = choix["ticker"]
        position = {
            "id": f"{jour.isoformat()}_{ticker}",
            "date_achat": jour.isoformat(),
            "ticker": ticker,
            "nom": choix.get("nom", ""),
            "allocation_eur": config.ALLOCATION_PAR_ACTION,
            "conviction": choix.get("conviction"),
            "catalyseur": choix.get("catalyseur", ""),
            "raisonnement": choix.get("raisonnement", ""),
            "risque": choix.get("risque", ""),
            "prix_decision_17h": prix_decision.get(ticker),
            "prix_entree": None,        # figé à l'évaluation = clôture du jour d'achat
            "evaluation": None,         # rempli le lendemain
        }
        donnees["positions"].append(position)
        nouvelles.append(position)

    _sauver(donnees)
    return nouvelles


def a_deja_achete(jour: dt.date) -> bool:
    """Vrai si des achats ont déjà été enregistrés pour cette date (anti-doublon)."""
    donnees = _charger()
    return any(p["date_achat"] == jour.isoformat() for p in donnees["positions"])


def positions_a_evaluer(aujourd_hui: dt.date) -> list[dict]:
    """Positions achetées une séance précédente et pas encore évaluées."""
    donnees = _charger()
    a_faire = []
    for p in donnees["positions"]:
        if p.get("evaluation") is None and p["date_achat"] < aujourd_hui.isoformat():
            a_faire.append(p)
    return a_faire


def mettre_a_jour_position(id_position: str, champs: dict) -> None:
    donnees = _charger()
    for p in donnees["positions"]:
        if p["id"] == id_position:
            p.update(champs)
            break
    _sauver(donnees)


def toutes_positions() -> list[dict]:
    return _charger()["positions"]
