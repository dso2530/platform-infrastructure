# Migration MinIO vers platform-infrastructure

## 1. Objectif

Ce document décrit la migration de la gestion du service MinIO depuis le dépôt `ai-public-benefits-platform` vers `platform-infrastructure`.

La migration concerne uniquement le service MinIO mutualisé.

Elle ne concerne pas les autres composants de l'ancienne stack Compose : PostgreSQL, Redis, Kafka, Keycloak, Prometheus, Grafana, etc.

## 2. État initial

| Élément | Situation actuelle |
|---|---|
| Hôte | `192.168.XX.XX` |
| Runtime | Podman |
| Conteneur | `minio` |
| Image | `quay.io/minio/minio` |
| API S3 | `9000` |
| Console | `9001` |
| Volume | `docker_minio-data` |
| Montage | `/data` |
| Réseau | `docker_default` |
| Bucket Harbor | `harbor-registry` |
| Consommateur principal à préserver | Harbor Registry |

Le conteneur existant utilise un volume et un réseau Podman déjà créés.

**La migration doit réutiliser ces ressources. Elle ne doit pas créer un nouveau stockage MinIO.**

## 3. État cible

Le fichier Compose centralisé est :

`infra/podman/compose/minio-compose.yml`

Les variables d'environnement sont fournies par :

`infra/podman/compose/.env.minio`

Ce dernier fichier reste local et ne doit jamais être versionné.

Le nouveau Compose référence explicitement :

- Le volume externe `docker_minio-data`.
- Le réseau externe `docker_default`.
- L'image MinIO figée par digest.
- Les ports 9000 et 9001.

## 4. Principes de sécurité

Les règles suivantes sont obligatoires :

1. Ne jamais supprimer le volume `docker_minio-data`.
2. Ne jamais utiliser `podman compose down -v`.
3. Ne jamais lancer une migration sans sauvegarde vérifiée.
4. Ne jamais afficher les identifiants dans les journaux ou le terminal.
5. Ne pas réutiliser le compte root MinIO pour les applications.
6. Ne pas supprimer l'ancien fichier Compose avant validation.
7. Ne pas lancer simultanément deux instances MinIO sur le même volume.

Les identifiants précédemment exposés doivent être considérés comme compromis et faire l'objet d'une rotation planifiée.

## 5. Phase 1 — Préparation

### 5.1 Vérifier le dépôt

Depuis le dépôt `platform-infrastructure` :

```bash
cd ~/projects/platform-infrastructure

git status --short
```

Vérifier que les fichiers nécessaires existent :

```bash
test -s infra/podman/compose/minio-compose.yml
test -s infra/podman/compose/.env.example
test -s infra/podman/compose/.env.minio

echo "Fichiers MinIO présents."
```

### 5.2 Vérifier les permissions du fichier de configuration

```bash
stat -c '%a %n' infra/podman/compose/.env.minio
```

Les permissions doivent être restrictives. Si nécessaire :

```bash
chmod 600 infra/podman/compose/.env.minio
```

Ne jamais afficher son contenu.

### 5.3 Valider le Compose

```bash
cd ~/projects/platform-infrastructure/infra/podman/compose

docker compose \
  --env-file .env.minio \
  -f minio-compose.yml \
  config -q

echo "Configuration Compose validée."
```

Cette validation ne doit produire aucune erreur.

### 5.4 Vérifier l'image

```bash
podman image exists \
  quay.io/minio/minio@sha256:a1a8bd4ac40ad7881a245bab97323e18f971e4d4cba2c2007ec1bedd21cbaba2

echo "Image MinIO disponible."
```

### 5.5 Vérifier les ressources persistantes

```bash
podman volume exists docker_minio-data
podman network exists docker_default

echo "Volume et réseau disponibles."
```

Contrôler également le montage du conteneur existant :

```bash
podman inspect minio \
  --format '{{range .Mounts}}{{println .Name .Destination}}{{end}}'
```

Le volume `docker_minio-data` doit être monté sur `/data`.

Vérifier son existence et son état :

```bash
podman volume inspect docker_minio-data
```

### 5.6 Vérifier l'état du conteneur

```bash
podman ps --filter name=minio
```

Ne pas poursuivre si le conteneur existant est déjà en erreur ou si le volume attendu n'est pas identifié.

## 6. Phase 2 — Sauvegarde préalable

Une sauvegarde récente et vérifiée doit être disponible avant toute interruption.

Pour Harbor, la sauvegarde doit couvrir :

- La base PostgreSQL Harbor.
- Les objets du bucket `harbor-registry`.
- Les configurations nécessaires à la reconstruction.
- Les éléments nécessaires à la récupération des identifiants.

Les sauvegardes PostgreSQL et MinIO doivent correspondre à une même fenêtre de maintenance.

Procédure de référence :

`docs/operations/harbor/backup.md`

La migration ne doit commencer qu'après validation des sommes SHA-256 et vérification du dump PostgreSQL.

Une sauvegarde ancienne ou réalisée à des instants différents ne doit pas être considérée comme une sauvegarde cohérente de Harbor.

## 7. Phase 3 — Préparation de la bascule

### 7.1 Organiser une fenêtre de maintenance

Avant la bascule :

- Prévenir les utilisateurs et consommateurs concernés.
- Suspendre les opérations d'écriture vers Harbor.
- Attendre la fin des uploads en cours.
- Suspendre les opérations automatisées susceptibles d'écrire dans MinIO.
- Vérifier que les sauvegardes sont disponibles.
- Préparer les commandes de retour arrière.

La durée d'interruption dépendra notamment du démarrage de MinIO et de la validation de Harbor.

### 7.2 Vérifier les identifiants

Le fichier `.env.minio` doit contenir des identifiants valides correspondant à la configuration administrative prévue pour le nouveau conteneur.

Ne pas remplacer les identifiants fonctionnels par des valeurs temporaires telles que `CHANGE_ME`.

Ne pas copier des identifiants exposés précédemment dans ce document ou dans un autre fichier.

Si les identifiants ne sont pas disponibles ou si leur validité n'est pas établie, interrompre la procédure.

## 8. Phase 4 — Bascule du conteneur

Cette phase entraîne une interruption temporaire de MinIO.

### 8.1 Arrêter l'ancien conteneur

```bash
podman stop minio
```

Vérifier son arrêt :

```bash
podman ps --filter name=minio
```

### 8.2 Retirer uniquement l'ancien conteneur

Après confirmation de l'arrêt :

```bash
podman rm minio
```

Cette commande retire le conteneur, pas le volume externe.

**Ne jamais ajouter `-v` à cette commande.**

Le volume `docker_minio-data` doit rester intact.

### 8.3 Démarrer MinIO avec le nouveau Compose

```bash
cd ~/projects/platform-infrastructure/infra/podman/compose

podman compose \
  --env-file .env.minio \
  -f minio-compose.yml \
  up -d
```

### 8.4 Vérifier le démarrage

```bash
podman ps --filter name=minio
```

Consulter les journaux :

```bash
podman logs --tail 100 minio
```

Ne pas partager de journaux contenant des identifiants ou des informations sensibles.

Vérifier que le conteneur utilise toujours le volume attendu :

```bash
podman inspect minio \
  --format '{{range .Mounts}}{{println .Name .Destination}}{{end}}'
```

Le résultat doit confirmer le montage de `docker_minio-data` sur `/data`.

## 9. Phase 5 — Tests fonctionnels

### 9.1 Vérifier le service MinIO

Tester le endpoint de disponibilité :

```bash
curl -fsS \
  http://127.0.0.1:9000/minio/health/live
```

Tester également la disponibilité :

```bash
curl -fsS \
  http://127.0.0.1:9000/minio/health/ready
```

### 9.2 Vérifier le bucket Harbor

Le bucket `harbor-registry` doit toujours être présent et ses objets doivent être accessibles avec les autorisations appropriées.

Ne pas effectuer de suppression ou de modification des objets pendant cette vérification.

### 9.3 Vérifier Harbor Registry

Contrôler l'état des composants :

```bash
kubectl -n harbor get pods
```

Vérifier les journaux du Registry :

```bash
kubectl -n harbor logs deployment/harbor-registry --tail=100
```

Contrôler ensuite les opérations suivantes depuis Harbor :

- Accès à l'interface.
- Consultation des projets et dépôts.
- Consultation des artefacts existants.
- Pull d'une image existante.
- Push d'une image de test.
- Pull de l'image de test.

Le test doit confirmer que Harbor utilise toujours le bucket MinIO existant.

### 9.4 Critères de validation

La migration est considérée comme validée lorsque :

| Contrôle | Résultat attendu |
|---|---|
| Conteneur MinIO | Running |
| Healthcheck | Healthy |
| API S3 | Accessible |
| Volume | `docker_minio-data` |
| Réseau | `docker_default` |
| Bucket Harbor | Accessible |
| Interface Harbor | Fonctionnelle |
| Pull d'image | Réussi |
| Push d'image | Réussi |
| Journaux Registry | Pas d'erreur de stockage |

## 10. Phase 6 — Retour arrière

Le retour arrière doit être possible sans restaurer les données si le volume existant est intact.

### 10.1 Conditions

Déclencher un retour arrière en cas de :

- Échec du démarrage MinIO.
- Perte d'accès au bucket Harbor.
- Erreurs persistantes de stockage S3.
- Échec des tests de lecture ou d'écriture.
- Comportement anormal du Registry.

### 10.2 Procédure

1. Suspendre les écritures vers Harbor.
2. Arrêter le nouveau conteneur MinIO.
3. Retirer uniquement le conteneur, sans supprimer le volume.
4. Recréer le conteneur avec la configuration précédente, préalablement sécurisée et validée.
5. Réutiliser le volume `docker_minio-data`.
6. Vérifier l'accès S3.
7. Vérifier Harbor et ses opérations de lecture.

Exemple de retrait du nouveau conteneur :

```bash
podman stop minio
podman rm minio
```

La recréation de l'ancien conteneur nécessite une définition Compose de secours et des identifiants valides.

**Important :** ne pas exécuter directement l'ancien Compose s'il contient des identifiants en clair ou une configuration non vérifiée. Préparer et valider cette configuration de secours avant la fenêtre de migration.

Si les objets ou les métadonnées ont été modifiés ou endommagés, le retour arrière par simple recréation du conteneur ne suffit pas. Une restauration coordonnée de Harbor peut alors être nécessaire.

Procédure de référence :

`docs/operations/harbor/restore.md`

## 11. Phase 7 — Nettoyage après validation

Après validation complète :

- Conserver une copie sécurisée de la configuration de secours.
- Conserver les sauvegardes.
- Documenter la date et les résultats de migration.
- Préparer la rotation des identifiants compromis.
- Préparer l'intégration Vault.
- Vérifier que les applications consommatrices utilisent les identifiants dédiés.

L'ancien fichier Compose ne doit être retiré du dépôt applicatif qu'après validation de la migration et vérification qu'aucun autre service ne dépend encore de ce fichier.

Ne pas supprimer les autres fichiers ou ressources de l'ancienne stack Compose dans le cadre de cette migration.

## 12. État de la migration

| Étape | État |
|---|---|
| Nouveau dépôt créé | Terminé |
| Structure MinIO créée | Terminé |
| Compose centralisé | Préparé |
| Image figée par digest | Validée |
| Volume externe identifié | Validé |
| Réseau externe identifié | Validé |
| Configuration Compose | Validée |
| Sauvegarde Harbor | Réalisée |
| Vérification PostgreSQL | Réalisée |
| Restauration MinIO isolée | En attente |
| Configuration de secours | À préparer |
| Bascule MinIO | En attente |
| Tests Harbor après bascule | En attente |
| Rotation des identifiants | En attente |

## 13. Règle finale

Aucune bascule ne doit être réalisée tant que les prérequis, la sauvegarde cohérente, les identifiants valides et le retour arrière ne sont pas vérifiés.

La priorité absolue est la conservation des données existantes et la continuité du service Harbor.