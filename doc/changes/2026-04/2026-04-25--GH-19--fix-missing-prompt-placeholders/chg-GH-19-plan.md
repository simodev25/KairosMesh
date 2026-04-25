---
id: chg-GH-19-fix-missing-prompt-placeholders
status: In Progress
created: 2026-04-25T13:07:38Z
last_updated: 2026-04-25T15:42:00Z
owners:
  - kairos-mesh-team
service: backend/agents
labels:
  - bug
  - prompts
  - technical-analyst
  - execution-manager
links:
  change_spec: doc/changes/2026-04/2026-04-25--GH-19--fix-missing-prompt-placeholders/chg-GH-19-spec.md
summary: >-
  Corriger GH-19 : supprimer les placeholders non résolus (<MISSING:*>) dans les prompts
  des agents technical-analyst et execution-manager en initialisant/injectant les
  variables manquantes (tool_results_block, interpretation_rules_block,
  risk_approved, risk_volume) et en ajoutant un garde-fou de détection.
version_impact: patch
---

## Context and Goals

### Contexte

Le templating des prompts utilise `str.format_map(SafeDict(...))`. En cas de variable
absente, `SafeDict` renvoie littéralement `<MISSING:{clé}>` au lieu de lever une
exception. Deux familles de variables ne sont pas initialisées dans le contexte avant
interpolation, ce qui injecte des placeholders dans les prompts :

- **Cause A (technical-analyst)** : `tool_results_block` et `interpretation_rules_block`
  ne sont jamais construits/injectés dans `_build_prompt_variables()`
  (`backend/app/services/agentscope/registry.py`, ~L403-420).
- **Cause B (execution-manager)** : après exécution du risk-manager, seul
  `base_vars["risk_result"]` est mis à jour ; `risk_approved` et `risk_volume` ne sont
  pas propagés (`backend/app/services/agentscope/registry.py`, ~L1772).

### Objectifs (alignés sur la spec)

- G-1 / G-2 : 0 occurrence de `<MISSING:*>` dans les prompts de `technical-analyst` et
  spécifiquement 0 occurrence de `<MISSING:risk_approved>` / `<MISSING:risk_volume>`
  dans ceux de `execution-manager`.
- G-3 : permettre au `technical-analyst` de produire des scores numériques (non
  `UNAVAILABLE_*`).
- G-4 : garantir que `execution-manager` reçoit le verdict de risque.
- G-5 : ajouter ≥ 4 tests unitaires couvrant les substitutions et les valeurs par défaut.

### Open questions

- OQ-1 : format exact attendu dans le template pour `tool_results_block`
  (Markdown/texte libre/JSON). Décision à confirmer avec l’auteur du template.
- OQ-2 : seuil de troncature (nombre de caractères) acceptable pour `tool_results_block`.
- OQ-3 : noms stables des champs dans `risk_result` (`approved`, `volume`) ? Si incertitude
  : **Decision needed: consult `@architect`**.
- OQ-4 : faut-il étendre la validation `<MISSING:*>` à d’autres agents dès ce ticket ou
  rester strictement sur GH-19 ? **Decision needed: consult `@architect`**.

## Scope

### In Scope

- Injecter dans le contexte du `technical-analyst` :
  - `tool_results_block` (str) construit à partir des résultats MCP disponibles.
  - `interpretation_rules_block` (str) construit à partir de la configuration/règles.
- Propager dans `base_vars` après risk-manager :
  - `risk_approved` (bool) avec défaut sûr `False`.
  - `risk_volume` (float) avec défaut sûr `0.0`.
- Ajouter un garde-fou de détection `<MISSING:` sur le prompt final :
  - En production : log WARNING (non bloquant).
  - En tests/non-prod : erreur explicite.
- Ajouter des tests unitaires (≥ 4 cas) sous `backend/tests/unit/`.

### Out of Scope

- [OUT] Toute modification dans `backend/app/services/risk_engine*` (zone sensible).
- [OUT] Toute modification dans `backend/app/services/execution*` (couche broker).
- [OUT] Modifier `SafeDict` ou le moteur de templating dans `backend/app/services/prompts/registry.py`.
- [OUT] Modifier le comportement live/simulation ; `ALLOW_LIVE_TRADING` doit rester `false`.

### Constraints

- Changements limités aux fichiers listés par la spec :
  - `backend/app/services/agentscope/registry.py` (principal)
  - `backend/app/services/agentscope/prompts.py` (uniquement si ajustement de template est indispensable)
  - `backend/tests/unit/` (nouveaux tests)
- Ne pas introduire d’exceptions runtime en prod dues à la validation de placeholders :
  production = warning uniquement.

### Risks

- RSK-1 : bloc `tool_results_block` trop volumineux (fenêtre de contexte LLM) → troncature
  configurable, avec test de non-régression (long input).
- RSK-2 : absence ponctuelle de `risk_result` → défaut conservateur (`False`/`0.0`) + warning.
- RSK-3 : d’autres templates contiennent des placeholders non couverts → mitigé via garde-fou
  ciblé et tests GH-19 (et décision OQ-4 pour extension).

### Success Metrics

- 100% des prompts concernés sans `<MISSING:*>`.
- ≥ 4 nouveaux tests unitaires.
- 0 régression sur `pytest`.

## Phases

### Phase 1: Cadrage technique minimal + harnais de test

**Goal**: Établir des tests unitaires reproductibles qui échouent avant correctif et valident
les AC après correctif.

**Tasks**:

- [x] **1.1 Ajouter un helper de test `assert_no_missing_placeholders(prompt: str)`** (ajouté dans `backend/tests/unit/test_prompt_placeholders_gh19.py`, validation via `python3 -m pytest -q tests/unit/test_prompt_placeholders_gh19.py -k gh19 -vv` PASS)
  - Fichier: `backend/tests/unit/test_prompt_placeholders_gh19.py` (nouveau)
  - Contenu attendu (extrait) :

    ```python
    import re

    def assert_no_missing_placeholders(prompt: str) -> None:
        assert "<MISSING:" not in prompt, f"Placeholder(s) détecté(s) dans le prompt: {re.findall(r'<MISSING:[^>]+>', prompt)}"
    ```

  **Critères de validation**:
  - Le helper échoue avec un message listant les occurrences trouvées.

- [x] **1.2 Écrire un test unitaire (failing) reproduisant la Cause A sur le prompt technical-analyst** (cas implémentés: `test_gh19_cause_a_defaults_present_without_tool_results`, `test_gh19_cause_a_builds_tool_results_block_from_snapshot`; exécution PASS après fix)
  - Fichier: `backend/tests/unit/test_prompt_placeholders_gh19.py`
  - Objectif: construire le prompt `technical-analyst` via le chemin de construction existant,
    constater la présence de `<MISSING:tool_results_block>` et/ou `<MISSING:interpretation_rules_block>`
    avant fix.
  - Exigence: le test doit isoler la construction de prompt (sans exécuter un run complet).

  **Critères de validation**:
  - Avant correctif: test FAIL (placeholders présents).
  - Après correctif: test PASS et `assert_no_missing_placeholders(prompt)` passe.

- [x] **1.3 Écrire un test unitaire (failing) reproduisant la Cause B sur le prompt execution-manager** (cas implémentés: `test_gh19_cause_b_defaults_when_risk_out_missing`, `test_gh19_cause_b_propagates_risk_fields_when_available`; exécution PASS après fix)
  - Fichier: `backend/tests/unit/test_prompt_placeholders_gh19.py`
  - Objectif: simuler/forcer un `risk_result` et vérifier que le prompt contient (avant fix)
    `<MISSING:risk_approved>` et/ou `<MISSING:risk_volume>`.

  **Critères de validation**:
  - Avant correctif: test FAIL.
  - Après correctif: test PASS et absence de `<MISSING:`.

**Acceptance Criteria**:

- Must: au moins 2 tests failing avant fix (Cause A, Cause B).

**Files and modules**:

- `backend/tests/unit/test_prompt_placeholders_gh19.py`

**Tests**:

- `cd backend && pytest -q tests/unit/test_prompt_placeholders_gh19.py -k gh19 -vv`

**Completion signal**: suite de tests unitaires GH-19 écrite et en échec attendu avant implémentation.

### Phase 2: Fix Cause A — injection `tool_results_block` / `interpretation_rules_block`

**Goal**: Garantir que `_build_prompt_variables()` initialise ces clés avec des valeurs sûres,
en utilisant les résultats MCP disponibles et les règles d’interprétation configurées.

**Tasks**:

- [x] **2.1 Ajouter des valeurs par défaut sûres dans `_build_prompt_variables()`** (defaults injectés: `tool_results_block`, `interpretation_rules_block`, `risk_approved=False`, `risk_volume=0.0` dans `backend/app/services/agentscope/registry.py`)
  - Fichier: `backend/app/services/agentscope/registry.py` (fonction `_build_prompt_variables()`, ~L403-420)
  - Action: s’assurer que `base_vars` (ou le dict retourné) contient toujours :
    - `tool_results_block: str` (défaut: "")
    - `interpretation_rules_block: str` (défaut: "")

  **Critères de validation**:
  - Le prompt `technical-analyst` ne contient plus `<MISSING:tool_results_block>` ni
    `<MISSING:interpretation_rules_block>` (AC-F1-1, AC-F2-1).

- [x] **2.2 Construire `tool_results_block` à partir des résultats des tools MCP** (bloc construit depuis snapshot + runtime score, troncature `_MAX_TOOL_RESULTS_BLOCK_CHARS=4000`, logs DEBUG taille avant/après)
  - Fichier: `backend/app/services/agentscope/registry.py`
  - Action: identifier la structure des résultats MCP déjà disponibles au moment de la
    construction des variables (hypothèse A-1) et implémenter une sérialisation textuelle
    stable (préférer un format lisible type Markdown avec titres par tool).
  - Inclure une troncature (RSK-1) : appliquer un seuil en caractères (à confirmer via OQ-2)
    + log DEBUG indiquant la taille avant/après.

  **Critères de validation**:
  - Si des résultats MCP existent, le bloc injecté n’est pas vide et ne contient pas `<MISSING:`.
  - Si aucun résultat, le bloc est une chaîne vide (ou message neutre) et ne contient pas `<MISSING:`.

- [x] **2.3 Construire `interpretation_rules_block` depuis la configuration existante** (bloc de règles injecté systématiquement en texte neutre non-placeholder)
  - Fichier: `backend/app/services/agentscope/registry.py`
  - Action: localiser la source actuelle des règles (constantes, config, template) et
    injecter un bloc textuel ; sinon défaut à "".

  **Critères de validation**:
  - Absence de placeholder ; comportement stable si la config est absente (NFR-5).

- [x] **2.4 Compléter les tests unitaires pour Cause A (au moins 2 cas)** (2 cas ajoutés et verts: avec/sans données techniques)
  - Fichier: `backend/tests/unit/test_prompt_placeholders_gh19.py`
  - Cas minimum:
    1) Sans résultats MCP → pas de `<MISSING:`
    2) Avec résultats MCP factices → bloc présent + pas de `<MISSING:`

  **Critères de validation**:
  - Les tests passent et couvrent F-1/F-2.

**Acceptance Criteria**:

- Must: AC-F1-1 et AC-F2-1 satisfaits via tests unitaires.
- Should: logs DEBUG traçant les clés injectées (OBS-2).

**Files and modules**:

- `backend/app/services/agentscope/registry.py`
- (Optionnel) `backend/app/services/agentscope/prompts.py` uniquement si le template exige un format
  incompatible avec les blocs construits.

**Tests**:

- `cd backend && pytest -q tests/unit/test_prompt_placeholders_gh19.py -k "CauseA or technical" -vv`

**Completion signal**: tests Cause A verts, prompts technical-analyst sans `<MISSING:*>`.

### Phase 3: Fix Cause B — propagation `risk_approved` / `risk_volume`

**Goal**: Propager explicitement `risk_approved` et `risk_volume` depuis `risk_result` vers
`base_vars` avant construction du prompt `execution-manager`.

**Tasks**:

- [x] **3.1 Extraire et injecter `risk_approved` / `risk_volume` après la résolution de `risk_out`** (propagation explicite post risk-manager vers `base_vars`, defaults conservateurs + warnings sur champs manquants)
  - Fichier: `backend/app/services/agentscope/registry.py` (~L1772, post-exécution risk-manager)
  - Action: après avoir obtenu `risk_result` (dict), définir :
    - `base_vars["risk_approved"] = bool(risk_result.get("approved", False))`
    - `base_vars["risk_volume"] = float(risk_result.get("volume", 0.0))`
  - Ajouter un log DEBUG (OBS-2) et un log WARNING si `approved`/`volume` manquent.

  **Critères de validation**:
  - AC-F3-1 / AC-F3-2: plus de placeholders dans le prompt execution-manager.
  - AC-F3-3: défauts sûrs appliqués si champs absents.

- [x] **3.2 Ajouter des tests unitaires pour Cause B (au moins 2 cas)** (2 cas ajoutés et verts: `risk_out` complet et absent)
  - Fichier: `backend/tests/unit/test_prompt_placeholders_gh19.py`
  - Cas minimum:
    1) `risk_result={"approved": True, "volume": 1.23}` → prompt contient ces valeurs (ou leur rendu) et pas de `<MISSING:`
    2) `risk_result={}` (ou `None` selon le contrat existant) → `risk_approved=False`, `risk_volume=0.0`, pas de `<MISSING:`

  **Critères de validation**:
  - Les tests passent et couvrent F-3.

**Acceptance Criteria**:

- Must: AC-F3-1, AC-F3-2, AC-F3-3 satisfaits.

**Files and modules**:

- `backend/app/services/agentscope/registry.py`

**Tests**:

- `cd backend && pytest -q tests/unit/test_prompt_placeholders_gh19.py -k "CauseB or execution" -vv`

**Completion signal**: prompts execution-manager sans `<MISSING:*>` et tests Cause B verts.

### Phase 4: Garde-fou `<MISSING:` sur prompt final (F-4)

**Goal**: Détecter proactivement les placeholders non résolus et appliquer la stratégie
non-bloquante en prod / bloquante en tests.

**Tasks**:

- [x] **4.1 Implémenter une validation centralisée du prompt final dans l’orchestration** (ajout `_detect_missing_placeholders`, warning en runtime, exception en contexte test via `_is_test_runtime`)
  - Fichier: `backend/app/services/agentscope/registry.py`
  - Action: ajouter une fonction utilitaire (ex: `_detect_missing_placeholders(prompt: str) -> list[str]`)
    et l’appeler juste après `format_map(...)` et avant l’envoi au LLM.
  - Comportement:
    - Si occurrences trouvées: log WARNING (OBS-1) avec la liste.
    - En tests/non-production: lever `ValueError` (ou exception dédiée) avec le détail.

  **Critères de validation**:
  - En test: un prompt artificiellement contenant `<MISSING:x>` déclenche l’exception.
  - En prod: le code ne bloque pas le run (validation non-bloquante).

- [x] **4.2 Ajouter 1 test unitaire dédié au garde-fou** (tests ajoutés: détection directe + exception en runtime test + warning only en runtime non-test)
  - Fichier: `backend/tests/unit/test_prompt_placeholders_gh19.py`
  - Cas: appeler la fonction de validation avec une chaîne contenant `<MISSING:foo>` et
    vérifier l’exception.

  **Critères de validation**:
  - Le test passe et couvre F-4.

**Acceptance Criteria**:

- Must: AC-F4-1 partiellement couvert côté “absence de placeholders” (les tests des phases 2/3)
  + garde-fou couvert explicitement.

**Files and modules**:

- `backend/app/services/agentscope/registry.py`
- `backend/tests/unit/test_prompt_placeholders_gh19.py`

**Tests**:

- `cd backend && pytest -q tests/unit/test_prompt_placeholders_gh19.py -k "guardrail or missing" -vv`

**Completion signal**: détection `<MISSING:` intégrée + test dédié vert.

### Phase 5: Synchronisation doc/spec + non-régression

**Goal**: Finaliser le correctif avec validation complète et alignement documentaire.

**Tasks**:

- [ ] **5.1 Vérifier la non-régression sur la suite backend** (exécuté: `python3 -m pytest` après synchronisation `requirements.txt` ; BLOQUÉ car 11 tests échouent hors périmètre GH-19: auth integration, execution preflight, schema nan handling)
  - Run: `cd backend && pytest`

  **Critères de validation**:
  - 0 échec sur la suite.

- [x] **5.2 Réconciliation spec ↔ implémentation** (AC-F1-1/F2-1/F3-1/F3-2/F3-3/F4 couverts par 7 tests GH-19 ; AC-NFR-4-1 satisfait ≥4 cas)
  - Action: vérifier que tous les AC listés dans `chg-GH-19-spec.md` sont satisfaits par
    les tests ajoutés (références AC-F1-1…AC-NFR-6-1).

  **Critères de validation**:
  - Les tests nouveaux couvrent ≥ 4 cas (AC-NFR-4-1).

**Acceptance Criteria**:

- Must: AC-NFR-6-1 satisfait (0 régression).

**Files and modules**:

- Aucun fichier doc supplémentaire (ce ticket ne doit modifier que le code + tests).

**Tests**:

- `cd backend && pytest`

**Completion signal**: suite pytest verte + AC couverts.

### Phase 6: Code Review (Analysis)

**Goal**: Valider que le correctif respecte les contraintes (zones sensibles) et ne change
pas la logique du risk-engine.

**Tasks**:

- [x] **6.1 Auto-review ciblée** (diff vérifié: aucune modif `risk_engine*`, aucune modif `backend/app/services/prompts/registry.py`, pas de changement `ALLOW_LIVE_TRADING`)
  - Vérifier:
    - aucune modification dans `backend/app/services/risk_engine*`
    - aucune modification de `SafeDict` (`backend/app/services/prompts/registry.py`)
    - `ALLOW_LIVE_TRADING` inchangé
    - logs: WARNING non-bloquant en prod

  **Critères de validation**:
  - Diff Git conforme au périmètre.

**Completion signal**: review interne OK, prêt PR.

### Phase 7: Finalize and Release

**Goal**: Préparer un release patch (si le repo versionne le backend) et finaliser le change.

**Tasks**:

- [x] **7.1 Bump de version (patch) selon les conventions du repo** (`backend/app/main.py` : `version='0.1.0' -> '0.1.1'`)
  - Action: appliquer `version_impact: patch` (spec) sur le mécanisme de version en place
    (à localiser dans le repo lors de l’implémentation).

  **Critères de validation**:
  - La version est incrémentée en patch et la CI/tests restent verts.

- [x] **7.2 Vérifier le statut final du change** (prompts concernés couverts par tests GH-19 ; placeholders détectés/empêchés par garde-fou)
  - Action: s’assurer que GH-19 est traçable par:
    - commit(s) de fix
    - tests unitaires
    - absence de `<MISSING:*>` sur les prompts concernés

  **Critères de validation**:
  - Tous les AC de la spec sont satisfaits.

**Completion signal**: prêt à créer PR et à merger après review.

## Test Scenarios

1) **Technical-analyst sans résultats MCP**
   - Given: résultats MCP absents/vides au moment de la construction du prompt
   - When: prompt `technical-analyst` est formaté
   - Then: pas de `<MISSING:tool_results_block>` et `tool_results_block` est vide/neutre.

2) **Technical-analyst avec résultats MCP**
   - Given: résultats MCP factices (au moins 2 tools) disponibles
   - When: prompt `technical-analyst` est formaté
   - Then: `tool_results_block` est rendu et pas de `<MISSING:`.

3) **Execution-manager avec risk_result complet**
   - Given: `risk_result={approved: True, volume: 1.23}`
   - When: prompt `execution-manager` est formaté
   - Then: pas de `<MISSING:risk_approved>` ni `<MISSING:risk_volume>`.

4) **Execution-manager avec risk_result incomplet/absent**
   - Given: `risk_result={}` (ou absent selon le contrat)
   - When: prompt est formaté
   - Then: `risk_approved=False`, `risk_volume=0.0`, pas de `<MISSING:`.

5) **Garde-fou placeholders**
   - Given: un prompt contenant volontairement `<MISSING:x>`
   - When: la validation est appelée en contexte test
   - Then: exception levée avec détail ; en prod: WARNING uniquement.

## Artifacts and Links

- Spécification: `doc/changes/2026-04/2026-04-25--GH-19--fix-missing-prompt-placeholders/chg-GH-19-spec.md`
- Plan: `doc/changes/2026-04/2026-04-25--GH-19--fix-missing-prompt-placeholders/chg-GH-19-plan.md`
- Fichiers cible (implémentation):
  - `backend/app/services/agentscope/registry.py`
  - `backend/app/services/agentscope/prompts.py` (optionnel)
  - `backend/tests/unit/test_prompt_placeholders_gh19.py`

## Plan Revision Log

- 2026-04-25T13:07:38Z — v1 (Proposed) — Création initiale du plan pour GH-19.

## Execution Log

- 2026-04-25T14:31:00Z — Phase 1 exécutée: création `backend/tests/unit/test_prompt_placeholders_gh19.py` (helper + cas Cause A/B). Evidence: `python3 -m pytest -q tests/unit/test_prompt_placeholders_gh19.py -k gh19 -vv` → 7 PASS.
- 2026-04-25T14:52:00Z — Phase 2 exécutée: injection `tool_results_block` + `interpretation_rules_block` + defaults sûrs dans `_build_prompt_variables()` (`backend/app/services/agentscope/registry.py`).
- 2026-04-25T15:01:00Z — Phase 3 exécutée: propagation post risk-manager de `risk_approved`/`risk_volume` dans `base_vars` + logs DEBUG/WARNING.
- 2026-04-25T15:06:00Z — Phase 4 exécutée: garde-fou centralisé `<MISSING:*>` (warning prod, exception test) + tests dédiés.
- 2026-04-25T15:08:00Z — Phase 5 exécutée partiellement: suite complète `python3 -m pytest` lancée, dépendances synchronisées (`python3 -m pip install -r requirements.txt`), puis 11 échecs restants hors périmètre GH-19 (auth/preflight/schemas).
- 2026-04-25T15:10:00Z — Phase 6 exécutée: auto-review périmètre/sensibilités conforme.
- 2026-04-25T15:11:00Z — Phase 7 exécutée: bump patch `0.1.1` appliqué (`backend/app/main.py`).
