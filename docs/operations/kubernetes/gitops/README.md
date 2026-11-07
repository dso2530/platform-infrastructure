# GitOps – Principes et fonctionnement

## 1. Objectif

Cette documentation décrit les principes de gestion GitOps utilisés dans l'infrastructure Kubernetes de la plateforme.

L'approche repose sur :

- Git comme source de vérité de la configuration déclarative ;
- Helm pour la génération des manifests Kubernetes ;
- ArgoCD pour la réconciliation de l'état désiré ;
- Kubernetes pour l'exécution des workloads.

La stratégie de centralisation des charts Helm est définie dans l'ADR-0001 : `docs/architecture/decisions/ADR-0001-centralisation-charts-helm.md`.

## 2. Séparation des responsabilités

| Composant | Responsabilité |
|---|---|
| Dépôt applicatif | Code source, tests, Dockerfiles et construction des images |
| `platform-infrastructure` | Charts Helm, valeurs et déclarations GitOps |
| Helm | Génération des manifests Kubernetes |
| ArgoCD | Synchronisation et suivi de l'état désiré |
| Kubernetes | Exécution et supervision des workloads |

Les configurations de déploiement ne doivent pas être dupliquées dans les dépôts applicatifs.

## 3. Organisation des configurations

Le dépôt `platform-infrastructure` centralise trois catégories de ressources :

### 3.1. Charts Helm

Emplacement :

```text
helm/charts/
```

Les charts génériques définissent les modèles de ressources Kubernetes réutilisables.

Exemple :

```text
helm/charts/spring-boot-microservice/
```

### 3.2. Valeurs Helm

Emplacement :

```text
helm/environments/
```

Les fichiers de valeurs définissent les paramètres propres aux environnements et aux applications.

Les valeurs communes peuvent être partagées entre plusieurs services.

### 3.3. Applications ArgoCD

Emplacement :

```text
gitops/applications/
```

Chaque Application ArgoCD déclare la source Helm, les valeurs, le projet ArgoCD et la destination Kubernetes.

## 4. Fonctionnement d'ArgoCD

ArgoCD surveille les dépôts Git configurés dans les Applications.

Le processus de réconciliation comprend :

1. Lecture de la configuration déclarée dans Git.
2. Génération des manifests Helm.
3. Comparaison avec les ressources présentes dans Kubernetes.
4. Présentation des différences.
5. Synchronisation après validation.
6. Suivi de l'état de santé des ressources.

Les synchronisations applicatives sont manuelles par défaut.

Aucune synchronisation automatique ne doit être activée sans décision explicite.

## 5. Applications racines et enfants

L'architecture peut utiliser une Application racine pour gérer plusieurs Applications enfants.

L'Application racine surveille un répertoire contenant les déclarations des Applications enfants.

Les Applications enfants gèrent individuellement les workloads.

Cette organisation permet :

- Une gestion centralisée des applications ;
- Une synchronisation indépendante des microservices ;
- Une meilleure isolation des opérations ;
- Une migration progressive des services.

La synchronisation de l'Application racine ne doit pas être confondue avec celle des workloads.

## 6. Applications Helm multi-source

ArgoCD permet de séparer le chart Helm et ses fichiers de valeurs au moyen de plusieurs sources Git.

Exemple de principe :

```yaml
spec:
  sources:
    - repoURL: https://github.com/dso2530/platform-infrastructure.git
      targetRevision: main
      path: helm/charts/spring-boot-microservice
      helm:
        valueFiles:
          - $values/helm/environments/dev/common.yaml
          - $values/helm/environments/dev/<service>.yaml

    - repoURL: https://github.com/dso2530/platform-infrastructure.git
      targetRevision: main
      ref: values
```

Le préfixe `$values` référence la source déclarée avec `ref: values`.

Cette approche permet de conserver les charts et les configurations d'environnement dans des emplacements distincts.

## 7. Validation avant synchronisation

Toute modification d'une Application doit respecter les contrôles suivants :

### Validation Helm

```bash
helm lint <chart-directory>
```

### Rendu local

```bash
helm template <release-name> <chart-directory> \
  --namespace <namespace> \
  -f <common-values.yaml> \
  -f <service-values.yaml>
```

### Vérification ArgoCD

```bash
argocd app get <application-name> --hard-refresh
argocd app diff <application-name>
```

Le diff doit être examiné avant toute synchronisation.

### Synchronisation manuelle

Après validation explicite :

```bash
argocd app sync <application-name>
```

## 8. Synchronisation et santé des workloads

Il est essentiel de distinguer deux états :

| État | Signification |
|---|---|
| `Synced` | Les ressources Kubernetes correspondent à la configuration déclarée dans Git |
| `Healthy` | Les ressources satisfont les critères de santé ArgoCD |
| `Progressing` | Les ressources sont en cours de déploiement ou n'ont pas encore atteint leur état attendu |
| `Degraded` | Une ou plusieurs ressources présentent un problème de santé |

Une Application peut être `Synced` et `Progressing` simultanément.

Une dépendance externe indisponible, comme une base de données, peut empêcher un service de devenir opérationnel sans remettre en cause la conformité de sa configuration GitOps.

## 9. Principes de gouvernance

Les règles suivantes s'appliquent :

1. Un microservice est migré à la fois.
2. Les changements sont versionnés dans Git.
3. Les charts génériques sont centralisés.
4. Les valeurs spécifiques restent séparées des templates.
5. Les noms et selectors Kubernetes existants sont préservés lors des migrations, sauf décision explicite.
6. Les Secrets ne sont jamais stockés en clair dans Git.
7. Le diff ArgoCD est examiné avant synchronisation.
8. Les workloads ne sont pas synchronisés automatiquement.
9. La santé applicative est contrôlée indépendamment de l'état de synchronisation GitOps.

## 10. Documentation complémentaire

- Architecture des charts Helm : `docs/architecture/decisions/ADR-0001-centralisation-charts-helm.md`
- Architecture d'observabilité : `docs/architecture/decisions/ADR-0002-observability-architecture.md`
- Implémentation GitOps Developer Content Creator : `docs/operations/kubernetes/gitops/developer-content-creator.md`