"""Accès aux données de marché via yfinance (cours, intraday, instantané)."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import pandas as pd
import yfinance as yf

import config


@dataclass
class Instantane:
    """Photo du marché pour un titre à l'heure de l'analyse (~17h)."""
    ticker: str
    nom: str
    dernier: float | None
    variation_1j: float | None   # % sur la séance
    variation_5j: float | None   # % sur 5 séances
    volume_ratio: float | None   # volume du jour / moyenne 20j
    position_range: float | None = None  # place du cours dans le range du jour [0..1]
                                          # 1.00 = clôture au plus haut (flux acheteur)

    def ligne(self) -> str:
        def pct(x):
            return f"{x:+.2f}%" if x is not None else "n/d"
        def num(x):
            return f"{x:.2f}" if x is not None else "n/d"
        vr = f"{self.volume_ratio:.2f}x" if self.volume_ratio is not None else "n/d"
        rg = f"{self.position_range:.2f}" if self.position_range is not None else "n/d"
        return (
            f"{self.ticker} ({self.nom}): dernier={num(self.dernier)} "
            f"1j={pct(self.variation_1j)} 5j={pct(self.variation_5j)} vol={vr} "
            f"clôt@{rg}"  # position dans le range du jour (1=plus haut)
        )


def instantane_univers(univers: dict[str, str]) -> list[Instantane]:
    """Télécharge ~1 mois d'historique et calcule un instantané par titre."""
    tickers = list(univers.keys())
    data = yf.download(
        tickers,
        period="1mo",
        interval="1d",
        group_by="ticker",
        auto_adjust=False,
        progress=False,
        threads=True,
    )

    resultats: list[Instantane] = []
    for t in tickers:
        try:
            df = data[t] if len(tickers) > 1 else data
            df = df.dropna()
            if len(df) < 2:
                resultats.append(Instantane(t, univers[t], None, None, None, None))
                continue

            cloture = df["Close"]
            dernier = float(cloture.iloc[-1])
            veille = float(cloture.iloc[-2])
            var_1j = (dernier / veille - 1) * 100 if veille else None

            ref5 = cloture.iloc[-6] if len(cloture) >= 6 else cloture.iloc[0]
            var_5j = (dernier / float(ref5) - 1) * 100 if ref5 else None

            vol = df["Volume"]
            vol_jour = float(vol.iloc[-1])
            vol_moy = float(vol.tail(20).mean())
            vol_ratio = vol_jour / vol_moy if vol_moy else None

            haut = float(df["High"].iloc[-1])
            bas = float(df["Low"].iloc[-1])
            pos_range = (dernier - bas) / (haut - bas) if haut > bas else None

            resultats.append(
                Instantane(t, univers[t], dernier, var_1j, var_5j, vol_ratio, pos_range)
            )
        except Exception:
            resultats.append(Instantane(t, univers[t], None, None, None, None))

    return resultats


def preselection(instantanes: list[Instantane], n: int) -> list[Instantane]:
    """Classe l'univers et retourne les n meilleurs candidats (shortlist).

    Score composite aligné sur le pari overnight :
      - momentum de clôture (position dans le range) : poids fort (flux acheteur),
      - variation du jour : momentum,
      - ratio de volume : conviction / liquidité.
    Chaque métrique est convertie en rang normalisé [0..1] pour éviter les
    problèmes d'échelle.
    """
    valides = [i for i in instantanes if i.dernier is not None
               and i.position_range is not None and i.variation_1j is not None]
    if not valides:
        return []

    def rangs(valeurs: list[float]) -> dict[int, float]:
        ordre = sorted(range(len(valeurs)), key=lambda k: valeurs[k])
        return {idx: pos / (len(valeurs) - 1 or 1) for pos, idx in enumerate(ordre)}

    r_range = rangs([i.position_range for i in valides])
    r_var = rangs([i.variation_1j for i in valides])
    r_vol = rangs([(i.volume_ratio or 0) for i in valides])

    notes = []
    for k, inst in enumerate(valides):
        score = 0.5 * r_range[k] + 0.3 * r_var[k] + 0.2 * r_vol[k]
        notes.append((score, inst))
    notes.sort(key=lambda x: x[0], reverse=True)
    return [inst for _, inst in notes[:n]]


def _prix_le_plus_proche(df: pd.DataFrame, cible: dt.datetime) -> float | None:
    """Retourne le cours de clôture du bar intraday le plus proche de `cible`."""
    if df.empty:
        return None
    idx = df.index
    # Tolérance : on ne retient un bar que s'il est à moins de 45 min de la cible.
    ecarts = abs(idx - cible)
    pos = ecarts.argmin()
    if ecarts[pos] > pd.Timedelta(minutes=45):
        return None
    return float(df["Close"].iloc[pos])


def prix_intraday(ticker: str, jour: dt.date) -> dict[str, float | None]:
    """Cours d'un titre à l'ouverture, +30 min, mi-journée et 17h pour `jour`.

    Renvoie aussi la clôture de la séance.
    """
    debut = dt.datetime.combine(jour, dt.time(0, 0))
    fin = debut + dt.timedelta(days=1)
    try:
        df = yf.download(
            ticker,
            start=debut.strftime("%Y-%m-%d"),
            end=fin.strftime("%Y-%m-%d"),
            interval="5m",
            auto_adjust=False,
            progress=False,
        )
    except Exception:
        df = pd.DataFrame()

    resultat = {"ouverture": None, "demi_heure": None, "mi_journee": None,
                "h17": None, "cloture": None}
    if df.empty:
        return resultat

    # Index en timezone Paris
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    df.index = df.index.tz_convert(config.FUSEAU_PARIS)
    # yfinance peut renvoyer un MultiIndex de colonnes pour un seul ticker
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    def cible(h, m):
        return pd.Timestamp(
            dt.datetime.combine(jour, dt.time(h, m)), tz=config.FUSEAU_PARIS
        )

    resultat["ouverture"] = _prix_le_plus_proche(df, cible(*config.HEURE_OUVERTURE))
    resultat["demi_heure"] = _prix_le_plus_proche(df, cible(*config.HEURE_DEMI_HEURE))
    resultat["mi_journee"] = _prix_le_plus_proche(df, cible(*config.HEURE_MI_JOURNEE))
    resultat["h17"] = _prix_le_plus_proche(df, cible(*config.HEURE_17H))
    resultat["cloture"] = float(df["Close"].iloc[-1])
    return resultat


def _variations_indices(tickers: list[str]) -> dict[str, tuple[float, float]]:
    """Retourne {ticker: (dernier, variation_%)} pour des indices."""
    try:
        data = yf.download(tickers, period="5d", interval="1d", group_by="ticker",
                           auto_adjust=False, progress=False, threads=True)
    except Exception:
        return {}
    out: dict[str, tuple[float, float]] = {}
    for t in tickers:
        try:
            df = (data[t] if len(tickers) > 1 else data).dropna()
            if len(df) < 2:
                continue
            dernier = float(df["Close"].iloc[-1])
            veille = float(df["Close"].iloc[-2])
            out[t] = (dernier, (dernier / veille - 1) * 100)
        except Exception:
            continue
    return out


def contexte_macro() -> str:
    """Contexte de marché à ~17h : CAC 40, S&P 500, Nasdaq, VIX.

    À 17h Paris, Wall Street est ouvert depuis ~1h30 : le sens de la tape US est
    un signal avancé majeur du gap du lendemain matin sur Paris.
    """
    noms = {"^FCHI": "CAC 40", "^GSPC": "S&P 500 (US, en séance)",
            "^IXIC": "Nasdaq (US, en séance)", "^VIX": "VIX (volatilité US)"}
    var = _variations_indices(list(noms))
    if not var:
        return "(Contexte macro indisponible.)"
    lignes = [f"- {noms[t]}: {p:.2f} ({v:+.2f}%)" for t, (p, v) in var.items()]
    return "\n".join(lignes)


def etat_regime() -> dict:
    """Évalue le régime de marché et le nombre de paris autorisé (0/1/2).

    L'effet overnight est plus fiable en régime calme et tape US verte.
    """
    var = _variations_indices(["^VIX", "^GSPC", "^IXIC"])
    vix = var.get("^VIX", (None, None))[0]
    sp = var.get("^GSPC", (None, None))[1]

    nb_max, label, raisons = config.NB_ACHATS_PAR_SOIR, "normal", []

    if vix is not None and vix >= config.VIX_EXTREME:
        nb_max, label = 0, "extrême"
        raisons.append(f"VIX très élevé ({vix:.1f})")
    elif sp is not None and sp <= config.SP500_HOSTILE:
        nb_max, label = 0, "hostile"
        raisons.append(f"tape US fortement rouge ({sp:+.2f}%)")
    elif (vix is not None and vix >= config.VIX_PRUDENCE) or \
         (sp is not None and sp <= config.SP500_PRUDENCE):
        nb_max, label = 1, "prudence"
        if vix is not None and vix >= config.VIX_PRUDENCE:
            raisons.append(f"VIX élevé ({vix:.1f})")
        if sp is not None and sp <= config.SP500_PRUDENCE:
            raisons.append(f"tape US rouge ({sp:+.2f}%)")

    return {
        "vix": vix, "sp500_pct": sp, "nb_max": nb_max, "label": label,
        "raison": ", ".join(raisons) if raisons else "régime favorable",
    }


def cloture_du_jour(ticker: str, jour: dt.date) -> float | None:
    """Cours de clôture quotidien d'un titre pour une date donnée."""
    debut = jour - dt.timedelta(days=4)
    fin = jour + dt.timedelta(days=1)
    try:
        df = yf.download(
            ticker, start=debut.strftime("%Y-%m-%d"), end=fin.strftime("%Y-%m-%d"),
            interval="1d", auto_adjust=False, progress=False,
        )
    except Exception:
        return None
    if df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df[df.index.date <= jour]
    if df.empty:
        return None
    return float(df["Close"].iloc[-1])
