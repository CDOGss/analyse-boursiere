"""Récupération des flux d'actualité du jour (RSS, sans clé API)."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import feedparser

import config


@dataclass
class Article:
    titre: str
    resume: str
    source: str
    date: str

    def texte_court(self) -> str:
        resume = (self.resume or "").strip().replace("\n", " ")
        if len(resume) > 280:
            resume = resume[:280] + "…"
        return f"[{self.source}] {self.titre} — {resume}"


def _nettoyer_html(texte: str) -> str:
    """Supprime grossièrement les balises HTML d'un résumé RSS."""
    import re

    return re.sub(r"<[^>]+>", "", texte or "").strip()


def recuperer_actualites(max_par_flux: int = 25) -> list[Article]:
    """Agrège les articles récents de tous les flux configurés.

    On ne garde que les articles des ~2 derniers jours pour rester sur le flux
    du jour (et la veille au soir).
    """
    limite = dt.datetime.now(config.FUSEAU_PARIS) - dt.timedelta(days=2)
    articles: list[Article] = []
    vus: set[str] = set()

    for url in config.FLUX_ACTU:
        try:
            flux = feedparser.parse(url)
        except Exception:
            continue
        source = flux.feed.get("title", url)
        for entree in flux.entries[:max_par_flux]:
            titre = (entree.get("title") or "").strip()
            if not titre or titre in vus:
                continue

            # Filtre temporel quand la date est disponible
            publie = entree.get("published_parsed") or entree.get("updated_parsed")
            date_str = ""
            if publie:
                date_pub = dt.datetime(*publie[:6], tzinfo=dt.timezone.utc)
                if date_pub.astimezone(config.FUSEAU_PARIS) < limite:
                    continue
                date_str = date_pub.astimezone(config.FUSEAU_PARIS).strftime("%Y-%m-%d %H:%M")

            vus.add(titre)
            articles.append(
                Article(
                    titre=titre,
                    resume=_nettoyer_html(entree.get("summary", "")),
                    source=source,
                    date=date_str,
                )
            )

    return articles


def bloc_actualites(articles: list[Article], maximum: int = 60) -> str:
    """Formate les articles en un bloc texte pour le prompt."""
    lignes = [a.texte_court() for a in articles[:maximum]]
    if not lignes:
        return "(Aucune actualité récupérée — flux indisponibles.)"
    return "\n".join(f"- {l}" for l in lignes)
