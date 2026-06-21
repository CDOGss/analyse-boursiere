"""Graphiques de plus/moins-values (PNG), affichables directement sur GitHub.

Génère 3 visuels mis à jour à chaque exécution :
  1. P&L cumulé (stratégie nette de frais) vs CAC 40 — bat-on le marché ?
  2. Plus/moins-values journalières au 17h (barres vert/rouge).
  3. Comparaison cumulée des 4 moments de revente (ouverture/9h30/midi/17h).

Backend « Agg » : fonctionne sans écran (CI / serveur).
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import MaxNLocator  # noqa: E402

import config  # noqa: E402
from app import benchmark, bilan  # noqa: E402

VERT, ROUGE, BLEU, GRIS = "#1a9850", "#d73027", "#2c7fb8", "#888888"


def _cumul(valeurs: list[float]) -> list[float]:
    total, sortie = 0.0, []
    for v in valeurs:
        total += v
        sortie.append(total)
    return sortie


def _series():
    """Construit les séries journalières (dates, P&L par scénario, frais, CAC€)."""
    jours = bilan._jours()
    refs = benchmark.references()
    dates, pnl, frais, cac_session = [], {s: [] for s in bilan.SCENARIOS}, [], []
    for date, b in jours.items():
        dates.append(date)
        for s in bilan.SCENARIOS:
            pnl[s].append(b["sommes"][s] or 0.0)
        frais.append(bilan._cout_jour(b["n"]))
        ref = refs.get(date)
        capital = b["n"] * config.ALLOCATION_PAR_ACTION
        cac_session.append(capital * ref["session_pct"] / 100 if ref else 0.0)
    return dates, pnl, frais, cac_session


def _style_dates(ax, dates):
    ax.set_xticks(range(len(dates)))
    ax.set_xticklabels([d[5:] for d in dates], rotation=45, ha="right", fontsize=8)
    ax.axhline(0, color=GRIS, linewidth=0.8)
    ax.grid(True, axis="y", alpha=0.3)


def generer() -> list[str]:
    dates, pnl, frais, cac_session = _series()
    chemins: list[str] = []
    if not dates:
        return chemins

    # 1) P&L cumulé net vs CAC 40
    net17 = [p - f for p, f in zip(pnl["h17"], frais)]
    cum_strat = _cumul(net17)
    cum_cac = _cumul(cac_session)
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.plot(range(len(dates)), cum_strat, marker="o", color=BLEU,
            linewidth=2, label="Stratégie (17h, net de frais)")
    ax.plot(range(len(dates)), cum_cac, marker="s", color=GRIS,
            linewidth=1.6, linestyle="--", label="CAC 40 (acheté chaque soir)")
    ax.fill_between(range(len(dates)), cum_strat, cum_cac,
                    where=[a >= b for a, b in zip(cum_strat, cum_cac)],
                    color=VERT, alpha=0.15)
    ax.fill_between(range(len(dates)), cum_strat, cum_cac,
                    where=[a < b for a, b in zip(cum_strat, cum_cac)],
                    color=ROUGE, alpha=0.15)
    ax.set_title("P&L cumulé : stratégie vs CAC 40")
    ax.set_ylabel("€ cumulés")
    ax.legend(fontsize=8)
    _style_dates(ax, dates)
    fig.tight_layout()
    c1 = config.DOSSIER_RAPPORTS / "graph_cumul.png"
    fig.savefig(c1, dpi=110); plt.close(fig); chemins.append(str(c1))

    # 2) Plus/moins-values journalières au 17h
    fig, ax = plt.subplots(figsize=(9, 4))
    couleurs = [VERT if v >= 0 else ROUGE for v in pnl["h17"]]
    ax.bar(range(len(dates)), pnl["h17"], color=couleurs)
    ax.set_title("Plus / moins-values par jour (revente à 17h)")
    ax.set_ylabel("€")
    ax.yaxis.set_major_locator(MaxNLocator(nbins=8))
    _style_dates(ax, dates)
    fig.tight_layout()
    c2 = config.DOSSIER_RAPPORTS / "graph_journalier.png"
    fig.savefig(c2, dpi=110); plt.close(fig); chemins.append(str(c2))

    # 3) Comparaison cumulée des 4 sorties
    fig, ax = plt.subplots(figsize=(9, 4.5))
    couleurs_sc = {"ouverture": "#fdae61", "premiere_demi_heure": "#abd9e9",
                   "mi_journee": "#2c7fb8", "h17": "#1a9850"}
    for s in bilan.SCENARIOS:
        ax.plot(range(len(dates)), _cumul(pnl[s]), marker=".",
                label=bilan.LIBELLES[s], color=couleurs_sc[s])
    ax.set_title("Quel moment de revente ? (P&L cumulé, brut)")
    ax.set_ylabel("€ cumulés")
    ax.legend(fontsize=8)
    _style_dates(ax, dates)
    fig.tight_layout()
    c3 = config.DOSSIER_RAPPORTS / "graph_sorties.png"
    fig.savefig(c3, dpi=110); plt.close(fig); chemins.append(str(c3))

    _ecrire_md()
    return chemins


def _ecrire_md() -> None:
    contenu = """# Graphiques — plus / moins-values

_Mis à jour à chaque exécution. Apparaissent dès les premières positions évaluées._

## P&L cumulé : stratégie (net de frais) vs CAC 40
![P&L cumulé](graph_cumul.png)

Zone verte = la stratégie bat le CAC 40 ; zone rouge = elle fait moins bien.

## Plus / moins-values par jour (revente à 17h)
![Journalier](graph_journalier.png)

## Quel moment de revente est le meilleur ?
![Sorties](graph_sorties.png)
"""
    (config.DOSSIER_RAPPORTS / "graphiques.md").write_text(contenu, encoding="utf-8")
