# Procédure de rollback Harbor

## 1. Objectif

Ce document définit la procédure de retour arrière de l'instance Harbor mutualisée.

L'objectif est de rétablir un état fonctionnel connu après :

- un échec de mise à jour de Harbor ;
- une mauvaise configuration Helm ;
- une régression du Registry ;
- une modification incorrecte de la configuration de stockage ;
- une corruption ou une incohérence des données ;
- une indisponibilité prolongée d'un composant critique.

La procédure distingue trois opérations :

1. **Rollback applicatif :** retour à une configuration ou à une version applicative précédente, sans restauration des données.
2. **Rétablissement de la configuration de stockage :** correction de la configuration Registry S3/MinIO sans restauration des objets.
3. **Restauration des données :** restauration coordonnée de PostgreSQL et MinIO à partir d'un point de sauvegarde cohérent.

Le rollback doit privilégier la préservation des données et la limitation de l'indisponibilité.

**État actuel :** Harbor utilise le backend S3/MinIO depuis la révision Helm 3. Les révisions Helm 1 et 2 utilisaient le backend filesystem et ne constituent pas des points de rollback directement utilisables.

## 2. Architecture concernée

| Composant | Déploiement | Élément de rollback |
|---|---|---|
| Harbor Core | Kubernetes / k0s | Version et configuration Helm |
| Harbor Registry | Kubernetes / k0s | Image et configuration Registry |
| Harbor Jobservice | Kubernetes / k0s | Version applicative |
| Harbor Portal | Kubernetes / k0s | Version applicative |
| Harbor Nginx | Kubernetes / k0s | Configuration d'exposition |
| PostgreSQL | Podman Compose | Dump de la base `harbor` |
| MinIO | Podman Compose | Sauvegarde du bucket `harbor-registry` |
| Redis | Kubernetes / k0s | StatefulSet et reconstruction du cache |
| Trivy | Kubernetes / k0s | StatefulSet et reconstruction ou actualisation de la base de vulnérabilités |
| Vault | Service externe | Secrets et politiques |
| External Secrets Operator | Kubernetes | Synchronisation des secrets |

### 2.1 Ressources identifiées

- Namespace Kubernetes : `harbor`
- Version Harbor : `2.15.4`
- Version du chart Helm : `1.19.4`
- Release Helm : `harbor`
- Deployment Registry : `harbor-registry`
- StatefulSet Redis : `harbor-redis`
- StatefulSet Trivy : `harbor-trivy`
- Base PostgreSQL : `harbor`
- Bucket MinIO : `harbor-registry`
- Volume MinIO : `docker_minio-data`
- Volume PostgreSQL : `docker_postgres-data`
- Endpoint MinIO : `http://192.168.1.40:9000`
- Endpoint Harbor : `http://192.168.1.40:30002`

PostgreSQL et MinIO sont hébergés en dehors du cluster Kubernetes.

Redis et Trivy sont déployés dans Kubernetes.

## 3. Principes et règles de sécurité

### 3.1 Principes fondamentaux

- Ne jamais supprimer les volumes PostgreSQL ou MinIO pendant un rollback.
- Ne jamais exécuter `podman compose down -v` sur les services hébergeant les données Harbor.
- Ne jamais écraser le bucket `harbor-registry` pendant un test.
- Ne jamais restaurer une sauvegarde PostgreSQL sans vérifier sa cohérence avec la sauvegarde MinIO correspondante.
- Ne jamais utiliser des identifiants administrateur dans les applications.
- Récupérer les secrets depuis Vault ou le mécanisme sécurisé prévu.
- Conserver les configurations et artefacts de la version précédente.
- Documenter chaque opération réalisée.
- Préserver les données MinIO tant qu'une migration ou une restauration n'a pas été validée.

### 3.2 Conditions d'arrêt

Interrompre la procédure si :

- le point de sauvegarde n'est pas identifié ;
- les sommes SHA-256 sont invalides ;
- les sauvegardes PostgreSQL et MinIO ne correspondent pas au même état ;
- l'espace disque est insuffisant ;
- l'accès aux secrets nécessaires est indisponible ;
- le diagnostic ne permet pas de déterminer le périmètre de la panne ;
- la configuration cible utilise un backend Registry incompatible avec le stockage existant.

En cas de doute sur la cohérence des données, ne pas relancer les écritures Harbor.

## 4. Classification des incidents

| Incident | Type de retour arrière | Restauration des données |
|---|---|---|
| Échec de mise à jour Helm | Applicatif | Non, si les données restent cohérentes |
| Mauvaise configuration Harbor | Applicatif | Non |
| Image Registry défectueuse | Applicatif | Non |
| Erreur de configuration S3 | Configuration de stockage | Non, sauf corruption avérée |
| Perte de métadonnées PostgreSQL | Restauration des données | Oui |
| Suppression ou corruption de blobs MinIO | Restauration des données | Oui |
| Incohérence PostgreSQL / MinIO | Restauration des données | Oui |
| Perte complète de l'infrastructure | Disaster recovery | Oui |

**Attention :** une erreur de connexion S3 ne signifie pas nécessairement que les objets MinIO sont corrompus. Il faut diagnostiquer la configuration, les permissions et la connectivité avant d'envisager une restauration.

## 5. Préparation du rollback

### 5.1 Déclarer l'incident

Avant toute intervention :

1. Identifier l'incident et son heure de début.
2. Identifier les composants affectés.
3. Évaluer les conséquences sur les opérations push/pull.
4. Identifier la dernière version fonctionnelle connue.
5. Déterminer si des écritures ont eu lieu depuis la dernière sauvegarde.
6. Définir le périmètre du rollback.
7. Déterminer si une interruption des écritures est nécessaire.

### 5.2 Collecter l'état initial

Vérifier les pods Harbor :

```bash
kubectl -n harbor get pods -o wide
```

Vérifier les déploiements :

```bash
kubectl -n harbor get deployments
```

Vérifier les StatefulSets :

```bash
kubectl -n harbor get statefulsets
```

Vérifier les ReplicaSets :

```bash
kubectl -n harbor get replicasets
```

Vérifier l'historique Helm :

```bash
helm -n harbor history harbor
```

Vérifier les conteneurs PostgreSQL et MinIO :

```bash
podman ps
```

Vérifier la disponibilité MinIO :

```bash
curl -fsS \
  http://192.168.1.40:9000/minio/health/ready
```

Les résultats doivent être conservés dans le dossier de suivi de l'incident.

### 5.3 Identifier le point de retour arrière

Pour un rollback applicatif :

- identifier la révision Helm précédente ;
- retrouver les valeurs Helm précédentes ;
- identifier les images utilisées ;
- vérifier que les images sont toujours disponibles dans Harbor ou dans un registre de secours ;
- vérifier la compatibilité du backend Registry de la révision cible avec le stockage réellement utilisé.

Pour un rollback des données :

- identifier le dump PostgreSQL ;
- identifier la sauvegarde MinIO correspondante ;
- vérifier les sommes SHA-256 ;
- vérifier la disponibilité des secrets et configurations ;
- confirmer la cohérence temporelle des sauvegardes.

Répertoire de sauvegarde :

```text
/home/mfo-dso/harbor-backups/<date>/
├── postgres/
├── minio/
├── configuration/
├── checksums/
└── metadata/
```

## 6. Scénario A – Rollback applicatif

### 6.1 Conditions

Ce scénario est adapté lorsque :

- Harbor ne démarre plus après une mise à jour ;
- une nouvelle configuration Helm provoque une régression ;
- un composant applicatif est défectueux ;
- les données PostgreSQL et MinIO restent cohérentes et accessibles.

Aucune restauration des données n'est nécessaire dans ce scénario.

### 6.2 Vérifier l'historique Helm

```bash
helm -n harbor history harbor
```

Identifier la dernière révision fonctionnelle.

Ne pas supposer que la révision immédiatement précédente est nécessairement saine.

Avant de sélectionner une révision, examiner sa configuration effective :

```bash
helm -n harbor get values harbor \
  --revision <REVISION_CIBLE> \
  --all -o yaml
```

Cette sortie doit être examinée de manière sécurisée et ne doit pas être publiée si elle contient des informations sensibles.

Vérifier également les images et les paramètres du Registry.

### 6.3 Effectuer le rollback Helm

**Attention :** ne jamais exécuter un rollback avant d'avoir vérifié la compatibilité de la configuration cible avec le backend de stockage Registry actuellement utilisé.

Après validation de la révision cible et autorisation de l'intervention :

```bash
helm -n harbor history harbor

helm -n harbor rollback harbor <REVISION_CIBLE> \
  --wait \
  --timeout 10m
```

Remplacer `<REVISION_CIBLE>` par la révision identifiée et validée pendant le diagnostic.

Le rollback Helm réapplique la configuration de la révision cible. Il ne restaure ni PostgreSQL ni les objets MinIO.

### 6.4 Protection du backend Registry MinIO

Depuis la révision Helm 3, Harbor utilise MinIO comme backend de stockage des images.

Configuration effective identifiée :

| Paramètre | Valeur |
|---|---|
| Révision Helm | 3 |
| Version du chart | `1.19.4` |
| Version Harbor | `2.15.4` |
| Backend Registry | `s3` |
| Bucket | `harbor-registry` |
| Endpoint | `http://192.168.1.40:9000` |
| Authentification | S3 v4 |
| Redirection | Désactivée |
| TLS S3 | Désactivé |
| PVC | Désactivés |

#### Historique des backends Registry

La comparaison des configurations effectives a établi :

| Paramètre | Révision 1 | Révision 2 | Révision 3 |
|---|---|---|---|
| Backend Registry | `filesystem` | `filesystem` | `s3` |
| Bucket MinIO | Non configuré | Non configuré | `harbor-registry` |
| Endpoint S3 | Non configuré | Non configuré | `http://192.168.1.40:9000` |
| Stockage attendu | Filesystem | Filesystem | MinIO |

**Un rollback direct de la révision 3 vers les révisions 1 ou 2 est interdit dans l'état actuel de l'infrastructure.**

Ces anciennes révisions ne configurent pas le backend S3 utilisé actuellement.

Leur application pourrait démarrer le Registry avec un backend filesystem alors que les blobs existants sont stockés dans MinIO.

Les objets MinIO ne seraient pas automatiquement supprimés, mais Harbor pourrait devenir incapable d'accéder aux images existantes.

Les révisions 1 et 2 ne constituent donc pas des points de rollback directement utilisables.

#### Vérifications obligatoires avant tout rollback Helm

1. Vérifier le backend Registry de la révision cible.
2. Vérifier le bucket et l'endpoint S3.
3. Vérifier les paramètres d'authentification S3.
4. Vérifier les références aux secrets Kubernetes.
5. Comparer la configuration cible avec la configuration actuellement opérationnelle.
6. Vérifier la compatibilité avec les données existantes.

Une révision ne peut être utilisée comme point de rollback que si son backend Registry est compatible avec le stockage réellement utilisé.

Si une ancienne révision ne contient pas la configuration S3 nécessaire, ne pas l'appliquer directement.

Pour revenir à une configuration applicative antérieure tout en conservant MinIO, il faut préparer et valider une configuration Helm explicite qui conserve le backend S3, puis effectuer une mise à jour contrôlée de la release.

Le rollback Helm ne restaure ni PostgreSQL ni les objets MinIO.

### 6.5 Vérifier les composants

Vérifier les Deployments :

```bash
kubectl -n harbor rollout status deployment/harbor-core
kubectl -n harbor rollout status deployment/harbor-registry
kubectl -n harbor rollout status deployment/harbor-jobservice
kubectl -n harbor rollout status deployment/harbor-portal
kubectl -n harbor rollout status deployment/harbor-nginx
```

Vérifier les StatefulSets :

```bash
kubectl -n harbor rollout status statefulset/harbor-redis
kubectl -n harbor rollout status statefulset/harbor-trivy
```

Vérifier ensuite l'état général :

```bash
kubectl -n harbor get pods
kubectl -n harbor get deployments
kubectl -n harbor get statefulsets
```

### 6.6 Vérifier le fonctionnement

Contrôler :

- l'accès à l'interface Harbor ;
- l'authentification ;
- l'accès aux projets ;
- la consultation des dépôts ;
- la consultation des tags ;
- les opérations pull ;
- les opérations push contrôlées.

Un rollback applicatif ne doit pas être considéré comme réussi uniquement parce que les pods sont `Running`.

## 7. Scénario B – Rétablissement de la configuration S3 / MinIO

### 7.1 Conditions

Ce scénario concerne notamment :

- une mauvaise URL S3 ;
- une erreur de configuration du bucket ;
- une mauvaise configuration du protocole ;
- un problème de permissions ;
- une modification incorrecte des paramètres Registry.

Avant toute restauration des objets, vérifier :

1. L'endpoint MinIO.
2. Le nom du bucket.
3. La connectivité réseau.
4. Les permissions du compte S3 utilisé par Harbor.
5. La configuration S3 du Registry.
6. Les logs du Registry.
7. La présence du Secret Kubernetes `harbor-registry-s3`.

### 7.2 Rétablir la configuration précédente

Restaurer une configuration Helm précédemment validée, en vérifiant impérativement qu'elle conserve le backend S3 compatible avec le stockage actuel.

Vérifier notamment :

- le nom du bucket `harbor-registry` ;
- l'endpoint MinIO ;
- le mode d'authentification S3 ;
- la configuration TLS ;
- les paramètres de redirection ;
- les références aux secrets Kubernetes.

Ne jamais réappliquer aveuglément une ancienne révision Helm si elle utilise un backend différent.

Ne jamais inscrire les clés S3 dans les fichiers de documentation ou les commandes visibles.

### 7.3 Redémarrer et contrôler le Registry

Après validation de la configuration :

```bash
kubectl -n harbor rollout restart deployment/harbor-registry

kubectl -n harbor rollout status deployment/harbor-registry
```

Vérifier les logs :

```bash
kubectl -n harbor logs deployment/harbor-registry \
  --tail=100
```

Si les objets sont toujours présents et accessibles, aucune restauration MinIO n'est nécessaire.

## 8. Scénario C – Restauration des données PostgreSQL et MinIO

### 8.1 Conditions

Ce scénario est réservé aux situations dans lesquelles les données sont perdues, corrompues ou incohérentes.

Il nécessite une restauration coordonnée de :

- la base PostgreSQL `harbor` ;
- le bucket MinIO `harbor-registry`.

La restauration doit utiliser un point de sauvegarde cohérent.

Consulter préalablement :

- `backup.md`
- `restore.md`

### 8.2 Mettre Harbor en maintenance

Avant de restaurer les données :

1. Informer les utilisateurs.
2. Suspendre les opérations push/pull.
3. Suspendre les traitements asynchrones susceptibles d'écrire dans les données.
4. Vérifier l'absence d'opérations en cours.
5. Empêcher le redémarrage automatique des composants applicatifs si nécessaire.

La méthode de mise en maintenance doit être adaptée à la configuration effective de Harbor.

Ne pas arrêter PostgreSQL ou MinIO avant d'avoir identifié les dépendances et les opérations en cours.

### 8.3 Préserver l'état actuel

Avant de remplacer des données :

- réaliser une sauvegarde de l'état actuel si celui-ci est encore exploitable ;
- conserver les fichiers de configuration actuels ;
- conserver les journaux ;
- noter les versions des composants ;
- identifier précisément le point de restauration retenu.

Ne jamais supprimer l'état actuel avant d'avoir validé la sauvegarde de retour arrière.

### 8.4 Restaurer PostgreSQL

La restauration de PostgreSQL doit suivre la procédure `restore.md`.

La base de production `harbor` ne doit être remplacée qu'après validation :

- du dump ;
- de sa date ;
- de sa cohérence avec MinIO ;
- des rôles et permissions nécessaires ;
- de la fenêtre de maintenance.

La restauration dans `harbor_restore_test` est recommandée avant toute opération de production.

### 8.5 Restaurer MinIO

La restauration MinIO doit suivre la procédure `restore.md`.

Le bucket cible de production est :

```text
harbor-registry
```

Le bucket de test :

```text
harbor-registry-restore-test
```

ne doit jamais être confondu avec le bucket de production.

Ne pas effectuer de synchronisation destructive ou de suppression d'objets sans validation explicite du plan de restauration.

### 8.6 Redémarrer les composants

Une fois PostgreSQL et MinIO restaurés et contrôlés :

1. Vérifier la disponibilité PostgreSQL.
2. Vérifier la disponibilité MinIO.
3. Vérifier l'accès au bucket Registry.
4. Vérifier les secrets Kubernetes.
5. Redémarrer ou réconcilier les composants Harbor.
6. Contrôler les logs.
7. Réaliser les tests fonctionnels.

## 9. Scénario D – Retour arrière après une migration d'infrastructure

Une migration de MinIO ou un changement d'infrastructure doit disposer d'un plan de retour arrière distinct.

Avant toute migration :

- conserver l'ancien service ;
- conserver son volume ;
- conserver sa configuration ;
- valider la sauvegarde ;
- valider la restauration sur une instance isolée ;
- documenter les endpoints et les dépendances.

En cas d'échec :

1. Suspendre les écritures Harbor.
2. Vérifier l'état du service cible.
3. Ne pas supprimer l'ancien volume.
4. Rétablir l'endpoint et la configuration précédents.
5. Vérifier l'accès aux objets.
6. Redémarrer le Registry si nécessaire.
7. Tester les opérations pull et push.

Le volume MinIO historique `docker_minio-data` doit être préservé tant que la migration n'est pas validée définitivement.

Aucune commande de suppression de volume ne doit être incluse dans la procédure de rollback.

## 10. Validation fonctionnelle

Après un rollback, exécuter les contrôles suivants :

| Contrôle | Résultat attendu |
|---|---|
| Pods Harbor | Disponibles |
| Harbor Core | Fonctionnel |
| Registry | Fonctionnel |
| Jobservice | Fonctionnel |
| PostgreSQL | Connexion opérationnelle |
| MinIO | Healthcheck opérationnel |
| Bucket `harbor-registry` | Accessible |
| Authentification | Fonctionnelle |
| Consultation des projets | Fonctionnelle |
| Consultation des dépôts | Fonctionnelle |
| Consultation des tags | Fonctionnelle |
| Pull d'une image de test | Réussi |
| Push d'une image de test | Réussi |
| Logs Registry | Pas d'erreur critique |

Pour les tests push/pull, utiliser un projet et une image de test dédiés.

Ne pas écraser une image métier existante.

## 11. Critères de réussite

Le rollback est considéré comme réussi lorsque :

- les composants Harbor sont disponibles ;
- les connexions PostgreSQL fonctionnent ;
- le Registry accède à MinIO ;
- les projets et dépôts attendus sont visibles ;
- les images existantes sont récupérables ;
- un push et un pull de test réussissent ;
- aucune erreur critique ne persiste dans les logs.

La clôture de l'incident doit être documentée.

## 12. Retour au service

Après validation :

1. Informer les utilisateurs de la reprise.
2. Réactiver les opérations d'écriture.
3. Réactiver les traitements suspendus.
4. Surveiller les logs Harbor.
5. Surveiller PostgreSQL et MinIO.
6. Vérifier les opérations push/pull.
7. Conserver les sauvegardes et journaux de l'incident.

Ne pas supprimer les sauvegardes utilisées pour le rollback.

## 13. Traçabilité de l'intervention

Chaque rollback doit faire l'objet d'un compte rendu contenant :

| Information | Description |
|---|---|
| Date et heure | Début et fin de l'intervention |
| Incident | Description du problème |
| Composants | Composants concernés |
| Version initiale | Version avant intervention |
| Version cible | Version restaurée |
| Révision Helm | Révision utilisée |
| Backend Registry | Backend avant et après intervention |
| Sauvegarde | Référence du point de restauration |
| Actions | Commandes et opérations réalisées |
| Résultat | Succès ou échec |
| Validation | Tests effectués |
| Responsable | Personne ayant validé l'intervention |

Les informations sensibles, notamment les mots de passe et clés d'accès, ne doivent jamais figurer dans le compte rendu.

## 14. Améliorations futures

Les évolutions suivantes pourront être intégrées :

- automatisation du rollback Helm ;
- sauvegarde automatique des valeurs Helm avant chaque mise à jour ;
- validation automatique des images et digests ;
- automatisation des contrôles de cohérence PostgreSQL / MinIO ;
- tests périodiques de restauration ;
- supervision des opérations de sauvegarde ;
- intégration des procédures dans les pipelines CI/CD ;
- gestion centralisée des secrets via Vault ;
- définition de RPO et RTO formels.

Toute automatisation devra être testée dans un environnement isolé avant son utilisation dans l'environnement opérationnel.

## 15. Documents associés

- `README.md` : documentation générale Harbor.
- `architecture.md` : architecture et dépendances.
- `backup.md` : procédure de sauvegarde.
- `restore.md` : procédure de restauration.
- `minio-migration.md` : procédure de migration MinIO.
- `troubleshooting.md` : diagnostic des incidents Harbor.