"""Calendrier de résultats (earnings) via yfinance.

Savoir si une société publie ses résultats avant l'ouverture de demain est un
signal majeur : c'est un événement binaire pendant la nuit qu'il faut soit
éviter, soit assumer explicitement comme thèse.

Note : les révisions d'analystes ne sont PAS disponibles via yfinance pour les
tickers Euronext (.PA) — données fondamentales US-centriques. Seules les dates
de résultats sont exploitées.
"""
from __future__ import annotations

import datetime as dt

import yfinance as yf

import config


def _prochaine_date_resultats(ticker: str, aujourd_hui: dt.date) -> dt.date | None:
    try:
        cal = yf.Ticker(ticker).calendar
    except Exception:
        return None
    if not isinstance(cal, dict):
        return None
    dates = cal.get("Earnings Date") or []
    futures = []
    for d in dates:
        if isinstance(d, dt.datetime):
            d = d.date()
        if isinstance(d, dt.date) and d >= aujourd_hui:
            futures.append(d)
    return min(futures) if futures else None


def enrichir(tickers: list[str], aujourd_hui: dt.date) -> dict[str, str]:
    """Retourne {ticker: note d'événement} pour les tickers fournis.

    La note est une chaîne courte (ou vide) prête à coller en bout de ligne du
    candidat dans le prompt.
    """
    notes: dict[str, str] = {}
    for t in tickers:
        date_res = _prochaine_date_resultats(t, aujourd_hui)
        if not date_res:
            notes[t] = ""
            continue
        jours = (date_res - aujourd_hui).days
        if jours <= 1:
            notes[t] = f" | ⚠️ RÉSULTATS imminents ({date_res:%d/%m}) — risque binaire overnight"
        elif jours <= config.FENETRE_RESULTATS_JOURS:
            notes[t] = f" | résultats dans {jours} j ({date_res:%d/%m})"
        else:
            notes[t] = ""
    return notes
