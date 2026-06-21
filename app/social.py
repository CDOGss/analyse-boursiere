"""Sentiment social via StockTwits (gratuit, sans clé).

StockTwits ne couvre pas les tickers Euronext (.PA). On interroge donc les
symboles ADR/US correspondants (config.ADR_STOCKTWITS), on agrège le sentiment
haussier/baissier des messages récents, et on produit un bloc texte injecté
dans le prompt d'analyse à côté des flux RSS.

Note : signal de sentiment retail, différé, sur la cotation US — à pondérer
modestement. Couvre seulement une vingtaine de grandes valeurs françaises.
"""
from __future__ import annotations

import datetime as dt
import json
import time
import urllib.request
from dataclasses import dataclass

import config

URL = "https://api.stocktwits.com/api/2/streams/symbol/{}.json"
_ENTETES = {"User-Agent": "Mozilla/5.0 (analyse-boursiere paper-trading)"}


@dataclass
class SentimentSocial:
    ticker: str          # ticker .PA
    nom: str
    symbole_us: str
    n_messages: int
    n_haussier: int
    n_baissier: int

    @property
    def score(self) -> float | None:
        """Score net dans [-1, 1] : (haussier - baissier) / (haussier + baissier)."""
        total = self.n_haussier + self.n_baissier
        return (self.n_haussier - self.n_baissier) / total if total else None

    def ligne(self) -> str:
        s = self.score
        if s is None:
            tendance = "neutre/sans avis"
        elif s > 0.3:
            tendance = "haussier"
        elif s < -0.3:
            tendance = "baissier"
        else:
            tendance = "mitigé"
        score_txt = f"{s:+.2f}" if s is not None else "n/d"
        return (
            f"{self.ticker} ({self.nom}) [{self.symbole_us}]: {tendance} "
            f"(score {score_txt}, {self.n_haussier}↑/{self.n_baissier}↓ "
            f"sur {self.n_messages} msg)"
        )


def _recuperer_symbole(symbole_us: str, depuis: dt.datetime) -> tuple[int, int, int]:
    """Retourne (n_messages, n_haussier, n_baissier) pour un symbole StockTwits."""
    url = URL.format(symbole_us)
    try:
        req = urllib.request.Request(url, headers=_ENTETES)
        with urllib.request.urlopen(req, timeout=12) as r:
            data = json.load(r)
    except Exception:
        return (0, 0, 0)

    messages = data.get("messages", [])
    n, haussier, baissier = 0, 0, 0
    for m in messages:
        # Filtre de fraîcheur
        cree = m.get("created_at", "")
        try:
            date_msg = dt.datetime.fromisoformat(cree.replace("Z", "+00:00"))
            if date_msg < depuis:
                continue
        except (ValueError, AttributeError):
            pass
        n += 1
        senti = (m.get("entities") or {}).get("sentiment") or {}
        basic = senti.get("basic")
        if basic == "Bullish":
            haussier += 1
        elif basic == "Bearish":
            baissier += 1
    return (n, haussier, baissier)


def recuperer_sentiment(univers: dict[str, str]) -> list[SentimentSocial]:
    """Interroge StockTwits pour les valeurs disposant d'un ADR couvert."""
    if not config.ACTIVER_SENTIMENT_SOCIAL:
        return []

    depuis = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=config.SENTIMENT_HEURES)
    resultats: list[SentimentSocial] = []

    for ticker_pa, symbole_us in config.ADR_STOCKTWITS.items():
        nom = univers.get(ticker_pa, ticker_pa)
        n, h, b = _recuperer_symbole(symbole_us, depuis)
        if n > 0:
            resultats.append(SentimentSocial(ticker_pa, nom, symbole_us, n, h, b))
        time.sleep(0.3)  # politesse / limite de débit StockTwits

    # Tri par intensité du signal (volume * |score|)
    resultats.sort(
        key=lambda s: (s.n_messages * abs(s.score)) if s.score is not None else 0,
        reverse=True,
    )
    return resultats


def bloc_social(sentiments: list[SentimentSocial]) -> str:
    """Formate le sentiment social pour le prompt d'analyse."""
    if not sentiments:
        return "(Aucun sentiment social disponible.)"
    lignes = [s.ligne() for s in sentiments]
    return "\n".join(f"- {l}" for l in lignes)
