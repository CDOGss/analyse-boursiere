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
et une revente le lendemain. Vise un titre capable d'ouvrir en hausse ET de tenir \
son gain en séance (le résultat est aussi mesuré à 17h).

Mécanisme à exploiter (du plus important au moins important) :
1. MOMENTUM DE FIN DE SÉANCE SPÉCIFIQUE AU TITRE : une clôture près du plus-haut \
du jour (champ « clôt@ » proche de 1.00) avec volume soutenu trahit un flux \
acheteur propre à la valeur — exactement ce qu'on cherche à prolonger. Une \
clôture près du plus-bas est un signal contraire. C'est TA source d'edge.
2. CATALYSEUR DATÉ : actualité du jour, et surtout tout événement attendu d'ici \
demain matin (résultats, guidance, opération). Attention aux résultats publiés \
avant l'ouverture = risque binaire (ne parie dessus que si c'est explicitement ta thèse).
3. LA TAPE AMÉRICAINE (contexte, PAS une thèse) : Paris ferme à 17h30 mais Wall \
Street tourne jusqu'à 22h ; une tape US verte est un vent porteur, une tape rouge \
un vent contraire. Mais la tape sert à DOSER le risque (la consigne de RÉGIME le \
fait déjà) — elle ne justifie JAMAIS à elle seule un choix de titre : le sens de \
la nuit US est imprévisible et peut se retourner après ta décision.
4. SENTIMENT SOCIAL (StockTwits via ADR/US) : signal d'appoint retail, à ne pas surpondérer.

Règles :
- Choisis EXCLUSIVEMENT des tickers de la SHORTLIST « candidats prioritaires » \
fournie (déjà filtrée : titres désertés et hausses paraboliques écartés — mais le \
volume peut rester modeste : à signal égal, privilégie le ratio de volume le plus \
élevé). N'invente aucun chiffre.
- DIVERSIFICATION OBLIGATOIRE : si tu retiens 2 actions, elles doivent être de \
SECTEURS NETTEMENT DIFFÉRENTS. Jamais deux valeurs du même secteur ou thème \
(ex. deux banques, deux aériennes, deux du luxe, deux pétrolières, deux foncières).
- Évite un titre déjà SUR-ÉTENDU (très forte hausse du jour ou cumulée sur 5 jours) \
même si le momentum est bon : il est le plus exposé à une prise de bénéfices à \
l'ouverture. Préfère une force « tranquille » (clôture au plus-haut, volume solide, \
hausse mesurée) à un titre qui vient d'exploser.
- PAS DE PARI « BETA PUR » : n'achète jamais un titre dont la seule thèse est de \
prolonger la tape US (ex. une valeur très corrélée au Nasdaq choisie uniquement \
parce que le Nasdaq est vert ce soir). Ce pari revient à jouer la direction du \
marché pendant la nuit — un ETF le fait sans risque spécifique. Chaque choix doit \
reposer d'abord sur une force PROPRE au titre (flux de clôture, volume, catalyseur) \
qui tiendrait même si la tape US se retournait.
- Si une action publie ses RÉSULTATS d'ici demain matin (signalé), c'est un risque \
binaire : évite-la, sauf si c'est explicitement et solidement ta thèse. Même \
prudence si un événement macro majeur (Fed, CPI, BCE) tombe avant demain matin.
- VENDREDI SOIR : le pari porte 3 nuits (tout le week-end) — bien plus de temps \
pour qu'une mauvaise nouvelle tombe, sans espérance supplémentaire en face. \
Monte d'un cran ton exigence ce soir-là.
- Sois SÉLECTIF. Tu peux retenir 2 actions, mais si une seule est vraiment \
convaincante, n'en retiens qu'UNE. Et si AUCUN candidat ne montre un vrai flux \
acheteur de clôture, ne retiens RIEN (sélection vide) : le cash vaut mieux qu'un \
pari forcé, l'edge overnight récompense la qualité, pas l'activité. Le cash doit \
rester l'exception (séance sans aucun flux net), pas la règle.
- Chaque choix doit citer un mécanisme concret tiré des données (catalyseur, \
momentum de clôture, tape US, sentiment). Si l'argument est faible, baisse la conviction.
- Tiens compte de ton TRACK RECORD récent fourni, mais SANS sur-réagir : n'ajuste \
que sur un MOTIF RÉPÉTÉ (le même type d'erreur 3 fois ou plus). Un pari bien \
construit peut perdre sur un retournement nocturne imprévisible — ce n'est pas \
une raison d'abandonner le type de pari.
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
            "description": "0, 1 ou 2 actions retenues (vide si aucun setup convaincant — le cash "
                           "est un choix valide mais exceptionnel), de la plus à la moins convaincante.",
            "items": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string"},
                    "nom": {"type": "string"},
                    "conviction": {
                        "type": "integer",
                        "description": "0 à 100 avec ancres : <45 = spéculatif faible (ne devrait "
                                       "pas être retenu), 45-60 = correct, 60-75 = solide, "
                                       ">75 = exceptionnel (rare, quelques fois par mois).",
                    },
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
Sélectionne 0, 1 ou 2 actions à acheter ce soir (≈5 min avant la clôture) pour
profiter d'une probable hausse demain matin. Privilégie la qualité : une seule
si une seule convainc, aucune si aucune ne convainc (cash = choix valide mais
exceptionnel). Respecte la consigne de régime ci-dessus. Réponds selon le
schéma demandé.
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
