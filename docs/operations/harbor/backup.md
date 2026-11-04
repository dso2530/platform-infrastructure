# Procédure de sauvegarde Harbor

## 1. Objectif

Ce document définit la stratégie de sauvegarde de l'instance Harbor mutualisée.

L'objectif est de garantir la disponibilité et la récupérabilité :

- des métadonnées Harbor ;
- des images et artefacts stockés dans le Registry ;
- de la configuration nécessaire à la reconstruction de Harbor ;
- des éléments nécessaires à une restauration cohérente.

Harbor utilise actuellement MinIO comme backend de stockage des images.

Les sauvegardes doivent être réalisées indépendamment du cycle de vie des conteneurs et des pods.

## 2. Architecture concernée

| Composant | Déploiement | Données à sauvegarder |
|---|---|---|
| Harbor Core | Kubernetes / k0s | Configuration et métadonnées applicatives |
| Harbor Registry | Kubernetes / k0s | Configuration du Registry |
| Harbor Portal | Kubernetes / k0s | Configuration de déploiement |
| Harbor Jobservice | Kubernetes / k0s | Configuration de déploiement |
| PostgreSQL | Podman Compose | Base `harbor` |
| MinIO | Podman Compose | Bucket `harbor-registry` |
| Redis | Kubernetes / k0s | Cache reconstructible, non sauvegardé |
| Trivy | Kubernetes / k0s | Données reconstructibles selon la configuration |
| Helm | Hôte / Git | Valeurs et configuration de déploiement |
| Kubernetes | k0s | Ressources et configuration Harbor |
| Vault | Service externe | Secrets nécessaires à la restauration |

### 2.1 Ressources identifiées

**PostgreSQL**

- Conteneur : `postgres`
- Image : `postgres:17`
- Base Harbor : `harbor`
- Volume persistant : `docker_postgres-data`

**MinIO**

- Conteneur : `minio`
- Image : `quay.io/minio/minio:latest`
- Bucket : `harbor-registry`
- Volume persistant : `docker_minio-data`
- Réseau Compose : `docker_default`

**Harbor**

- Namespace Kubernetes : `harbor`
- Registry Deployment : `harbor-registry`
- Version Harbor : `2.15.4`
- Version du chart Helm : `1.19.4`
- Révision Helm actuellement déployée : `3`
- Backend de stockage : S3 / MinIO

**Redis et Trivy**

Redis et Trivy sont déployés dans Kubernetes, dans le namespace `harbor`. Ils ne font pas partie des dépendances externes Podman Compose.

Redis est considéré comme un composant de cache. Son contenu peut être reconstruit et n'est pas une source de vérité pour les images.

## 3. Stratégie de sauvegarde

La sauvegarde Harbor repose sur trois éléments essentiels :

1. PostgreSQL : métadonnées et configuration persistante.
2. MinIO : contenu des images et artefacts.
3. Configuration : éléments nécessaires à la reconstruction de l'instance.

Redis n'est pas considéré comme une source de données durable dans cette stratégie. Son contenu est principalement constitué de données de cache et de données temporaires.

La sauvegarde Redis pourra être ajoutée ultérieurement si des besoins spécifiques sont identifiés.

### 3.1 Cohérence des sauvegardes

Les données Harbor sont réparties entre PostgreSQL et MinIO.

Une sauvegarde isolée de ces deux composants peut produire un état incohérent si des opérations d'écriture sont en cours pendant leur exécution.

La stratégie cible repose donc sur une sauvegarde coordonnée en fenêtre de maintenance.

#### Procédure de sauvegarde cohérente

Les opérations doivent être exécutées dans l'ordre suivant :

1. Informer les utilisateurs de la fenêtre de maintenance.
2. Empêcher temporairement les nouvelles opérations d'écriture sur Harbor.
3. Attendre la fin des uploads et des opérations en cours.
4. Suspendre les traitements asynchrones susceptibles de modifier les données.
5. Réaliser le dump PostgreSQL de la base `harbor`.
6. Sauvegarder les objets du bucket MinIO `harbor-registry`.
7. Sauvegarder les configurations nécessaires à la reconstruction de Harbor.
8. Générer les sommes de contrôle SHA-256.
9. Vérifier l'intégrité des fichiers produits.
10. Réautoriser les opérations sur Harbor et reprendre les traitements suspendus.

#### Règles de cohérence

- PostgreSQL et MinIO doivent correspondre à une même période de référence.
- Aucune écriture ne doit intervenir pendant la phase de sauvegarde coordonnée.
- Les sauvegardes doivent être horodatées et regroupées dans un même répertoire.
- Les sauvegardes partielles doivent être identifiées comme telles et ne doivent pas être considérées comme un point de restauration valide.
- Redis est considéré comme un composant de cache : son contenu n'est pas une source de vérité et peut être reconstruit.
- Les identifiants nécessaires à la restauration doivent être récupérés depuis le mécanisme de gestion des secrets.

#### Évolution envisagée

Une automatisation pourra ultérieurement intégrer :

- la mise en maintenance de Harbor ;
- la vérification de l'absence d'opérations d'écriture ;
- la sauvegarde PostgreSQL ;
- la sauvegarde MinIO ;
- la validation des sauvegardes ;
- la reprise contrôlée des composants Harbor.

La procédure devra être validée par un test réel de restauration avant d'être considérée comme opérationnelle.

## 4. Organisation des sauvegardes

Répertoire de sauvegarde sur l'hôte :

```text
/home/mfo-dso/harbor-backups/
└── 2026-11-04/
    ├── postgres/
    │   └── harbor-115118.dump
    ├── minio/
    │   └── harbor-registry/
    └── SHA256SUMS
```

Chaque exécution doit disposer de son propre répertoire horodaté.

Les sauvegardes ne doivent pas être stockées exclusivement dans les volumes des conteneurs PostgreSQL ou MinIO.

Le répertoire de sauvegarde doit être protégé par des permissions restrictives.

Les fichiers de configuration peuvent être conservés dans un sous-répertoire `configuration/`, en veillant à ne jamais y inclure de secrets en clair.

## 5. Sauvegarde PostgreSQL

### 5.1 Périmètre

La base Harbor à sauvegarder est :

```text
harbor
```

Les autres bases présentes dans PostgreSQL appartiennent à différents services et ne sont pas incluses dans cette procédure.

### 5.2 Format de sauvegarde

Le format PostgreSQL recommandé est le format personnalisé (`custom`).

Il permet notamment :

- une restauration sélective ;
- une compression intégrée ;
- une inspection avec `pg_restore` ;
- une restauration indépendante du serveur source.

### 5.3 Commande de sauvegarde

Exemple de commande :

```bash
set -euo pipefail

BACKUP_DIR="/home/mfo-dso/harbor-backups/$(date +%F)"

install -d -m 700 "$BACKUP_DIR/postgres"

DUMP="$BACKUP_DIR/postgres/harbor-$(date +%H%M%S).dump"
TEMP_DUMP="${DUMP}.partial"

podman exec postgres \
  pg_dump -U postgres -d harbor -Fc \
  > "$TEMP_DUMP"

test -s "$TEMP_DUMP"

mv "$TEMP_DUMP" "$DUMP"

chmod 600 "$DUMP"
```

Le dump est écrit sur l'hôte et non dans le système de fichiers interne du conteneur.

Le fichier temporaire évite de considérer un dump interrompu comme une sauvegarde terminée.

### 5.4 Vérification

Vérifier que le fichier existe et qu'il n'est pas vide :

```bash
test -s "$DUMP"
```

Inspecter son contenu :

```bash
podman exec -i postgres \
  pg_restore -l < "$DUMP"
```

Une restauration réelle dans un environnement isolé reste nécessaire pour valider complètement le dump.

## 6. Sauvegarde MinIO

### 6.1 Périmètre

Le bucket Harbor à sauvegarder est :

```text
harbor-registry
```

Les autres buckets MinIO ne doivent pas être modifiés.

Le client `mc` est déjà présent dans le conteneur MinIO.

L'alias `harbor` est configuré dans ce conteneur et pointe vers le service MinIO local.

### 6.2 Principe

La sauvegarde MinIO est réalisée depuis un conteneur client temporaire utilisant le réseau Podman Compose `docker_default`.

Le répertoire de sauvegarde de l'hôte est monté dans ce conteneur afin que les objets copiés soient conservés indépendamment du cycle de vie de MinIO.

Répertoire cible :

```text
/home/mfo-dso/harbor-backups/<date>/minio/harbor-registry/
```

La procédure doit :

1. récupérer les identifiants MinIO depuis un mécanisme sécurisé ;
2. configurer un alias temporaire `harbor-backup` ;
3. vérifier l'accès au bucket `harbor-registry` ;
4. copier les objets vers le répertoire de sauvegarde ;
5. vérifier le résultat de la copie ;
6. supprimer le conteneur client temporaire.

La commande `mc mirror` sera utilisée sans l'option `--remove`, afin d'éviter la suppression d'objets dans la destination.

Exemple de direction de copie :

```text
MinIO / harbor-registry
          |
          v
Répertoire de sauvegarde local
```

La configuration des identifiants ne doit jamais être enregistrée dans Git, dans les arguments visibles des processus ou dans les journaux.

**Important :** le client MinIO doit être exécuté depuis une image dont la provenance et la version sont vérifiées. L'utilisation de `quay.io/minio/mc:latest` ou `docker.io/minio/mc:latest` n'est pas retenue, ces images n'ayant pas été accessibles lors des vérifications.

### 6.3 Contrôles

Après la copie :

- vérifier le nombre d'objets ;
- vérifier le volume total transféré ;
- contrôler les erreurs signalées par `mc` ;
- comparer les inventaires source et destination ;
- conserver les journaux de sauvegarde.

Une copie miroir seule ne garantit pas l'absence de corruption silencieuse. Des contrôles d'intégrité complémentaires sont nécessaires.

## 7. Sauvegarde de la configuration

La configuration Harbor est nécessaire à une reconstruction complète.

Les éléments à conserver comprennent :

- les fichiers de valeurs Helm ;
- la version exacte du chart ;
- la version Harbor ;
- la révision Helm ;
- les paramètres de stockage S3 ;
- les manifestes Kubernetes nécessaires ;
- les paramètres réseau et TLS ;
- les références aux secrets ;
- les informations de configuration des dépendances PostgreSQL et MinIO.

Le fichier de valeurs actuellement exporté est :

```text
infra/kubernetes/harbor/values/values-production.yaml
```

Il correspond à la configuration personnalisée de la révision Helm 3 et décrit notamment le backend S3/MinIO.

La configuration doit être conservée dans un emplacement protégé et intégrée au dispositif de sauvegarde.

Les secrets ne doivent jamais être enregistrés en clair dans Git ou dans les archives de sauvegarde non chiffrées.

Il faut privilégier la sauvegarde des références aux secrets et la conservation sécurisée des valeurs dans Vault.

### 7.1 Gestion des secrets

La gestion des identifiants du stockage MinIO suit une stratégie cible centralisée.

Vault constitue la source de vérité des identifiants et External Secrets Operator assure leur synchronisation vers Kubernetes.

Le Secret Kubernetes `harbor-registry-s3`, situé dans le namespace `harbor`, contient actuellement les clés :

- `REGISTRY_STORAGE_S3_ACCESSKEY`
- `REGISTRY_STORAGE_S3_SECRETKEY`

Son intégration avec External Secrets Operator reste à réaliser.

Les sauvegardes ne doivent jamais contenir les valeurs des secrets en clair.

La procédure de restauration devra prévoir :

1. la disponibilité de Vault ;
2. la configuration de l'authentification Kubernetes ;
3. le déploiement d'External Secrets Operator ;
4. la création de l'ExternalSecret Harbor ;
5. la synchronisation du Secret `harbor-registry-s3` ;
6. la vérification de l'accès de Harbor au stockage MinIO.

## 8. Contrôle d'intégrité SHA-256

Chaque sauvegarde doit être accompagnée d'un fichier de sommes de contrôle `SHA256SUMS`, placé à la racine du répertoire de sauvegarde.

Génération :

```bash
set -euo pipefail

cd "$BACKUP_DIR"

find . -type f \
  ! -name "SHA256SUMS" \
  -print0 |
  sort -z |
  xargs -0 sha256sum \
  > SHA256SUMS
```

Vérification :

```bash
cd "$BACKUP_DIR"
sha256sum -c SHA256SUMS
```

Les empreintes permettent de détecter les modifications accidentelles ou les corruptions des fichiers de sauvegarde.

Elles ne remplacent pas un test de restauration.

Le manifeste doit être conservé avec la sauvegarde et protégé contre les modifications non autorisées.

## 9. Rétention et sécurisation

La politique de rétention reste à définir.

Les recommandations suivantes constituent une base de travail :

| Type | Rétention proposée | Statut |
|---|---|---|
| Sauvegarde quotidienne | 7 jours | À valider |
| Sauvegarde hebdomadaire | 4 semaines | À valider |
| Sauvegarde mensuelle | 12 mois | À valider |

Les sauvegardes doivent :

- être protégées contre les accès non autorisés ;
- être chiffrées au repos ;
- être conservées hors des volumes sources ;
- disposer d'une copie indépendante du serveur ;
- faire l'objet de contrôles d'intégrité réguliers.

## 10. Automatisation

L'automatisation pourra être réalisée au moyen de scripts shell exécutés sur l'hôte.

Structure envisagée :

```text
scripts/
└── backup/
    ├── backup-harbor-postgres.sh
    ├── backup-harbor-minio.sh
    ├── backup-harbor-config.sh
    └── backup-harbor.sh
```

Le script principal devra :

1. créer un répertoire horodaté ;
2. vérifier les prérequis ;
3. contrôler l'état des composants ;
4. exécuter les sauvegardes ;
5. vérifier les fichiers générés ;
6. calculer les empreintes ;
7. produire un journal d'exécution ;
8. signaler toute erreur.

Une sauvegarde partiellement échouée ne doit jamais être déclarée réussie.

L'automatisation planifiée pourra ensuite être intégrée à des systemd timers.

## 11. Limites et points à valider

| Point | Statut |
|---|---|
| Dump PostgreSQL Harbor | Réalisé et vérifié |
| Copie du bucket MinIO | Réalisée et vérifiée |
| Restauration PostgreSQL isolée | Réussie |
| Restauration MinIO isolée | Réussie |
| Cohérence PostgreSQL / MinIO après restauration coordonnée | À tester |
| Sauvegarde des valeurs Helm | Export réalisée |
| Sauvegarde sécurisée des secrets | À formaliser |
| Chiffrement des archives | À mettre en place |
| Politique de rétention | À définir |
| Copie hors site | À définir |
| Automatisation | À développer |
| Test de restauration complet Harbor | À réaliser |

## 12. Critères de validation

La procédure de sauvegarde sera considérée comme opérationnelle lorsque :

- le dump PostgreSQL est généré et vérifié ;
- les objets du bucket `harbor-registry` sont sauvegardés ;
- la configuration nécessaire à la reconstruction est conservée ;
- les sommes de contrôle sont validées ;
- les sauvegardes sont protégées et externalisées ;
- une restauration complète a été testée dans un environnement isolé ;
- un pull d'image depuis Harbor est validé après cette restauration ;
- les journaux de sauvegarde sont conservés.

## 13. Première sauvegarde – 4 novembre 2026

Une première sauvegarde des composants PostgreSQL et MinIO a été réalisée le 4 novembre 2026.

Les deux copies constituent un premier jeu de sauvegarde. Elles n'ayant pas été réalisées exactement au même instant, elles ne doivent pas être considérées comme un point de restauration coordonné garanti.

### Résultats

| Composant | Résultat |
|---|---|
| PostgreSQL | Dump `harbor-115118.dump` créé |
| Format PostgreSQL | Custom (`pg_dump -Fc`) |
| Vérification PostgreSQL | `pg_restore -l` réussie |
| MinIO | Bucket `harbor-registry` sauvegardé |
| Volume MinIO | Environ 149 MiB |
| Nombre de fichiers | 74 |
| Vérification SHA-256 | Réussie |
| Manifeste | `SHA256SUMS` |

### Emplacement

```text
/home/mfo-dso/harbor-backups/2026-11-04/
├── postgres/
│   └── harbor-115118.dump
├── minio/
│   └── harbor-registry/
└── SHA256SUMS
```

### Résultats des tests de restauration ultérieurs

Les tests isolés réalisés après cette première sauvegarde ont donné les résultats suivants :

| Contrôle | Résultat |
|---|---|
| Restauration PostgreSQL dans `harbor_restore_test` | Réussie |
| Tables restaurées | 49 |
| Séquences restaurées | 47 |
| Restauration MinIO dans un bucket isolé | Réussie |
| Objets restaurés | 74 |
| Blobs vérifiés cryptographiquement | 37 |
| Erreurs de vérification des blobs | Aucune |

La restauration PostgreSQL isolée a été réalisée avec `--no-owner` et `--no-privileges`. Les propriétaires et privilèges d'origine ne sont donc pas validés par ce test.

Un pull de l'image de référence après redémarrage du Registry a également été validé séparément. Ce contrôle ne constitue pas une validation d'un pull après restauration complète.

### Limites restantes

Les étapes suivantes restent nécessaires :

- réaliser une restauration coordonnée de PostgreSQL et MinIO ;
- vérifier la cohérence entre les métadonnées et les blobs restaurés ;
- restaurer la configuration et les secrets nécessaires ;
- valider un pull d'image depuis Harbor après restauration complète ;
- formaliser une automatisation et une politique de rétention ;
- mettre en place une copie indépendante et chiffrée des sauvegardes.

**Statut : sauvegarde initiale réalisée, intégrité vérifiée et restaurations isolées validées. PRA complet encore à valider.**

### Conclusion

La stratégie de sauvegarde Harbor repose sur la conservation de PostgreSQL, des objets MinIO et de la configuration de déploiement.

Les tests isolés démontrent que les données sauvegardées peuvent être restaurées séparément. La validation définitive du PRA dépend encore d'une restauration coordonnée de ces composants et d'un test fonctionnel complet de Harbor.