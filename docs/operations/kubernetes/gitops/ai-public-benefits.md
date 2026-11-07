# GitOps — AI Public Benefits Platform

## 1. Objectif et périmètre

Ce document décrit l'organisation GitOps du projet `ai-public-benefits-platform` dans le dépôt `platform-infrastructure`.

Il présente :

- l'organisation des Applications ArgoCD ;
- la séparation entre Applications actives et Applications préparées ;
- l'AppProject utilisé par les microservices ;
- la centralisation des charts Helm ;
- l'organisation des valeurs Helm par projet et environnement ;
- la stratégie de migration progressive des microservices.

La stratégie de centralisation des charts Helm est définie dans l'ADR-0001 :

`docs/architecture/decisions/ADR-0001-centralisation-charts-helm.md`

## 2. Dépôts et responsabilités

### 2.1. Dépôt platform-infrastructure

Dépôt :

`https://github.com/dso2530/platform-infrastructure.git`

Il centralise :

- les charts Helm génériques ;
- les valeurs Helm par environnement et par projet ;
- les Applications ArgoCD ;
- les AppProjects ;
- les Applications racines ;
- la configuration GitOps et la documentation d'exploitation.

### 2.2. Dépôt applicatif

Dépôt :

`https://github.com/dso2530/ai-public-benefits-platform.git`

Il contient notamment :

- le code source des microservices ;
- les modules backend ;
- les configurations applicatives ;
- les pipelines CI/CD ;
- les ressources propres au développement des services.

La séparation des responsabilités permet de faire évoluer indépendamment le code applicatif et l'infrastructure de déploiement.

## 3. Organisation GitOps

### 3.1. Arborescence

L'organisation actuelle est la suivante :

```text
gitops/
├── bootstrap/
│   ├── ai-public-benefits-root.yaml
│   └── developer-content-creator-root.yaml
│
├── projects/
│   ├── platform-infrastructure.yaml
│   ├── public-benefits.yaml
│   └── developer-content-creator.yaml
│
└── applications/
    ├── ai-public-benefits/
    │   ├── dev/
    │   │   └── document-service.yaml
    │   │
    │   └── prepared/
    │       ├── application-service.yaml
    │       ├── citizen-bff.yaml
    │       ├── connector-service.yaml
    │       ├── document-extraction-service.yaml
    │       ├── eligibility-service.yaml
    │       ├── knowledge-service.yaml
    │       ├── llm-extraction-service.yaml
    │       ├── notification-service.yaml
    │       ├── profile-service.yaml
    │       ├── security-service.yaml
    │       └── territorial-rag-service.yaml
    │
    └── developer-content-creator/
        └── dev/
            └── repository-service.yaml
```

### 3.2. Application racine

Fichier :

`gitops/bootstrap/ai-public-benefits-root.yaml`

Application :

`ai-public-benefits-root`

AppProject :

`platform-infrastructure`

Configuration principale :

```yaml
spec:
  project: platform-infrastructure
  source:
    repoURL: https://github.com/dso2530/platform-infrastructure.git
    targetRevision: main
    path: gitops/applications/ai-public-benefits/dev
    directory:
      recurse: true
  destination:
    server: https://kubernetes.default.svc
    namespace: argocd
```

L'Application racine surveille récursivement le répertoire :

`gitops/applications/ai-public-benefits/dev`

Elle découvre les Applications enfants présentes dans ce répertoire.

Le répertoire `prepared/` est volontairement situé en dehors du périmètre surveillé.

### 3.3. Applications actives et préparées

Deux catégories sont utilisées pour organiser les Applications ArgoCD.

**Applications déclarées dans `dev/`**

Elles sont destinées à être découvertes et gérées par l'Application racine.

Actuellement :

| Application | Présence dans Git | Découverte par le Root Application |
|---|---|---|
| document-service | Oui | Oui, répertoire surveillé |

**Applications dans `prepared/`**

Ces fichiers constituent des configurations préparées pour les futures migrations.

| Application | Présence dans Git | Découverte par le Root Application |
|---|---|---|
| application-service | Oui | Non |
| citizen-bff | Oui | Non |
| connector-service | Oui | Non |
| document-extraction-service | Oui | Non |
| eligibility-service | Oui | Non |
| knowledge-service | Oui | Non |
| llm-extraction-service | Oui | Non |
| notification-service | Oui | Non |
| profile-service | Oui | Non |
| security-service | Oui | Non |
| territorial-rag-service | Oui | Non |

La présence d'un fichier dans `prepared/` ne signifie pas que l'Application est enregistrée, découverte ou synchronisée dans ArgoCD.

Le Root Application surveille uniquement `dev/`. Les fichiers de `prepared/` restent donc hors de son périmètre de découverte.

**Politique de synchronisation**

Toutes les Applications du projet `ai-public-benefits` utilisent une synchronisation manuelle.

Cette règle s'applique aussi bien aux Applications déclarées dans `dev/` qu'à celles présentes dans `prepared/`.

Aucune politique `automated`, `prune` ou `selfHeal` n'est configurée dans les fichiers d'Application actuellement concernés.

Les options suivantes sont conservées :

```yaml
syncPolicy:
  syncOptions:
    - CreateNamespace=true
    - PruneLast=true
```

La synchronisation manuelle permet de contrôler explicitement le moment où les changements désirés sont appliqués au cluster.

**Procédure de migration d'une Application préparée**

Avant de déplacer une Application dans `dev/`, il faut :

1. vérifier sa configuration ;
2. migrer ses valeurs vers le dépôt `platform-infrastructure` ;
3. configurer le chart Helm générique ;
4. comparer les manifests générés avec ceux de l'ancien chart ;
5. vérifier l'AppProject et ses autorisations ;
6. conserver la synchronisation manuelle ;
7. contrôler le diff ArgoCD après son intégration.

## 4. Gouvernance ArgoCD — AppProjects

Deux AppProjects interviennent dans le déploiement de la plateforme.

### 4.1. AppProject platform-infrastructure

Fichier :

`gitops/projects/platform-infrastructure.yaml`

Il est utilisé par l'Application racine `ai-public-benefits-root`.

Ses responsabilités sont limitées à la gestion des Applications ArgoCD dans le namespace `argocd`.

Configuration des autorisations :

| Paramètre | Autorisation |
|---|---|
| Dépôt source | `platform-infrastructure.git` uniquement |
| Cluster cible | Cluster Kubernetes local |
| Namespace cible | `argocd` uniquement |
| Ressources cluster-scoped | Aucune |
| Ressources namespaced | `Application` uniquement |

Ce projet constitue la couche de gouvernance GitOps. Il ne déploie pas directement les workloads applicatifs.

### 4.2. AppProject public-benefits

Fichier :

`gitops/projects/public-benefits.yaml`

Les Applications enfants des microservices utilisent :

```yaml
spec:
  project: public-benefits
```

**Dépôts autorisés**

- `https://github.com/dso2530/ai-public-benefits-platform.git`
- `https://github.com/dso2530/platform-infrastructure.git`
- `https://charts.external-secrets.io`

Le dépôt applicatif permet de conserver la compatibilité avec les services qui n'ont pas encore été migrés. Le dépôt d'infrastructure héberge les charts génériques et les valeurs centralisées.

**Destinations autorisées**

| Cluster | Namespace |
|---|---|
| Kubernetes local | `argocd` |
| Kubernetes local | `public-benefits` |
| Kubernetes local | `external-secrets` |
| `floci-gke-dev` | `public-benefits` |
| `floci-gke-dev` | `external-secrets` |

**Ressources cluster-scoped autorisées**

| API Group | Kind |
|---|---|
| Core (`""`) | Namespace |
| `apiextensions.k8s.io` | CustomResourceDefinition |
| `rbac.authorization.k8s.io` | ClusterRole |
| `rbac.authorization.k8s.io` | ClusterRoleBinding |
| `admissionregistration.k8s.io` | ValidatingWebhookConfiguration |

**Ressources namespaced**

La configuration autorise tous les groupes et tous les types de ressources namespaced :

```yaml
namespaceResourceWhitelist:
  - group: "*"
    kind: "*"
```

Cette autorisation étendue facilite le déploiement des différents composants de la plateforme, mais constitue également un périmètre de permissions important. Elle devra être réévaluée à mesure que les besoins des services seront stabilisés.

### 4.3. Séparation des responsabilités

| Élément | AppProject | Responsabilité |
|---|---|---|
| Application racine | `platform-infrastructure` | Découverte et gestion des Applications enfants |
| Microservices | `public-benefits` | Déploiement des workloads applicatifs |
| External Secrets | `public-benefits` | Déploiement des composants et ressources associés |

Cette séparation permet de distinguer la gouvernance GitOps de la gestion des workloads.

## 5. Organisation des charts Helm

### 5.1. Chart générique

Le chart générique des microservices Spring Boot est centralisé dans :

```text
helm/charts/spring-boot-microservice/
```

Il fournit les éléments communs aux services :

- Deployment ;
- Service ;
- ServiceAccount ;
- configuration des probes ;
- ressources CPU et mémoire ;
- variables d'environnement ;
- configuration de sécurité des conteneurs ;
- configuration des volumes ;
- options de déploiement.

Les paramètres propres à chaque microservice sont définis dans ses fichiers de valeurs.

### 5.2. Organisation des valeurs Helm

Structure actuelle :

```text
helm/
└── environments/
    └── dev/
        ├── common.yaml
        │
        ├── ai-public-benefits/
        │   └── document-service.yaml
        │
        └── developer-content-creator/
            └── repository-service.yaml
```

Le fichier `common.yaml` contient les valeurs communes de l'environnement.

Chaque projet dispose ensuite de son propre répertoire.

Cette organisation évite de mélanger les configurations de plusieurs applications et facilite l'évolution vers plusieurs environnements.

Convention :

```text
helm/environments/<environment>/<project>/<service>.yaml
```

Exemples :

```text
helm/environments/dev/ai-public-benefits/document-service.yaml

helm/environments/dev/developer-content-creator/repository-service.yaml
```

## 6. Application enfant : document-service

Fichier :

`gitops/applications/ai-public-benefits/dev/document-service.yaml`

Nom de l'Application :

`document-service`

AppProject :

`public-benefits`

Namespace :

`public-benefits`

### 6.1. Sources Helm

L'Application utilise le mécanisme multi-source d'ArgoCD.

Source principale : chart générique.

```yaml
sources:
  - repoURL: https://github.com/dso2530/platform-infrastructure.git
    targetRevision: main
    path: helm/charts/spring-boot-microservice
    helm:
      releaseName: document-service
      valueFiles:
        - $values/helm/environments/dev/common.yaml
        - $values/helm/environments/dev/ai-public-benefits/document-service.yaml
```

Source secondaire : dépôt contenant les valeurs Helm.

```yaml
  - repoURL: https://github.com/dso2530/platform-infrastructure.git
    targetRevision: main
    ref: values
```

Les deux sources sont actuellement hébergées dans le même dépôt, mais leur séparation logique permet de distinguer le chart et les valeurs utilisées pour son rendu.

### 6.2. Destination

```yaml
destination:
  server: https://kubernetes.default.svc
  namespace: public-benefits
```

### 6.3. Politique de synchronisation

```yaml
syncPolicy:
  syncOptions:
    - CreateNamespace=true
    - PruneLast=true

revisionHistoryLimit: 5
```

Aucune politique `automated` n'est déclarée.

La synchronisation est donc manuelle.

Cette approche permet de contrôler les migrations et les modifications de ressources avant leur application dans le cluster.

## 7. Stratégie de migration des microservices

La migration des services vers le chart générique doit être réalisée progressivement.

Chaque service doit faire l'objet d'une validation indépendante.

### 7.1. Préparation

Pour chaque microservice :

1. identifier son Application ArgoCD actuelle ;
2. identifier son chart Helm actuel ;
3. recenser ses valeurs spécifiques ;
4. identifier ses ressources Kubernetes ;
5. relever ses labels et selectors ;
6. relever ses probes, ports et variables d'environnement ;
7. identifier les secrets et ConfigMaps utilisés.

### 7.2. Centralisation des valeurs

Créer le fichier de valeurs dans :

```text
helm/environments/dev/ai-public-benefits/<service>.yaml
```

Les paramètres communs doivent être placés dans :

```text
helm/environments/dev/common.yaml
```

Les valeurs spécifiques au service doivent rester dans son propre fichier.

### 7.3. Validation Helm

Avant de modifier l'Application ArgoCD :

```bash
helm lint helm/charts/spring-boot-microservice
```

Puis rendre les manifests :

```bash
helm template <release-name> \
  helm/charts/spring-boot-microservice \
  -f helm/environments/dev/common.yaml \
  -f helm/environments/dev/ai-public-benefits/<service>.yaml
```

### 7.4. Comparaison des manifests

Comparer les manifests issus de l'ancien chart avec ceux du chart générique.

Vérifier notamment :

- noms des ressources ;
- namespaces ;
- labels et selectors ;
- ServiceAccounts ;
- images et tags ;
- ports ;
- probes ;
- ressources CPU et mémoire ;
- variables d'environnement ;
- références aux Secrets ;
- volumes et montages ;
- stratégies de déploiement.

Les différences doivent être comprises et validées avant toute synchronisation.

### 7.5. Migration ArgoCD

Après validation :

1. modifier l'Application enfant ;
2. remplacer l'ancien chart par `spring-boot-microservice` ;
3. configurer les sources multi-source ;
4. référencer `common.yaml` ;
5. référencer les valeurs spécifiques du service ;
6. vérifier que l'AppProject autorise les sources ;
7. actualiser l'Application racine si nécessaire ;
8. examiner le rendu ArgoCD ;
9. exécuter `argocd app diff` ;
10. procéder à une synchronisation manuelle après validation explicite.

### 7.6. Vérification après migration

Vérifier séparément :

- le statut de synchronisation ArgoCD ;
- le statut de santé ArgoCD ;
- les ressources Kubernetes rendues ;
- l'absence de différences inattendues.

Un statut `Synced` ne signifie pas nécessairement que le workload est `Healthy`.

Il faut donc distinguer la conformité entre Git et le cluster de l'état opérationnel de l'application.

## 8. Gestion des secrets

Les secrets ne doivent pas être stockés en clair dans les fichiers de valeurs Helm.

Les configurations doivent utiliser des références Kubernetes adaptées, notamment :

```yaml
valueFrom:
  secretKeyRef:
    name: <secret-name>
    key: <secret-key>
```

La gestion et la distribution des secrets doivent rester conformes à l'architecture retenue pour Vault et External Secrets Operator.

Les valeurs Helm peuvent référencer les Secrets Kubernetes, mais ne doivent pas contenir leurs données sensibles.

## 9. Gouvernance et règles d'exploitation

Les règles suivantes s'appliquent au projet :

- un chart générique centralisé ;
- un fichier de valeurs par microservice et environnement ;
- des valeurs communes mutualisées ;
- des Applications ArgoCD déclarées dans le périmètre surveillé ;
- des migrations progressives, service par service ;
- une synchronisation contrôlée pendant les migrations ;
- aucune synchronisation sans examen préalable du diff ;
- aucune donnée sensible dans Git ;
- une documentation mise à jour après chaque migration significative.

## 10. État d'avancement

L'état d'avancement doit être maintenu à mesure des migrations.

| Microservice | Application déclarée dans dev/ | Chart générique | Synchronisation validée |
|---|---|---|---|
| document-service | Oui | Oui, configuré | À suivre dans ArgoCD |
| application-service | Non, préparée | Non | Non |
| citizen-bff | Non, préparée | Non | Non |
| connector-service | Non, préparée | Non | Non |
| document-extraction-service | Non, préparée | Non | Non |
| eligibility-service | Non, préparée | Non | Non |
| knowledge-service | Non, préparée | Non | Non |
| llm-extraction-service | Non, préparée | Non | Non |
| notification-service | Non, préparée | Non | Non |
| profile-service | Non, préparée | Non | Non |
| security-service | Non, préparée | Non | Non |
| territorial-rag-service | Non, préparée | Non | Non |

Les statuts de synchronisation et de santé doivent être confirmés depuis ArgoCD avant d'être déclarés terminés.

## 11. Références

- Architecture de centralisation Helm : `docs/architecture/decisions/ADR-0001-centralisation-charts-helm.md`
- Architecture d'observabilité : `docs/architecture/decisions/ADR-0002-observability-architecture.md`
- Documentation GitOps générale : `docs/operations/kubernetes/gitops/README.md`
- Chart générique : `helm/charts/spring-boot-microservice/`
- Valeurs de développement : `helm/environments/dev/`
- Application racine : `gitops/bootstrap/ai-public-benefits-root.yaml`
- AppProject : `gitops/projects/public-benefits.yaml`