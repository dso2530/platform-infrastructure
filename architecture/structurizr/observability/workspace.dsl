workspace "Observability Platform" "Architecture C4 de la plateforme d'observabilité centralisée de AI Public Benefits Platform." {

    model {
        devops = person "Équipe DevOps / SRE" "Administre les plateformes, supervise les services et exploite les données d'observabilité."

        platform = softwareSystem "AI Public Benefits Platform" "Plateforme de services publics numériques composée de microservices Spring Boot et de composants d'infrastructure." {
            tags "Business System"
        }

        observability = softwareSystem "Centralized Observability Platform" "Collecte, centralise, stocke et permet d'explorer les métriques, logs et traces des environnements." {
            tags "Observability"

            prometheus = container "Prometheus" "Collecte les métriques par scraping des endpoints exposés par les applications et les infrastructures." "Prometheus" {
                tags "Metrics"
            }

            grafana = container "Grafana" "Fournit les tableaux de bord et les interfaces d'exploration des données d'observabilité." "Grafana" {
                tags "Visualization"
            }

            loki = container "Loki" "Centralise et stocke les logs des applications et des infrastructures." "Grafana Loki" {
                tags "Logs"
            }

            alloy = container "Grafana Alloy" "Agent de collecte déployé au plus près des sources applicatives. Collecte les logs et les transmet au Loki central de son environnement." "Grafana Alloy" {
                tags "Log Collector"
            }

            otelCollector = container "OpenTelemetry Collector" "Reçoit, traite et exporte les données de télémétrie, notamment les traces OTLP." "OpenTelemetry Collector" {
                tags "Telemetry"
            }

            jaeger = container "Jaeger" "Stocke et permet d'explorer les traces distribuées." "Jaeger" {
                tags "Tracing"
            }

            // Flux de collecte
            prometheus -> platform "Scrape les endpoints de métriques"
            platform -> alloy "Expose les logs à l'agent de collecte"
            platform -> otelCollector "Exporte les traces via OTLP"

            // Flux de stockage
            alloy -> loki "Transmet les logs collectés"
            otelCollector -> jaeger "Exporte les traces"

            // Flux de consultation
            grafana -> prometheus "Interroge les métriques"
            grafana -> loki "Interroge les logs"
            grafana -> jaeger "Explore les traces"
        }

        // Relations inter-systèmes visibles dans le diagramme C1
        platform -> observability "Exporte les traces distribuées via OTLP"

        // Accès opérationnels
        devops -> grafana "Consulte les tableaux de bord"
        devops -> prometheus "Consulte les métriques et les alertes"
        devops -> loki "Explore les logs"
        devops -> jaeger "Analyse les traces distribuées"

        // ============================================================
        // DEV
        // Sources applicatives : clusters k0s et Floci/GKE
        // Observabilité centrale : Ubuntu 192.168.1.40
        // ============================================================

        dev = deploymentEnvironment "DEV" {

            // Un groupe par cluster source.
            // Ils empêchent les relations croisées entre les instances Alloy.
            k0sGroup = deploymentGroup "k0s"
            flociGroup = deploymentGroup "Floci/GKE"

            deploymentNode "Infrastructures applicatives DEV" "Clusters hébergeant les services applicatifs DEV." {

                deploymentNode "Cluster k0s" "Cluster Kubernetes local." "Kubernetes" {
                    softwareSystemInstance platform k0sGroup
                    containerInstance alloy k0sGroup
                }

                deploymentNode "Cluster Floci/GKE" "Cluster GKE émulé par Floci." "Kubernetes / Floci" {
                    softwareSystemInstance platform flociGroup
                    containerInstance alloy flociGroup
                }
            }

            deploymentNode "Ubuntu host 192.168.1.40" "Hôte Linux hébergeant la plateforme centrale d'observabilité DEV." "Ubuntu" {
                deploymentNode "Podman / Compose" "Runtime des conteneurs d'observabilité centrale." "Podman" {

                    // Les composants centraux servent les deux clusters.
                    containerInstance prometheus k0sGroup,flociGroup
                    containerInstance grafana k0sGroup,flociGroup
                    containerInstance loki k0sGroup,flociGroup
                    containerInstance otelCollector k0sGroup,flociGroup
                    containerInstance jaeger k0sGroup,flociGroup
                }
            }
        }

        // ============================================================
        // STAGING
        // Sources applicatives et observabilité sur infrastructures
        // distinctes et indépendantes.
        // ============================================================

        staging = deploymentEnvironment "STAGING" {

            stagingGroup = deploymentGroup "STAGING"

            deploymentNode "Infrastructure applicative STAGING" "Infrastructure hébergeant les services applicatifs STAGING." {
                softwareSystemInstance platform stagingGroup
                containerInstance alloy stagingGroup
            }

            deploymentNode "Infrastructure observabilité STAGING" "Infrastructure indépendante de DEV et PROD." {
                deploymentNode "Runtime observabilité" "Runtime des composants centraux d'observabilité STAGING." {

                    containerInstance prometheus stagingGroup
                    containerInstance grafana stagingGroup
                    containerInstance loki stagingGroup
                    containerInstance otelCollector stagingGroup
                    containerInstance jaeger stagingGroup
                }
            }
        }

        // ============================================================
        // PROD
        // Sources applicatives et observabilité sur infrastructures
        // distinctes, avec exigences renforcées.
        // ============================================================

        prod = deploymentEnvironment "PROD" {

            prodGroup = deploymentGroup "PROD"

            deploymentNode "Infrastructure applicative PROD" "Infrastructure hébergeant les services applicatifs PROD." {
                softwareSystemInstance platform prodGroup
                containerInstance alloy prodGroup
            }

            deploymentNode "Infrastructure observabilité PROD" "Infrastructure indépendante avec exigences renforcées de disponibilité et de sécurité." {
                deploymentNode "Runtime observabilité" "Runtime des composants centraux d'observabilité PROD." {

                    containerInstance prometheus prodGroup
                    containerInstance grafana prodGroup
                    containerInstance loki prodGroup
                    containerInstance otelCollector prodGroup
                    containerInstance jaeger prodGroup
                }
            }
        }
    }

    views {
        systemContext observability "C1-System-Context" {
            include *
            autoLayout lr
        }

        container observability "C2-Containers" {
            include *
            autoLayout lr
        }

        deployment observability dev "Deployment-DEV" {
            include *
            autoLayout lr
        }

        deployment observability staging "Deployment-STAGING" {
            include *
            autoLayout lr
        }

        deployment observability prod "Deployment-PROD" {
            include *
            autoLayout lr
        }

        styles {
            element "Person" {
                shape person
                background "#08427B"
                color "#FFFFFF"
            }

            element "Software System" {
                background "#1168BD"
                color "#FFFFFF"
            }

            element "Observability" {
                background "#438DD5"
                color "#FFFFFF"
            }

            element "Container" {
                background "#23A2D9"
                color "#FFFFFF"
            }

            element "Metrics" {
                background "#1D6F42"
                color "#FFFFFF"
            }

            element "Visualization" {
                background "#6B4C9A"
                color "#FFFFFF"
            }

            element "Logs" {
                background "#A65E18"
                color "#FFFFFF"
            }

            element "Log Collector" {
                background "#A65E18"
                color "#FFFFFF"
            }

            element "Telemetry" {
                background "#147D80"
                color "#FFFFFF"
            }

            element "Tracing" {
                background "#7A4E9B"
                color "#FFFFFF"
            }
        }
    }

    configuration {
        scope softwaresystem
    }
}
