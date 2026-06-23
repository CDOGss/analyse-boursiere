"""Analyse générative : Claude Opus 4.8 choisit la/les meilleure(s) action(s)."""
from __future__ import annotations

import datetime as dt
import json

import anthropic

import config
from app.market import Instantane

SYSTEME = """\
Tu es un gérant actions spécialisé sur la place de Paris (Euronext, CAC 40 et \
SBF 120). On t'interroge environ 30 minutes avant la clôture (17h30). Objectif : \
identifier la ou les actions de l'univers fourni qui ont la meilleure probabilité \
d'OUVRIR EN HAUSSE demain matin, pour un achat ce soir (~5 min avant la clôture) \
et une revente le lendemain matin.

Mécanisme à exploiter (du plus important au moins important) :
1. LA TAPE AMÉRICAINE : Paris ferme à 17h30 mais Wall Street tourne jusqu'à 22h. \
Le gap clôture→ouverture du lendemain est largement piloté par le sens du marché \
US ce soir (S&P 500, Nasdaq) et le VIX. Une tape US verte favorise une ouverture \
parisienne en hausse ; une tape rouge est un vent contraire.
2. CATALYSEUR DATÉ : actualité du jour, et surtout tout événement attendu d'ici \
demain matin (résultats, guidance, opération). Attention aux résultats publiés \
avant l'ouverture = risque binaire (ne parie dessus que si c'est explicitement ta thèse).
3. MOMENTUM DE FIN DE SÉANCE : une clôture près du plus-haut du jour (champ « clôt@ » \
proche de 1.00) avec volume soutenu trahit un flux acheteur — exactement ce qu'on \
cherche à prolonger. Une clôture près du plus-bas est un signal contraire.
4. SENTIMENT SOCIAL (StockTwits via ADR/US) : signal d'appoint retail, à ne pas surpondérer.

Règles :
- Choisis uniquement des tickers présents dans l'univers fourni. N'invente aucun chiffre.
- Privilégie les CANDIDATS PRIORITAIRES (shortlist enrichie : meilleur momentum de \
clôture / volume, avec calendrier de résultats). Tu peux choisir hors shortlist \
seulement si un catalyseur d'actualité fort le justifie.
- Si une action publie ses RÉSULTATS d'ici demain matin (signalé), c'est un risque \
binaire : évite-la, sauf si c'est explicitement et solidement ta thèse.
- Sois SÉLECTIF. Tu peux retenir 2 actions, mais si une seule est vraiment \
convaincante, n'en retiens qu'UNE. La qualité prime sur la quantité.
- Chaque choix doit citer un mécanisme concret tiré des données (catalyseur, \
momentum de clôture, tape US, sentiment). Si l'argument est faible, baisse la conviction.
- Tiens compte de ton TRACK RECORD récent fourni : ajuste si un type de pari échoue.
- Reste lucide : c'est une simulation, l'edge overnight est mince et bruité.
"""

SCHEMA = {
    "type": "object",
    "properties": {
        "synthese_marche": {
            "type": "string",
            "description": "2-3 phrases : ambiance Paris du jour ET sens de la tape US ce soir.",
        },
        "selection": {
            "type": "array",
            "description": "1 OU 2 actions retenues (au moins 1), de la plus à la moins convaincante.",
            "items": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string"},
                    "nom": {"type": "string"},
                    "conviction": {"type": "integer", "description": "0 à 100."},
                    "catalyseur": {
                        "type": "string",
                        "description": "Le déclencheur concret attendu pour la hausse de demain matin.",
                    },
                    "raisonnement": {
                        "type": "string",
                        "description": "Argumentaire (2-4 phrases) reliant tape US / momentum / catalyseur.",
                    },
                    "risque": {
                        "type": "string",
                        "description": "Principal risque ou point de vigilance (ex: résultats demain, tape US fragile).",
                    },
                },
                "required": ["ticker", "nom", "conviction", "catalyseur",
                             "raisonnement", "risque"],
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
    contexte_macro: str = "",
    bilan_recent: str = "",
    bloc_shortlist: str = "",
    consigne_regime: str = "",
) -> dict:
    """Interroge Claude et renvoie la sélection structurée (dict)."""
    if not config.ANTHROPIC_API_KEY:
        raise RuntimeError(
            "ANTHROPIC_API_KEY manquante. Copie .env.example en .env et renseigne ta clé."
        )

    # Robustesse : aux heures de pointe l'API peut renvoyer un 529 « overloaded »
    # transitoire (ou un 429/5xx). Le SDK réessaie automatiquement avec un backoff
    # exponentiel ; on relève la limite à 8 pour encaisser un pic de charge plutôt
    # que de faire planter tout le run sur un simple à-coup passager.
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY, max_retries=8)

    def section(titre: str, contenu: str) -> str:
        return f"\n=== {titre} ===\n{contenu}\n" if contenu else ""

    invite = f"""\
Date du jour : {jour.strftime('%A %d %B %Y')} (~17h, séance Euronext Paris bientôt close).
{section("CONTEXTE MACRO (tape US en séance, CAC, VIX)", contexte_macro)}\
{section("TON TRACK RECORD RÉCENT (apprends de tes résultats)", bilan_recent)}\
=== FLUX D'ACTUALITÉ DU JOUR ===
{bloc_actu}
{section("CANDIDATS PRIORITAIRES — shortlist enrichie (clôt@=range 1=haut ; résultats à venir signalés)", bloc_shortlist)}\
=== UNIVERS COMPLET (contexte ; clôt@ = position dans le range, 1=plus haut) ===
{_bloc_marche(instantanes)}
{section("SENTIMENT SOCIAL (StockTwits, ADR/US — signal d'appoint)", bloc_social)}\
{section("RÉGIME DE MARCHÉ", consigne_regime)}\
Sélectionne 1 ou 2 actions à acheter ce soir (≈5 min avant la clôture) pour
profiter d'une probable hausse demain matin. Privilégie la qualité : une seule
si une seule convainc. Respecte la consigne de régime ci-dessus. Réponds selon
le schéma demandé.
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
