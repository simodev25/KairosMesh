# Agentic V2 - Source Of Truth

Cette documentation a été reconstruite uniquement à partir du code lu dans le dépôt local. Aucun document existant n'a été lu ni utilisé comme source de vérité.

## Fichiers lus

| Fichier | Rôle observé |
| --- | --- |
| `backend/app/services/agent_runtime/runtime.py` | Boucle principale du runtime, outils, sessions, événements, agrégation finale |
| `backend/app/services/agent_runtime/session_store.py` | Persistance SQL runtime, miroir `trace`, hydratation, reprise |
| `backend/app/services/agent_runtime/models.py` | Structures `RuntimeEvent` et `RuntimeSessionState` |
| `backend/app/services/agent_runtime/planner.py` | Sélection du prochain outil, fallback déterministe, contrat JSON LLM |
| `backend/app/services/agent_runtime/tool_registry.py` | Registre d'outils runtime et politique d'autorisation |
| `backend/app/services/agent_runtime/dispatcher.py` | Point d'entrée qui instancie `AgenticTradingRuntime` |
| `backend/app/services/agent_runtime/constants.py` | Constante `agentic_v2` |
| `backend/app/services/agent_runtime/__init__.py` | Exports du runtime |
| `backend/app/db/models/run.py` | Table `analysis_runs` et relations runtime |
| `backend/app/db/models/agent_runtime_session.py` | Table `agent_runtime_sessions` |
| `backend/app/db/models/agent_runtime_message.py` | Table `agent_runtime_messages` |
| `backend/app/db/models/agent_runtime_event.py` | Table `agent_runtime_events` |
| `backend/app/db/models/agent_step.py` | Table legacy `agent_steps` toujours alimentée |
| `backend/app/db/models/execution_order.py` | Table `execution_orders` |
| `backend/app/db/models/memory_entry.py` | Table `memory_entries` |
| `backend/alembic/versions/0005_agentic_runtime_storage.py` | Migration des tables sessions/messages |
| `backend/alembic/versions/0006_agentic_runtime_events.py` | Migration de la table événements |
| `backend/app/api/routes/runs.py` | Endpoints `/runs` observés |
| `backend/app/api/router.py` | Inclusion des routes API |
| `backend/app/tasks/run_analysis_task.py` | Exécution Celery du runtime |
| `backend/app/main.py` | WebSocket `/ws/runs/{run_id}`, auth WS, bootstrap FastAPI |
| `backend/app/schemas/run.py` | Schémas `RunOut` et `RunDetailOut` |
| `backend/app/services/orchestrator/engine.py` | Orchestrator utilisé par le runtime, market snapshot, mémoire, debug trace |
| `backend/app/services/orchestrator/agents.py` | Agents techniques/news/context/debate/trader/risk/execution |
| `backend/app/services/llm/provider_client.py` | Abstraction LLM multi-provider |
| `backend/app/services/llm/model_selector.py` | Defaults LLM par agent, skills, mode de décision |
| `backend/app/services/execution/executor.py` | Exécution simulation/paper/live, idempotence, MetaApi |
| `backend/app/services/risk/rules.py` | Règles de risque déterministes |
| `backend/app/services/memory/vector_memory.py` | Recherche mémoire vectorielle, signal mémoire, persistance de run |
| `backend/app/services/memory/memori_memory.py` | Recall et persistance `memori` |
| `backend/app/services/market/yfinance_provider.py` | Snapshot marché fallback, news agrégées, macro events |
| `backend/app/core/config.py` | Settings runtime, WS, mémoire, exécution |
| `frontend/src/api/client.ts` | Appels REST, URL WebSocket de run |
| `frontend/src/types/index.ts` | Types runtime exposés au frontend |
| `frontend/src/pages/DashboardPage.tsx` | Liste des runs et visibilité dashboard |
| `frontend/src/pages/RunDetailPage.tsx` | Vue détail run, WS, rendu sessions/messages/events |

## Artefacts utilisés comme preuves

| Artefact | Ce qu'il prouve |
| --- | --- |
| `AgenticTradingRuntime.execute()` dans `backend/app/services/agent_runtime/runtime.py:942` | Boucle principale, reprise, finalisation, écriture `decision` et `trace` |
| `RuntimeSessionStore.initialize()` dans `backend/app/services/agent_runtime/session_store.py:457` | Initialisation du miroir `trace.agentic_runtime` et de la session racine SQL |
| `RuntimeSessionStore.append_event()` dans `backend/app/services/agent_runtime/session_store.py:843` | Persistance durable des événements dans `agent_runtime_events` |
| `RuntimeSessionStore.append_session_message()` dans `backend/app/services/agent_runtime/session_store.py:728` | Persistance durable des messages dans `agent_runtime_messages` |
| `RuntimeSessionStore.persist_session()` dans `backend/app/services/agent_runtime/session_store.py:522` | Snapshot racine stocké dans `agent_runtime_sessions.state_snapshot` |
| `RuntimeSessionStore.hydrate_trace()` dans `backend/app/services/agent_runtime/session_store.py:356` | Reconstitution API de `sessions`, `session_history` et `events` depuis SQL |
| `run_with_selected_runtime()` dans `backend/app/services/agent_runtime/dispatcher.py:9` | Le dispatcher appelle toujours `AgenticTradingRuntime` |
| `list_runs`, `create_run`, `get_run` dans `backend/app/api/routes/runs.py` | Surface REST réellement exposée pour le runtime |
| `run_updates_socket()` dans `backend/app/main.py:269` | Le streaming temps réel repose sur un WebSocket qui poll la base |
| `AgenticRuntimePlanner.choose_tool()` dans `backend/app/services/agent_runtime/planner.py:168` | Le planner est LLM-assisté mais a un fallback déterministe |
| `DEFAULT_AGENT_LLM_ENABLED` dans `backend/app/services/llm/model_selector.py:12` | Activation LLM par défaut par agent |
| `RiskManagerAgent.run()` dans `backend/app/services/orchestrator/agents.py:2913` | Le rejet déterministe de risque n'est pas surclassé par le LLM |
| `ExecutionManagerAgent.run()` dans `backend/app/services/orchestrator/agents.py:3071` | Confirmation stricte same-side si LLM activé, HOLD forcé sinon |
| `ExecutionService.execute()` dans `backend/app/services/execution/executor.py:143` | Idempotence et modes `simulation` / `paper` / `live` |
| `VectorMemoryService.compute_memory_signal()` dans `backend/app/services/memory/vector_memory.py:820` | Ajustement déterministe score/confiance et blocs de risque mémoire |
| `MemoriMemoryService.recall()` dans `backend/app/services/memory/memori_memory.py:177` | Existence d'une seconde couche mémoire `memori` si activée |
| `RunDetailPage` dans `frontend/src/pages/RunDetailPage.tsx:136` | L'UI lit `trace.agentic_runtime`, ouvre le WS et affiche sessions/messages/events |

## Faits observés

### Tableau `observed_code_truths`

| topic | observed_fact | code_artifact | certainty_level | notes |
| --- | --- | --- | --- | --- |
| runtime-entrypoint | Le dispatcher runtime instancie toujours `AgenticTradingRuntime`; aucun autre runtime n'est sélectionné dans le code lu. | `backend/app/services/agent_runtime/dispatcher.py:9` | observé | Le nom `run_with_selected_runtime` est plus générique que l'implémentation actuelle. |
| run-creation | `POST /api/v1/runs` crée un `AnalysisRun` avec `trace.requested_metaapi_account_ref` et `trace.runtime_engine = agentic_v2`. | `backend/app/api/routes/runs.py:62` | observé | Le run est ensuite soit mis en queue Celery, soit exécuté inline. |
| runtime-plan | Le vrai plan runtime interne contient 10 outils: contexte marché, mémoire, 3 analystes, 2 débatteurs, trader, risk, execution. | `backend/app/services/agent_runtime/runtime.py:35` | observé | Ce plan diffère du `workflow` top-level hérité de l'orchestrator. |
| sql-sessions | La table `agent_runtime_sessions` existe et stocke `session_key`, `parent_session_key`, `status`, `summary`, `state_snapshot`, `resume_count`, etc. | `backend/app/db/models/agent_runtime_session.py:9`, `backend/alembic/versions/0005_agentic_runtime_storage.py:17` | observé | Relation vers `analysis_runs`. |
| sql-messages | La table `agent_runtime_messages` existe et stocke l'historique par session. | `backend/app/db/models/agent_runtime_message.py:9`, `backend/alembic/versions/0005_agentic_runtime_storage.py:60` | observé | Les messages sont prunés par session au-delà de `history_limit`. |
| sql-events | La table `agent_runtime_events` existe et est effectivement écrite par `append_event()`. | `backend/app/db/models/agent_runtime_event.py:9`, `backend/app/services/agent_runtime/session_store.py:843`, `backend/alembic/versions/0006_agentic_runtime_events.py:17` | observé | Séquence `seq` unique par run. |
| trace-mirror | `analysis_runs.trace` reste utilisé comme miroir de compatibilité: `agentic_runtime`, `market`, `news`, `analysis_outputs`, mémoire, gouverneur, debug trace, etc. | `backend/app/services/agent_runtime/session_store.py:457`, `backend/app/services/agent_runtime/runtime.py:1082`, `backend/app/services/agent_runtime/runtime.py:1171` | observé | Le runtime n'a pas migré vers SQL-only. |
| trace-hydration | `GET /runs/{id}` hydrate `trace.agentic_runtime` depuis SQL avec sessions, events et session_history. | `backend/app/api/routes/runs.py:23`, `backend/app/services/agent_runtime/session_store.py:356` | observé | `include_state_snapshot` n'est pas activé par l'API observée. |
| websocket | Le temps réel de run passe par `/ws/runs/{run_id}`; le serveur poll la DB et pousse `status` puis `event`. | `backend/app/main.py:269` | observé | Pas de bus push observé. |
| websocket-fallback | Si aucun événement SQL n'est encore vu et `last_event_id == 0`, le WS relit `trace.agentic_runtime.events`. | `backend/app/main.py:315` | observé | Fallback de compatibilité au premier chargement. |
| ui-dashboard | Le dashboard affiche une synthèse de runs et un lien détail, mais pas les sessions/messages/events runtime. | `frontend/src/pages/DashboardPage.tsx:677` | observé | La page recharge les runs toutes les 5 secondes. |
| ui-run-detail | La page détail affiche la décision, les `AgentStep` legacy, les sessions runtime, les messages par session, les événements runtime et la trace complète. | `frontend/src/pages/RunDetailPage.tsx:334` | observé | Aucun filtre ni pagination runtime observés. |
| llm-boundary | Le planner, `news-analyst`, `bullish-researcher`, `bearish-researcher` sont activés par défaut côté LLM; `technical`, `market-context`, `trader`, `risk`, `execution` sont désactivés par défaut. | `backend/app/services/llm/model_selector.py:12` | observé | Les settings DB peuvent surcharger ces defaults. |
| deterministic-risk | Le `RiskManagerAgent` applique d'abord `RiskEngine`, puis un LLM éventuel ne peut pas transformer un rejet déterministe en acceptation. | `backend/app/services/orchestrator/agents.py:2913`, `backend/app/services/risk/rules.py:37` | observé | Un veto LLM peut par contre bloquer une acceptation déterministe. |
| deterministic-execution | `ExecutionManagerAgent` construit une décision déterministe; si le LLM est activé, il faut une confirmation JSON stricte same-side sinon HOLD. | `backend/app/services/orchestrator/agents.py:3063` | observé | Si le LLM est désactivé, le plan déterministe est utilisé tel quel. |
| execution-idempotency | L'exécution crée une clé d'idempotence et rejoue une `ExecutionOrder` existante si la même requête a déjà été soumise. | `backend/app/services/execution/executor.py:55`, `backend/app/services/execution/executor.py:95` | observé | Cela protège surtout le chemin broker. |
| memory-layers | Le runtime peut combiner mémoire vectorielle SQL/Qdrant et mémoire `memori`, puis persister une mémoire de run en fin d'exécution. | `backend/app/services/orchestrator/engine.py:791`, `backend/app/services/memory/vector_memory.py:657`, `backend/app/services/memory/memori_memory.py:267` | observé | `memori` est conditionnée par settings et package disponible. |
| internal-session-tools | Des outils runtime `sessions_list`, `sessions_history`, `sessions_send`, `sessions_resume`, `session_status` existent, mais aucune route REST/UI lue ne les expose. | `backend/app/services/agent_runtime/runtime.py:104`, `backend/app/api/routes/runs.py:19`, `frontend/src/pages/RunDetailPage.tsx:136` | observé | Ce sont des capacités internes au runtime actuel. |
| correlation-fields | Les colonnes `correlation_id` et `causation_id` existent sur `agent_runtime_events`, mais aucun code lu ne peuple explicitement ces champs. | `backend/app/db/models/agent_runtime_event.py:23`, `backend/app/services/agent_runtime/session_store.py:881` | observé | Les champs sont prévus mais restent vides dans le flux observé. |

## Inférences

- `Inférence`: le runtime garde `analysis_runs.trace` pour compatibilité de lecture parce que le frontend lit encore `trace.agentic_runtime` et que le WebSocket a un fallback sur cette structure.
- `Inférence`: le snapshot racine SQL est la vraie source de reprise du runtime, car `restore_state()` lit d'abord `agent_runtime_sessions.state_snapshot` avant de retomber sur `trace.agentic_runtime.state_snapshot`.
- `Inférence`: les sous-sessions ne sont pas exécutées par des workers séparés; elles encapsulent un appel synchrone à une fonction locale, puis sont immédiatement finalisées.
- `Inférence`: `analysis_runs.trace.workflow` est un champ legacy/orchestrator, tandis que `trace.agentic_runtime.plan` reflète le plan runtime complet, car les deux listes n'ont pas le même contenu dans le code.

## Hypothèses

- `Hypothèse due to missing data`: la documentation parle des comportements configurables en disant "si activé" lorsque l'effet dépend de settings ou de données DB non visibles dans le dépôt.
- `Hypothèse due to missing data`: les modèles/migrations lus sont supposés représenter l'état cible de la base, sans vérification d'une base réellement migrée.

## Points non vérifiables

- Le provider LLM réellement utilisé en environnement, car `ConnectorConfig('ollama').settings` peut surcharger les defaults observés.
- L'activation effective de `memori`, `Qdrant`, `MetaApi`, `debug_trade_json` et des skills bootstrap en environnement.
- L'état réel des migrations déjà appliquées dans la base d'une instance déployée.
- L'existence d'un consommateur externe des champs `correlation_id` / `causation_id`.
- L'éventuelle présence de jobs externes de purge/archivage non visibles dans le périmètre lu.
- Le volume réel de données runtime et la taille moyenne des payloads `trace` en production.
