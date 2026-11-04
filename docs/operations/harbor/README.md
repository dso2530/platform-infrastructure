# Harbor — Documentation opérationnelle

**Projet :** Platform Infrastructure  
**Service :** Harbor Container Registry  
**Environnement de référence :** Kubernetes / k0s  
**Namespace :** `harbor`  
**Chart Helm :** `harbor-1.19.4`  
**Version Harbor :** `2.15.4`  
**Révision Helm actuelle :** `3`  
**Statut :** Service opérationnel — PRA partiellement validé

---

## 1. Présentation

Harbor est le registre centralisé d'images Docker et OCI de la plateforme d'infrastructure.

Il fournit un service mutualisé aux différents projets applicatifs :

- `developer-content-creator`
- `ai-public-benefits-platform`
- autres projets présents ou futurs.

Harbor est administré indépendamment des applications clientes.

Son architecture repose sur :

- PostgreSQL externe pour les métadonnées ;
- MinIO externe pour le stockage des blobs ;
- Redis déployé dans Kubernetes ;
- Trivy déployé dans Kubernetes ;
- les composants applicatifs Harbor déployés dans Kubernetes.

Les applications clientes consomment Harbor pour publier et récupérer leurs images.

## 2. Architecture

| Composant | Hébergement | Fonction |
|---|---|---|
| Harbor Core | Kubernetes | API et gestion |
| Harbor Registry | Kubernetes | Images et manifests |
| Harbor Portal | Kubernetes | Interface utilisateur |
| Harbor Jobservice | Kubernetes | Tâches asynchrones |
| Harbor Nginx | Kubernetes | Reverse proxy et exposition |
| Harbor Redis | Kubernetes | Cache et files de tâches |
| Harbor Trivy | Kubernetes | Analyse des vulnérabilités |
| PostgreSQL | Externe / Podman | Métadonnées |
| MinIO | Externe / Podman | Stockage des blobs |
| Vault | Externe | Gestion des secrets |
| External Secrets Operator | Kubernetes | Synchronisation des secrets |
| ArgoCD | Kubernetes | GitOps de la plateforme ; intégration Harbor à finaliser |

Le stockage objet utilise le bucket dédié `harbor-registry`.

### 2.1 Configuration Helm de référence

La configuration Helm de référence est conservée dans :

```text
infra/kubernetes/harbor/values/values-production.yaml
```

Ce fichier correspond aux valeurs personnalisées exportées de la révision Helm 3.

Il définit notamment :

- le PostgreSQL externe ;
- le backend S3 compatible MinIO ;
- le bucket `harbor-registry` ;
- les paramètres de connexion au stockage ;
- le mode d'exposition NodePort ;
- le nombre de replicas ;
- l'activation de Trivy.

Les identifiants ne sont pas enregistrés dans ce fichier. Les références aux Secrets Kubernetes sont conservées :

| Secret Kubernetes | Utilisation |
|---|---|
| `harbor-db` | Connexion PostgreSQL |
| `harbor-registry-s3` | Authentification S3 / MinIO |

Les valeurs sensibles sont gérées séparément de la configuration Helm.

**Attention :** le fichier constitue une configuration de référence, mais son intégration complète dans le workflow GitOps reste à réaliser.

Pour plus de détails : `architecture.md`.

## 3. Documentation disponible

| Document | Description | Statut |
|---|---|---|
| `architecture.md` | Architecture technique et décisions | Documenté |
| `minio-migration.md` | Migration et configuration du stockage MinIO | À distinguer des tests de fonctionnement du backend |
| `backup.md` | Sauvegarde Harbor et MinIO | Procédure documentée et contrôles réalisés |
| `restore.md` | Restauration PostgreSQL, MinIO et Harbor | Tests isolés réalisés ; PRA complet non validé |
| `rollback.md` | Retour arrière et protection du stockage | Procédure documentée |
| `troubleshooting.md` | Diagnostic des incidents Harbor | Guide documenté ; procédures à valider en conditions opérationnelles |

## 4. Informations d'exploitation

### 4.1 Kubernetes

Namespace :

```text
harbor
```

Commandes de diagnostic :

```bash
kubectl -n harbor get pods -o wide
kubectl -n harbor get deployments
kubectl -n harbor get statefulsets
kubectl -n harbor get services
```

Vérification des composants applicatifs :

```bash
kubectl -n harbor rollout status deployment/harbor-core
kubectl -n harbor rollout status deployment/harbor-registry
kubectl -n harbor rollout status deployment/harbor-jobservice
kubectl -n harbor rollout status deployment/harbor-portal
kubectl -n harbor rollout status deployment/harbor-nginx
```

Vérification de Redis et Trivy :

```bash
kubectl -n harbor rollout status statefulset/harbor-redis
kubectl -n harbor rollout status statefulset/harbor-trivy
```

### 4.2 Accès Harbor

Endpoint local de référence :

```text
http://192.168.1.40:30002
```

Le service est exposé en NodePort.

**Attention :** le TLS est actuellement désactivé dans cet environnement. Cette configuration est réservée à l'environnement local et ne doit pas être reproduite telle quelle sur une infrastructure exposée.

### 4.3 MinIO

Endpoint local de référence :

```text
http://192.168.1.40:9000
```

Vérification de santé :

```bash
curl -fsS \
  http://192.168.1.40:9000/minio/health/live
```

Bucket Harbor :

```text
harbor-registry
```

Le backend Registry utilise le stockage S3 compatible MinIO avec :

- authentification S3 V4 ;
- redirection désactivée ;
- endpoint HTTP local ;
- bucket dédié.

### 4.4 PostgreSQL

PostgreSQL est hébergé hors Kubernetes.

Paramètres non sensibles de référence :

| Paramètre | Valeur |
|---|---|
| Hôte | `192.168.1.40` |
| Port | `5432` |
| Base | `harbor` |
| Type | Externe |

Les identifiants sont référencés via le Secret Kubernetes `harbor-db`.

### 4.5 Redis et Trivy

Redis et Trivy sont déployés dans le namespace `harbor` sous forme de StatefulSets.

Ils font partie des composants Kubernetes à contrôler lors des opérations de maintenance et de restauration.

Redis constitue un cache reconstructible. Trivy nécessite la disponibilité de sa base de vulnérabilités, qui peut devoir être actualisée après une restauration.

## 5. Sécurité

Les principes de sécurité sont les suivants :

- stockage des secrets dans Vault ;
- synchronisation avec External Secrets Operator ;
- absence de credentials en clair dans Git ;
- séparation entre configuration et credentials ;
- isolation du bucket MinIO ;
- permissions Harbor par projet ;
- limitation des droits des comptes techniques ;
- utilisation de TLS dans les environnements exposés ;
- contrôle des accès aux endpoints d'administration.

Les fichiers Helm versionnés ne doivent contenir que des paramètres non sensibles et des références aux Secrets Kubernetes.

**État de l'intégration des secrets :** les références `harbor-db` et `harbor-registry-s3` sont présentes dans la configuration Helm. L'intégration ExternalSecret propre à Harbor doit encore être finalisée et validée.

## 6. Déploiement et configuration Helm

### 6.1 Configuration de référence

Le fichier de valeurs est :

```text
infra/kubernetes/harbor/values/values-production.yaml
```

Il correspond à la configuration personnalisée de la révision Helm 3 et constitue la référence pour les opérations de maintenance.

### 6.2 Vérification de la release

```bash
helm -n harbor list
helm -n harbor history harbor
helm -n harbor status harbor
```

### 6.3 Vérification des valeurs déployées

```bash
helm -n harbor get values harbor
```

Ne pas publier la sortie brute de cette commande si elle contient des paramètres sensibles.

### 6.4 Règles de modification

Toute modification de configuration doit respecter les principes suivants :

1. Modifier le fichier de valeurs de référence.
2. Vérifier les différences avec la configuration actuellement déployée.
3. Vérifier la compatibilité avec la version du chart.
4. Contrôler les références aux Secrets Kubernetes.
5. Vérifier que le backend S3 reste correctement configuré.
6. Prévoir une sauvegarde avant toute opération présentant un risque sur les données.
7. Contrôler l'état des composants après déploiement.
8. Documenter la révision Helm obtenue.

## 7. Sauvegarde et restauration

La sauvegarde Harbor doit couvrir deux ensembles de données complémentaires :

- les métadonnées PostgreSQL ;
- les blobs stockés dans MinIO.

Une sauvegarde isolée de PostgreSQL ou de MinIO ne constitue pas une sauvegarde complète de Harbor.

### 7.1 État des sauvegardes

Les opérations suivantes ont été réalisées :

| Opération | Statut |
|---|---|
| Sauvegarde PostgreSQL | Réalisée |
| Sauvegarde du bucket MinIO | Réalisée |
| Vérification SHA-256 | Validée |
| Restauration PostgreSQL isolée | Testée |
| Restauration MinIO isolée | Testée |
| Vérification d'intégrité des blobs | Validée |
| Automatisation périodique | À mettre en place |

Les tests isolés ont notamment donné les résultats suivants :

- PostgreSQL : 49 tables et 47 séquences restaurées ;
- MinIO : 74 objets restaurés ;
- MinIO : 37 blobs vérifiés cryptographiquement.

**Limite importante :** les sauvegardes PostgreSQL et MinIO du 4 novembre 2026 n'ont pas été réalisées exactement au même instant. Leur restauration indépendante ne prouve donc pas l'existence d'un point de récupération coordonné.

### 7.2 Principe de restauration

La restauration doit préserver la cohérence entre les métadonnées PostgreSQL et les objets Registry stockés dans MinIO.

Une restauration coordonnée doit être réalisée à partir d'un jeu de sauvegardes cohérent.

**Statut du PRA :** les restaurations isolées ont été validées. La restauration complète et coordonnée de Harbor reste à tester.

Procédures détaillées :

- `backup.md`
- `restore.md`

## 8. Rollback et protection du stockage

Le rollback Harbor nécessite une attention particulière en raison de l'externalisation du stockage Registry.

### 8.1 Backend actuel

La configuration actuellement déployée utilise :

```yaml
persistence:
  enabled: false
  imageChartStorage:
    type: s3
    disableredirect: true
    s3:
      bucket: harbor-registry
      region: us-east-1
      regionendpoint: http://192.168.1.40:9000
      secure: false
      v4auth: true
      existingSecret: harbor-registry-s3
```

### 8.2 Historique Helm

Les configurations effectives des révisions examinées sont les suivantes :

| Paramètre | Révision 1 | Révision 2 | Révision 3 |
|---|---|---|---|
| Backend Registry | `filesystem` | `filesystem` | `s3` |
| Bucket MinIO | Non configuré | Non configuré | `harbor-registry` |
| Endpoint S3 | Non configuré | Non configuré | `192.168.1.40:9000` |

**Les révisions 1 et 2 ne doivent donc pas être utilisées comme cibles de rollback direct.**

Un retour à une ancienne version applicative doit préserver la configuration du stockage MinIO.

### 8.3 Règles obligatoires

Avant toute opération de rollback :

1. Vérifier l'historique Helm.
2. Identifier les différences de configuration entre les révisions.
3. Vérifier la compatibilité de la version cible avec le backend S3.
4. Vérifier les Secrets Kubernetes.
5. Vérifier PostgreSQL et MinIO.
6. Disposer de sauvegardes exploitables.
7. Prévoir une procédure de retour à la configuration actuelle.

Un rollback Helm ne restaure ni PostgreSQL ni les objets MinIO.

La procédure détaillée est disponible dans `rollback.md`.

## 9. État opérationnel

| Fonctionnalité | Statut |
|---|---|
| Déploiement Harbor sur k0s | Opérationnel |
| PostgreSQL externe | Opérationnel |
| Redis dans Kubernetes | Opérationnel |
| Trivy dans Kubernetes | Opérationnel |
| Stockage des blobs dans MinIO | Opérationnel |
| Isolation du bucket Harbor | Validée |
| Push et pull des images | Validés |
| Persistance après redémarrage Registry | Validée |
| Sauvegarde PostgreSQL | Réalisée |
| Sauvegarde MinIO | Réalisée |
| Restauration PostgreSQL isolée | Testée |
| Restauration MinIO isolée | Testée |
| Restauration complète coordonnée | À valider |
| Intégration ExternalSecret Harbor | À finaliser |
| Sauvegardes automatisées | À faire |
| Supervision complète | À formaliser |
| Rollback applicatif compatible S3 | Procédure documentée, test à réaliser |
| Intégration Harbor dans GitOps | À finaliser |

Harbor est opérationnel pour les usages courants. En revanche, la capacité de reprise après sinistre complète ne doit pas être considérée comme validée tant que la restauration coordonnée n'a pas été testée.

## 10. Travaux prioritaires

1. Automatiser les sauvegardes PostgreSQL et MinIO.
2. Définir une stratégie de rétention.
3. Mettre en place des tests périodiques de restauration.
4. Valider une restauration coordonnée PostgreSQL / MinIO.
5. Finaliser l'intégration ExternalSecret Harbor.
6. Formaliser la rotation des identifiants S3.
7. Mettre en place les alertes de capacité et de disponibilité.
8. Intégrer la configuration Helm de référence dans le workflow GitOps.
9. Renforcer la supervision des composants Harbor.
10. Tester un rollback applicatif compatible avec le backend S3.

## 11. Relations avec les autres dépôts

| Dépôt | Responsabilité |
|---|---|
| `platform-infrastructure` | Harbor, MinIO, Vault, Kubernetes et exploitation |
| `platform-engineering-idp` | Backstage et portail développeur |
| `developer-content-creator` | Application DCC et publication de ses images |
| `ai-public-benefits-platform` | Applications métier et publication de leurs images |

**Principe :** les projets applicatifs consomment Harbor. Ils ne possèdent pas son infrastructure.

---

*Dernière mise à jour : 4 novembre 2026.*
