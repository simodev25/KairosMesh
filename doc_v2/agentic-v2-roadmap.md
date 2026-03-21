# Agentic V2 - Roadmap Recommandée

Cette roadmap est une recommandation fondée sur les écarts visibles dans le code. Ce n'est pas une description de fonctionnalités déjà présentes.

## Principes de priorisation

- `Recommandation`: traiter d'abord les sujets qui réduisent le risque opérationnel sans remettre en cause les acquis déjà visibles dans le code.
- `Recommandation`: prioriser la séparation entre persistance durable, diffusion temps réel et API de consultation.
- `Recommandation`: ne pas rouvrir ce qui existe déjà en partie. Exemple: un gouverneur de second pass existe déjà; la roadmap vise son enrichissement, pas sa création ex nihilo.

## Roadmap P1

1. Mettre en place un protocole de session réellement opérable, avec inbox/outbox asynchrone au lieu de sous-sessions strictement synchrones.
2. Ajouter lease, heartbeat et règles explicites de reprise contrôlée au niveau du run et de la session racine.
3. Ajouter un verrou applicatif contre la double reprise concurrente d'un même run.
4. Exposer une API runtime dédiée avec pagination et filtrage des événements, sessions et historiques.
5. Clarifier la frontière `SQL source of truth` vs `trace miroir de compatibilité`, idéalement via un payload runtime dédié.

## Roadmap P2

1. Introduire un bus/outbox durable si le runtime doit alimenter d'autres consommateurs que le WebSocket actuel.
2. Ajouter un replay cohérent des sessions et des événements à partir du stockage SQL.
3. Ajouter compaction, résumés versionnés et couches mémoire plus explicites au-dessus du couple actuel `vector + memori`.
4. Extraire un `evidence coordinator` dédié et enrichir le gouverneur de second pass déjà présent pour gérer plus d'une stratégie de relance.
5. Ajouter purge, archivage et métriques runtime SQL.
6. Étendre l'UI de pilotage runtime: filtres, recherche, pagination, actions de contrôle, lecture ciblée des événements/messages.

## Dépendances entre chantiers

- `P1 session protocol` dépend peu du reste et prépare `P1 lease/heartbeat`.
- `P1 API runtime dédiée` devient beaucoup plus utile une fois la frontière `SQL vs trace` clarifiée.
- `P2 replay` dépend d'abord d'un modèle de session plus stable et d'une surface API/runtime mieux bornée.
- `P2 bus/outbox` ne doit venir qu'après clarification de la vérité durable en SQL.
- `P2 UI de pilotage` dépend d'une API runtime dédiée et paginée.

## Bénéfices attendus

- réduction du risque de double exécution ou de reprise concurrente
- lecture runtime plus fine et moins coûteuse côté UI et intégrations
- séparation plus claire entre stockage durable et compatibilité legacy
- meilleure auditabilité grâce à des surfaces de replay et d'archivage explicites
- capacité à faire évoluer les sous-sessions au-delà du wrapper synchrone actuel

## Risques si non traités

- couplage persistant entre `analysis_runs.trace` et les tables runtime
- difficulté croissante à suivre des runs volumineux dans l'UI
- reprise de run difficile à sécuriser si plusieurs workers ou opérateurs interviennent
- absence de surface propre pour industrialiser le runtime au-delà du WebSocket par polling

## Tableau de roadmap

### Tableau `maturity_roadmap`

| phase | objective | target_area | expected_benefit | risk_if_skipped | priority |
| --- | --- | --- | --- | --- | --- |
| P1 | Protocole de session avec inbox/outbox asynchrone | Runtime session layer | Sous-sessions pilotables et extensibles | Les sous-sessions restent de simples wrappers synchrones | haute |
| P1 | Lease + heartbeat + reprise contrôlée | Reprise du runtime | Réduit les reprises ambiguës | Double reprise difficile à prévenir | haute |
| P1 | Verrou contre double reprise concurrente | Sécurité d'exécution | Cohérence des décisions et événements | Duplication potentielle du traitement | haute |
| P1 | Pagination et filtrage des événements | API/observabilité runtime | Lecture ciblée, UI plus légère | Payloads trop larges et suivi moins précis | haute |
| P1 | API runtime dédiée et découplage `trace` | Surface d'intégration | Contrat runtime plus clair | Dépendance durable à `RunDetailOut` large | haute |
| P2 | Bus/outbox durable | Streaming et intégrations | Diffusion robuste vers d'autres consommateurs | Le WS poll DB reste le seul canal | moyenne |
| P2 | Replay cohérent des sessions | Audit et incident review | Reconstruction fiable des runs | Investigation limitée aux payloads bruts | moyenne |
| P2 | Compaction et résumés versionnés | Mémoire runtime | Meilleure qualité et tenue dans le temps | Dérive du volume et du bruit mémoire | moyenne |
| P2 | Evidence coordinator + second-pass enrichi | Gouvernance décisionnelle | Meilleure isolation de la logique de relance | Le `TraderAgent` reste très chargé | moyenne |
| P2 | Purge, archivage, métriques SQL runtime, UI de pilotage | Exploitation | Maîtrise de la croissance et support opérateur | Coût d'exploitation croissant | moyenne |
