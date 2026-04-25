# Plan de tests — GH-19 : Fix placeholders <MISSING:*>

## Objectif
Valider la correction du bug GH-19 pour garantir que les placeholders `<MISSING:*>` ne remontent plus dans les prompts LLM, en couvrant les deux causes racines : (A) blocs `tool_results_block` / `interpretation_rules_block` non construits dans `_build_prompt_variables()`, et (B) variables `risk_approved` / `risk_volume` non propagées dans `base_vars` après exécution du risk-manager.

## Périmètre de test
- `backend/app/services/agentscope/registry.py`
- `backend/app/services/agentscope/prompt_renderer.py` (ou module de rendu de prompt équivalent)
- `backend/app/services/risk_manager.py` (ou flux de résolution `risk_out` équivalent)
- `backend/tests/unit/services/agentscope/test_registry_prompt_variables.py`
- `backend/tests/unit/services/agentscope/test_prompt_rendering_missing_placeholders.py`

## Cas de tests

### TC-01 — Présence de `tool_results_block` dans `base_vars`
- **Précondition :** un contexte agent est initialisé avec au moins un résultat d’outil simulé (mock tool output).
- **Action :** appeler `_build_prompt_variables()` depuis `registry.py`.
- **Résultat attendu :** la clé `tool_results_block` est présente dans `base_vars` et contient une chaîne non vide formatée pour le prompt.
- **Fichier cible :** `backend/tests/unit/services/agentscope/test_registry_prompt_variables.py`

### TC-02 — Présence de `interpretation_rules_block` dans `base_vars`
- **Précondition :** un contexte agent standard est disponible avec règles d’interprétation chargées.
- **Action :** appeler `_build_prompt_variables()`.
- **Résultat attendu :** la clé `interpretation_rules_block` est présente dans `base_vars`, avec un contenu textuel prêt à l’injection template.
- **Fichier cible :** `backend/tests/unit/services/agentscope/test_registry_prompt_variables.py`

### TC-03 — Propagation de `risk_approved` après résolution de `risk_out`
- **Précondition :** un `risk_out` mocké est fourni avec `approved=True`.
- **Action :** exécuter le flux qui fusionne la sortie risk-manager dans `base_vars`.
- **Résultat attendu :** `base_vars["risk_approved"]` existe et vaut `True` (ou valeur équivalente normalisée attendue par les templates).
- **Fichier cible :** `backend/tests/unit/services/agentscope/test_registry_prompt_variables.py`

### TC-04 — Propagation de `risk_volume` après résolution de `risk_out`
- **Précondition :** un `risk_out` mocké est fourni avec un volume explicite (ex. `0.25`).
- **Action :** exécuter le flux de propagation vers `base_vars`.
- **Résultat attendu :** `base_vars["risk_volume"]` existe et reflète la valeur issue de `risk_out` sans perte de précision significative.
- **Fichier cible :** `backend/tests/unit/services/agentscope/test_registry_prompt_variables.py`

### TC-05 — Absence de `<MISSING:*>` dans le prompt `technical-analyst`
- **Précondition :** toutes les variables attendues par le template `technical-analyst` sont injectées (incluant les nouvelles clés corrigées).
- **Action :** rendre le prompt final `technical-analyst` via le renderer de templates.
- **Résultat attendu :** le prompt rendu ne contient aucune occurrence du pattern `<MISSING:.*>`.
- **Fichier cible :** `backend/tests/unit/services/agentscope/test_prompt_rendering_missing_placeholders.py`

### TC-06 — Absence de `<MISSING:*>` dans le prompt `execution-manager`
- **Précondition :** un scénario décisionnel complet est simulé avec passage par le risk-manager.
- **Action :** rendre le prompt final `execution-manager`.
- **Résultat attendu :** aucune occurrence `<MISSING:.*>` n’apparaît dans la chaîne finale du prompt.
- **Fichier cible :** `backend/tests/unit/services/agentscope/test_prompt_rendering_missing_placeholders.py`

### TC-07 — Valeurs par défaut si aucun résultat tool disponible
- **Précondition :** aucun résultat d’outil n’est fourni (liste vide / `None`).
- **Action :** appeler `_build_prompt_variables()` en mode « no tools ».
- **Résultat attendu :** `tool_results_block` et `interpretation_rules_block` sont tout de même définis avec des valeurs par défaut sûres (ex. texte neutre), sans générer de placeholder `<MISSING:*>`.
- **Fichier cible :** `backend/tests/unit/services/agentscope/test_registry_prompt_variables.py`

### TC-08 — Non-régression des tests existants liés au registry/prompting
- **Précondition :** la suite de tests unitaires existante du module agentscope est disponible.
- **Action :** exécuter les tests existants impactés par la zone modifiée (`registry`, rendering prompts, risk propagation).
- **Résultat attendu :** aucun test historique ne casse ; les nouveaux tests passent avec la même configuration.
- **Fichier cible :** `backend/tests/unit/services/agentscope/test_registry_prompt_variables.py`

## Non-régression
Exécuter les tests unitaires de la zone `backend/tests/unit/services/agentscope/` ainsi que les tests existants dépendant des variables de prompt et du résultat risk-manager. Vérifier explicitement qu’aucun prompt rendu (au minimum `technical-analyst` et `execution-manager`) ne contient `<MISSING:*>` et que les comportements précédents non liés à GH-19 restent inchangés.
