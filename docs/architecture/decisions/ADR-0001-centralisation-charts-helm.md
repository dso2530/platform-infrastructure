# ADR-0001 — Centralisation et standardisation des charts Helm

- **Statut :** Accepté
- **Date :** 6 novembre 2026
- **Décideurs :** Équipe architecture / infrastructure
- **Périmètre :** `platform-infrastructure`, Kubernetes, Helm et ArgoCD

## 1. Contexte

Le projet utilise Kubernetes et ArgoCD pour gérer le déploiement de ses services applicatifs et de son infrastructure.

Les services backend reposent principalement sur Java 21 et Spring Boot. Ils partagent des caractéristiques communes :

- Déploiement sous forme de conteneurs ;
- Configuration externalisée ;
- Exposition via des Services Kubernetes ;
- Probes de disponibilité et de vivacité ;
- Gestion des ressources CPU et mémoire ;
- Exigences de sécurité des conteneurs ;
- Besoins d'observabilité ;
- Déploiement sur plusieurs environnements : dev, staging et prod.

La multiplication de charts Helm spécifiques à chaque microservice entraînerait une duplication des templates, une maintenance plus complexe et un risque de divergence entre les configurations.

Il est donc nécessaire de définir une stratégie de gestion des charts Helm cohérente avec l'architecture GitOps existante.

## 2. Problématique

Deux approches ont été étudiées.

### Option A — Centralisation des charts Helm

Les charts génériques sont stockés dans le dépôt `platform-infrastructure`.

Les configurations propres aux services et aux environnements sont conservées séparément.

### Option B — Charts Helm dans chaque dépôt applicatif

Chaque service possède son propre chart Helm dans son dépôt applicatif.

Le dépôt `platform-infrastructure` référence les charts et leurs configurations.

## 3. Décision

**L'option A est retenue : centralisation des charts Helm dans `platform-infrastructure`.**

Les charts seront génériques, réutilisables, versionnés et maintenus indépendamment du code applicatif.

Les valeurs propres aux microservices et aux environnements seront conservées dans le dépôt d'infrastructure.

Le code source, les Dockerfiles et les pipelines de compilation des applications restent dans leurs dépôts respectifs.

## 4. Architecture cible

```text
platform-infrastructure/
├── helm/
│   ├── charts/
│   │   ├── spring-boot-microservice/
│   │   │   ├── Chart.yaml
│   │   │   ├── values.yaml
│   │   │   ├── values.schema.json
│   │   │   └── templates/
│   │   │       ├── _helpers.tpl
│   │   │       ├── deployment.yaml
│   │   │       ├── service.yaml
│   │   │       ├── serviceaccount.yaml
│   │   │       ├── configmap.yaml
│   │   │       ├── hpa.yaml
│   │   │       └── ingress.yaml
│   │   │
│   │   └── infrastructure-service/
│   │
│   └── environments/
│       └── dev/
│           ├── common.yaml
│           ├── ai-public-benefits/
│           │   └── document-service.yaml
│           └── developer-content-creator/
│               └── repository-service.yaml
│
├── scripts/
│   └── helm/
│
├── tests/
│   └── helm/
│
└── .github/
    └── workflows/
        └── helm-validation.yml
```

Cette structure constitue une cible d'organisation. Les charts et les fichiers de valeurs sont introduits progressivement, après validation du chart pilote.

## 5. Principes de conception

### 5.1. Réutilisabilité

Le chart `spring-boot-microservice` devra prendre en charge les fonctionnalités communes :

- Deployment ;
- Service ;
- ServiceAccount ;
- ConfigMap facultatif ;
- Références à des Secrets Kubernetes ;
- Readiness, liveness et startup probes ;
- Requests et limits CPU/mémoire ;
- SecurityContext ;
- HPA facultatif ;
- Ingress facultatif ;
- Annotations Prometheus facultatives.

Les fonctionnalités facultatives seront désactivées par défaut.

### 5.2. Séparation des responsabilités

| Élément | Responsabilité |
|---|---|
| Dépôt applicatif | Code, tests, compilation et image |
| `platform-infrastructure` | Charts, valeurs et configuration Kubernetes |
| Helm | Génération des manifests Kubernetes |
| ArgoCD | Réconciliation de l'état désiré |
| Kubernetes | Exécution des workloads |

### 5.3. Configuration par environnement

Les différences entre environnements seront exprimées dans des fichiers de valeurs dédiés.

Exemple :

```yaml
# helm/environments/dev/ai-public-benefits/document-service.yaml

replicaCount: 1

image:
  repository: harbor.example.local/public-benefits/document-service
  tag: "1.0.0"

resources:
  requests:
    cpu: 100m
    memory: 256Mi
  limits:
    cpu: 500m
    memory: 768Mi

autoscaling:
  enabled: false
```

Les valeurs de staging et de production pourront définir des ressources, un nombre de réplicas et des paramètres de sécurité différents.

Les Applications ArgoCD référenceront d'abord le fichier `common.yaml`, puis le fichier spécifique au microservice. Helm appliquera les valeurs dans l'ordre indiqué : les valeurs spécifiques au service pourront donc remplacer les valeurs communes.

Aucun secret ou identifiant sensible ne devra être stocké en clair dans ces fichiers.

### 5.4. Gestion des versions

Les charts suivront le versionnement sémantique SemVer.

- **MAJOR** : rupture de compatibilité des valeurs ou des templates ;
- **MINOR** : ajout rétrocompatible de fonctionnalités ;
- **PATCH** : correction rétrocompatible.

Le champ `version` de `Chart.yaml` représentera la version du chart.

Le champ `appVersion` représentera la version de l'application, sans être nécessairement identique à celle du chart.

## 6. Intégration ArgoCD

ArgoCD référence le chart Helm depuis son chemin Git dans le dépôt `platform-infrastructure`.

L'intégration repose sur le mécanisme multi-source d'ArgoCD :

```yaml
spec:
  sources:
    - repoURL: https://github.com/dso2530/platform-infrastructure.git
      targetRevision: main
      path: helm/charts/spring-boot-microservice
      helm:
        releaseName: document-service
        valueFiles:
          - $values/helm/environments/dev/common.yaml
          - $values/helm/environments/dev/ai-public-benefits/document-service.yaml

    - repoURL: https://github.com/dso2530/platform-infrastructure.git
      targetRevision: main
      ref: values
```

Cette configuration utilise deux sources Git :

- La première source référence le chart Helm `spring-boot-microservice` et définit le nom de release Helm.
- La seconde source, identifiée par `ref: values`, permet de référencer les fichiers de valeurs depuis la racine du dépôt avec le préfixe `$values`.

Cette approche permet de centraliser les charts et leurs configurations sans les dupliquer dans les dépôts applicatifs.

Une évolution vers des charts Helm publiés dans un dépôt OCI pourra être étudiée ultérieurement.

## 7. Stratégie de validation CI

Une CI Helm indépendante sera mise en place dans GitHub Actions.

Elle devra exécuter les contrôles suivants :

| Contrôle | Outil |
|---|---|
| Validation des métadonnées | `helm lint` |
| Construction des dépendances | `helm dependency build` |
| Génération des manifests | `helm template` |
| Validation des valeurs | JSON Schema |
| Validation Kubernetes | Kubeconform |
| Tests spécifiques | pytest |
| Analyse de configuration | Checkov, selon le périmètre retenu |

La CI sera exécutée sur les Pull Requests, les pushs sur `main` et à la demande.

### 7.1. Limites de sécurité

La CI Helm sera exclusivement une chaîne de validation.

Elle ne devra :

- Disposer d'aucun accès au cluster Kubernetes ;
- Utiliser aucun kubeconfig ;
- Exécuter aucun `kubectl apply` ;
- Déclencher aucune synchronisation ArgoCD ;
- Effectuer aucun déploiement ;
- Modifier aucune infrastructure externe.

Le déploiement restera une responsabilité distincte du processus de validation, assurée par ArgoCD selon la politique GitOps définie.

## 8. Conséquences positives

- Standardisation des déploiements Spring Boot ;
- Réduction de la duplication des templates Helm ;
- Cohérence entre les environnements ;
- Maintenance centralisée ;
- Meilleure maîtrise des politiques de sécurité Kubernetes ;
- Validation automatisée avant intégration ;
- Séparation claire entre CI et CD ;
- Possibilité de faire évoluer les charts indépendamment des applications.

## 9. Conséquences négatives et risques

- Le dépôt d'infrastructure devient responsable de la compatibilité des charts avec plusieurs services.
- Une modification du chart générique peut affecter plusieurs applications.
- La coordination entre les équipes applicatives et infrastructure devient nécessaire.
- La gestion des versions des charts et des valeurs demande une discipline supplémentaire.
- Les services présentant des besoins très spécifiques pourront nécessiter des extensions ou des charts dédiés.

Ces risques seront réduits par le versionnement SemVer, les tests de non-régression et une validation systématique des charts rendus.

## 10. Alternatives rejetées

### Option B — Charts dans chaque dépôt applicatif

Cette option n'est pas retenue pour le moment.

Elle entraînerait une multiplication des implémentations et des configurations communes, avec un risque de divergence entre les microservices.

Elle pourra toutefois être réévaluée si certains services deviennent suffisamment spécifiques pour justifier un cycle de vie Helm indépendant.

## 11. Plan de mise en œuvre

| Étape | Action | Statut |
|---|---|---|
| 1 | Formaliser la décision architecturale | Terminé |
| 2 | Centraliser la structure Helm | Réalisé |
| 3 | Développer le chart générique `spring-boot-microservice` | Réalisé pour le pilote |
| 4 | Ajouter les valeurs du service pilote | Terminé |
| 5 | Tester et comparer les manifests | Terminé pour le pilote |
| 6 | Intégrer Kubeconform | À vérifier |
| 7 | Ajouter la CI Helm GitHub Actions | À vérifier |
| 8 | Valider la CI sur GitHub | À vérifier |
| 9 | Migrer progressivement les Applications ArgoCD | En cours |

## 12. Réexamen de la décision

Cette décision pourra être réévaluée si :

- Les microservices nécessitent des cycles de vie Helm fortement indépendants ;
- Les charts deviennent trop complexes pour rester génériques ;
- Une stratégie de publication OCI devient nécessaire ;
- Les contraintes de gouvernance imposent une séparation des dépôts.

---

**Décision finale :** centralisation des charts Helm génériques et de leurs configurations d'environnement dans `platform-infrastructure`, avec validation CI indépendante et absence de déploiement automatique.
