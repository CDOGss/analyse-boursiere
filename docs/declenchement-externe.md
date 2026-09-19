# Déclenchement externe (cron-job.org)

Le cron interne de GitHub Actions est *best-effort* : il est parfois retardé,
voire abandonné en cas de charge (c'est ce qui a fait rater le 1er jour). Pour un
déclenchement **fiable sans laisser le PC allumé**, un service de cron externe
appelle l'API GitHub chaque jour ouvré à heure fixe pour lancer le workflow.

Le cron GitHub interne a été **retiré** : il se déclenchait avec des heures de
retard. cron-job.org est donc le **seul** déclencheur — s'il s'arrête, plus
rien ne tourne (voir « Dépannage » en bas). Le groupe de concurrence du workflow
et l'anti-doublon (`ledger.a_deja_achete`) protègent quand même contre un
double lancement le même jour.

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

## Dépannage : « plus aucune analyse depuis le … »

Symptôme : dans l'onglet **Actions** du dépôt, plus aucun run *workflow_dispatch*
depuis plusieurs jours (ce n'est pas un run qui échoue : il n'y a **pas de run
du tout**). C'est cron-job.org qui n'appelle plus GitHub. Arrivé le 11/09/2026.

1. **Console cron-job.org** → ouvre le cronjob → onglet **History** (historique
   des exécutions). Regarde le code HTTP des dernières tentatives :
   - **401 Unauthorized** → le jeton GitHub a **expiré** ou a été révoqué
     (cause la plus fréquente : les jetons fine-grained ont une date de fin).
   - **404 Not Found** → dépôt renommé, ou jeton sans accès au dépôt.
   - **403** → permission « Actions : Read and write » manquante.
   - **Pas de tentative du tout** → le job est **désactivé** (cron-job.org
     désactive un job après trop d'échecs consécutifs, et te l'envoie par mail).
2. **Si 401 : régénère un jeton** (étape 1 ci-dessus), puis dans le cronjob
   remplace la valeur du header `Authorization` par `Bearer <NOUVEAU_JETON>`.
   Note la nouvelle date d'expiration dans ton agenda.
3. **Réactive le job** (interrupteur *Enabled*) puis **Test run** : attends
   `204`, et vérifie qu'un run apparaît dans **Actions** dans la minute.

### Tester la configuration GitHub sans polluer les données

Un jour **sans séance** (week-end, jour férié), ne lance pas le workflow en mode
normal : il « achèterait » des actions datées d'un jour sans cotation (une garde
week-end bloque désormais l'achat, mais autant ne pas compter dessus). Utilise
le mode test :

- **Actions** → *Analyse boursière quotidienne* → **Run workflow** → **mode :
  `test-api`** → un ping minimal du modèle valide la clé `GEMINI_API_KEY` et le
  nom du modèle, sans écrire aucune donnée.
- En ligne de commande : `gh workflow run analyse.yml -f mode=test-api`.

Résultat attendu dans le log : `Clé API et modèle valides.`

## Pourquoi 17:05 ?

Le déclenchement via `workflow_dispatch` lance l'analyse complète immédiatement
(sans le garde-fou horaire, réservé aux crons internes). 17:05 place donc la
sélection juste avant la clôture (17:30), conformément à la stratégie. Le prix
d'entrée réellement utilisé reste la **clôture officielle du jour** (figée le
lendemain à l'évaluation), donc la minute exacte du déclenchement n'affecte que
les données vues par le modèle, pas le P&L.
