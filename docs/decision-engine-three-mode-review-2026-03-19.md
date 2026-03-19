# Revue du moteur de decision trois modes

Date: 2026-03-19

Auteur: Codex

Statut: revue d'architecture et de logique decisionnelle terminee

## Resume executif

[Fait] Le moteur de decision est largement deterministe sur la couche finale `trader-agent -> risk-manager -> execution-manager`, mais le coeur de scoring est structurellement faible car `net_score`, `debate_score` et `confidence` reexploitent en grande partie la meme information source au lieu de representer trois dimensions distinctes.

[Fait] La differentiation entre `conservative`, `balanced` et `permissive` existe dans le code, mais elle est etroite dans la pratique. Sur 25 traces debug rejouees localement avec le code courant sur les trois modes, le resultat est:

- `HOLD / HOLD / HOLD` sur 21 cas
- `HOLD / SELL / SELL` sur 3 cas
- `HOLD / BUY / BUY` sur 1 cas

[Inference] `balanced` joue un vrai role intermediaire uniquement sur un sous-ensemble etroit de setups techniques directionnels avec peu de sources alignees. `permissive` ajoute surtout un bypass supplementaire via `permissive_technical_override`, mais apporte peu de divergence additionnelle sur l'echantillon fourni.

[Fait] La severite des contradictions n'est pas monotone entre les modes: `conservative` est plus strict sur l'evidence minimale, mais moins strict que `balanced` et `permissive` sur la contradiction majeure car `block_major_contradiction=False`.

[Fait] Le pipeline aval decision -> risque -> execution est globalement coherent dans les traces fournies: aucun trade n'est execute sans `decision in {BUY, SELL}`, `risk.accepted=true` et `execution_allowed=true`.

[Inference] Le systeme est exploitable comme base de travail, mais il n'est pas encore au niveau d'un moteur de decision de trading suffisamment precis, stable et controlable pour une exploitation production serieuse.

## Perimetre reellement analyse

[Fait] Artefacts lus:

- [`backend/app/services/orchestrator/agents.py`](../backend/app/services/orchestrator/agents.py)
- [`backend/app/services/orchestrator/engine.py`](../backend/app/services/orchestrator/engine.py)
- [`backend/app/services/llm/model_selector.py`](../backend/app/services/llm/model_selector.py)
- [`backend/app/services/risk/rules.py`](../backend/app/services/risk/rules.py)
- [`backend/app/services/execution/executor.py`](../backend/app/services/execution/executor.py)
- [`backend/app/services/backtest/engine.py`](../backend/app/services/backtest/engine.py)
- [`backend/config/agent-skills.json`](../backend/config/agent-skills.json)
- [`backend/tests/unit/test_trader_agent.py`](../backend/tests/unit/test_trader_agent.py)
- [`backend/tests/unit/test_risk_execution_agents.py`](../backend/tests/unit/test_risk_execution_agents.py)
- [`backend/tests/unit/test_agent_runtime_skills.py`](../backend/tests/unit/test_agent_runtime_skills.py)
- [`backend/tests/unit/test_orchestrator_debug_trace.py`](../backend/tests/unit/test_orchestrator_debug_trace.py)
- [`backend/tests/unit/test_agent_model_selector.py`](../backend/tests/unit/test_agent_model_selector.py)
- [`backend/tests/unit/test_connectors_settings_sanitization.py`](../backend/tests/unit/test_connectors_settings_sanitization.py)
- [`docs/agents.md`](./agents.md)
- [`docs/orchestration.md`](./orchestration.md)
- [`docs/testing.md`](./testing.md)
- [`docs/architecture.md`](./architecture.md)
- [`docs/ai-prompt-architecture-trading-review-tracker.md`](./ai-prompt-architecture-trading-review-tracker.md)
- 25 fichiers de trace sous [`backend/debug-traces`](../backend/debug-traces)

[Fait] Verifications executees:

- replay local des 25 traces debug avec re-evaluation des trois modes sur le code courant
- execution de tests cibles:
  - `pytest -q tests/unit/test_trader_agent.py tests/unit/test_risk_execution_agents.py tests/unit/test_agent_runtime_skills.py tests/unit/test_orchestrator_debug_trace.py tests/unit/test_agent_model_selector.py tests/unit/test_connectors_settings_sanitization.py`
  - resultat observe: `40 passed`

[Hypothese due to missing data] Le depot ne contient pas de campagne historique comparee meme-input / trois-modes a grande echelle. La comparaison exacte entre modes repose donc sur:

- le code
- les tests unitaires
- le replay local des traces disponibles avec le code courant

## Vue d'ensemble de l'architecture decisionnelle

[Fait] La hierarchie de decision actuelle est:

1. generation de scores analystes:
   - `technical-analyst`
   - `news-analyst`
   - `macro-analyst`
   - `sentiment-agent`
2. synthese bull / bear:
   - `bullish-researcher`
   - `bearish-researcher`
3. aggregation trader:
   - `net_score`
   - `debate_score`
   - `combined_score`
   - `confidence`
4. gating trader:
   - `technical_neutral_gate`
   - `minimum_evidence_ok`
   - `low_edge`
   - penalties et blocages de contradiction
   - overrides selon le mode
5. validation risque:
   - `risk-manager`
6. autorisation d'execution:
   - `execution-manager`
7. appel broker ou simulation:
   - `ExecutionService`

[Fait] Le code source de verite pour cette chaine est:

- [`backend/app/services/orchestrator/engine.py`](../backend/app/services/orchestrator/engine.py)
- [`backend/app/services/orchestrator/agents.py`](../backend/app/services/orchestrator/agents.py)

## Fonctions et workflows analyses

[Fait] Fonctions et zones principales etudiees:

- policies des modes:
  - [`DecisionGatingPolicy`](../backend/app/services/orchestrator/agents.py#L281)
  - [`DECISION_POLICIES`](../backend/app/services/orchestrator/agents.py#L305)
- scoring et gating trader:
  - [`TraderAgent.run`](../backend/app/services/orchestrator/agents.py#L1016)
- contradiction et penalties:
  - [`trend_momentum_opposition` et `contradiction_level`](../backend/app/services/orchestrator/agents.py#L1101)
- evidence / low-edge / overrides:
  - [`minimum_evidence_ok`, `low_edge_override`, `permissive_technical_override`](../backend/app/services/orchestrator/agents.py#L1184)
- risk:
  - [`RiskEngine.evaluate`](../backend/app/services/risk/rules.py#L19)
  - [`RiskManagerAgent.run`](../backend/app/services/orchestrator/agents.py#L1503)
- execution:
  - [`ExecutionManagerAgent.run`](../backend/app/services/orchestrator/agents.py#L1656)
  - [`ExecutionService.execute`](../backend/app/services/execution/executor.py#L46)
- backtest:
  - [`BacktestEngine._signals_from_agents`](../backend/app/services/backtest/engine.py#L97)

## Ecarts entre implementation actuelle et bonnes pratiques de moteurs de decision

[Fait] `debate_score` n'est pas un score vraiment independant du `net_score`.

- `bullish_confidence` est la somme des scores positifs cappee a 1.0
- `bearish_confidence` est la somme absolue des scores negatifs cappee a 1.0
- `debate_balance = bullish_confidence - bearish_confidence`
- `debate_score = debate_balance * 0.3`
- `net_score = somme brute des scores`

[Fait] Sur les 25 traces debug fournies, `debate_score == 0.3 * net_score` dans 25 cas sur 25.

[Inference] Le moteur ne capture pas un "debat" au sens d'une information orthogonale. Il recompense simplement une deuxieme fois le meme signal brut.

[Fait] `confidence` depend aussi principalement de `combined_score` et `debate_balance`, donc du meme noyau informationnel. Voir [`backend/app/services/orchestrator/agents.py`](../backend/app/services/orchestrator/agents.py#L1159).

[Inference] Le moteur triple-compte de fait:

- une premiere fois dans `net_score`
- une deuxieme fois dans `debate_score`
- une troisieme fois dans `confidence`

[Fait] Les composantes amont sont tres discretes:

- technique: paliers fixes bases sur trend, RSI, MACD
- news: souvent `-0.2`, `0`, `0.2`
- macro: `-0.1`, `0`, `0.1`
- sentiment: `-0.1`, `0`, `0.1`

[Inference] Le score est trop quantifie, donc peu granulaire pour un moteur qui se veut calibrable finement.

## Analyse de la hierarchie des regles

[Fait] Le moteur mixe deux representations du signal:

- un score continu
- une evidence discrete par `signal` et `aligned_source_count`

[Fait] Une source n'est comptee comme directionnelle que si son `signal` n'est pas `neutral` et si `abs(score)` depasse un seuil de credibilite. Voir [`backend/app/services/orchestrator/agents.py`](../backend/app/services/orchestrator/agents.py#L1083).

[Fait] Le calcul du `signal` utilise une stricte inegalite:

- `bullish` si `score > threshold`
- `bearish` si `score < -threshold`
- sinon `neutral`

Voir [`backend/app/services/orchestrator/agents.py`](../backend/app/services/orchestrator/agents.py#L226).

[Fait] Exemple observe dans les traces:

- [`backend/debug-traces/run-28-20260319T135657Z.json`](../backend/debug-traces/run-28-20260319T135657Z.json#L2213)
- `combined_score=0.423`
- `confidence=0.478`
- `decision_mode=balanced`
- `decision=HOLD`
- `technical_signal=neutral`
- `aligned_directional_source_count=0`
- `decision_gates = technical_neutral_gate, low_edge, insufficient_aligned_sources`

[Inference] La hierarchie actuelle laisse le score monter significativement avant de le faire ecraser par une couche discrete de gating. Cela produit des faux negatifs d'architecture, pas seulement des seuils mal calibres.

[Fait] `low_edge_override` et `minimum_evidence_ok` ne sont pas fusionnes. Un override peut retirer `low_edge` mais laisser la decision en `HOLD` parce que `minimum_evidence_ok` reste faux.

[Inference] La hierarchie n'est pas lineaire. Elle est composee d'exceptions partiellement superposees.

## Analyse du scoring

### Structure exacte

[Fait] Formules actuelles:

- `net_score = sum(agent_outputs[*].score)`
- `bullish_confidence = min(sum(max(score, 0)), 1.0)`
- `bearish_confidence = min(abs(sum(min(score, 0))), 1.0)`
- `debate_balance = bullish_confidence - bearish_confidence`
- `debate_score = debate_balance * 0.3`
- `raw_combined_score = net_score + debate_score`
- `combined_score = raw_combined_score` puis penalties de contradiction eventuelles
- `confidence_base = min(abs(combined_score) + max(abs(debate_balance) - 0.05, 0.0) * 0.2, 1.0)`
- `confidence = confidence_base * confidence_multiplier`

### Constats

[Fait] `combined_score` n'est pas reellement borne. Une trace atteint `1.04`:

- [`backend/debug-traces/run-21-20260319T134033Z.json`](../backend/debug-traces/run-21-20260319T134033Z.json#L2244)

[Fait] Les valeurs observees sur l'echantillon debug sont tres discretes:

- `-0.487`, `-0.423`, `-0.325`, `-0.227`, `-0.13`, `0.0`, `0.03`, `0.065`, `0.107`, `0.127`, `0.13`, `0.325`, `0.423`, `1.04`

[Inference] Le moteur produit des paliers logiques grossiers. Cela complique:

- la calibration fine des seuils
- la stabilite des decisions
- la lisibilite comparative entre modes

## Analyse comparative de conservative, balanced et permissive

### Policies observees dans le code

[Fait] Parametres principaux:

| mode | min_combined_score | min_confidence | min_aligned_sources | allow_low_edge_technical_override | allow_technical_single_source_override | block_major_contradiction |
|---|---:|---:|---:|---|---|---|
| conservative | 0.30 | 0.35 | 2 | false | false | false |
| balanced | 0.25 | 0.30 | 1 | true | false | true |
| permissive | 0.22 | 0.26 | 1 | true | true | true |

Source: [`backend/app/services/orchestrator/agents.py`](../backend/app/services/orchestrator/agents.py#L305)

### Comportement observe par replay local sur les 25 traces

[Fait] Resultats de comparaison meme-input / trois-modes:

| profil de sortie | nombre de cas |
|---|---:|
| `HOLD / HOLD / HOLD` | 21 |
| `HOLD / SELL / SELL` | 3 |
| `HOLD / BUY / BUY` | 1 |

[Inference] La separation principale n'est pas:

- `conservative` vs `balanced` vs `permissive`

mais plutot:

- `conservative`
- `balanced` + `permissive`

### Cas canoniques verifies sur inputs controles

[Fait] Cas "technical clair, source unique":

- `conservative`: `HOLD`
- `balanced`: `BUY` ou `SELL`
- `permissive`: `BUY` ou `SELL`

[Fait] Cas "override permissive uniquement" avec score technique encore trop faible pour l'override balanced:

- `conservative`: `HOLD`
- `balanced`: `HOLD`
- `permissive`: `BUY`

[Fait] Cas "technical neutral + combined fort":

- `conservative`: `HOLD`
- `balanced`: `HOLD`
- `permissive`: `HOLD`

[Inference] La vraie zone utile de `permissive` est aujourd'hui tres etroite. `balanced` n'est pas completement inutile, mais son territoire fonctionnel reste limite.

## Analyse du role du technical_signal

[Fait] Le `technical_signal` a un poids hierarchique superieur a ce que laisse entendre le `combined_score`.

[Fait] Si `technical_signal == neutral`, alors:

- il faut une `technical_neutral_exception`
- sinon `technical_neutral_block = true`

Voir [`backend/app/services/orchestrator/agents.py`](../backend/app/services/orchestrator/agents.py#L1147).

[Fait] Le bootstrap de skills pousse deja le `technical-analyst` vers plus de prudence:

- recherche de convergence
- reduction de conviction
- privilege a `neutral`

Source: [`backend/config/agent-skills.json`](../backend/config/agent-skills.json#L3)

[Inference] Le design courant fait de `technical_signal` un meta-gate dominant. Le score combine ne peut souvent pas compenser un `technical neutral`, meme quand il depasse les seuils du mode.

[Fait] Cas observe:

- [`backend/debug-traces/run-28-20260319T135657Z.json`](../backend/debug-traces/run-28-20260319T135657Z.json#L2213)
- `combined_score=0.423`
- `confidence=0.478`
- `technical_signal=neutral`
- decision finale `HOLD`

## Analyse du minimum evidence et du low_edge

[Fait] `minimum_evidence_ok` exige:

- `decision in {BUY, SELL}`
- `abs(combined_score) >= min_combined_score`
- `confidence >= min_confidence`
- `evidence_source_ok` ou `permissive_technical_override`
- pas de `major_contradiction_block`

[Fait] `low_edge` est ensuite calcule avec une logique partiellement distincte. En mode `permissive`, sa base est differente de celle des deux autres modes.

[Inference] `minimum_evidence_ok` et `low_edge` representent deux notions tres proches:

- autorisation d'ouverture
- absence d'edge marginal

mais elles ne sont pas modelees proprement comme deux niveaux hierarchiques complementaires.

[Fait] En `balanced`, on peut observer:

- `low_edge_override = true`
- `decision = HOLD`

si l'evidence minimale reste insuffisante.

[Inference] Le nom `low_edge_override` est trompeur. Il ne signifie pas toujours "autorisation finale d'ouvrir".

## Analyse des contradictions et penalites

[Fait] La contradiction detectee est aujourd'hui uniquement:

- opposition entre `trend` et signe de `macd_diff`
- severity selon `abs(macd_diff) / atr`

Voir [`backend/app/services/orchestrator/agents.py`](../backend/app/services/orchestrator/agents.py#L1101).

[Fait] `conservative`:

- penalise la contradiction moderee et majeure
- ne bloque pas explicitement la contradiction majeure

[Fait] `balanced` et `permissive`:

- penalisent
- bloquent explicitement la contradiction majeure

[Fait] Cas controle observe localement sur le code courant:

- contradiction majeure + setup bearish aligne
- `conservative` retourne `SELL` avec `execution_allowed=true`
- `balanced` retourne `HOLD`
- `permissive` retourne `HOLD`

[Inference] La severite de contradiction est logiquement incoherente. Un mode plus prudent ne doit pas etre moins bloquant qu'un mode plus agressif sur une contradiction majeure.

[Fait] Cas observe en trace ou la contradiction majeure bloque bien en `balanced`:

- [`backend/debug-traces/run-31-20260319T135731Z.json`](../backend/debug-traces/run-31-20260319T135731Z.json#L2211)

## Analyse des overrides decisionnels

[Fait] Overrides identifies:

- `technical_neutral_exception`
- `technical_single_source_override`
- `permissive_technical_override`
- `low_edge_override`

[Fait] `permissive_technical_override` bypass explicitement l'exigence d'evidence source quand:

- le signal technique est directionnel
- le score et la confiance depassent les seuils du mode
- il n'y a pas de contradiction majeure bloquante
- il manque des sources alignees

[Inference] Cet override corrige certains faux negatifs reels, mais il ouvre aussi un risque de faux positifs car il s'appuie encore sur un scoring qui double-compte l'information.

[Fait] Le depot contient des tests explicites pour:

- `balanced` qui ouvre sur signal technique clair a source unique
- `permissive` qui ouvre avec override supplementaire

Source: [`backend/tests/unit/test_trader_agent.py`](../backend/tests/unit/test_trader_agent.py)

## Analyse de la frontiere decision / execution

[Fait] Contrat d'execution deterministe actuel:

- `trader_decision.decision in {BUY, SELL}`
- `trader_decision.execution_allowed == true`
- `risk_output.accepted == true`
- alors `execution-manager.should_execute = true`

[Fait] Verification realisee sur les 25 traces debug:

- 0 incoherence observee entre `decision`, `execution_allowed`, `risk.accepted` et `execution_manager.should_execute`

[Fait] Les 4 trades non-HOLD observes dans les traces sont:

| pair | mode decisionnel | decision | execution_allowed | risk.accepted | should_execute | execution_result.status |
|---|---|---|---|---|---|---|
| GBPUSD.PRO | permissive | BUY | true | true | true | submitted |
| AUDUSD.PRO | permissive | SELL | true | true | true | submitted |
| EURJPY.PRO | permissive | SELL | true | true | true | submitted |
| EURJPY.PRO | balanced | SELL | true | true | true | submitted |

[Fait] `ExecutionService` normalise bien les statuts via `status`, `executed`, `reason`. Voir [`backend/app/services/execution/executor.py`](../backend/app/services/execution/executor.py#L28).

[Fait] En backtest `agents_v1`, la decision de signal utilise `risk.accepted` mais ne re-verifie pas explicitement `execution_allowed`. Voir [`backend/app/services/backtest/engine.py`](../backend/app/services/backtest/engine.py#L142).

[Inference] La frontiere live est correcte, mais la parite backtest/live merite d'etre renforcee.

## Analyse des runs observes

[Fait] Repartition des 25 traces du depot:

- `conservative`: 10 traces
- `balanced`: 7 traces
- `permissive`: 8 traces

[Fait] Distribution des decisions observees dans ces traces:

| mode | BUY | SELL | HOLD |
|---|---:|---:|---:|
| conservative | 0 | 0 | 10 |
| balanced | 0 | 1 | 6 |
| permissive | 1 | 2 | 5 |

[Fait] Exemple de cas permissif ouvert:

- [`backend/debug-traces/run-21-20260319T134033Z.json`](../backend/debug-traces/run-21-20260319T134033Z.json#L2244)

[Fait] Exemple de cas balanced bloque malgre score eleve:

- [`backend/debug-traces/run-28-20260319T135657Z.json`](../backend/debug-traces/run-28-20260319T135657Z.json#L2213)

[Hypothese due to missing data] Les traces ne comparent pas toujours la meme photographie de marche entre les trois modes. Elles ne suffisent donc pas a elles seules a quantifier la valeur relative des modes sans replay ou fixtures synchrones.

## Analyse de la frontiere LLM vs logique deterministe

[Fait] Le coeur du `trader-agent` est deterministe. Le LLM du `trader-agent` ne produit qu'une `execution_note`. Voir [`backend/app/services/orchestrator/agents.py`](../backend/app/services/orchestrator/agents.py#L1377).

[Fait] Les agents amont peuvent rester LLM-driven:

- `technical-analyst`
- `news-analyst`
- `macro-analyst`
- `sentiment-agent`
- chercheurs bull/bear

[Fait] `risk-manager` et `execution-manager` restent activables via la configuration runtime. Voir:

- [`backend/app/services/llm/model_selector.py`](../backend/app/services/llm/model_selector.py#L108)
- [`backend/tests/unit/test_agent_model_selector.py`](../backend/tests/unit/test_agent_model_selector.py#L85)

[Fait] Cela contredit partiellement le tracker documentaire qui parle de verrouillage deterministic-only deja finalise:

- [`docs/ai-prompt-architecture-trading-review-tracker.md`](./ai-prompt-architecture-trading-review-tracker.md#L198)

[Inference] La frontiere deterministe souhaitable n'est pas totalement verrouillee en code aujourd'hui.

## Analyse de la qualite et de la stabilite des decisions

[Fait] Le moteur est stable au sens logiciel:

- tests critiques passes
- pipeline aval coherent
- traces riches et exploitables

[Fait] Le moteur est moins stable au sens metier:

- score trop discret
- debat non independant
- neutral gate dominant
- contradiction majeure non monotone entre modes

[Inference] Les risques principaux aujourd'hui sont:

- faux negatifs:
  - `conservative`
  - `balanced`
  - cas techniques clairs mais peu diversifies
- faux positifs:
  - `permissive`
  - cas ouverts via bypass technique avec faible independance de preuves
- rigidite excessive:
  - `technical neutral` quasi bloquant
- permissivite excessive:
  - `permissive_technical_override` base sur un score deja suramplifie

## Plan de tests d'integration

Table `integration_test_plan`

| test_name | scope | dependencies | expected_result | priority |
|---|---|---|---|---|
| validation d'un cas technical neutral avec score faible dans les trois modes | trader-agent | fixtures deterministes | `HOLD`, `execution_allowed=false` dans les trois modes | P0 |
| test d'un cas technical bearish fort sans contradiction majeure dans les trois modes | trader-agent | fixtures deterministes | `conservative=HOLD`, `balanced/permissive=SELL` sur cas single-source clair | P0 |
| validation d'un cas contradiction major bloquant dans les trois modes | trader-agent + risk + execution | fixtures deterministes | aucun trade autorise dans les trois modes | P0 |
| gestion d'un cas low_edge avec technical neutral dans les trois modes | trader-agent | fixtures deterministes | `HOLD` motive et stable | P0 |
| test d'un override balanced sur signal technique intermediaire | trader-agent | fixture single-source clair | `balanced` ouvre, `conservative` bloque | P0 |
| test d'un override permissive sur signal technique fort mais sources manquantes | trader-agent | fixture permissive-only | seul `permissive` ouvre | P0 |
| test de coherence entre final_decision et execution_allowed | trader-agent | fixtures decisionnelles | aucune decision `BUY/SELL` non executable par contradiction logique | P0 |
| workflow complet avec risk-manager et execution-manager | orchestrator | DB + mocks providers | pas d'execution hors contrat | P0 |
| comparaison conservative vs balanced vs permissive sur le meme input | trader-agent | matrice fixtures | diff claire et explicable entre modes | P0 |
| test de stabilite d'un meme input sur plusieurs runs identiques | trader-agent | deterministic fixtures | sortie identique a chaque run | P0 |

## Plan d'evaluation et de performance

Table `performance_test_plan`

| scenario | target_component_or_flow | metric | load_profile | success_criteria | priority |
|---|---|---|---|---|---|
| temps total d'un run decisionnel complet par mode | orchestrator | p50/p95 duree | 30 runs par mode | variance faible et controlee | P0 |
| cout logique par couche de gating | trader-agent | temps par branche | 10k evaluations offline | pas de couche couteuse sans valeur | P1 |
| impact du nombre de regles sur la latence | trader-agent | delta p95 | A/B avant/apres simplification | gain net mesurable | P1 |
| impact des penalites de contradiction sur la stabilite | trader-agent | divergence decisions | corpus synthetique | severite monotone et stable | P0 |
| impact des modes sur la frequence des trades | trader-agent | trade rate | corpus fixe 500 cas | gradation claire et utile | P0 |
| impact d'une granularite de score plus fine | scoring | dispersion decisions | A/B scoring | baisse des paliers artificiels | P1 |
| stabilite des temps de reponse sous charge | orchestrator | p95, erreurs | burst 50 runs | pas de derive critique | P1 |
| cout de calcul marginal d'un override supplementaire | trader-agent | delta latence | A/B | surcout justifie | P2 |
| gain reel d'une simplification du moteur | trader-agent | complexite et latence | avant/apres | moins de logique pour meme comportement | P1 |
| ecart de comportement entre les trois modes a volume d'inputs constant | trader-agent | divergence rate | corpus fixe | `balanced` distinct de `permissive` sur une vraie zone metier | P0 |

## Tables de revue

### Table `decision_logic_review`

| component_or_rule | current_usage | best_practice | gap | optimization_opportunity | priority |
|---|---|---|---|---|---|
| `net_score` | somme brute des scores | score brut distinct du reste | base acceptable mais trop discrete | garder comme noyau simple | P1 |
| `debate_score` | 30% du meme signal | information orthogonale au score brut | double comptage | remplacer par score de convergence ou de contradiction | P0 |
| `confidence` | amplitude du score recyclee | confiance = fiabilite du setup | confusion conceptuelle | separer `edge_strength` et `decision_confidence` | P0 |
| `combined_score` | non borne proprement | echelle bornee et stable | 1.04 observe | normaliser ou clipper | P1 |
| `aligned_source_count` | evidence discrete | evidence reelle et non redondante | friction score vs signaux | revoir seuils et independance | P0 |

### Table `decision_hierarchy_review`

| rule_layer | current_role | problem_or_conflict | recommended_adjustment | expected_benefit | priority |
|---|---|---|---|---|---|
| technical signal | gate quasi dominant | neutral ecrase score eleve | aligner seuils score/signal | moins de HOLD artificiels | P0 |
| minimum evidence | autorisation d'ouvrir | overlap avec low_edge | fusionner ou clarifier l'ordre | meilleure lisibilite | P0 |
| low_edge | filtre de qualite | semantique partiellement doublon | redefinir comme quality flag pur | moins d'ambiguite | P0 |
| contradiction block | filtrage de securite | severite non monotone | hard-block identique sur contradiction majeure | coherence metier | P0 |
| execution authorization | frontiere vers execution | redondance partielle avec decision finale | simplifier contrat | pipeline plus net | P1 |

### Table `three_mode_behavior_review`

| mode | intended_behavior | observed_behavior | gap_or_issue | recommended_adjustment | priority |
|---|---|---|---|---|---|
| conservative | mode strict et prudent | tres bloqueur, 0 trade observe sur 10 traces | trop de faux negatifs et contradiction majeure non hard-block | garder strict sur evidence, durcir contradiction majeure | P0 |
| balanced | vrai milieu | utile sur cas techniques clairs a source unique | zone fonctionnelle trop etroite | lui donner une zone metier propre | P0 |
| permissive | mode opportuniste encadre | proche de balanced sur la plupart des cas | faible divergence additionnelle | formaliser son corridor d'ouverture | P1 |

### Table `cross_mode_case_review`

| case_type | conservative_expected | balanced_expected | permissive_expected | observed_gap | recommended_adjustment |
|---|---|---|---|---|---|
| technical neutral + score faible | HOLD | HOLD | HOLD | conforme | conserver |
| technical clair a source unique | HOLD | BUY ou SELL | BUY ou SELL | utile et coherent | conserver ce differenciateur |
| signal directionnel encore trop faible pour balanced | HOLD | HOLD | BUY ou SELL | seul vrai corridor propre a permissive | borner par tests dedies |
| contradiction majeure forte | HOLD | HOLD | HOLD | conservative peut encore trader sur cas controle | rendre le blocage monotone |
| technical neutral + combined eleve | HOLD | HOLD | HOLD | sur-blocage potentiel | revoir neutral gate |

### Table `low_edge_override_review`

| flow_or_case | current_low_edge_or_override_usage | problem | recommended_strategy | expected_benefit |
|---|---|---|---|---|
| balanced clear technical | `low_edge_override` ouvre | utile mais implicite | renommer ou fusionner avec evidence gate | meilleure traçabilite |
| permissive weak directional technical | `permissive_technical_override` bypass evidence | risque de faux positif | ajouter garde technique plus robuste | ouverture mieux controlee |
| technical neutral high combined | `low_edge` reste vrai | faux negatif probable | revoir exception neutral | plus de pertinence metier |
| major contradiction | `low_edge` force a vrai en plus du blocage | doublon logique | separer quality flag et hard-block | logique plus claire |

### Table `execution_contract_review`

| flow_or_component | current_execution_contract | problem | recommended_contract_change | expected_benefit | priority |
|---|---|---|---|---|---|
| trader -> risk | decision + levels + `execution_allowed` | redondance partielle | expliciter `decision_authorized` | contrat plus lisible | P1 |
| risk -> execution-manager | `accepted`, `suggested_volume` | globalement sain | conserver | stabilite | P0 |
| execution-manager -> broker | `should_execute`, `side`, `volume` | globalement sain | conserver | securite | P0 |
| backtest agents | depend surtout de `risk.accepted` | possible ecart avec live | verifier aussi `execution_allowed` | coherence backtest/live | P0 |

### Table `llm_vs_deterministic_review`

| component_or_flow | current_mode | problem | recommended_mode | reason | priority |
|---|---|---|---|---|---|
| analyst signals | mixte | variabilite amont | mixte mais valide schema strict | l'IA doit rester en amont | P1 |
| debate researchers | mixte | texte peu utile au score | explicatif surtout | eviter faux "debat" | P1 |
| score aggregation | deterministe | bon placement | deterministe strict | coeur du moteur | P0 |
| minimum evidence checks | deterministe | bon placement | deterministe strict | controle metier critique | P0 |
| contradiction penalties | deterministe | bon placement mais mal calibre | deterministe strict | necessite de robustesse | P0 |
| risk-manager | activable LLM | frontiere non verrouillee | deterministe strict | controle critique | P0 |
| execution-manager | activable LLM | frontiere non verrouillee | deterministe strict | securite execution | P0 |

### Table `failure_modes_review`

| component_or_rule | failure_mode | cause | impact | recommended_mitigation | priority |
|---|---|---|---|---|---|
| `debate_score` | faux sentiment de robustesse | double comptage du score | calibration trompeuse | refonte complete | P0 |
| contradiction major | mode strict moins bloquant | `block_major_contradiction=False` en conservative | incoherence metier | rendre monotone | P0 |
| `technical_neutral_gate` | faux negatif | score continu contredit par signal discret | trade bloque a tort | aligner seuils | P0 |
| source independence | faux positif d'evidence | macro/sentiment derives du meme snapshot | evidence surevaluee | redefinir l'independance | P1 |
| position sizing | volume non robuste | pip value fixe | sizing non production-grade | sizing instrument-aware | P0 |
| backtest/live parity | potentiel ecart | `execution_allowed` peu re-verifie en backtest | validation trompeuse | test et correctif dedies | P1 |

## Top bottlenecks

- `debate_score` n'apporte pas d'information independante
- `confidence` remeasure surtout l'amplitude du score
- `technical_neutral_gate` sur-domine plusieurs cas a edge fort
- `low_edge` et `minimum_evidence_ok` se chevauchent
- `conservative` n'est pas monotone sur les contradictions majeures
- `independent_directional_source_count` surestime l'independance des preuves
- `suggested_volume` reste trop simplifie pour la production multi-instruments

## Quick wins

- rendre `block_major_contradiction=true` en `conservative`
- verrouiller `risk-manager` et `execution-manager` en deterministic-only si c'est bien l'intention produit
- supprimer ou redefinir `debate_score`
- separer `edge_strength` de `decision_confidence`
- aligner la conversion `score -> signal` sur les cas frontiere
- ajouter une matrice de tests meme-input / trois-modes
- verifier `execution_allowed` dans le backtest `agents_v1`

## Recommandations prioritaires

[Recommandation] P0: refondre le trio `net_score / debate_score / confidence` pour separer:

- force brute du signal
- qualite de l'evidence
- niveau de conflit

[Recommandation] P0: retablir une severite monotone des contradictions entre les trois modes.

[Recommandation] P0: simplifier la hierarchie `minimum_evidence_ok / low_edge / overrides` en une logique plus lineaire.

[Recommandation] P0: recalibrer `technical_neutral_gate` pour qu'un score combine fort et une convergence pertinente puissent etre traites plus proprement.

[Recommandation] P0: redefinir la notion de source independante.

[Recommandation] P1: normaliser `combined_score` sur une echelle bornee.

[Recommandation] P1: rendre le sizing instrument-aware.

[Recommandation] P1: renforcer la parite live / backtest.

## Decisions d'architecture logique recommandees

[Recommandation] Le moteur doit rester strictement deterministe pour:

- score aggregation finale
- minimum evidence checks
- contradiction penalties
- required field checks
- execution authorization
- volume multiplier rules
- config validation
- fallback routing
- run classification

[Recommandation] Le LLM peut rester sur:

- l'analyse amont
- les arguments explicatifs
- les notes de synthese

mais ne doit pas decider directement:

- l'autorisation risque
- l'autorisation d'execution
- le coeur de l'aggregation de score

## Verdict final

[Fait] Le moteur actuel est un bon socle deterministe pour iterer.

[Inference] Ce n'est pas encore un moteur de decision de trading mature ni assez finement controle pour la production. Le vrai probleme est la conception du scoring et de la hierarchie des gates, plus que l'absence d'une regle supplementaire.

[Recommandation] La priorite absolue est de refondre la couche de scoring et les regles de gating avant d'ajouter de nouveaux overrides.

## Ce que Codex doit faire

Cette section decrit un plan d'action concret et executable par Codex dans le depot.

### Lot 1 - Correctifs P0 de logique

1. Rendre `conservative` au moins aussi strict que `balanced` et `permissive` sur la contradiction majeure.
2. Introduire un modele explicite avec trois notions separees:
   - `edge_strength`
   - `evidence_quality`
   - `decision_confidence`
3. Supprimer ou remplacer `debate_score` s'il ne transporte pas une information independante.
4. Simplifier `minimum_evidence_ok`, `low_edge`, `low_edge_override` et `permissive_technical_override` pour obtenir une hierarchie deterministe claire.
5. Revoir la conversion `score -> signal` et le `technical_neutral_gate` afin d'eviter les blocages artificiels sur les cas frontiere.

### Lot 2 - Correctifs P0 de frontiere deterministe

1. Verrouiller `risk-manager` en deterministic-only si la decision produit confirme cette orientation.
2. Verrouiller `execution-manager` en deterministic-only si la decision produit confirme cette orientation.
3. Aligner la documentation avec le comportement reel du code.
4. Ajouter une validation de configuration qui refuse toute tentative de re-activer un composant critique si la politique produit est deterministic-only.

### Lot 3 - Tests a ajouter

1. Ajouter des fixtures decisionnelles explicites pour les trois modes.
2. Ajouter des tests de non-regression sur:
   - contradiction majeure
   - technical neutral avec combined fort
   - balanced true intermediate
   - permissive-only override
3. Ajouter un test de parite live / backtest sur `execution_allowed`.
4. Ajouter un test qui verifie que `debate_score` ne re-duplique pas `net_score`.

### Lot 4 - Durcissement production

1. Rendre le sizing instrument-aware.
2. Borner et documenter l'echelle de score finale.
3. Ajouter un rapport de debug plus synthetique pour la lecture des decisions:
   - score brut
   - evidence quality
   - contradiction severity
   - gate final
4. Ajouter un benchmark offline sur un corpus fixe de cas synthetiques et de traces reelles.

### Ordre recommande pour Codex

1. Patch logique contradictions et monotonicite des modes.
2. Refactor scoring pour supprimer le double comptage.
3. Refactor hierarchie `minimum_evidence / low_edge / overrides`.
4. Ajouter les tests de non-regression.
5. Aligner backtest.
6. Aligner docs et configuration runtime.
7. Ajouter benchmark offline.

### Definition of done pour Codex

Le lot sera considere termine quand:

- les trois modes auront une monotonicite metier defendable
- `balanced` sera demonstrablement distinct de `conservative` et de `permissive`
- les contradictions majeures seront bloquees dans les trois modes sauf decision explicite contraire documentee
- `debate_score` ne sera plus un simple multiple de `net_score`
- la matrice de tests trois-modes passera en CI
- le backtest respectera la meme frontiere decision / execution que le live

### Commandes de verification pour Codex

```bash
cd backend
pytest -q tests/unit/test_trader_agent.py tests/unit/test_risk_execution_agents.py tests/unit/test_backtest_engine.py
pytest -q
```

## Notes finales

[Fait] Ce rapport distingue explicitement:

- faits observes dans le code, les tests et les traces
- inferences d'architecture
- hypotheses liees aux donnees manquantes
- recommandations

[Recommandation] La prochaine intervention Codex ne devrait pas commencer par ajouter un nouvel override. Elle devrait commencer par simplifier et re-separer les dimensions du moteur de decision.
