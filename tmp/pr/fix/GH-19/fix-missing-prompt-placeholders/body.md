## Résumé

Correction du bug GH-19 : deux causes distinctes provoquaient l'injection de placeholders non résolus (`<MISSING:*>`) dans les prompts des agents `technical-analyst` et `execution-manager`, rendant 100 % des runs incapables de produire des scores numériques ou de propager correctement la décision du risk-manager.

**Causes corrigées** :

- **Cause A (technical-analyst)** : `tool_results_block` et `interpretation_rules_block` n'étaient jamais construits dans `_build_prompt_variables()`.
- **Cause B (execution-manager)** : après exécution du risk-manager, seul `risk_result` était mis à jour ; `risk_approved` et `risk_volume` n'étaient pas propagés dans `base_vars`.

**Solution** :

- Injection de `tool_results_block` (construit depuis snapshot + runtime score breakdown, tronqué à 4000 chars) et `interpretation_rules_block` (5 règles métier) dans le contexte du `technical-analyst`.
- Propagation de `risk_approved` (bool, défaut `False`) et `risk_volume` (float, défaut `0.0`) depuis `risk_result.metadata` vers `base_vars` après exécution du risk-manager.
- Ajout d'un garde-fou proactif (`_detect_missing_placeholders()`) : log WARNING en production, erreur en tests si un placeholder `<MISSING:*>` est détecté.

## Changements

- **Code principal** :
  - `backend/app/services/agentscope/registry.py` (+128 lignes) : construction blocs manquants + propagation risk + garde-fou
  - `backend/app/main.py` : version bump `0.1.0` → `0.1.1`

- **Tests** :
  - `backend/tests/unit/test_prompt_placeholders_gh19.py` (+250 lignes, 7 tests) :
    - 2 tests Cause A (défauts + construction depuis snapshot)
    - 2 tests Cause B (défauts + propagation depuis risk_result)
    - 3 tests garde-fou (détection, comportement test/prod)

- **Artefacts ADOS** :
  - Spec (447 lignes), Plan (433 lignes), Test Plan (64 lignes) dans `doc/changes/2026-04/2026-04-25--GH-19--fix-missing-prompt-placeholders/`

## Tests

✅ **7/7 tests GH-19 passent** (`pytest tests/unit/test_prompt_placeholders_gh19.py`)

✅ **Aucune régression** : 590 tests backend passent (9 échecs préexistants sur main exclus du périmètre)

## Risque & Rollback

- **Risque** : Faible — modifications limitées à l'orchestration AgentScope, aucune zone sensible touchée (`risk_engine*`, `execution*`, `SafeDict` inchangés).
- **Rollback** : Revert du merge commit si régression détectée en CI.

## Conformité

- ✅ Zones sensibles non touchées (rule : `governance-zone-rules`)
- ✅ Aucune modification de `ALLOW_LIVE_TRADING` (reste `false`)
- ✅ Spec + Plan + Test Plan présents
- ✅ Tests unitaires couvrant tous les chemins critiques

Closes #19
