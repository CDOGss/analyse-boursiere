"""Benchmark CAC 40 : « acheter l'indice chaque soir » comme témoin.

Pour chaque jour évalué, on mesure le rendement du CAC 40 si on l'avait acheté
à la clôture du jour d'achat et revendu :
  - à l'ouverture du lendemain (overnight, comparable au scénario « ouverture »),
  - à la clôture du lendemain (séance complète, comparable au scénario « 17h »).

Cela permet de mesurer l'ALPHA réel de la stratégie (talent) vs simplement être
exposé au marché (beta). Calculé une fois par jour évalué et mis en cache dans
data/benchmark.json (n'utilise que des données journalières, robuste).
"""
from __future__ import annotations

import datetime as dt
import json

import pandas as pd
import yfinance as yf

import config


def _charger() -> dict:
    if config.FICHIER_BENCHMARK.exists():
        with open(config.FICHIER_BENCHMARK, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _sauver(d: dict) -> None:
    with open(config.FICHIER_BENCHMARK, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)


def _journalier(date_achat: dt.date, date_eval: dt.date) -> dict | None:
    debut = date_achat - dt.timedelta(days=6)
    fin = date_eval + dt.timedelta(days=1)
    try:
        df = yf.download(config.INDICE_BENCHMARK, start=debut.strftime("%Y-%m-%d"),
                         end=fin.strftime("%Y-%m-%d"), interval="1d",
                         auto_adjust=False, progress=False)
    except Exception:
        return None
    if df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    avant = df[df.index.date <= date_achat]
    jour = df[df.index.date == date_eval]
    if avant.empty or jour.empty:
        return None

    cloture_achat = float(avant["Close"].iloc[-1])
    ouverture_eval = float(jour["Open"].iloc[0])
    cloture_eval = float(jour["Close"].iloc[0])
    if not cloture_achat:
        return None
    return {
        "date_achat": date_achat.isoformat(),
        "overnight_pct": round((ouverture_eval / cloture_achat - 1) * 100, 3),
        "session_pct": round((cloture_eval / cloture_achat - 1) * 100, 3),
    }


def assurer(date_eval: dt.date, date_achat: dt.date) -> None:
    """Calcule et met en cache la référence CAC 40 pour un jour évalué (si absente)."""
    cache = _charger()
    cle = date_eval.isoformat()
    if cle in cache:
        return
    ref = _journalier(date_achat, date_eval)
    if ref:
        cache[cle] = ref
        _sauver(cache)


def references() -> dict:
    """Retourne {date_eval: {overnight_pct, session_pct, date_achat}}."""
    return _charger()
