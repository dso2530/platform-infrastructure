# Harbor — Guide de diagnostic et de résolution des incidents

**Projet :** Platform Infrastructure  
**Date :** 4 novembre 2026  
**Statut :** Guide de diagnostic documenté — procédures à valider en conditions opérationnelles  
**Environnement :** Kubernetes / k0s local  
**Namespace :** `harbor`  
**Version Harbor :** `2.15.4`  
**Chart Helm :** `harbor-1.19.4`  
**Révision Helm de référence :** `3`

---

## 1. Objectif

Ce document décrit les procédures de diagnostic et les actions de résolution des incidents susceptibles d'affecter Harbor.

Il couvre les composants suivants :

- Harbor Core ;
- Harbor Registry ;
- Harbor Portal ;
- Harbor Jobservice ;
- Redis ;
- Trivy ;
- PostgreSQL ;
- MinIO ;
- Kubernetes et Helm ;
- les Secrets Kubernetes ;
- les dépendances Vault et External Secrets Operator ;
- l'intégration GitOps avec ArgoCD.

L'objectif est de privilégier les diagnostics non destructifs, de préserver les données et de limiter les interruptions de service.

### 1.1 Règles d'intervention

Avant toute intervention :

1. Identifier le composant concerné.
2. Collecter les événements Kubernetes et les journaux utiles.
3. Vérifier l'état des dépendances externes.
4. Identifier les éventuelles opérations en cours.
5. Vérifier la disponibilité et l'intégrité des sauvegardes.
6. Évaluer l'impact d'une éventuelle modification.
7. Définir une procédure de retour arrière avant toute modification risquée.

**Ne jamais supprimer un volume, un bucket ou une base de données pour résoudre un incident sans procédure de restauration validée.**

Ne pas afficher ni transmettre les valeurs des Secrets Kubernetes, les mots de passe ou les clés d'accès.

Les commandes présentées dans ce document sont principalement des commandes de diagnostic. Les actions correctives doivent être adaptées à la cause identifiée.

---

## 2. Vue d'ensemble des composants

### 2.1 Répartition des composants

| Composant | Hébergement | Ressource |
|---|---|---|
| Harbor Core | Kubernetes | Deployment |
| Harbor Registry | Kubernetes | Deployment |
| Harbor Portal | Kubernetes | Deployment |
| Harbor Jobservice | Kubernetes | Deployment |
| Redis | Kubernetes | StatefulSet |
| Trivy | Kubernetes | StatefulSet |
| PostgreSQL | Podman | Service externe |
| MinIO | Podman | Service externe |

Redis et Trivy font partie du périmètre Kubernetes de Harbor. PostgreSQL et MinIO sont hébergés séparément sous Podman.

### 2.2 Endpoints de référence

| Service | Endpoint |
|---|---|
| PostgreSQL | `192.168.1.40:5432` |
| MinIO | `http://192.168.1.40:9000` |
| Harbor HTTP | `http://192.168.1.40:30002` |
| Harbor HTTPS | NodePort `30003` — TLS actuellement désactivé |

**Attention :** Harbor utilise actuellement HTTP dans l'environnement local. Ne pas considérer cette configuration comme adaptée à une exposition externe.

---

## 3. Diagnostic initial Kubernetes

### 3.1 Vérifier les pods

```bash
kubectl -n harbor get pods -o wide
```

Identifier les pods :

- en `Pending` ;
- en `CrashLoopBackOff` ;
- en `ImagePullBackOff` ;
- en `Error` ;
- avec un nombre inhabituel de redémarrages ;
- dont les conteneurs ne sont pas tous prêts.

Un pod en état `Running` n'implique pas nécessairement que l'application fonctionne correctement. Vérifier également les probes et les journaux.

### 3.2 Vérifier les Deployments

```bash
kubectl -n harbor get deployments
```

Vérifier que :

- le nombre de réplicas désirés correspond au nombre de réplicas disponibles ;
- les pods sont prêts ;
- aucun rollout n'est bloqué.

Pour examiner les conditions d'un Deployment :

```bash
kubectl -n harbor describe deployment <deployment-name>
```

### 3.3 Vérifier les StatefulSets

```bash
kubectl -n harbor get statefulsets
```

Les StatefulSets concernés sont :

```text
harbor-redis
harbor-trivy
```

Vérifier notamment :

- le nombre de réplicas désirés ;
- le nombre de réplicas prêts ;
- l'état des pods associés ;
- les éventuels problèmes de stockage.

### 3.4 Consulter les événements

```bash
kubectl -n harbor get events \
  --sort-by='.lastTimestamp'
```

Les événements permettent notamment d'identifier :

- les problèmes de scheduling ;
- les erreurs de montage ;
- les échecs de téléchargement d'images ;
- les problèmes de probes ;
- les erreurs de configuration ;
- les problèmes de ressources.

### 3.5 Examiner un pod

```bash
kubectl -n harbor describe pod <pod-name>
```

Consulter les journaux :

```bash
kubectl -n harbor logs <pod-name> \
  --since=30m
```

Pour un conteneur particulier :

```bash
kubectl -n harbor logs <pod-name> \
  -c <container-name> \
  --since=30m
```

Pour un conteneur précédent après un redémarrage :

```bash
kubectl -n harbor logs <pod-name> \
  --previous
```

Cette dernière commande permet d'examiner les journaux du conteneur précédent, lorsqu'ils sont encore disponibles.

Avant de partager les journaux, vérifier qu'ils ne contiennent pas de données sensibles.

### 3.6 Examiner les redémarrages

```bash
kubectl -n harbor get pods \
  -o custom-columns='NAME:.metadata.name,STATUS:.status.phase,RESTARTS:.status.containerStatuses[*].restartCount'
```

Pour identifier les raisons des redémarrages :

```bash
kubectl -n harbor describe pod <pod-name>
```

Examiner notamment :

- `Last State` ;
- `Reason` ;
- `Exit Code` ;
- les événements associés ;
- les journaux précédents.

Un compteur de redémarrages non nul ne démontre pas, à lui seul, une panne actuelle.

---

## 4. Incidents Harbor Core

### 4.1 Symptômes

- Interface Harbor inaccessible ;
- erreurs HTTP 500 ;
- erreurs d'authentification ;
- impossibilité de consulter les projets ;
- erreurs de connexion à PostgreSQL ou Redis.

### 4.2 Diagnostic

Identifier le pod :

```bash
kubectl -n harbor get pods \
  -l component=core
```

Consulter les journaux :

```bash
kubectl -n harbor logs deployment/harbor-core \
  --since=30m
```

Vérifier le Deployment :

```bash
kubectl -n harbor describe deployment harbor-core
```

Vérifier les dépendances :

- PostgreSQL ;
- Redis ;
- Secrets Kubernetes ;
- connectivité réseau ;
- disponibilité des autres composants Harbor.

### 4.3 Actions de résolution

En fonction du diagnostic :

- corriger une dépendance indisponible ;
- vérifier les paramètres de connexion ;
- vérifier les références aux Secrets ;
- examiner les erreurs applicatives avant tout redémarrage ;
- vérifier les probes et les ressources disponibles.

Ne pas supprimer ou recréer la base PostgreSQL pour résoudre une erreur applicative.

---

## 5. Incidents Harbor Registry

### 5.1 Symptômes

- échec de push ;
- échec de pull ;
- erreur HTTP 500 ;
- erreurs d'accès au stockage ;
- blobs introuvables ;
- erreurs S3 ;
- erreurs de connexion à MinIO.

### 5.2 Diagnostic

Identifier les pods :

```bash
kubectl -n harbor get pods \
  -l component=registry
```

Consulter les journaux :

```bash
kubectl -n harbor logs deployment/harbor-registry \
  --since=30m
```

Examiner le Deployment :

```bash
kubectl -n harbor describe deployment harbor-registry
```

Vérifier la configuration Helm :

```bash
helm -n harbor get values harbor \
  --revision 3
```

La configuration attendue repose sur un backend S3 :

```yaml
persistence:
  enabled: false
  imageChartStorage:
    type: s3
    s3:
      bucket: harbor-registry
      existingSecret: harbor-registry-s3
```

Ne pas partager une sortie de configuration sans avoir vérifié qu'elle ne contient aucun secret.

### 5.3 Actions de résolution

Vérifier :

1. La disponibilité de MinIO.
2. L'existence du bucket `harbor-registry`.
3. La connectivité réseau entre Registry et MinIO.
4. La présence du Secret `harbor-registry-s3`.
5. Les droits d'accès au bucket.
6. Les journaux du Registry.
7. La configuration S3 active dans Helm.

Ne pas supprimer les blobs ou modifier manuellement leur structure.

**Important :** les métadonnées PostgreSQL et les blobs MinIO doivent rester cohérents. Une restauration partielle ne doit pas être considérée comme une reprise complète de Harbor.

---

## 6. Incidents Redis

### 6.1 Symptômes

- erreurs de connexion Redis ;
- erreurs dans Harbor Core ;
- problèmes de traitement des tâches ;
- indisponibilité temporaire de certaines fonctionnalités ;
- redémarrages répétés du pod Redis.

### 6.2 Diagnostic

Vérifier le StatefulSet :

```bash
kubectl -n harbor get statefulsets
```

Identifier le pod Redis :

```bash
kubectl -n harbor get pods \
  -l component=redis
```

Examiner les événements :

```bash
kubectl -n harbor describe statefulset harbor-redis
```

Consulter les journaux :

```bash
kubectl -n harbor logs statefulset/harbor-redis \
  --since=30m
```

Examiner les redémarrages du pod :

```bash
kubectl -n harbor describe pod <redis-pod-name>
```

### 6.3 Actions de résolution

Vérifier :

- l'état du pod ;
- les redémarrages ;
- la mémoire disponible ;
- les erreurs de connexion ;
- la connectivité depuis les composants Harbor ;
- les erreurs de persistance éventuelles.

Redis est utilisé par Harbor pour des fonctions de cache et de traitement.

**Précaution importante :**

Ne pas exécuter les commandes suivantes comme procédure de dépannage :

```text
FLUSHDB
FLUSHALL
```

Une suppression globale des données Redis peut perturber le fonctionnement de Harbor.

Toute suppression ciblée doit être précédée d'une identification précise des clés concernées et d'une évaluation de leur usage.

Une sauvegarde RDB réussie est un indicateur positif de persistance, mais ne remplace pas les sauvegardes PostgreSQL et MinIO.

---

## 7. Incidents Trivy

### 7.1 Symptômes

- analyses de vulnérabilités indisponibles ;
- erreurs de scan ;
- base de vulnérabilités obsolète ;
- erreurs de téléchargement de la base ;
- redémarrages répétés du pod Trivy.

### 7.2 Diagnostic

Vérifier le StatefulSet :

```bash
kubectl -n harbor get statefulsets
```

Identifier le pod :

```bash
kubectl -n harbor get pods \
  -l component=trivy
```

Consulter les journaux :

```bash
kubectl -n harbor logs statefulset/harbor-trivy \
  --since=30m
```

Examiner les événements :

```bash
kubectl -n harbor describe statefulset harbor-trivy
```

Examiner le pod :

```bash
kubectl -n harbor describe pod harbor-trivy-0
```

En cas de redémarrage :

```bash
kubectl -n harbor logs harbor-trivy-0 \
  --previous
```

### 7.3 Actions de résolution

Vérifier :

- la disponibilité du pod ;
- les ressources disponibles ;
- l'accès réseau aux sources de vulnérabilités ;
- les erreurs de téléchargement ;
- l'état de la base de vulnérabilités ;
- les raisons des redémarrages.

Une indisponibilité de Trivy ne signifie pas que les blobs du Registry sont perdus.

Ne pas supprimer les données persistantes de Trivy sans avoir identifié précisément les conséquences.

### 7.4 État observé le 4 novembre 2026

Le pod `harbor-trivy-0` a été observé dans l'état suivant :

| Indicateur | Valeur |
|---|---|
| Pod | `harbor-trivy-0` |
| Disponibilité | `1/1` |
| État | `Running` |
| Redémarrages | 4 |
| Dernier redémarrage observé | Environ 2 jours et 2 heures auparavant |
| Ancienneté | 7 jours |

Les journaux consultés sur les cinq dernières minutes ne présentaient aucune sortie.

**Interprétation :** Trivy était opérationnel au moment du contrôle. La cause des quatre redémarrages historiques reste à examiner. Ce compteur ne justifie pas, à lui seul, un redémarrage manuel.

---

## 8. Incidents PostgreSQL

### 8.1 Symptômes

- Harbor Core ne démarre pas ;
- erreurs de connexion à la base ;
- erreurs SQL ;
- impossibilité de consulter les projets ;
- erreurs liées aux métadonnées.

### 8.2 Diagnostic

PostgreSQL est hébergé hors Kubernetes, sous Podman.

Sur l'hôte :

```bash
podman ps
```

Vérifier les conteneurs :

```bash
podman ps --format \
  "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

Consulter les journaux du conteneur PostgreSQL identifié :

```bash
podman logs <postgres-container> \
  --since=30m
```

Tester la connectivité TCP :

```bash
nc -vz 192.168.1.40 5432
```

### 8.3 Vérifications PostgreSQL

Les paramètres de référence sont :

| Paramètre | Valeur |
|---|---|
| Hôte | `192.168.1.40` |
| Port | `5432` |
| Base | `harbor` |
| Utilisateur | `harbor` |
| Secret Kubernetes | `harbor-db` |

Vérifier la disponibilité de la base sans afficher de mot de passe :

```bash
pg_isready \
  -h 192.168.1.40 \
  -p 5432 \
  -d harbor
```

Un résultat positif confirme que PostgreSQL accepte les connexions. Il ne garantit pas à lui seul que les identifiants applicatifs ou les permissions sont corrects.

### 8.4 Actions de résolution

Vérifier :

- l'état du conteneur PostgreSQL ;
- la disponibilité du port ;
- les journaux PostgreSQL ;
- les connexions autorisées ;
- l'espace disque ;
- la disponibilité de la base `harbor` ;
- les références au Secret `harbor-db`.

Ne jamais supprimer ou réinitialiser la base en réponse à une erreur de connexion.

Avant toute intervention sur les données, vérifier l'existence d'un dump PostgreSQL exploitable.

---

## 9. Incidents MinIO / stockage S3

### 9.1 Symptômes

- échec de push ou pull ;
- erreurs S3 ;
- erreurs `AccessDenied` ;
- erreurs de connexion ;
- blobs introuvables ;
- erreurs de redirection Registry.

### 9.2 Diagnostic MinIO

MinIO est hébergé sous Podman.

```bash
podman ps
```

Vérifier le service :

```bash
nc -vz 192.168.1.40 9000
```

Consulter les journaux du conteneur MinIO identifié :

```bash
podman logs <minio-container> \
  --since=30m
```

Vérifier également l'état du projet Compose :

```bash
podman compose ps
```

Cette dernière commande doit être exécutée depuis le répertoire contenant le fichier Compose concerné.

### 9.3 Paramètres S3 de référence

| Paramètre | Valeur |
|---|---|
| Endpoint | `http://192.168.1.40:9000` |
| Bucket | `harbor-registry` |
| Région | `us-east-1` |
| Secret Kubernetes | `harbor-registry-s3` |
| Signature | S3 V4 |
| Redirection | Désactivée |

### 9.4 Vérification du Secret

Vérifier uniquement l'existence du Secret :

```bash
kubectl -n harbor get secret harbor-registry-s3
```

Ne pas utiliser :

```bash
kubectl get secret harbor-registry-s3 -o yaml
```

pour partager le résultat : cette sortie expose des valeurs encodées qu'il ne faut pas divulguer.

### 9.5 Actions de résolution

Vérifier :

1. L'état du conteneur MinIO.
2. La disponibilité du port 9000.
3. L'existence du bucket.
4. Les permissions du compte S3.
5. La connectivité réseau depuis Kubernetes.
6. La correspondance entre les identifiants MinIO et le Secret Kubernetes.
7. Les erreurs S3 dans les journaux Registry.

Ne pas recréer le bucket et ne pas supprimer les objets pour tenter de corriger une erreur d'accès.

**Attention :** un test de connectivité TCP réussi ne garantit pas que l'authentification S3 et les autorisations sur le bucket fonctionnent.

---

## 10. Incidents d'authentification et de Secrets

### 10.1 Symptômes

- erreurs d'authentification ;
- échec de connexion PostgreSQL ;
- erreurs S3 ;
- pods ne démarrant pas ;
- Secret introuvable ;
- erreur de référence à un Secret.

### 10.2 Diagnostic

Lister les Secrets sans afficher leurs valeurs :

```bash
kubectl -n harbor get secrets
```

Vérifier les deux Secrets attendus :

```bash
kubectl -n harbor get secret harbor-db
kubectl -n harbor get secret harbor-registry-s3
```

Vérifier les références dans les valeurs Helm :

```bash
helm -n harbor get values harbor \
  --revision 3
```

Attention : examiner la sortie avant tout partage.

### 10.3 Vault et External Secrets Operator

Vault constitue la source centralisée cible des secrets.

L'intégration External Secrets propre à Harbor reste à finaliser et à valider.

Ne pas supposer que les Secrets Harbor sont actuellement réconciliés automatiquement depuis Vault.

En cas de problème :

- vérifier l'existence du Secret Kubernetes ;
- vérifier les références Helm ;
- vérifier les événements du namespace ;
- vérifier l'état d'External Secrets Operator si nécessaire ;
- vérifier les conditions de synchronisation uniquement lorsque l'intégration Harbor sera déployée.

Ne jamais publier les valeurs des Secrets dans les journaux ou dans Git.

---

## 11. Incidents de push et pull

### 11.1 Vérifier l'accès à Harbor

```bash
curl -I http://192.168.1.40:30002
```

Une réponse HTTP confirme que le point d'accès répond, mais ne garantit pas que toutes les opérations Registry fonctionnent.

### 11.2 Vérifier le Registry

```bash
kubectl -n harbor get deployment harbor-registry
```

### 11.3 Vérifier le stockage

En cas d'échec de push ou pull, examiner dans cet ordre :

1. Disponibilité de Harbor.
2. État du Registry.
3. État de MinIO.
4. Référence au Secret S3.
5. Journaux Registry.
6. Existence et intégrité des blobs concernés.

### 11.4 Vérifier une image

Depuis un environnement disposant d'un accès autorisé au Registry :

```bash
podman pull <harbor-host>/<project>/<image>:<tag>
```

Ne pas modifier les tags ou supprimer les images pendant le diagnostic.

Pour un incident de push, examiner également les journaux Registry et les erreurs S3 avant de retenter l'opération.

---

## 12. Incidents Helm et configuration

### 12.1 Consulter l'historique

```bash
helm -n harbor history harbor
```

La révision de référence actuellement utilisée est la révision 3.

### 12.2 Examiner la configuration

```bash
helm -n harbor get values harbor \
  --revision 3
```

### 12.3 Examiner les ressources déployées

```bash
helm -n harbor get manifest harbor
```

Attention : les manifests peuvent contenir des données de configuration sensibles. Ne pas publier leur contenu sans vérification.

### 12.4 Précaution sur les anciennes révisions

Les révisions 1 et 2 utilisaient un stockage Registry basé sur `filesystem`.

La révision 3 utilise le stockage S3 avec MinIO.

**Un rollback direct de la révision 3 vers les révisions 1 ou 2 n'est pas une procédure de reprise sûre.**

Un rollback Helm ne restaure pas les blobs MinIO et ne réconcilie pas automatiquement les données PostgreSQL.

Toute opération de rollback doit être précédée :

- d'une analyse des différences de configuration ;
- d'une vérification de compatibilité du stockage ;
- d'une stratégie de restauration des données ;
- d'une validation de la cohérence PostgreSQL / MinIO.

Voir `rollback.md`.

---

## 13. Incidents de sauvegarde et restauration

### 13.1 Vérifier les sauvegardes

Les sauvegardes de référence du 4 novembre 2026 sont documentées dans `backup.md`.

Elles comprennent :

- un dump PostgreSQL ;
- une sauvegarde des objets MinIO ;
- des contrôles SHA-256.

### 13.2 État des tests de restauration

| Test | Résultat |
|---|---|
| Restauration PostgreSQL isolée | Testée |
| Restauration MinIO isolée | Testée |
| Vérification des objets restaurés | Testée |
| Restauration coordonnée Harbor | À valider |

Les sauvegardes PostgreSQL et MinIO n'ayant pas été réalisées exactement au même instant, leur cohérence temporelle n'est pas garantie.

### 13.3 Règles de reprise

Avant une restauration :

1. Identifier le point de sauvegarde.
2. Vérifier les sommes de contrôle.
3. Préserver les données existantes.
4. Restaurer dans un environnement isolé lorsque cela est possible.
5. Vérifier les métadonnées et les blobs.
6. Planifier une restauration coordonnée.

Voir :

- `backup.md`
- `restore.md`
- `rollback.md`

---

## 14. GitOps et ArgoCD

ArgoCD pilote la gestion GitOps de la plateforme.

L'intégration spécifique de Harbor dans ArgoCD reste à finaliser.

En cas d'écart entre la configuration attendue et la configuration déployée :

1. Vérifier la révision Helm active.
2. Vérifier les valeurs Helm.
3. Vérifier les ressources Kubernetes.
4. Vérifier le contenu du dépôt Git.
5. Identifier les modifications manuelles éventuelles.

Ne pas considérer une application ArgoCD comme propriétaire de Harbor tant que son intégration n'a pas été créée et validée.

---

## 15. Sécurité et précautions

Les opérations suivantes sont interdites sans procédure validée :

- suppression de volumes PostgreSQL ;
- suppression de volumes MinIO ;
- suppression du bucket `harbor-registry` ;
- suppression globale des clés Redis ;
- suppression manuelle de blobs ;
- réinitialisation de la base PostgreSQL ;
- rollback Helm vers une configuration filesystem sans plan de migration ;
- exposition de Harbor sur Internet en HTTP.

L'environnement local utilise actuellement HTTP, avec TLS désactivé.

Cette configuration ne doit pas être considérée comme acceptable pour une exposition externe ou un environnement de production accessible depuis Internet.

Avant toute intervention :

- préserver les journaux utiles ;
- vérifier les sauvegardes ;
- éviter les modifications simultanées de plusieurs composants ;
- documenter les actions réalisées ;
- vérifier le fonctionnement de Harbor après intervention.

---

## 16. Checklist de diagnostic

| Contrôle | Commande / action |
|---|---|
| Pods Harbor | `kubectl -n harbor get pods -o wide` |
| Deployments | `kubectl -n harbor get deployments` |
| StatefulSets | `kubectl -n harbor get statefulsets` |
| Événements | `kubectl -n harbor get events --sort-by='.lastTimestamp'` |
| Détails d'un pod | `kubectl -n harbor describe pod <pod-name>` |
| Logs Core | `kubectl -n harbor logs deployment/harbor-core --since=30m` |
| Logs Registry | `kubectl -n harbor logs deployment/harbor-registry --since=30m` |
| Logs Redis | `kubectl -n harbor logs statefulset/harbor-redis --since=30m` |
| Logs Trivy | `kubectl -n harbor logs statefulset/harbor-trivy --since=30m` |
| PostgreSQL | `pg_isready -h 192.168.1.40 -p 5432 -d harbor` |
| MinIO | `nc -vz 192.168.1.40 9000` |
| Secret PostgreSQL | `kubectl -n harbor get secret harbor-db` |
| Secret S3 | `kubectl -n harbor get secret harbor-registry-s3` |
| Historique Helm | `helm -n harbor history harbor` |

---

## 17. Priorités d'amélioration

| Priorité | Action | Statut |
|---|---|---|
| Haute | Valider une restauration coordonnée PostgreSQL / MinIO | À faire |
| Haute | Finaliser ExternalSecret Harbor | À faire |
| Haute | Finaliser l'intégration GitOps Harbor | À faire |
| Moyenne | Automatiser les sauvegardes | À faire |
| Moyenne | Définir les politiques de rétention | À faire |
| Moyenne | Formaliser les objectifs RPO / RTO | À faire |
| Moyenne | Mettre en place une supervision des dépendances externes | À faire |
| Moyenne | Définir une stratégie TLS | À faire |
| Moyenne | Analyser les redémarrages historiques de Trivy | À faire |

---

## 18. Références

| Document | Description |
|---|---|
| `README.md` | Présentation générale de Harbor |
| `architecture.md` | Architecture technique |
| `backup.md` | Procédure de sauvegarde |
| `restore.md` | Procédure de restauration |
| `rollback.md` | Procédure de rollback |
| `minio-migration.md` | Retour d'expérience de migration MinIO |
| `troubleshooting.md` | Diagnostic et résolution des incidents |

---

**Conclusion :** Ce guide privilégie les vérifications non destructives et distingue clairement les composants Kubernetes des dépendances externes hébergées sous Podman. Les opérations de reprise doivent préserver la cohérence entre PostgreSQL et MinIO. Le PRA complet, l'automatisation des sauvegardes et les intégrations GitOps et External Secrets propres à Harbor restent des chantiers à finaliser.
