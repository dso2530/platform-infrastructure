# Architecture MinIO — Infrastructure mutualisée

## 1. Objectif

Ce document décrit l'architecture du service MinIO mutualisé, son intégration dans l'infrastructure et les responsabilités des dépôts applicatifs.

MinIO est administré centralement par le dépôt `platform-infrastructure`.

Les applications consomment le stockage objet via l'API S3, sans gérer le cycle de vie du serveur MinIO.

## 2. Positionnement architectural

MinIO est déployé sur l'hôte Linux à l'aide de Podman.

Il fonctionne en dehors du cluster Kubernetes k0s.

```text
                 platform-infrastructure
                          |
                          |
                   Podman Compose
                          |
                          v
                    +-----------+
                    |   MinIO   |
                    |           |
                    | S3 : 9000 |
                    | UI : 9001 |
                    +-----------+
                          |
                          v
                  docker_minio-data
                          |
              +-----------+-----------+
              |                       |
              v                       v
         Harbor Registry       Applications
         harbor-registry       consommatrices
```

## 3. Environnement technique

| Composant | Configuration |
|---|---|
| Runtime | Podman |
| Orchestration | Docker Compose via Podman |
| Image | quay.io/minio/minio |
| Architecture | linux/amd64 |
| Version d'image | Référence figée par digest |
| Conteneur | minio |
| Volume | docker_minio-data |
| Point de montage | /data |
| Réseau | docker_default |
| API S3 | TCP 9000 |
| Console | TCP 9001 |
| Hôte | 192.168.1.40 |

Référence d'image actuellement validée :

`quay.io/minio/minio@sha256:a1a8bd4ac40ad7881a245bab97323e18f971e4d4cba2c2007ec1bedd21cbaba2`

## 4. Organisation des responsabilités

### 4.1 platform-infrastructure

Responsabilités :

- Déployer et maintenir MinIO.
- Gérer les volumes persistants.
- Administrer les réseaux Podman.
- Gérer les politiques de stockage.
- Organiser les sauvegardes et restaurations.
- Superviser la disponibilité.
- Organiser la rotation des identifiants.
- Préparer l'intégration avec Vault.

### 4.2 ai-public-benefits-platform

Responsabilités :

- Définir les besoins de stockage documentaire.
- Définir les buckets applicatifs.
- Configurer les accès S3 des microservices.
- Gérer les politiques d'accès applicatives.
- Assurer la conformité RGPD des documents.

### 4.3 developer-content-creator

Responsabilités :

- Consommer les services de stockage nécessaires à l'application.
- Utiliser des comptes S3 dédiés.
- Ne pas gérer le cycle de vie de MinIO.

## 5. Stockage persistant

Le volume Podman existant est :

`docker_minio-data`

Il est monté dans le conteneur sur :

`/data`

Le volume est déclaré comme externe dans le Compose.

Cette déclaration empêche Compose de créer un nouveau volume portant un nom différent.

Règles :

- Ne jamais supprimer ce volume lors d'une mise à jour.
- Ne jamais utiliser `down -v` sur cette infrastructure.
- Vérifier le volume avant chaque opération de maintenance.
- Effectuer une sauvegarde avant toute opération destructive.

## 6. Sécurité

Le compte root MinIO est réservé à l'administration.

Les applications doivent disposer de comptes dédiés, avec des politiques limitées aux buckets nécessaires.

Les identifiants locaux sont actuellement fournis par `.env.minio`, exclu du versionnement Git.

Objectif :

- Centraliser les secrets dans Vault.
- Prévoir un mécanisme de distribution sécurisé vers Podman.
- Organiser la rotation des identifiants.
- Limiter l'accès à la console d'administration.
- Éviter l'exposition publique des ports 9000 et 9001.

## 7. Sauvegarde et restauration

La sauvegarde doit couvrir :

- Les objets stockés dans MinIO.
- Les métadonnées Harbor dans PostgreSQL.
- Les configurations nécessaires à la reconstruction.
- Les secrets et les procédures de récupération.

Les sauvegardes Harbor doivent être coordonnées afin de préserver la cohérence entre les métadonnées PostgreSQL et les objets du bucket `harbor-registry`.

Les procédures détaillées sont décrites dans :

- `backup.md`
- `restore.md`

## 8. Haute disponibilité et résilience

L'installation actuelle utilise un seul conteneur MinIO avec un volume local.

Elle ne constitue pas une architecture MinIO distribuée ni une haute disponibilité.

La résilience repose actuellement sur :

- La persistance du volume Podman.
- Les sauvegardes externalisées.
- La possibilité de recréer le conteneur.
- La vérification régulière des restaurations.

Une évolution vers un stockage distribué pourra être étudiée ultérieurement.

## 9. État de l'architecture

| Élément | État |
|---|---|
| MinIO Podman | Opérationnel |
| Volume persistant | Existant |
| Compose centralisé | Préparé et validé |
| Image figée | Validée |
| Gestion des secrets par Vault | À réaliser |
| Rotation des identifiants | À réaliser |
| Documentation d'architecture | En cours |
| Migration du Compose | En attente |
| Test de restauration MinIO isolé | En attente |

## 10. Décisions architecturales

| Décision | Justification |
|---|---|
| MinIO centralisé dans platform-infrastructure | Séparation des responsabilités |
| Podman comme runtime | Cohérence avec l'infrastructure existante |
| Volume externe | Protection des données persistantes |
| Image figée par digest | Reproductibilité |
| Comptes S3 dédiés | Principe du moindre privilège |
| Vault comme cible de gestion des secrets | Centralisation et sécurité |
| Buckets applicatifs gérés séparément | Isolation des responsabilités |