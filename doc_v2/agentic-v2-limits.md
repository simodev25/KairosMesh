# Agentic V2 - Limites Observées

Cette page documente uniquement les limites encore vraies dans le code lu.

## Limites encore vraies

- `Fait observé`: il n'existe pas de REST API runtime dédiée pour lister les sessions, messages ou événements; seules les routes `/runs` et le WebSocket de run sont exposés.
- `Fait observé`: le temps réel repose sur un WebSocket qui poll la base, pas sur un bus push/outbox observé.
- `Fait observé`: `RunDetailPage` affiche toutes les sessions, tous les messages hydratés et tous les événements connus sans filtre ni pagination.
- `Fait observé`: les messages SQL sont prunés par session au-delà de `agentic_runtime_history_limit`; l'historique n'est donc pas illimité.
- `Fait observé`: `trace.agentic_runtime.session_history` n'est pas maintenu comme miroir durable à l'écriture; il est reconstruit à la lecture depuis SQL.
- `Fait observé`: la reprise de run ne montre aucun lease, heartbeat, owner lock ou protection explicite contre une double reprise concurrente.
- `Fait observé`: les sous-sessions sont exécutées de manière synchrone autour d'un appel local; le code lu ne montre pas d'inbox/outbox asynchrone réellement opérée.
- `Fait observé`: `analysis_runs.trace` continue de porter à la fois un miroir runtime et des artefacts métier volumineux, ce qui maintient un couplage de compatibilité.
- `Fait observé`: les colonnes `correlation_id` et `causation_id` existent dans `agent_runtime_events`, mais le runtime observé ne les renseigne pas.
- `Fait observé`: l'API de liste des runs retourne par défaut 50 runs, et le dashboard ne pagine que ce sous-ensemble côté client.

## Capacités absentes mais souvent attendues

- `Fait observé`: aucune route HTTP paginée pour lire `agent_runtime_events` avec `after_id`, `session_key`, `stream` ou `limit`.
- `Fait observé`: aucune route HTTP pour lire ou envoyer des messages runtime malgré les outils internes `sessions_send` et `sessions_history`.
- `Fait observé`: aucune route HTTP pour reprendre explicitement une session ou un run avec contrôle de concurrence.
- `Fait observé`: aucune mécanique de replay de session cohérente n'est exposée.
- `Fait observé`: aucun bus/outbox durable n'est visible entre la persistance SQL et le streaming WebSocket.
- `Fait observé`: aucune stratégie de purge/archivage runtime SQL n'est visible dans le périmètre lu.
- `Fait observé`: aucune UI de pilotage runtime n'est visible pour reprendre, envoyer un message, filtrer, rechercher ou compacter l'historique.

## Ce qui n'est pas observable dans le code

- `Point non vérifiable`: l'état réel des tables en base d'une instance déployée.
- `Point non vérifiable`: la configuration active des providers LLM, des models et des skills stockées en base.
- `Point non vérifiable`: la disponibilité effective de `Qdrant`, `MetaApi` ou du package `memori` en environnement.
- `Point non vérifiable`: une éventuelle chaîne externe de replay, d'archivage ou d'export runtime non versionnée dans ce dépôt.

## Risques d'exploitation ou de montée en maturité

- `Fait observé`: sans lease/heartbeat, deux workers pourraient théoriquement reprendre le même run si la coordination externe échoue.
- `Fait observé`: le couplage entre SQL runtime et `analysis_runs.trace` impose des règles de synchronisation et de compatibilité supplémentaires.
- `Fait observé`: l'UI détail charge et rend des payloads complets; la pression monte avec le nombre d'événements et de sessions.
- `Fait observé`: le WebSocket par polling DB augmente le coût en lectures répétées quand plusieurs runs actifs sont suivis.
- `Fait observé`: l'absence d'API runtime dédiée force le frontend à dépendre d'un payload `RunDetailOut` large et composite.

## Sujets explicitement exclus car non observés

- `Exclu car non observé`: un bus d'événements push/outbox déjà opérationnel.
- `Exclu car non observé`: un protocole inbox/outbox asynchrone réellement traité par des workers de session.
- `Exclu car non observé`: un replay durable de session exposé à l'API.
- `Exclu car non observé`: un `evidence coordinator` séparé du `TraderAgent`.
- `Exclu car non observé`: une UI de contrôle fine des sous-sessions runtime.

## Tableau des gaps restants

### Tableau `remaining_gaps`

| topic | current_state | missing_capability | impact | recommended_phase |
| --- | --- | --- | --- | --- |
| surface-api-runtime | Le runtime externe passe par `GET /runs/{id}` + WebSocket | API dédiée sessions/messages/events/runtime-control | Payloads couplés, lecture coarse-grained | P1 |
| session-protocol | Les sous-sessions sont synchrones et finalisées dans le même processus | Inbox/outbox asynchrone réellement opérée | Pilotage runtime limité, peu extensible | P1 |
| resume-safety | Reprise par snapshot SQL sans lease/heartbeat visible | Lease, heartbeat, ownership, reprise contrôlée | Risque de double reprise et d'état concurrent | P1 |
| concurrency-guard | Aucun verrou explicite contre une seconde reprise du même run | Verrouillage applicatif contre reprise concurrente | Décisions/événements potentiellement dupliqués | P1 |
| event-access | `list_events()` sait filtrer/paginer en interne mais aucune route ne l'expose | Pagination et filtrage REST des événements | UI et intégrations lisent trop gros | P1 |
| trace-compatibility | `analysis_runs.trace` reste un miroir mixte legacy/runtime | Payload runtime dédié, schéma clarifié | Ambiguïté entre vérité SQL et compatibilité | P1 |
| streaming-backbone | Le WS poll la base puis fallback sur `trace` | Bus/outbox durable ou diffusion non pollée | Coût de lecture et intégration limitée | P2 |
| replay | Les événements sont durables en SQL, mais aucun replay cohérent n'est exposé | Replay de session et reconstruction opérable | Investigation et audit plus difficiles | P2 |
| memory-governance | Mémoire vectorielle + memori existent, sans compaction/versioning visibles | Résumés versionnés, compaction, couches mémoire plus nettes | Dérive de volume et qualité mémoire | P2 |
| runtime-ops-ui | La page détail est principalement read-only | UI de pilotage, filtres, recherche, actions runtime | Exploitation manuelle peu efficace | P2 |
| retention | Pas de purge/archivage runtime observés | Politique d'archivage, purge, métriques SQL runtime | Croissance de stockage | P2 |
