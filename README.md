# Analyse boursière — marche à blanc (paper trading)

Application qui, chaque jour vers **17h** (≈30 min avant la clôture d'Euronext
Paris), demande à **Claude Opus 4.8** d'analyser :

- le **flux d'actualité du jour** (RSS Boursorama, Les Échos, Le Monde…),
- un **instantané de marché** des actions du **CAC 40 et du SBF 120**,

- le **sentiment social** (StockTwits, optionnel),

puis sélectionne les **2 meilleures actions** à « acheter » ce soir (500 € chacune
par défaut) dans l'espoir d'une hausse le lendemain matin.

Le lendemain, au lancement suivant, l'app **évalue ce qui s'est passé** sur les
actions achetées la veille et calcule le **gain/perte théorique** selon 4 moments
de revente : ouverture (09:00), première demi-heure (09:30), mi-journée (13:00) et 17h.

> ⚠️ **C'est une marche à blanc : aucun ordre réel n'est passé.** Le but est
> d'observer, sur la durée, la pertinence des conseils — pas de garantir un gain.
> Une hausse le lendemain matin n'est jamais assurée. Ne l'utilise pas comme
> conseil d'investissement.

## Installation

```bash
make install            # ou : python -m pip install -r requirements.txt
cp .env.example .env    # puis renseigne ANTHROPIC_API_KEY dans .env
```

## Utilisation

```bash
make run                # exécution quotidienne complète (évaluation + analyse + achat papier)
make eval               # évaluation seule des positions de la veille
make dashboard          # tableau de bord récapitulatif sur tout l'historique
python main.py --date 2026-06-19   # forcer une date (tests / rattrapage)
```

Le **tableau de bord** (`make dashboard`, aussi ajouté en bas de chaque rapport
quotidien) agrège tout l'historique et indique, pour chacun des 4 scénarios de
sortie : le **P&L cumulé**, le **rendement moyen**, le **taux de réussite**
(positions gagnantes), le meilleur/pire trade, et désigne la **meilleure
stratégie de sortie a posteriori**.

Chaque exécution :

1. **évalue** les positions de la séance précédente (fige le prix d'entrée =
   clôture du jour d'achat, puis calcule les 4 scénarios de revente) ;
2. **analyse** l'actualité + le marché et **enregistre** 2 achats papier.

Un rapport lisible est écrit dans `reports/rapport_AAAA-MM-JJ.md`, et le
portefeuille complet est conservé dans `data/portefeuille.json`.

## Exécution automatique dans le cloud (GitHub Actions — PC éteint)

Le dépôt contient un workflow [.github/workflows/analyse.yml](.github/workflows/analyse.yml)
qui lance l'analyse **chaque jour ouvré à 17h (heure de Paris)** sur les serveurs
de GitHub — gratuitement, sans que ton PC soit allumé. Le portefeuille
(`data/portefeuille.json`) et les rapports sont **sauvegardés dans le dépôt** à
chaque exécution, ce qui assure la persistance entre les jours.

Mise en place (une seule fois) :

1. **Créer un dépôt GitHub** (privé de préférence) et y pousser le projet :
   ```bash
   git init
   git add .
   git commit -m "Analyse boursière marche à blanc"
   git branch -M main
   git remote add origin https://github.com/<toi>/<depot>.git
   git push -u origin main
   ```
2. **Ajouter ta clé API en secret** : sur GitHub, *Settings → Secrets and
   variables → Actions → New repository secret*. Nom : `ANTHROPIC_API_KEY`,
   valeur : ta clé `sk-ant-...`. (Le `.env` n'est jamais poussé, il est ignoré.)
3. **Tester** : onglet *Actions → Analyse boursière quotidienne → Run workflow*
   (le déclenchement manuel ignore le garde-fou horaire pour te permettre de
   tester à n'importe quelle heure).

Détails techniques :

- Le cron GitHub est en **UTC sans heure d'été** : deux horaires sont programmés
  (15h et 16h UTC) et le garde-fou `--garde-cloture` (n'agit que si l'heure de
  Paris vaut 17h) garantit qu'**un seul** fait réellement le travail toute l'année.
- Un **anti-doublon** empêche un second achat le même jour si jamais le workflow
  se relançait.
- Limite : si GitHub Actions est très chargé, un cron peut être **retardé de
  quelques minutes** — sans conséquence ici (le prix d'entrée reste la clôture).

## Planification à 17h (alternative : PC allumé)

L'app est conçue pour un **lancement unique à 17h** qui fait tout (l'évaluation
de la veille se déroule donc juste avant les nouveaux achats, exactement comme
demandé).

- **Windows (Planificateur de tâches)** — créer une tâche déclenchée chaque jour
  ouvré à 17:00 exécutant :
  ```
  python "C:\Users\chris\Desktop\Mes applis\Analyse boursiere\main.py"
  ```
- **Linux/macOS (cron)** :
  ```cron
  0 17 * * 1-5  cd /chemin/projet && make run >> reports/cron.log 2>&1
  ```

> `make` n'est pas installé par défaut sous Windows. Soit tu utilises
> directement `python main.py`, soit tu installes `make`
> (`winget install GnuWin32.Make` ou via Chocolatey/MSYS2).

## Structure

```
config.py            Paramètres + univers d'actions (CAC 40 + SBF 120 ≈ 115 titres, éditable)
main.py              Orchestrateur (lancé par make / planificateur)
dashboard.py         Tableau de bord récapitulatif (script autonome)
app/news.py          Récupération des flux RSS du jour
app/market.py        Données de marché (yfinance) : instantané + intraday
app/analysis.py      Appel à Claude Opus 4.8 (sortie structurée JSON)
app/ledger.py        Registre du portefeuille papier (data/portefeuille.json)
app/evaluate.py      Calcul des gains/pertes du lendemain
app/report.py        Rapports console + markdown
app/dashboard.py     Statistiques agrégées (P&L cumulé, taux de réussite)
app/social.py        Sentiment social StockTwits (via ADR/US, optionnel)
app/bilan.py         Calendrier quotidien (CSV) + tableau de bord mensuel
```

## Calendrier quotidien & bilan mensuel

À chaque exécution, l'app met à jour :

- **`reports/journal_quotidien.csv`** — une ligne par jour de résultat, avec la
  **somme gain/perte** à l'ouverture / 9h30 / midi / 17h, les frais estimés et le
  **P&L net** au 17h. Séparateur `;` et décimales `,` → s'ouvre directement dans
  Excel / Google Sheets.
- **`reports/bilan_mensuel.md`** — récap **par mois** : total par scénario de
  revente (**brut ET net de frais**), taux de réussite, meilleur/pire jour, et le
  détail jour par jour du mois en cours. Mis à jour avec les résultats du jour.

Les résultats sont indexés par **date d'évaluation** (le jour où la position
aurait été revendue). Frais d'aller-retour configurables via `COUT_TRANSACTION_PCT`
dans `config.py` (défaut 0,20 %).

## Signaux fournis à Claude (étape 2)

Pour maximiser la probabilité d'ouverture en hausse le lendemain, le prompt reçoit :

- **Contexte macro** : CAC 40, S&P 500, Nasdaq, VIX (la tape US en séance à 17h est
  le 1er prédicteur du gap parisien du lendemain).
- **Momentum de clôture** : position du cours dans le range du jour (`clôt@`,
  1 = au plus haut = flux acheteur de fin de séance).
- **Actualité du jour** (RSS) + **sentiment social** (StockTwits/ADR).
- **Track record récent** réinjecté pour auto-correction.

Claude peut retenir **1 ou 2 actions** (qualité > quantité) et fournit pour chacune
un catalyseur, un raisonnement et un **risque** explicite.

## Sentiment social (StockTwits)

À l'étape 2, l'app ajoute un **sentiment social retail** issu de StockTwits, à
côté des flux RSS. Limites importantes :

- StockTwits **ne couvre pas** les tickers Euronext (`.PA`). On passe par les
  **ADR / cotations américaines**, donc seules ~21 grandes valeurs françaises
  sont couvertes (correspondance vérifiée dans `config.ADR_STOCKTWITS`).
- Le signal est **retail, différé, partiel** — Claude reçoit la consigne de ne
  pas le surpondérer. C'est un appoint, pas une preuve.
- Le volume est faible le week-end / hors séance ; il monte quand le marché US
  est actif (les valeurs à vraie cotation US comme Stellantis, STM, TotalEnergies
  ont le plus de flux).

Désactivable via `ACTIVER_SENTIMENT_SOCIAL = False` dans `config.py`. Aucune clé
requise (API publique gratuite).

## Limites connues

- Les données yfinance sont **différées** et l'intraday n'est disponible que sur
  les jours récents — l'évaluation doit donc tourner le lendemain (ou surlendemain).
- L'« achat 5 min avant la clôture » est approximé par la **clôture de la séance**
  d'achat (figée lors de l'évaluation).
- L'univers SBF 120 fourni dans `config.py` est un point de départ : complète-le
  ou corrige les tickers Yahoo si besoin.
