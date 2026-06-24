"""Paramètres globaux de l'application d'analyse boursière (marche à blanc)."""
from __future__ import annotations

import os
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

# --- Chemins ---------------------------------------------------------------
RACINE = Path(__file__).resolve().parent
DOSSIER_DATA = RACINE / "data"
DOSSIER_RAPPORTS = RACINE / "reports"
FICHIER_PORTEFEUILLE = DOSSIER_DATA / "portefeuille.json"
FICHIER_BENCHMARK = DOSSIER_DATA / "benchmark.json"

DOSSIER_DATA.mkdir(exist_ok=True)
DOSSIER_RAPPORTS.mkdir(exist_ok=True)

# --- Marché ----------------------------------------------------------------
FUSEAU_PARIS = ZoneInfo("Europe/Paris")
HEURE_OUVERTURE = (9, 0)        # Euronext Paris ouvre à 09:00
HEURE_DEMI_HEURE = (9, 30)      # première demi-heure
HEURE_MI_JOURNEE = (13, 0)      # mi-journée
HEURE_17H = (17, 0)             # 17h (la séance ferme à 17:30)

# Fenêtre d'exécution autorisée (heure de Paris) pour le garde-fou --garde-cloture.
# Les crons UTC de GitHub Actions sont souvent RETARDÉS (parfois de plus d'une
# heure). Plutôt qu'exiger 17h pile (et rater la journée au moindre retard), on
# accepte toute la soirée : la clôture est figée dès 17h30 et le pari overnight
# reste valable jusqu'à l'ouverture du lendemain. L'anti-doublon empêche les
# achats en double si plusieurs crons retardés se déclenchent.
HEURE_EXEC_MIN = 17            # ne pas acheter avant ~la clôture
HEURE_EXEC_MAX = 21            # filet de sécurité tardif (Wall Street ouvre jusqu'à 22h)

# --- API / modèle ----------------------------------------------------------
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
MODELE = os.getenv("ANALYSE_MODEL", "claude-opus-4-8")
ALLOCATION_PAR_ACTION = float(os.getenv("ALLOCATION_PAR_ACTION", "500"))
NB_ACHATS_PAR_SOIR = 2

# Coût estimé d'un aller-retour (achat + vente) en % du montant investi.
# Sert à afficher un P&L NET de frais dans le bilan mensuel (les frais rongent
# l'edge overnight). ~0.20% est réaliste pour de grandes valeurs liquides chez
# un courtier discount. Mets 0 pour ignorer les frais.
COUT_TRANSACTION_PCT = float(os.getenv("COUT_TRANSACTION_PCT", "0.20"))

# Présélection : nombre de candidats prioritaires (shortlist) envoyés à Claude
# avec données enrichies (résultats à venir, momentum de clôture, social).
SHORTLIST_N = 25
# Fenêtre d'alerte « résultats imminents » (jours).
FENETRE_RESULTATS_JOURS = 4
# Indice de référence (benchmark) : CAC 40.
INDICE_BENCHMARK = "^FCHI"

# --- Filtre de régime ------------------------------------------------------
# L'effet overnight s'affaiblit (voire s'inverse) en régime stressé. On module
# le nombre de paris selon le VIX et la tape US à 17h. Seuils ajustables.
ACTIVER_FILTRE_REGIME = True
VIX_PRUDENCE = 25.0       # au-dessus : au plus 1 pari
VIX_EXTREME = 32.0        # au-dessus : aucun pari (cash)
SP500_PRUDENCE = -0.5     # tape US sous ce % : au plus 1 pari
SP500_HOSTILE = -1.5      # tape US sous ce % : aucun pari (cash)

# --- Garde-fous de sélection -----------------------------------------------
# Principes de bon sens appliqués AVANT (filtrage de la shortlist) et APRÈS
# (validation de la sélection de Claude) le choix, pour corriger trois travers
# classiques du momentum. Indépendants du P&L récent → pas de sur-optimisation.
VOLUME_MIN_RATIO = 1.0     # volume du jour ≥ moyenne 20j, sinon flux non confirmé
HAUSSE_MAX_1J_PCT = 6.0    # au-delà : titre sur-étendu sur la séance, écarté
HAUSSE_MAX_5J_PCT = 15.0   # idem sur 5 séances (montée parabolique)

# Regroupement sectoriel (thèmes à forte corrélation) pour interdire deux paris
# du même secteur le même soir. Couvre les clusters les plus concentrants ; un
# ticker absent est considéré « secteur inconnu » → pas de collision (autorisé).
GROUPES_SECTEURS = {
    "banque": {"BNP.PA", "ACA.PA", "GLE.PA"},
    "assurance": {"CS.PA", "SCR.PA", "COFA.PA"},
    "luxe": {"MC.PA", "RMS.PA", "KER.PA", "EL.PA"},
    "spiritueux": {"RI.PA", "RCO.PA"},
    "auto": {"RNO.PA", "STLAP.PA", "ML.PA", "FR.PA", "OPM.PA", "FRVIA.PA"},
    "aérien": {"AF.PA", "ADP.PA"},
    "aéronautique-défense": {"AIR.PA", "SAF.PA", "HO.PA", "AM.PA"},
    "semi-conducteurs": {"STMPA.PA", "SOI.PA"},
    "tech-logiciels": {"CAP.PA", "SOP.PA", "ATO.PA", "DSY.PA", "WLN.PA", "OVH.PA"},
    "énergie": {"TTE.PA", "RUI.PA", "MAU.PA", "TE.PA"},
    "utilities": {"ENGI.PA", "VIE.PA", "VLTSA.PA"},
    "foncières": {"URW.PA", "GFC.PA", "ICAD.PA", "COV.PA", "LI.PA", "CARM.PA",
                  "MERY.PA", "ALTA.PA", "NXI.PA"},
    "construction-concessions": {"DG.PA", "FGR.PA", "SGO.PA", "SPIE.PA", "EN.PA"},
    "santé-pharma": {"SAN.PA", "IPN.PA", "BIM.PA", "ERF.PA", "DIM.PA", "VLA.PA",
                     "VIRP.PA", "EAPI.PA"},
    "conso-base": {"BN.PA", "CA.PA"},
    "médias-pub": {"PUB.PA", "MMT.PA", "TFI.PA"},
    "matériaux-chimie": {"AI.PA", "AKE.PA", "MT.AS", "ERA.PA", "NK.PA"},
}

# --- Flux d'actualité (RSS, gratuits, sans clé) ----------------------------
FLUX_ACTU = [
    "https://www.boursorama.com/bourse/actualites/rss/",
    "https://www.lesechos.fr/rss/rss_bourse.xml",
    "https://www.lemonde.fr/economie/rss_full.xml",
    "https://feeds.feedburner.com/lexpansion/rss",
]

# --- Univers d'actions -----------------------------------------------------
# Tickers Yahoo Finance. Le CAC 40 est inclus dans le SBF 120.
# Liste éditable : ajoute/retire selon tes besoins. Suffixe .PA = Euronext Paris.
CAC40 = {
    "AC.PA": "Accor",
    "AI.PA": "Air Liquide",
    "AIR.PA": "Airbus",
    "MT.AS": "ArcelorMittal",
    "CS.PA": "AXA",
    "BNP.PA": "BNP Paribas",
    "EN.PA": "Bouygues",
    "CAP.PA": "Capgemini",
    "CA.PA": "Carrefour",
    "ACA.PA": "Crédit Agricole",
    "BN.PA": "Danone",
    "DSY.PA": "Dassault Systèmes",
    "EDEN.PA": "Edenred",
    "ENGI.PA": "Engie",
    "EL.PA": "EssilorLuxottica",
    "ERF.PA": "Eurofins Scientific",
    "RMS.PA": "Hermès",
    "KER.PA": "Kering",
    "LR.PA": "Legrand",
    "OR.PA": "L'Oréal",
    "MC.PA": "LVMH",
    "ML.PA": "Michelin",
    "ORA.PA": "Orange",
    "RI.PA": "Pernod Ricard",
    "PUB.PA": "Publicis",
    "RNO.PA": "Renault",
    "SAF.PA": "Safran",
    "SGO.PA": "Saint-Gobain",
    "SAN.PA": "Sanofi",
    "SU.PA": "Schneider Electric",
    "GLE.PA": "Société Générale",
    "STLAP.PA": "Stellantis",
    "STMPA.PA": "STMicroelectronics",
    "TEP.PA": "Teleperformance",
    "HO.PA": "Thales",
    "TTE.PA": "TotalEnergies",
    "URW.PA": "Unibail-Rodamco-Westfield",
    "VIE.PA": "Veolia",
    "DG.PA": "Vinci",
    "VIV.PA": "Vivendi",
}

# Valeurs du SBF 120 hors CAC 40. Avec le CAC 40 ci-dessus, on couvre ~120 titres.
# Instantané indicatif : l'indice est révisé chaque trimestre — ajuste si besoin.
# (Valeurs délistées/nationalisées comme EDF ou Tarkett retirées.)
SBF120_EXTRA = {
    "ADP.PA": "Aéroports de Paris (ADP)",
    "AF.PA": "Air France-KLM",
    "ALO.PA": "Alstom",
    "ALTA.PA": "Altarea",
    "ATE.PA": "Alten",
    "AMUN.PA": "Amundi",
    "APAM.AS": "Aperam",
    "AKE.PA": "Arkema",
    "ATO.PA": "Atos",
    "AVT.PA": "Avantium",
    "BEN.PA": "Bénéteau",
    "BB.PA": "BIC",
    "BIM.PA": "bioMérieux",
    "BOL.PA": "Bolloré",
    "BVI.PA": "Bureau Veritas",
    "CARM.PA": "Carmila",
    "CLARI.PA": "Clariane (ex-Korian)",
    "COFA.PA": "Coface",
    "COV.PA": "Covivio",
    "AM.PA": "Dassault Aviation",
    "DBG.PA": "Derichebourg",
    "EAPI.PA": "Euroapi",
    "RF.PA": "Eurazeo",
    "ENX.PA": "Euronext",
    "FGR.PA": "Eiffage",
    "ELIOR.PA": "Elior",
    "ELIS.PA": "Elis",
    "ERA.PA": "Eramet",
    "FDJU.PA": "FDJ United (ex-La Française des Jeux)",
    "FNAC.PA": "Fnac Darty",
    "FRVIA.PA": "Forvia (ex-Faurecia)",
    "GFC.PA": "Gecina",
    "GET.PA": "Getlink",
    "GTT.PA": "GTT (Gaztransport & Technigaz)",
    "ICAD.PA": "Icade",
    "NK.PA": "Imerys",
    "IPN.PA": "Ipsen",
    "IPS.PA": "Ipsos",
    "DEC.PA": "JCDecaux",
    "LI.PA": "Klépierre",
    "AYV.PA": "Ayvens (ex-ALD)",
    "MAU.PA": "Maurel & Prom",
    "MERY.PA": "Mercialys",
    "MRN.PA": "Mersen",
    "MMT.PA": "Métropole Télévision (M6)",
    "NEX.PA": "Nexans",
    "NXI.PA": "Nexity",
    "OVH.PA": "OVHcloud",
    "OPM.PA": "OPmobility (ex-Plastic Omnium)",
    "PLX.PA": "Pluxee",
    "RCO.PA": "Rémy Cointreau",
    "RXL.PA": "Rexel",
    "RUI.PA": "Rubis",
    "DIM.PA": "Sartorius Stedim Biotech",
    "SCR.PA": "SCOR",
    "SK.PA": "SEB",
    "SESG.PA": "SES",
    "SW.PA": "Sodexo",
    "SOI.PA": "Soitec",
    "S30.PA": "Solutions 30",
    "SOP.PA": "Sopra Steria",
    "SPIE.PA": "SPIE",
    "TE.PA": "Technip Energies",
    "TFI.PA": "TF1",
    "TRI.PA": "Trigano",
    "UBI.PA": "Ubisoft",
    "VK.PA": "Vallourec",
    "FR.PA": "Valeo",
    "VLA.PA": "Valneva",
    "VRLA.PA": "Verallia",
    "VCT.PA": "Vicat",
    "VIRP.PA": "Virbac",
    "VLTSA.PA": "Voltalia",
    "MF.PA": "Wendel",
    "WLN.PA": "Worldline",
}


def univers() -> dict[str, str]:
    """Retourne {ticker: nom} pour tout l'univers analysé (CAC 40 + SBF 120)."""
    u = {**CAC40, **SBF120_EXTRA}
    return {t: n for t, n in u.items() if n}  # élimine les placeholders vides


# --- Sentiment social (StockTwits) -----------------------------------------
# StockTwits ne couvre PAS les tickers Euronext (.PA). On passe par les ADR /
# cotations US, seule façon fiable d'obtenir du sentiment sur ces valeurs.
# Correspondance VÉRIFIÉE manuellement (ticker .PA -> symbole StockTwits).
# Les valeurs sans ADR couvert sont simplement absentes (dégradation propre).
ACTIVER_SENTIMENT_SOCIAL = True
SENTIMENT_HEURES = 72  # fenêtre de fraîcheur des messages retenus

ADR_STOCKTWITS = {
    "TTE.PA": "TTE",        # TotalEnergies
    "AIR.PA": "EADSY",      # Airbus
    "MC.PA": "LVMUY",       # LVMH
    "SAN.PA": "SNY",        # Sanofi
    "CS.PA": "AXAHY",       # AXA
    "OR.PA": "LRLCY",       # L'Oréal
    "SU.PA": "SBGSY",       # Schneider Electric
    "BNP.PA": "BNPQY",      # BNP Paribas
    "BN.PA": "DANOY",       # Danone
    "KER.PA": "PPRUY",      # Kering
    "RMS.PA": "HESAY",      # Hermès
    "ORA.PA": "ORAN",       # Orange
    "VIE.PA": "VEOEY",      # Veolia
    "STLAP.PA": "STLA",     # Stellantis
    "STMPA.PA": "STM",      # STMicroelectronics
    "DSY.PA": "DASTY",      # Dassault Systèmes
    "CA.PA": "CRRFY",       # Carrefour
    "RNO.PA": "RNLSY",      # Renault
    "ENGI.PA": "ENGIY",     # Engie
    "ML.PA": "MGDDF",       # Michelin
    "ALO.PA": "ALSMY",      # Alstom
}
