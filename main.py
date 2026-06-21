"""Point d'entrée — lancé tous les jours à 17h (via make / planificateur).

Déroulé d'une exécution :
  1. ÉVALUATION : pour les actions achetées la séance précédente, calcule le
     gain/perte théorique aux 4 moments de la séance du jour (ouverture, 1re
     demi-heure, mi-journée, 17h).
  2. ANALYSE : récupère le flux d'actualité du jour + un instantané du marché,
     demande à Claude Opus 4.8 les 2 meilleures actions, et les « achète » à
     blanc (500€ chacune par défaut).

C'est une MARCHE À BLANC : aucun ordre réel n'est passé.
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys

# Force l'UTF-8 en sortie (les rapports contiennent des emojis/accents) — utile
# notamment sur la console Windows qui utilise cp1252 par défaut.
for flux in (sys.stdout, sys.stderr):
    try:
        flux.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

import config
from app import (analysis, bilan, dashboard, evaluate, evenements, ledger,
                market, news, report, social)


def run(jour: dt.date | None = None, sans_analyse: bool = False) -> None:
    jour = jour or dt.datetime.now(config.FUSEAU_PARIS).date()
    print(f"=== Analyse boursière (marche à blanc) — {jour.isoformat()} ===\n")

    # 1) Évaluation des achats de la veille -------------------------------
    print("[1/2] Évaluation des positions de la séance précédente…")
    resultats_eval = evaluate.evaluer_positions(jour)
    bloc_eval = report.rapport_evaluation(resultats_eval)
    print(bloc_eval)

    contenu = bloc_eval

    # 2) Analyse + sélection du soir --------------------------------------
    if not sans_analyse and ledger.a_deja_achete(jour):
        print("Des achats existent déjà pour aujourd'hui — analyse ignorée (anti-doublon).")
    elif not sans_analyse:
        print("[2/2] Récupération de l'actualité et du marché…")
        univers = config.univers()
        articles = news.recuperer_actualites()
        bloc_actu = news.bloc_actualites(articles)
        instantanes = market.instantane_univers(univers)
        prix_decision = {i.ticker: i.dernier for i in instantanes}

        print("       Récupération du sentiment social (StockTwits)…")
        sentiments = social.recuperer_sentiment(univers)
        bloc_social = social.bloc_social(sentiments)
        print(f"       {len(sentiments)} valeur(s) avec sentiment social.")

        print("       Contexte macro (tape US, CAC, VIX)…")
        ctx_macro = market.contexte_macro()
        bilan_recent = bilan.historique_recent_texte(10)

        print(f"       Présélection des {config.SHORTLIST_N} meilleurs candidats…")
        shortlist = market.preselection(instantanes, config.SHORTLIST_N)
        sentiment_par_ticker = {s.ticker: s for s in sentiments}
        print("       Calendrier de résultats des candidats…")
        notes_events = evenements.enrichir([s.ticker for s in shortlist], jour)
        lignes_sl = []
        for inst in shortlist:
            ligne = inst.ligne() + notes_events.get(inst.ticker, "")
            s = sentiment_par_ticker.get(inst.ticker)
            if s and s.score is not None:
                ligne += f" | social {s.score:+.2f}"
            lignes_sl.append(f"- {ligne}")
        bloc_shortlist = "\n".join(lignes_sl)

        print("       Interrogation de Claude Opus 4.8…")
        analyse = analysis.choisir_actions(
            instantanes, bloc_actu, jour, bloc_social, ctx_macro, bilan_recent,
            bloc_shortlist,
        )
        selection = analyse.get("selection", [])[: config.NB_ACHATS_PAR_SOIR]

        positions = ledger.enregistrer_achats(jour, selection, prix_decision)
        bloc_sel = report.rapport_selection(analyse, positions)
        print(bloc_sel)
        contenu += "\n" + bloc_sel

    # 3) Tableau de bord récapitulatif (tout l'historique) ----------------
    bloc_tdb = dashboard.rendu_texte(dashboard.calculer_stats())
    print(bloc_tdb)
    contenu += "\n" + bloc_tdb

    # 4) Calendrier quotidien (CSV) + tableau de bord mensuel -------------
    chemin_csv = bilan.ecrire_csv()
    bloc_mensuel = bilan.rendu_mensuel()
    chemin_mensuel = bilan.ecrire_bilan_mensuel()
    print(bloc_mensuel)
    contenu += "\n" + bloc_mensuel

    chemin = report.ecrire_rapport(jour, contenu)
    print(f"\nRapport écrit : {chemin}")
    print(f"Calendrier CSV : {chemin_csv}")
    print(f"Bilan mensuel : {chemin_mensuel}")


def main() -> int:
    parseur = argparse.ArgumentParser(description="Analyse boursière en marche à blanc.")
    parseur.add_argument("--date", help="Forcer la date (AAAA-MM-JJ), utile pour les tests.")
    parseur.add_argument("--eval-seulement", action="store_true",
                         help="N'exécuter que l'évaluation de la veille (pas d'achat).")
    parseur.add_argument("--garde-cloture", action="store_true",
                         help="Ne s'exécute que si l'heure de Paris est 17h (DST-safe pour "
                              "les crons UTC de GitHub Actions).")
    args = parseur.parse_args()

    # Garde-fou horaire : avec deux crons UTC (été/hiver), un seul tombe à 17h Paris.
    if args.garde_cloture:
        maintenant = dt.datetime.now(config.FUSEAU_PARIS)
        if maintenant.hour != 17:
            print(f"Hors fenêtre de clôture (heure de Paris {maintenant:%H:%M}) — arrêt.")
            return 0

    jour = dt.date.fromisoformat(args.date) if args.date else None
    try:
        run(jour=jour, sans_analyse=args.eval_seulement)
    except Exception as e:  # noqa: BLE001
        print(f"\n[ERREUR] {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
