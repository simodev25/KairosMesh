# Permissive Mode Calibration and Prompt Alignment Report

Date: 2026-03-20
Project: `forex-permissive-mode-calibration-and-agent-prompt-alignment-001`

## 1) Diagnostic du sur-filtrage actuel en mode Permissive

Le pipeline était cohérent en fin de chaîne, mais `permissive` restait trop proche d'un mode prudent:

- seuils minimaux de preuve encore élevés pour des setups borderline (`min_combined_score`, `min_confidence`);
- exception `technical_neutral_exception` trop exigeante pour laisser vivre des cas plausibles;
- prompts amont non explicitement orientés `permissive`, favorisant des sorties trop neutres.

Effet observé: beaucoup de `HOLD` malgré des contextes exploitables.

## 2) Différences actuelles entre Permissive, Balanced et Conservative

Constat après patch:

- `permissive` est assoupli localement (seuils/gates plus tolérants).
- `balanced` et `conservative` conservent leurs seuils historiques.
- le blocage de contradiction majeure reste actif dans les 3 modes.

Hiérarchie attendue maintenue: `permissive` < `balanced` < `conservative` en exigence.

## 3) Liste précise des règles modifiées uniquement pour Permissive

Fichier: `backend/app/services/orchestrator/agents.py`

- `min_combined_score`: `0.22 -> 0.18`
- `min_confidence`: `0.26 -> 0.22`
- `technical_neutral_exception_min_sources`: `3 -> 1`
- `technical_neutral_exception_min_strength`: `0.28 -> 0.10`
- `technical_neutral_exception_min_combined`: `0.35 -> 0.20`
- `technical_single_source_min_score`: `0.22 -> 0.18`

Inchangé volontairement:

- `block_major_contradiction=True` (garde-fou critique);
- constantes `balanced` et `conservative`.

## 4) Prompts agents ajustés et justification

Ajout d'une guidance conditionnelle par mode:

- helper `_permissive_mode_prompt_guidance(agent_name)`
- helper `_apply_mode_prompt_guidance(system_prompt, user_prompt, decision_mode, agent_name)`

Injection de la guidance `permissive` dans:

- `technical-analyst`
- `news-analyst`
- `market-context-analyst` (et alias legacy `macro-analyst`)
- `bullish-researcher` / `bearish-researcher` (debate)
- `trader-agent`

Objectif: autoriser un biais modéré exploitable en `permissive` sans transformer le bruit en signal fort, et sans toucher à la philosophie `balanced`/`conservative`.

## 5) Patch / diff proposé

Fichiers modifiés:

- `backend/app/services/orchestrator/agents.py`
- `backend/tests/unit/test_trader_agent.py`
- `backend/tests/unit/test_orchestrator_debug_trace.py`

Correction technique mineure incluse:

- suppression d'un doublon de résolution `decision_mode` dans `NewsAnalystAgent`.

## 6) Tests ajoutés ou modifiés

### Tests unitaires trader

- assertions seuils permissifs rendues dynamiques via `result['rationale']`.
- `test_balanced_and_conservative_policy_thresholds_remain_stable`
- `test_trader_agent_mode_hierarchy_keeps_permissive_more_opportunistic`
- `test_apply_mode_prompt_guidance_is_permissive_only_and_deduplicated`

### Test orchestrateur (cohérence terminale)

- renforcement de `test_orchestrator_writes_debug_trade_trace_json` avec assertions:
  - `run.decision.execution.status == skipped`
  - `run.decision.execution_manager.status == skipped`
  - `run.decision.execution_manager.execution.status == skipped`
  - `run.decision.execution_manager.should_execute == False`

## 7) Risques de régression

- `permissive` peut produire plus de BUY/SELL borderline (comportement voulu).
- garde-fous critiques maintenus: contradiction majeure, cohérence exécution.
- `balanced`/`conservative` verrouillés par tests de stabilité.

## 8) Résumé des gains attendus

- moins de `HOLD` excessifs en `permissive`;
- meilleure séparation de comportement entre modes;
- prompts amont alignés avec une permissivité contrôlée et traçable;
- cohérence finale `trader -> execution_manager -> execution_result` conservée.

## 9) Validations exécutées

- `pytest -q backend/tests/unit` -> `189 passed`
- `pytest -q backend/tests/integration` -> `3 passed`

## 10) Limites et hypothèses restantes

- Pas de changement de philosophie globale du trader ni des modes `balanced`/`conservative`.
- Patch limité à calibration + prompt alignment; pas de refonte de scoring structurelle.
- L'effet quantitatif exact sur le taux de trade dépendra du mix réel de marchés/runs en production.
