# Déclenchement externe (cron-job.org)

Le cron interne de GitHub Actions est *best-effort* : il est parfois retardé,
voire abandonné en cas de charge (c'est ce qui a fait rater le 1er jour). Pour un
déclenchement **fiable sans laisser le PC allumé**, un service de cron externe
appelle l'API GitHub chaque jour ouvré à heure fixe pour lancer le workflow.

Le cron GitHub interne est **conservé en secours** (voir
`.github/workflows/analyse.yml`). Si les deux se déclenchent le même jour,
l'anti-doublon (`ledger.a_deja_achete`) garantit **un seul achat**, et le groupe
de concurrence du workflow sérialise les exécutions : aucun risque de doublon.

## 1. Créer un jeton GitHub (fine-grained, portée minimale)

GitHub → **Settings** → **Developer settings** → **Personal access tokens** →
**Fine-grained tokens** → **Generate new token**.

- **Name** : `cron-job analyse-boursiere`
- **Expiration** : 1 an (à renouveler — note la date dans ton agenda)
- **Resource owner** : `CDOGss`
- **Repository access** : *Only select repositories* → `analyse-boursiere`
- **Permissions** → *Repository permissions* → **Actions : Read and write**
  (la permission obligatoire « Metadata : Read-only » s'ajoute toute seule)
- **Generate token** → **copie-le tout de suite** (`github_pat_…`) : il ne
  s'affiche qu'une seule fois.

⚠️ Ce jeton ne va QUE dans cron-job.org (et éventuellement un test local).
Ne le commite jamais.

## 2. Créer le cronjob sur cron-job.org

Compte gratuit sur <https://console.cron-job.org> → **Create cronjob**.

- **Title** : `Analyse boursière — déclenchement quotidien`
- **URL** :
  `https://api.github.com/repos/CDOGss/analyse-boursiere/actions/workflows/analyse.yml/dispatches`
- **Request method** : `POST`
- **Headers** :

  | Clé | Valeur |
  |---|---|
  | `Authorization` | `Bearer <TON_JETON>` |
  | `Accept` | `application/vnd.github+json` |
  | `X-GitHub-Api-Version` | `2022-11-28` |
  | `Content-Type` | `application/json` |

- **Request body** : `{"ref":"main"}`
- **Schedule** :
  - **Timezone : Europe/Paris** (gère l'heure d'été/hiver automatiquement)
  - Jours : **lundi → vendredi**
  - Heure : **17:05**
- **Notifications** : active « notifier en cas d'échec » (email) pour être
  prévenu immédiatement si l'appel casse un jour (jeton expiré, etc.).

GitHub répond **`204 No Content`** en cas de succès (c'est normal : 2xx = OK).

## 3. Tester tout de suite

Bouton **Test run** sur cron-job.org, ou en local :

```bash
curl -i -X POST \
  -H "Authorization: Bearer <TON_JETON>" \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  https://api.github.com/repos/CDOGss/analyse-boursiere/actions/workflows/analyse.yml/dispatches \
  -d '{"ref":"main"}'
```

Réponse attendue : `HTTP/2 204`. Ensuite, vérifie l'onglet **Actions** du dépôt :
un run de type *workflow_dispatch* doit apparaître dans la minute.

## Pourquoi 17:05 ?

Le déclenchement via `workflow_dispatch` lance l'analyse complète immédiatement
(sans le garde-fou horaire, réservé aux crons internes). 17:05 place donc la
sélection juste avant la clôture (17:30), conformément à la stratégie. Le prix
d'entrée réellement utilisé reste la **clôture officielle du jour** (figée le
lendemain à l'évaluation), donc la minute exacte du déclenchement n'affecte que
les données vues par le modèle, pas le P&L.
