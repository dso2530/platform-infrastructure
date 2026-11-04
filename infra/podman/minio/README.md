# MinIO — Infrastructure mutualisée

## 1. Responsabilité

MinIO est un service de stockage objet mutualisé géré par le dépôt `platform-infrastructure`.

Les applications consomment ce service, mais ne gèrent pas son cycle de vie.

## 2. Configuration

Le service est déclaré dans :

`infra/podman/compose/minio-compose.yml`

Les identifiants sont fournis par un fichier `.env.minio` local, non versionné.

Le fichier `.env.example` sert uniquement de modèle.

## 3. Ressources persistantes

| Ressource | Nom |
|---|---|
| Conteneur | `minio` |
| Volume | `docker_minio-data` |
| Point de montage | `/data` |
| Réseau | `docker_default` |
| API S3 | Port 9000 |
| Console | Port 9001 |

Le volume existant est externe. Il ne doit jamais être supprimé lors d'une mise à jour du Compose.

## 4. Sécurité

- Ne jamais versionner les identifiants.
- Ne pas utiliser le compte root pour les applications.
- Créer un compte et une politique dédiés à chaque consommateur.
- Prévoir la rotation des identifiants.
- Prévoir l'intégration avec Vault.
- Limiter l'exposition réseau de la console et de l'API.

## 5. Buckets

Les buckets sont provisionnés selon les responsabilités applicatives.

Les initialisations propres à AI Public Benefits ne doivent pas être intégrées au cycle de vie du service MinIO mutualisé.

## 6. Exploitation

Toute modification du service doit préserver le volume externe `docker_minio-data`.

Aucune commande de suppression de volume ne doit être utilisée dans les procédures courantes.

Les opérations de sauvegarde et de restauration sont documentées dans `docs/operations/minio/`.