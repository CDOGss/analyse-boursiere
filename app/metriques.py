"""Couche d'évaluation rigoureuse (statistiques ajustées du risque).

Calcule, sur la série des rendements journaliers (scénario 17h, NET de frais) :
  - Sharpe et Sortino annualisés (rendement par unité de risque),
  - max drawdown (pire perte cumulée pic-à-creux),
  - profit factor, taux de réussite, gain/perte moyens, espérance,
  - alpha vs CAC 40 : moyenne, t-stat et INTERVALLE DE CONFIANCE 95 % par
    bootstrap → l'alpha est-il distinguable de zéro, ou est-ce du bruit ?

Objectif : juger honnêtement s'il y a un signal, plutôt que se raconter une
histoire sur quelques jours. La maximisation des gains composés passe par le
rendement GÉOMÉTRIQUE et le contrôle de la variance, pas par la somme brute.
"""
from __future__ import annotations

import numpy as np

import config
from app import benchmark, bilan

ANNUEL = np.sqrt(252)  # facteur d'annualisation (rendements ~quotidiens)


def _series_rendements():
    """Retourne (rendements_strat_net, rendements_alpha, pnl_net_eur) par jour."""
    refs = benchmark.references()
    strat, alpha, pnl_net = [], [], []
    for date, b in bilan._jours().items():
        if b["sommes"]["h17"] is None:
            continue
        capital = b["n"] * config.ALLOCATION_PAR_ACTION
        if capital <= 0:
            continue
        net = b["sommes"]["h17"] - bilan._cout_jour(b["n"])
        r = net / capital
        strat.append(r)
        pnl_net.append(net)
        ref = refs.get(date)
        if ref:
            alpha.append(r - ref["session_pct"] / 100)
    return np.array(strat), np.array(alpha), np.array(pnl_net)


def _max_drawdown(pnl_eur: np.ndarray) -> float:
    """Pire perte pic-à-creux sur la courbe cumulée (en €)."""
    if len(pnl_eur) == 0:
        return 0.0
    cum = np.cumsum(pnl_eur)
    pic = np.maximum.accumulate(cum)
    return float((cum - pic).min())


def _bootstrap_ic(echantillon: np.ndarray, b: int = 2000, seed: int = 42):
    """Intervalle de confiance 95 % de la moyenne par bootstrap percentile."""
    if len(echantillon) < 2:
        return (None, None)
    rng = np.random.default_rng(seed)
    moyennes = echantillon[rng.integers(0, len(echantillon),
                                        size=(b, len(echantillon)))].mean(axis=1)
    return (float(np.percentile(moyennes, 2.5)),
            float(np.percentile(moyennes, 97.5)))


def calculer() -> dict | None:
    strat, alpha, pnl_net = _series_rendements()
    n = len(strat)
    if n == 0:
        return None

    moy = float(strat.mean())
    ecart = float(strat.std(ddof=1)) if n > 1 else 0.0
    negatifs = strat[strat < 0]
    downside = float(np.sqrt((negatifs ** 2).mean())) if len(negatifs) else 0.0

    gains = pnl_net[pnl_net > 0].sum()
    pertes = -pnl_net[pnl_net < 0].sum()

    res = {
        "n": n,
        "total_net_eur": float(pnl_net.sum()),
        "rendement_moyen_pct": moy * 100,
        "sharpe": (moy / ecart * ANNUEL) if ecart else None,
        "sortino": (moy / downside * ANNUEL) if downside else None,
        "max_drawdown_eur": _max_drawdown(pnl_net),
        "profit_factor": (gains / pertes) if pertes else None,
        "taux_reussite_pct": float((pnl_net > 0).mean() * 100),
        "gain_moyen_eur": float(pnl_net[pnl_net > 0].mean()) if (pnl_net > 0).any() else 0.0,
        "perte_moyenne_eur": float(pnl_net[pnl_net < 0].mean()) if (pnl_net < 0).any() else 0.0,
        "esperance_eur": float(pnl_net.mean()),
        "alpha_n": len(alpha),
    }

    if len(alpha) >= 2:
        a_moy = float(alpha.mean())
        a_ec = float(alpha.std(ddof=1))
        res["alpha_moyen_pct"] = a_moy * 100
        res["alpha_tstat"] = (a_moy / (a_ec / np.sqrt(len(alpha)))) if a_ec else None
        ic_bas, ic_haut = _bootstrap_ic(alpha)
        res["alpha_ic95_pct"] = (ic_bas * 100 if ic_bas is not None else None,
                                 ic_haut * 100 if ic_haut is not None else None)
    return res


def _verdict(res: dict) -> str:
    n = res["alpha_n"]
    if n < 8:
        return ("⏳ **Échantillon insuffisant** ({} jours avec benchmark). À ce stade "
                "rien n'est significatif — les intervalles sont trop larges. "
                "Patiente : il faut typiquement plusieurs dizaines de jours."
                .format(n))
    ic = res.get("alpha_ic95_pct")
    if not ic or ic[0] is None:
        return "Données insuffisantes pour conclure sur l'alpha."
    bas, haut = ic
    if bas > 0:
        return ("🟢 **Alpha positif significatif** à 95 % (IC bootstrap [{:+.3f}% ; "
                "{:+.3f}%] exclut zéro). Signal crédible — à confirmer dans le temps."
                .format(bas, haut))
    if haut < 0:
        return ("🔴 **Alpha négatif significatif** : la sélection fait pire que le CAC. "
                "L'IC [{:+.3f}% ; {:+.3f}%] est sous zéro.".format(bas, haut))
    return ("⚪ **Alpha non distinguable de zéro** (IC [{:+.3f}% ; {:+.3f}%] contient 0). "
            "Pas encore de preuve d'un edge — continue de mesurer.".format(bas, haut))


def rendu_texte() -> str:
    res = calculer()
    if not res:
        return ("## Métriques ajustées du risque\n\n_Aucune position évaluée. "
                "Les statistiques apparaîtront après quelques séances._\n")

    def f(x, suf="", dec=2):
        return f"{x:.{dec}f}{suf}" if x is not None else "n/d"

    lignes = ["## Métriques ajustées du risque (scénario 17h, net de frais)\n"]
    lignes.append(f"_Basé sur {res['n']} jour(s) évalué(s). Total net : "
                  f"{res['total_net_eur']:+.2f}€._\n")
    lignes.append("| Métrique | Valeur | Lecture |")
    lignes.append("|---|---:|---|")
    lignes.append(f"| Sharpe (annualisé) | {f(res['sharpe'])} | >1 bon, >2 excellent |")
    lignes.append(f"| Sortino (annualisé) | {f(res['sortino'])} | pénalise la baisse |")
    lignes.append(f"| Max drawdown | {f(res['max_drawdown_eur'],'€')} | pire creux cumulé |")
    lignes.append(f"| Profit factor | {f(res['profit_factor'])} | gains/pertes, >1,5 solide |")
    lignes.append(f"| Taux de réussite | {f(res['taux_reussite_pct'],'%',0)} | jours gagnants |")
    lignes.append(f"| Espérance / jour | {f(res['esperance_eur'],'€')} | gain moyen par séance |")
    lignes.append(f"| Gain moyen | {f(res['gain_moyen_eur'],'€')} | sur jours gagnants |")
    lignes.append(f"| Perte moyenne | {f(res['perte_moyenne_eur'],'€')} | sur jours perdants |")
    lignes.append("")

    lignes.append("**Significativité de l'alpha vs CAC 40 :**\n")
    if "alpha_moyen_pct" in res:
        lignes.append(f"- Alpha moyen/jour : {res['alpha_moyen_pct']:+.3f}% "
                      f"(t-stat {f(res['alpha_tstat'])})")
        ic = res.get("alpha_ic95_pct")
        if ic and ic[0] is not None:
            lignes.append(f"- IC 95 % (bootstrap) : [{ic[0]:+.3f}% ; {ic[1]:+.3f}%]")
    lignes.append("")
    lignes.append(_verdict(res))
    lignes.append("")
    return "\n".join(lignes)


def ecrire() -> str:
    chemin = config.DOSSIER_RAPPORTS / "metriques.md"
    chemin.write_text("# Métriques\n\n" + rendu_texte(), encoding="utf-8")
    return str(chemin)
