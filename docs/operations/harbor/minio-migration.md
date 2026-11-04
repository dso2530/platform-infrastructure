# Migration opérationnelle de Harbor vers MinIO

**Date :** 3 novembre 2026  
**Environnement :** Infrastructure locale k0s  
**Namespace Kubernetes :** `harbor`  
**Version Harbor :** 2.15.4  
**Version Helm Chart :** 1.19.4  
**Statut :** Migration fonctionnelle — sauvegarde et restauration à formaliser.

## 1. Objectif

Externaliser le stockage des images Docker/OCI de Harbor vers MinIO afin de :

- garantir la persistance des blobs indépendamment du cycle de vie des pods Registry ;
- bénéficier d'un stockage objet persistant ;
- isoler les données du registre dans un bucket dédié ;
- préparer une stratégie de sauvegarde et de restauration.

## 2. Architecture cible

| Composant | Configuration |
|---|---|
| Harbor | Namespace `harbor` |
| Registry | Deployment `harbor-registry` |
| MinIO | Instance Podman |
| Endpoint S3 | `http://192.168.1.40:9000` |
| Bucket | `harbor-registry` |
| Utilisateur S3 | `harbor-registry` |
| Secret Kubernetes | `harbor-registry-s3` |
| Redis | `harbor-redis`, DB 2 |
| PostgreSQL | Base `harbor` |

Les autres buckets MinIO (`documents`, `documents-ai`, `applications`, etc.) ne doivent pas être modifiés par les opérations Harbor.

## 3. Configuration du stockage S3

Fichier Helm :

`infra/kubernetes/harbor/harbor-s3-storage.yaml`

```yaml
persistence:
  imageChartStorage:
    disableredirect: true
    type: s3
    s3:
      region: us-east-1
      bucket: harbor-registry
      existingSecret: harbor-registry-s3
      regionendpoint: http://192.168.1.40:9000
      secure: false
      v4auth: true
```

Le Secret Kubernetes `harbor-registry-s3` contient les identifiants dédiés à l'accès au bucket.

**Sécurité :**
- Ne jamais versionner les identifiants S3.
- Ne jamais afficher les valeurs du Secret dans les journaux ou les rapports.
- Conserver les permissions IAM limitées au bucket `harbor-registry`.
- Prévoir la rotation des identifiants MinIO.

La configuration conserve `persistence.enabled: false`. Les blobs du Registry sont désormais stockés dans MinIO, et non dans le système de fichiers éphémère du pod.

## 4. Déroulement de la migration

### 4.1 Préparation

Les sauvegardes suivantes ont été réalisées avant la migration :

| Fichier | Description |
|---|---|
| `harbor-values-before-s3.yaml` | Valeurs Helm avant migration |
| `harbor-manifest-before-s3.yaml` | Manifeste Kubernetes avant migration |
| `harbor-postgres-before-s3.dump` | Dump PostgreSQL de la base Harbor |

Emplacement :

`/home/mfo-dso/harbor-backups/`

Les fichiers de sauvegarde sont protégés avec des permissions restrictives.

### 4.2 Création du stockage MinIO

Les opérations suivantes ont été réalisées :

1. Création du bucket privé `harbor-registry`.
2. Création de l'utilisateur MinIO `harbor-registry`.
3. Création et association d'une politique IAM dédiée.
4. Configuration de l'alias MinIO `harbor`.
5. Vérification des droits de lecture, écriture et suppression.
6. Vérification de l'isolation vis-à-vis des autres buckets.

### 4.3 Déploiement de la configuration S3

Commande exécutée :

```bash
helm upgrade harbor harbor/harbor \
  --namespace harbor \
  --version 1.19.4 \
  --reuse-values \
  --values ../kubernetes/harbor/harbor-s3-storage.yaml \
  --wait \
  --timeout 10m
```

Résultat : release `harbor` déployée, révision 3.

La configuration effective du Registry a été vérifiée : le provider S3 est actif.

### 4.4 Incident rencontré : cache Redis

Après le changement de backend, le premier push d'image n'a pas produit un manifeste récupérable.

Les observations ont montré :
- des réponses HTTP 200 aux vérifications HEAD de certains blobs ;
- des réponses HTTP 404 lors de la récupération du manifeste ;
- la présence de métadonnées de blobs dans Redis ;
- l'absence initiale des objets correspondants dans MinIO.

L'hypothèse retenue est celle d'entrées de cache Redis devenues incohérentes après le changement de backend de stockage.

Une suppression ciblée des clés de cache de blobs dans la DB Redis 2 a été effectuée.

**Point de vigilance :** ne pas utiliser `FLUSHDB` ou `FLUSHALL` pour résoudre ce type de problème. Le nettoyage doit être ciblé, précédé d'un diagnostic et limité aux clés concernées.

Après cette opération, les blobs ont été effectivement écrits dans MinIO et le pull a fonctionné.

## 5. Validation de la migration

### 5.1 Image de référence

Image concernée :

`developer-content-creator/repository-service`

Digest du manifeste :

```text
sha256:85fb9769566f4f3e031cf5fb9974f979d6602d1e70461de81add578104189324
```

Digest de configuration :

```text
sha256:2be1a0e16631ea52677728ca1b94f0f883cc86b7139b00045660c79d99fea136
```

L'image contient 35 layers et un objet de configuration.

### 5.2 Sauvegarde de l'image

L'archive Docker de référence :

`/home/mfo-dso/harbor-backups/repository-service-85fb9769.docker.tar`

Son chargement avec Podman a été vérifié. L'identifiant de l'image obtenu correspond à celui de l'image initiale.

Une archive OCI avait également été produite, mais son chargement a échoué lors de la vérification du digest. Elle ne doit donc pas être considérée comme la sauvegarde de référence.

### 5.3 Tag de migration

Tag de validation :

```text
192.168.1.40:30002/developer-content-creator/repository-service:migration-backup-85fb9769
```

Le tag a été poussé vers Harbor.

### 5.4 Tests réalisés

| Test | Résultat |
|---|---|
| Accès MinIO | Réussi |
| Écriture et lecture dans le bucket | Réussi |
| Isolation des buckets | Réussie |
| Activation du provider S3 | Réussie |
| Écriture des blobs dans MinIO | Réussie |
| Pull de l'image depuis Harbor | Réussi |
| Pull répété | Réussi |
| Redémarrage du pod Registry | Réussi |
| Pull après redémarrage du Registry | Réussi |
| Vérification de l'identifiant de l'image | Réussie |

La persistance du stockage a donc été validée après recréation du pod Registry.

## 6. Consignes d'exploitation

### 6.1 Vérifier le Registry

```bash
kubectl -n harbor get pods
kubectl -n harbor get deployment harbor-registry
kubectl -n harbor rollout status deployment/harbor-registry
```

### 6.2 Vérifier MinIO

```bash
curl -I http://192.168.1.40:9000/minio/health/live
```

Le résultat attendu est HTTP 200.

### 6.3 Vérifier les objets Harbor

Depuis le conteneur MinIO :

```bash
mc ls --recursive harbor/harbor-registry
```

Les objets du Registry doivent être présents sous :

```text
docker/registry/v2/blobs/
docker/registry/v2/repositories/
```

### 6.4 Vérifier la récupération d'une image

```bash
podman pull --tls-verify=false \
  192.168.1.40:30002/developer-content-creator/repository-service:migration-backup-85fb9769
```

La désactivation de la vérification TLS correspond ici à l'environnement HTTP local actuel. Elle ne doit pas être transposée telle quelle à un environnement de production HTTPS.

## 7. Retour arrière et précautions

Le retour arrière nécessite une attention particulière.

La configuration précédente utilisait un stockage filesystem éphémère. Le simple retour aux anciennes valeurs Helm ne restaure donc pas automatiquement les blobs.

Avant toute opération de rollback :

1. Préserver le bucket `harbor-registry`.
2. Préserver le dump PostgreSQL.
3. Préserver l'archive Docker de référence.
4. Vérifier la disponibilité des sauvegardes.
5. Déterminer une procédure cohérente de restauration du stockage et des métadonnées Harbor.

**Important :** ne pas supprimer le bucket MinIO, les sauvegardes ou le tag de migration tant que la stratégie de restauration n'a pas été testée.

## 8. Travaux restants

| Priorité | Action | Statut |
|---|---|---|
| Haute | Documenter la sauvegarde MinIO | À faire |
| Haute | Automatiser les sauvegardes PostgreSQL Harbor | À faire |
| Haute | Définir la restauration coordonnée MinIO/PostgreSQL | À faire |
| Haute | Tester une restauration dans un environnement isolé | À faire |
| Moyenne | Définir la rétention des sauvegardes | À faire |
| Moyenne | Automatiser le contrôle d'intégrité des sauvegardes | À faire |
| Moyenne | Documenter la rotation des identifiants S3 | À faire |
| Moyenne | Mettre en place une supervision de la capacité MinIO | À faire |

## 9. Critères de clôture

La migration technique est fonctionnelle.

La clôture opérationnelle complète nécessitera :

- une sauvegarde cohérente des objets MinIO ;
- une sauvegarde régulière de PostgreSQL Harbor ;
- une procédure de restauration documentée ;
- un test réel de restauration ;
- une politique de rétention et de supervision.

**Conclusion :** Harbor utilise désormais MinIO comme backend de stockage des images. La persistance a été validée après redémarrage du Registry. La prochaine étape est l'industrialisation de la sauvegarde et de la restauration.
