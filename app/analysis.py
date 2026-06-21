"""Analyse générative : Claude Opus 4.8 choisit les 2 meilleures actions."""
from __future__ import annotations

import datetime as dt
import json

import anthropic

import config
from app.market import Instantane

SYSTEME = """\
Tu es un analyste actions spécialisé sur la place de Paris (Euronext, CAC 40 et \
SBF 120). On t'interroge environ 30 minutes avant la clôture (17h30). \
Ta mission : à partir du flux d'actualité du jour et d'un instantané de marché, \
identifier les DEUX actions de l'univers fourni qui ont la meilleure probabilité \
d'ouvrir en hausse le lendemain matin (effet de continuation haussière, \
catalyseur d'actualité, momentum, flux acheteur de fin de séance).

Contraintes :
- Choisis uniquement des tickers présents dans l'univers fourni.
- Sois sélectif et argumente chaque choix par un catalyseur concret et vérifiable \
dans les données fournies (actualité, momentum, volume, sentiment social).
- Reste lucide : il s'agit d'une simulation. N'invente pas de chiffres. \
Si un catalyseur est faible, baisse la conviction.
- Le sentiment social provient de StockTwits sur la cotation US/ADR (avis retail, \
différé, partiel) : utilise-le comme signal d'appoint, pas comme preuve. \
Ne le surpondère pas.
"""

# Schéma de sortie structuré (output_config.format)
SCHEMA = {
    "type": "object",
    "properties": {
        "synthese_marche": {
            "type": "string",
            "description": "2-3 phrases sur l'ambiance du marché parisien du jour.",
        },
        "selection": {
            "type": "array",
            "description": "Exactement 2 actions retenues, de la plus à la moins convaincante.",
            "items": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string"},
                    "nom": {"type": "string"},
                    "conviction": {
                        "type": "integer",
                        "description": "Niveau de conviction de 0 à 100.",
                    },
                    "catalyseur": {
                        "type": "string",
                        "description": "Le déclencheur concret attendu pour la hausse du lendemain.",
                    },
                    "raisonnement": {
                        "type": "string",
                        "description": "Argumentaire court (2-4 phrases).",
                    },
                },
                "required": ["ticker", "nom", "conviction", "catalyseur", "raisonnement"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["synthese_marche", "selection"],
    "additionalProperties": False,
}


def _bloc_marche(instantanes: list[Instantane]) -> str:
    lignes = [i.ligne() for i in instantanes if i.dernier is not None]
    return "\n".join(f"- {l}" for l in lignes)


def choisir_actions(
    instantanes: list[Instantane],
    bloc_actu: str,
    jour: dt.date,
    bloc_social: str = "",
) -> dict:
    """Interroge Claude et renvoie la sélection structurée (dict)."""
    if not config.ANTHROPIC_API_KEY:
        raise RuntimeError(
            "ANTHROPIC_API_KEY manquante. Copie .env.example en .env et renseigne ta clé."
        )

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    section_social = ""
    if bloc_social:
        section_social = (
            "\n=== SENTIMENT SOCIAL (StockTwits, ADR/US — signal d'appoint) ===\n"
            f"{bloc_social}\n"
        )

    invite = f"""\
Date du jour : {jour.strftime('%A %d %B %Y')} (~17h, séance Euronext Paris bientôt close).

=== FLUX D'ACTUALITÉ DU JOUR ===
{bloc_actu}

=== INSTANTANÉ DE MARCHÉ (univers CAC 40 + SBF 120) ===
{_bloc_marche(instantanes)}
{section_social}
Sélectionne les 2 meilleures actions à acheter ce soir (≈5 min avant la clôture)
pour profiter d'une probable hausse demain matin. Réponds selon le schéma demandé.
"""

    reponse = client.messages.create(
        model=config.MODELE,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        output_config={
            "effort": "high",
            "format": {"type": "json_schema", "schema": SCHEMA},
        },
        system=SYSTEME,
        messages=[{"role": "user", "content": invite}],
    )

    texte = next((b.text for b in reponse.content if b.type == "text"), "")
    return json.loads(texte)
