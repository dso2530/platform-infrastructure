# ADR-0002 — Architecture d'observabilité centralisée

| Métadonnée | Valeur |
|---|---|
| Identifiant | ADR-0002 |
| Statut | Proposé |
| Date | 06/11/2026 |
| Domaine | Architecture technique |
| Périmètre | AI Public Benefits Platform |
| ADR précédent | ADR-0001 — Centralisation des charts Helm |

## 1. Contexte

La plateforme AI Public Benefits repose sur une architecture distribuée composée de microservices Spring Boot, de composants Kubernetes, de middleware et de services d'intelligence artificielle.

Les principaux composants sont :

- Microservices Spring Boot.
- PostgreSQL et pgvector.
- Redis.
- Kafka et Apicurio Registry.
- MinIO.
- Keycloak.
- Services RAG et IA.
- Kubernetes, k0s et GKE.

Une première stack d'observabilité existe déjà dans l'environnement de développement. Elle repose sur des conteneurs exécutés sur l'hôte Ubuntu `192.168.1.40`.

Cette installation comprend Prometheus, Grafana, Loki, Promtail et Jaeger.

Cependant, aucune architecture transverse industrialisée n'avait encore été formalisée pour standardiser la collecte, le stockage, la consultation et la conservation des métriques, logs et traces.

L'objectif est de définir une architecture d'observabilité indépendante du cycle de vie des clusters Kubernetes et des applications métier.

Cette indépendance ne signifie pas que les composants de collecte doivent nécessairement être centralisés sur une seule infrastructure. Les agents peuvent être déployés au plus près des sources, tandis que les systèmes de stockage et de consultation restent centralisés dans chaque environnement.

## 2. Objectifs

L'architecture d'observabilité doit permettre :

- De surveiller la disponibilité des applications et infrastructures.
- De mesurer les performances des microservices.
- De centraliser les logs.
- De suivre les requêtes distribuées entre microservices.
- De détecter les incidents et les dégradations.
- De faciliter les diagnostics techniques.
- De standardiser l'instrumentation des applications.
- De garantir l'isolation des données entre environnements.
- De découpler les applications des systèmes de stockage et de consultation.
- De respecter les exigences de sécurité et du RGPD.
- De permettre une évolution indépendante des composants d'observabilité.

## 3. Existant — environnement de développement

Une première installation est présente sur l'hôte Ubuntu `192.168.1.40`.

Les composants actuellement configurés sont :

| Composant | Image | Port hôte | Fonction |
|---|---|---:|---|
| Prometheus | prom/prometheus | 9099 | Collecte des métriques |
| Grafana | grafana/grafana | 3001 | Visualisation |
| Jaeger | jaegertracing/all-in-one | 16686, 4317, 4318 | Traces distribuées |
| Loki | grafana/loki:3.5.2 | 3100 | Centralisation des logs |
| Promtail | grafana/promtail:3.5.2 | 9080 | Collecte des logs |

Prometheus utilise actuellement une configuration statique avec plusieurs cibles :

- Prometheus.
- citizen-bff.
- document-service.
- Kafka Exporter.

Les applications Spring Boot exposent leurs métriques via `/actuator/prometheus`.

Promtail collecte notamment les logs du citizen-bff et prévoit une extension aux autres microservices.

Cette installation constitue une base expérimentale et ne représente pas encore l'architecture industrialisée.

Par ailleurs, Promtail ayant atteint sa fin de vie le 2 mars 2026, Grafana Alloy est retenu comme cible de migration pour la collecte des logs.

La migration sera progressive afin de préserver la continuité de la collecte pendant la transition.

## 4. Décision architecturale

Adopter une architecture d'observabilité centralisée par environnement, indépendante des clusters Kubernetes.

La centralisation concerne principalement les systèmes de stockage, de traitement et de consultation. Les agents de collecte sont déployés au plus près des sources lorsque cela est nécessaire.

### 4.1 Localisation des infrastructures

| Environnement | Infrastructure applicative | Infrastructure d'observabilité |
|---|---|---|
| DEV | Clusters k0s et Floci/GKE | Hôte Ubuntu `192.168.1.40`, hors Kubernetes |
| STAGING | Infrastructure applicative STAGING | Infrastructure dédiée à STAGING |
| PROD | Infrastructure applicative PROD | Infrastructure dédiée à PROD |

L'environnement DEV dispose actuellement de deux sources applicatives distinctes : k0s et Floci/GKE.

L'infrastructure centrale DEV héberge les composants suivants :

- Prometheus.
- Grafana.
- Loki.
- OpenTelemetry Collector.
- Jaeger.

Grafana Alloy est déployé au plus près des sources applicatives, notamment dans les infrastructures k0s et Floci/GKE.

En STAGING et PROD, les infrastructures applicatives et les infrastructures d'observabilité sont également séparées.

Chaque environnement possède ses propres systèmes de stockage et de consultation.

### 4.2 Principes structurants

Les principes suivants sont retenus :

1. Séparation des infrastructures applicatives et des infrastructures centrales d'observabilité.
2. Collecte distribuée au plus près des sources.
3. Centralisation des données dans l'infrastructure de l'environnement concerné.
4. Isolation stricte des données entre DEV, STAGING et PROD.
5. Absence de dépendance fonctionnelle directe entre les applications métier et les interfaces de visualisation.
6. Possibilité de faire évoluer les agents et les systèmes centraux indépendamment des applications.
7. Aucun déploiement d'une seconde stack complète d'observabilité dans les clusters applicatifs.

Les agents de collecte ne constituent donc pas une stack autonome : ils assurent la collecte et la transmission vers les systèmes centraux de leur environnement.

## 5. Technologies retenues

| Fonction | Technologie | Responsabilité |
|---|---|---|
| Métriques | Prometheus | Collecte et stockage des métriques |
| Visualisation | Grafana | Dashboards et exploration |
| Logs | Grafana Loki | Stockage et consultation des logs |
| Collecte des logs | Grafana Alloy | Collecte et transmission des logs |
| Instrumentation | OpenTelemetry | Standardisation de la production et de la propagation de la télémétrie |
| Traitement et transport des traces | OpenTelemetry Collector | Réception, traitement et export des traces |
| Traces | Jaeger | Stockage et exploration des traces distribuées |

Les responsabilités sont distinguées :

- OpenTelemetry constitue le standard d'instrumentation et de propagation de la télémétrie.
- OpenTelemetry Collector constitue le composant chargé de recevoir, traiter et exporter les données.
- Jaeger assure le stockage et l'exploration des traces selon le mode de déploiement retenu.
- Grafana Alloy assure la collecte des logs et leur transmission vers Loki.

La migration de Promtail vers Grafana Alloy sera progressive.

Les versions des images devront être explicitement fixées. L'utilisation de tags `latest` sera évitée dans les environnements industrialisés.

Le choix définitif des modes de stockage et de déploiement sera précisé lors de la conception détaillée.

## 6. Architecture logique

L'architecture repose sur trois chaînes de collecte distinctes.

### 6.1 Vue logique des flux

```text
                 APPLICATIONS ET INFRASTRUCTURES
                              |
             +----------------+----------------+
             |                |                |
          METRIQUES          LOGS             TRACES
             |                |                |
          Micrometer      Grafana Alloy    OpenTelemetry
             |                |                |
             v                v                v
         Prometheus           Loki        OTel Collector
             |                |                |
             |                |                v
             |                |              Jaeger
             |                |                |
             +----------------+----------------+
                              |
                           Grafana
                              |
                    Dashboards / Alertes
```

### 6.2 Principe de collecte distribuée

Les agents de collecte sont positionnés au plus près des sources applicatives.

Pour les logs :

```text
Sources applicatives
        |
        v
Grafana Alloy
        |
        v
Loki central de l'environnement
        |
        v
Grafana
```

Pour les métriques :

```text
Applications et infrastructures
        |
        | Exposition des endpoints
        v
Prometheus central de l'environnement
        |
        v
Grafana
```

Pour les traces :

```text
Applications instrumentées
        |
        | Export OTLP
        v
OpenTelemetry Collector central
        |
        v
Jaeger
        |
        v
Grafana / Exploration des traces
```

La centralisation concerne les systèmes de stockage et de consultation, et non nécessairement tous les agents de collecte.

Les flux de télémétrie doivent rester confinés à leur environnement d'origine.

## 7. Stratégie par signal

### 7.1 Métriques

Les microservices Spring Boot utilisent Spring Boot Actuator et Micrometer.

Les métriques couvrent notamment :

- Requêtes HTTP.
- Latence et taux d'erreurs.
- Utilisation CPU et mémoire.
- JVM et garbage collection.
- Pools de connexions.
- Consommation Kafka.
- État des dépendances.

Prometheus collecte les métriques exposées par les applications et les infrastructures.

En DEV, la configuration statique existante pourra être conservée temporairement.

Pour Kubernetes, une découverte dynamique sera privilégiée.

Les mécanismes possibles comprennent :

- Prometheus Operator.
- ServiceMonitor.
- PodMonitor.
- Découverte Kubernetes native.
- Exporters spécifiques aux infrastructures et middleware.

Le choix entre Prometheus autonome et Prometheus Operator reste à arbitrer selon les environnements.

Les métriques devront respecter les règles de cardinalité afin de limiter la consommation mémoire et les coûts de stockage.

Les identifiants citoyens, les identifiants de documents et les autres données métier à forte cardinalité ne devront pas être utilisés comme labels Prometheus.

### 7.2 Logs

Les applications produisent des logs structurés, idéalement en JSON.

Les informations de corrélation doivent être propagées entre les services.

Les champs recommandés comprennent :

- Timestamp.
- Niveau de sévérité.
- Nom du service.
- Environnement.
- Correlation ID.
- Trace ID.
- Message technique.
- Code d'erreur éventuel.

Grafana Alloy assure la collecte des logs au plus près des applications et des infrastructures.

Les agents transmettent les logs vers le Loki central de leur environnement.

Les responsabilités sont les suivantes :

- Applications : production des logs.
- Grafana Alloy : collecte, filtrage et transmission.
- Loki : stockage et interrogation.
- Grafana : exploration et visualisation.

Les agents doivent être supervisés afin de détecter les interruptions de collecte, les erreurs d'envoi et les pertes éventuelles de données.

La migration de Promtail vers Alloy ne devra pas provoquer de rupture de service de collecte.

### 7.3 Traces distribuées

OpenTelemetry sera utilisé pour instrumenter les appels interservices.

Les traces permettront de suivre :

- Les requêtes entrantes.
- Les appels HTTP entre microservices.
- Les interactions avec PostgreSQL et Redis.
- Les échanges Kafka.
- Les appels aux services RAG et IA.

Les applications exportent les traces vers OpenTelemetry Collector via OTLP.

Le Collector reçoit, traite et transmet les traces à Jaeger.

Cette architecture permet de découpler les applications des systèmes de stockage et de consultation.

Le mode de déploiement du Collector et les mécanismes de traitement resteront à préciser lors de la conception détaillée.

### 7.4 Alertes

Les alertes devront couvrir notamment :

- Indisponibilité d'un service.
- Augmentation du taux d'erreurs.
- Dégradation de la latence.
- Saturation des ressources.
- Redémarrages anormaux de pods.
- Retard des consommateurs Kafka.
- Indisponibilité des dépendances critiques.
- Indisponibilité de Prometheus, Loki ou Jaeger.
- Erreurs et interruptions des pipelines de collecte.
- Absence de réception des données de télémétrie.

Les seuils seront définis progressivement à partir des comportements observés.

Le mécanisme de gestion et de routage des alertes reste à arbitrer.

## 8. Intégration avec Kubernetes et GitOps

L'architecture d'observabilité est indépendante des clusters Kubernetes.

Les clusters k0s et GKE transmettent leurs données vers les systèmes centraux de leur environnement.

Les mécanismes d'intégration pourront utiliser :

- Exporters Kubernetes.
- Prometheus Operator.
- ServiceMonitor et PodMonitor.
- Grafana Alloy.
- OpenTelemetry Collector.
- Exporters spécifiques aux middleware.

Les agents installés dans Kubernetes ne devront pas entraîner le déploiement d'une seconde stack complète.

Grafana Alloy pourra être déployé au plus près des workloads et des sources de logs.

Les configurations spécifiques à chaque environnement seront gérées dans le dépôt `platform-infrastructure`.

Les éventuels déploiements Kubernetes seront gérés par Helm et ArgoCD.

Les configurations de collecte devront être versionnées et adaptées à chaque environnement.

Les déploiements et évolutions de l'observabilité devront faire l'objet de validations spécifiques, notamment sur les flux réseau et la compatibilité des versions.

## 9. Sécurité réseau

Les flux seront limités au strict nécessaire.

La séparation des environnements doit être garantie au niveau réseau et au niveau des systèmes de stockage.

### 9.1 Développement

L'hôte Ubuntu `192.168.1.40` héberge les systèmes centraux d'observabilité DEV.

Les sources applicatives sont les clusters k0s et Floci/GKE.

Les flux attendus sont :

| Source | Destination | Fonction |
|---|---|---|
| Applications k0s | Prometheus DEV | Exposition des métriques |
| Applications Floci/GKE | Prometheus DEV | Exposition des métriques |
| Alloy k0s | Loki DEV | Transmission des logs |
| Alloy Floci/GKE | Loki DEV | Transmission des logs |
| Applications k0s et Floci/GKE | OTel Collector DEV | Export des traces OTLP |

Les communications devront être privées, contrôlées et limitées aux ports nécessaires.

Les endpoints Actuator ne devront pas être exposés publiquement.

### 9.2 STAGING et PROD

Les infrastructures d'observabilité seront indépendantes.

Les flux réseau seront documentés et limités à chaque environnement.

Les communications entre les applications, les agents et les systèmes centraux devront être sécurisées.

Les agents Alloy de STAGING transmettront uniquement vers Loki STAGING.

Les agents Alloy de PROD transmettront uniquement vers Loki PROD.

Les applications exporteront leurs traces vers le Collector de leur environnement.

Les règles réseau devront empêcher tout échange involontaire de données entre DEV, STAGING et PROD.

La configuration des NetworkPolicies devra être adaptée aux flux réels et aux contraintes réseau de chaque environnement.

La connectivité entre les clusters et les infrastructures centrales devra être supervisée.

## 10. Sécurité et conformité RGPD

Les systèmes d'observabilité ne doivent pas devenir un vecteur de fuite de données personnelles.

Les données de télémétrie devront respecter les principes de minimisation, de limitation des finalités et de conservation maîtrisée.

Les principes suivants sont retenus :

- Exclusion des secrets, mots de passe et tokens des logs.
- Absence de données personnelles inutiles dans les métriques.
- Interdiction d'utiliser les identifiants citoyens comme labels Prometheus.
- Filtrage des données sensibles dans les traces.
- Contrôle des données transmises aux systèmes centraux.
- Contrôle d'accès aux dashboards et aux interfaces d'administration.
- Authentification des agents et sécurisation des communications.
- Définition des durées de conservation par type de signal.
- Isolation des données selon l'environnement.
- Traçabilité des accès aux données d'observabilité.
- Protection des données lors des sauvegardes et restaurations.

Les pipelines de collecte devront intégrer des mécanismes de filtrage lorsque cela est nécessaire.

La supervision technique ne doit pas conduire à collecter systématiquement des données métier ou personnelles.

Les durées de conservation devront être définies séparément pour :

- Les métriques.
- Les logs.
- Les traces.

Les exigences détaillées seront intégrées à la matrice de conformité RGPD de la plateforme.

## 11. Stratégie de déploiement

La mise en œuvre sera progressive.

| Phase | Objectif | Livrables |
|---|---|---|
| 1 | Formalisation | ADR, modèle Structurizr et diagrammes C4 |
| 2 | Standardisation Spring Boot | Actuator, Micrometer et logs structurés |
| 3 | Métriques | Prometheus et découverte des services |
| 4 | Logs | Loki et migration progressive vers Grafana Alloy |
| 5 | Traces | Instrumentation OpenTelemetry, Collector et Jaeger |
| 6 | Supervision | Dashboards, alertes et supervision des collecteurs |
| 7 | Industrialisation | Helm, GitOps, sécurité réseau et tests |
| 8 | Renforcement de la production | Haute disponibilité, sauvegarde et restauration |

Chaque phase fera l'objet d'une validation avant généralisation.

La formalisation de l'architecture et la validation des diagrammes précèdent l'industrialisation des déploiements.

Aucun déploiement de composants supplémentaires ne sera engagé avant la validation de l'architecture et la définition des configurations cibles.

## 12. Conséquences

### 12.1 Avantages

- Centralisation de l'observabilité par environnement.
- Indépendance vis-à-vis des clusters Kubernetes.
- Séparation des infrastructures applicatives et d'observabilité.
- Collecte distribuée au plus près des sources.
- Standardisation des pratiques d'instrumentation.
- Diagnostic facilité des incidents distribués.
- Isolation des environnements.
- Évolutivité des composants.
- Possibilité de remplacer les systèmes de stockage sans modifier profondément les applications.
- Mutualisation des pratiques sans mutualisation des données entre environnements.

### 12.2 Contraintes

- Consommation de ressources supplémentaires.
- Coût du stockage des logs et des traces.
- Complexité de gestion des collecteurs distribués.
- Gestion de la cardinalité des métriques.
- Nécessité de maintenir la connectivité réseau entre sources et infrastructures centrales.
- Supervision des agents et des pipelines de collecte.
- Sécurisation des communications.
- Nécessité de définir des politiques de rétention.
- Gestion des mises à jour et de la compatibilité des composants.
- Besoin de mécanismes de sauvegarde et de restauration.
- Risque de perte de télémétrie en cas d'indisponibilité prolongée des systèmes centraux.

### 12.3 Compromis architecturaux

La collecte distribuée permet de rapprocher les agents des sources et de limiter les dépendances directes des applications envers les systèmes centraux.

En contrepartie, elle introduit des contraintes supplémentaires :

- Gestion du cycle de vie des agents.
- Supervision de leur disponibilité.
- Gestion des files d'attente et des éventuels mécanismes de buffering.
- Maîtrise des flux réseau.
- Gestion des erreurs de transmission.

La centralisation des systèmes de stockage et de consultation simplifie l'exploitation par environnement, mais nécessite un dimensionnement adapté et des mécanismes de résilience.

Les exigences de disponibilité de PROD seront supérieures à celles de DEV et devront être définies dans une architecture de production spécifique.

## 13. Points restant à arbitrer

Les décisions suivantes restent ouvertes et devront être traitées lors de la conception détaillée :

1. Prometheus autonome ou Prometheus Operator selon l'environnement.
2. Mécanismes de découverte Kubernetes : ServiceMonitor, PodMonitor ou découverte native.
3. Stockage et rétention des métriques.
4. Mode de déploiement de Grafana Alloy selon les sources : DaemonSet, agent sur hôte ou autre mode adapté.
5. Architecture de collecte des logs et mécanismes de buffering.
6. Mode de déploiement de l'OpenTelemetry Collector : agent, gateway ou architecture hybride.
7. Traitement, filtrage et enrichissement des traces.
8. Stockage des traces Jaeger et backend associé.
9. Stockage Loki et éventuelle utilisation d'un stockage objet compatible S3.
10. Authentification et autorisation Grafana.
11. Authentification des collecteurs et sécurisation des flux OTLP.
12. Gestion des alertes et notifications.
13. Dimensionnement des infrastructures STAGING et PROD.
14. Sauvegarde et restauration des données d'observabilité.
15. Haute disponibilité des composants de production.
16. Durées de conservation et politiques de purge par signal.
17. Supervision des agents Alloy et des pipelines OpenTelemetry.

Ces arbitrages ne remettent pas en cause les principes structurants définis dans le présent ADR.

## 14. Références

### 14.1 Documentation technique

- OpenTelemetry.
- Prometheus.
- Grafana.
- Grafana Loki.
- Grafana Alloy.
- Jaeger.
- Spring Boot Actuator.
- Micrometer.

### 14.2 Documentation interne

**Modèle architectural Structurizr :**

`architecture/structurizr/observability/workspace.dsl`

**Diagrammes C4 générés :**

`docs/architecture/c4/observability/`

- `structurizr-C1-System-Context.mmd`
- `structurizr-C2-Containers.mmd`
- `structurizr-Deployment-DEV.mmd`
- `structurizr-Deployment-STAGING.mmd`
- `structurizr-Deployment-PROD.mmd`

**Décisions architecturales associées :**

- ADR-0001 — Centralisation des charts Helm.

---

**Décision finale :** en attente de validation.

Cette architecture constitue la référence cible proposée pour l'observabilité de la plateforme AI Public Benefits.

Les principes de centralisation par environnement, de collecte distribuée, de séparation des infrastructures et d'isolation des données sont définis.

Les choix détaillés de déploiement, de stockage, de sécurité et de haute disponibilité feront l'objet d'arbitrages complémentaires avant l'industrialisation.