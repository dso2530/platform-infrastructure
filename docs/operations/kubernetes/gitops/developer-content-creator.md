# GitOps – Developer Content Creator

## 1. Objectif

Ce document décrit l'organisation GitOps du projet Developer Content Creator dans le dépôt `platform-infrastructure`.

Il formalise :

- L'organisation des Applications ArgoCD ;
- L'utilisation du chart Helm générique ;
- La séparation des valeurs communes et spécifiques ;
- La procédure de migration des microservices ;
- La migration de référence de `repository-service`.

La stratégie architecturale est définie dans l'ADR-0001.

## 2. Dépôts Git

Deux dépôts interviennent dans le cycle de vie du projet.

| Dépôt | Responsabilité |
|---|---|
| `developer-content-creator` | Code applicatif, tests, Dockerfiles et pipelines de construction |
| `platform-infrastructure` | Charts Helm, valeurs d'environnement et déclarations GitOps |

Dépôts :

- https://github.com/dso2530/developer-content-creator
- https://github.com/dso2530/platform-infrastructure

Le dépôt `platform-infrastructure` constitue la source de vérité pour la configuration de déploiement Kubernetes.

## 3. Organisation GitOps

Les ressources GitOps du projet sont centralisées dans :

```text
gitops/
├── bootstrap/
│   └── developer-content-creator-root.yaml
│
├── projects/
│   └── developer-content-creator.yaml
│
└── applications/
    └── developer-content-creator/
        └── dev/
            └── repository-service.yaml
```

Les valeurs Helm sont centralisées dans :

```text
helm/
├── charts/
│   └── spring-boot-microservice/
│
└── environments/
    └── dev/
        ├── common.yaml
        └── developer-content-creator/
            └── repository-service.yaml
```

Cette structure sera étendue progressivement aux autres microservices.

## 4. Application racine

L'Application racine est :

```text
developer-content-creator-root
```

Elle référence le dépôt :

```text
https://github.com/dso2530/platform-infrastructure.git
```

Branche :

```text
main
```

Répertoire surveillé :

```text
gitops/applications/developer-content-creator/dev
```

Son rôle est de gérer les déclarations des Applications enfants.

La synchronisation de l'Application racine ne déclenche pas automatiquement la synchronisation des workloads.

## 5. AppProject

Le projet ArgoCD est :

```text
developer-content-creator
```

Fichier :

```text
gitops/projects/developer-content-creator.yaml
```

Les dépôts autorisés comprennent :

```yaml
sourceRepos:
  - https://github.com/dso2530/developer-content-creator.git
  - https://github.com/dso2530/platform-infrastructure.git
```

Le second dépôt est nécessaire puisque les charts Helm et leurs valeurs sont désormais centralisés dans `platform-infrastructure`.

La destination Kubernetes est :

```yaml
destinations:
  - server: https://kubernetes.default.svc
    namespace: developer-content-creator
```

## 6. Application enfant : repository-service

Nom :

```text
developer-content-creator-repository-service-dev
```

Fichier :

```text
gitops/applications/developer-content-creator/dev/repository-service.yaml
```

### 6.1. Sources Helm

L'Application utilise une configuration multi-source.

Source du chart :

```yaml
- repoURL: https://github.com/dso2530/platform-infrastructure.git
  targetRevision: main
  path: helm/charts/spring-boot-microservice
  helm:
    releaseName: developer-content-creator-repository-service-dev
    valueFiles:
      - $values/helm/environments/dev/common.yaml
      - $values/helm/environments/dev/developer-content-creator/repository-service.yaml
```

Source des valeurs :

```yaml
- repoURL: https://github.com/dso2530/platform-infrastructure.git
  targetRevision: main
  ref: values
```

Les deux sources sont versionnées sur la branche `main`.

### 6.2. Destination

```yaml
destination:
  server: https://kubernetes.default.svc
  namespace: developer-content-creator
```

### 6.3. Synchronisation

La synchronisation est manuelle.

```yaml
syncPolicy:
  syncOptions:
    - CreateNamespace=true
```

Aucun mécanisme `automated` n'est configuré.

## 7. Valeurs Helm

### 7.1. Valeurs communes

Fichier :

```text
helm/environments/dev/common.yaml
```

Il contient les paramètres mutualisés :

- Sécurité des Pods ;
- Sécurité des conteneurs ;
- Ressources par défaut ;
- Variables d'environnement communes ;
- Configuration d'observabilité.

Exemple :

```yaml
podSecurityContext:
  runAsNonRoot: true
  seccompProfile:
    type: RuntimeDefault

securityContext:
  allowPrivilegeEscalation: false
  capabilities:
    drop:
      - ALL
  readOnlyRootFilesystem: true
```

### 7.2. Valeurs spécifiques

Fichier :

```text
helm/environments/dev/developer-content-creator/repository-service.yaml
```

Il définit notamment :

- L'image et son tag ;
- Le nombre de réplicas ;
- Le ServiceAccount ;
- Les ports ;
- Les variables d'environnement ;
- Les références aux Secrets Kubernetes ;
- Les ressources CPU et mémoire ;
- Les probes ;
- La stratégie de déploiement.

Les listes YAML, en particulier `env`, doivent être définies avec attention : une liste déclarée dans les valeurs spécifiques remplace généralement la liste correspondante des valeurs communes lors de la fusion Helm.

## 8. Procédure de migration d'un microservice

Chaque microservice doit être migré individuellement.

### Étape 1 — Identifier la configuration existante

Recenser :

- L'ancien chart ;
- Les fichiers de valeurs ;
- Les noms des ressources Kubernetes ;
- Les selectors et labels ;
- Les images ;
- Les ports ;
- Les probes ;
- Les ressources ;
- Les variables d'environnement ;
- Les références aux Secrets.

### Étape 2 — Créer les valeurs spécifiques

Créer un fichier dans :

```text
helm/environments/dev/developer-content-creator/
```

Exemple :

```text
repository-service.yaml
```

### Étape 3 — Valider le chart générique

```bash
helm lint helm/charts/spring-boot-microservice
```

### Étape 4 — Comparer les manifests

Rendre les anciens et nouveaux manifests :

```bash
helm template <release-name> <old-chart> \
  --namespace developer-content-creator \
  -f <old-values.yaml> \
  > /tmp/service-old.yaml
```

```bash
helm template <release-name> \
  helm/charts/spring-boot-microservice \
  --namespace developer-content-creator \
  -f helm/environments/dev/common.yaml \
  -f helm/environments/dev/developer-content-creator/<service>.yaml \
  > /tmp/service-new.yaml
```

Comparer les résultats et examiner les éventuelles différences.

### Étape 5 — Modifier l'Application ArgoCD

Mettre à jour la source Helm et les références aux valeurs.

Conserver le nom de l'Application, le projet ArgoCD, le namespace et la politique de synchronisation.

### Étape 6 — Actualiser et contrôler le rendu

```bash
argocd app get <application-name> --hard-refresh
argocd app get <application-name>
```

Vérifier les sources, la branche, le chart et les fichiers de valeurs.

### Étape 7 — Examiner le diff

```bash
argocd app diff <application-name>
```

La synchronisation ne doit intervenir qu'après examen et validation explicite du diff.

### Étape 8 — Synchroniser manuellement

```bash
argocd app sync <application-name>
```

### Étape 9 — Vérifier les ressources

```bash
argocd app get <application-name>

kubectl -n developer-content-creator get deploy,svc,sa

kubectl -n developer-content-creator get rs,pods
```

La conformité GitOps et la santé applicative doivent être évaluées séparément.

## 9. Migration de référence : repository-service

### 9.1. Situation initiale

Le service utilisait un chart Helm spécifique au dépôt applicatif :

```text
developer-content-creator/
└── deployment/
    └── helm/
        └── developer-content-creator/
```

### 9.2. Situation cible

Le service utilise désormais le chart centralisé :

```text
platform-infrastructure/
└── helm/
    └── charts/
        └── spring-boot-microservice/
```

Les valeurs sont externalisées dans :

```text
helm/environments/dev/common.yaml

helm/environments/dev/developer-content-creator/repository-service.yaml
```

### 9.3. Ressources Kubernetes préservées

Les noms des ressources et les selectors ont été conservés.

| Ressource | Nom |
|---|---|
| Deployment | `developer-content-creator-repository-service` |
| Service | `developer-content-creator-repository-service` |
| ServiceAccount | `developer-content-creator` |
| Namespace | `developer-content-creator` |

Selector :

```yaml
app.kubernetes.io/instance: developer-content-creator-repository-service-dev
app.kubernetes.io/name: repository-service
```

### 9.4. Sécurité

La nouvelle configuration applique notamment :

- Exécution non-root ;
- Profil seccomp `RuntimeDefault` ;
- Suppression des capabilities Linux ;
- Désactivation de l'élévation des privilèges ;
- Système de fichiers racine en lecture seule ;
- Désactivation du montage automatique du token ServiceAccount ;
- Volume temporaire `emptyDir` pour `/tmp`.

### 9.5. Validation réalisée

Les contrôles suivants ont été réalisés :

| Contrôle | Résultat |
|---|---|
| Validation Helm | Réussie |
| Rendu des anciens manifests | Réalisé |
| Rendu des nouveaux manifests | Réalisé |
| Comparaison des manifests | Réalisée |
| Conservation des noms et selectors | Confirmée |
| Mise à jour de l'Application ArgoCD | Réalisée |
| Autorisation du dépôt dans l'AppProject | Confirmée |
| Synchronisation ArgoCD | Réussie |
| Vérification du Deployment | Réalisée |
| `argocd app diff` après synchronisation | Aucune différence |

### 9.6. État après migration

L'Application ArgoCD référence désormais :

```text
Repo:
https://github.com/dso2530/platform-infrastructure.git

Target:
main

Path:
helm/charts/spring-boot-microservice
```

L'état de synchronisation est :

```text
Sync Status: Synced
Health Status: Progressing
Sync Policy: Manual
```

L'état `Progressing` concerne la disponibilité du Deployment et ne remet pas en cause la migration de la configuration GitOps.

La migration Helm de `repository-service` est considérée comme terminée.

## 10. Prochaines étapes

Les prochaines migrations devront suivre la même procédure :

1. Identifier le chart et les valeurs du service.
2. Créer les valeurs dans `platform-infrastructure`.
3. Valider le rendu du chart générique.
4. Comparer les anciens et nouveaux manifests.
5. Modifier l'Application ArgoCD.
6. Examiner le diff.
7. Synchroniser après validation explicite.
8. Vérifier les ressources et l'état de synchronisation.

Les services suivants seront migrés individuellement, sans modifier les Applications qui ne sont pas concernées.