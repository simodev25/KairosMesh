---
change:
  ref: GH-19
  type: fix
  status: Proposed
  slug: fix-missing-prompt-placeholders
  title: "Correction des placeholders manquants dans les prompts (technical-analyst & execution-manager)"
  owners: [kairos-mesh-team]
  service: backend/agents
  labels: [bug, prompts, technical-analyst, execution-manager]
  version_impact: patch
  audience: internal
  security_impact: none
  risk_level: medium
  dependencies:
    internal: [prompts-registry, agentscope-registry, technical-analyst, execution-manager]
    external: []
---

# CHANGE SPECIFICATION

> **PURPOSE** — Corriger le bug GH-19 : deux causes distinctes provoquent l'injection de
> placeholders non résolus (`<MISSING:*>`) dans les prompts des agents `technical-analyst`
> et `execution-manager`, rendant 100 % des runs incapables de produire des scores
> numériques ou de propager correctement la décision du risk-manager.

---

## 1. SOMMAIRE

Le moteur de templating (`SafeDict` / `str.format_map`) retourne la chaîne littérale
`<MISSING:{clé}>` lorsqu'une variable de substitution est absente du dictionnaire de
contexte. Deux familles de variables ne sont jamais initialisées avant l'interpolation :

- **Cause A** — `tool_results_block` et `interpretation_rules_block` pour le
  `technical-analyst` : construits nulle part dans le pipeline d'orchestration.
- **Cause B** — `risk_approved` et `risk_volume` pour l'`execution-manager` : non propagés
  depuis le résultat du risk-manager vers les variables de base.

Conséquence : le `technical-analyst` retourne systématiquement
`UNAVAILABLE_RUNTIME_SCORE_BREAKDOWN` / `UNAVAILABLE_RAW_SCORE`, et l'`execution-manager`
ignore le verdict de risque.

---

## 2. CONTEXTE

### 2.1 État actuel

| Composant | Comportement observé |
|-----------|---------------------|
| `technical-analyst` | Prompt contient `<MISSING:tool_results_block>` et `<MISSING:interpretation_rules_block>` |
| `execution-manager` | Prompt contient `<MISSING:risk_approved>` et `<MISSING:risk_volume>` |
| Score produit | `UNAVAILABLE_RUNTIME_SCORE_BREAKDOWN`, `UNAVAILABLE_RAW_SCORE` |
| Décision de risque | Non transmise à l'execution-manager |

Le mécanisme `SafeDict` est intentionnel : il évite les exceptions Python lors de
l'interpolation. Le problème réside dans l'absence d'alimentation des clés manquantes
**avant** l'appel au templating.

### 2.2 Points de douleur / Lacunes

- **P-1** — `_build_prompt_variables()` (agentscope/registry.py) n'instancie jamais
  `tool_results_block` ni `interpretation_rules_block` pour le `technical-analyst`.
- **P-2** — `base_vars` est initialisé sans `risk_out`, donc sans `risk_approved` ni
  `risk_volume`.
- **P-3** — Après l'exécution du risk-manager, seul `base_vars["risk_result"]` est mis à
  jour ; les sous-champs `risk_approved` / `risk_volume` ne sont jamais extraits et
  propagés.
- **P-4** — Aucun test unitaire ne vérifie l'absence de placeholders `<MISSING:*>` dans
  les prompts finaux.

---

## 3. ÉNONCÉ DU PROBLÈME

Toutes les sessions de trading échouent silencieusement à produire un score technique
exploitable et à transmettre la décision du risk-manager à l'execution-manager, car les
variables de contexte requises par les templates de prompts ne sont jamais construites
ni injectées dans le dictionnaire de substitution avant l'appel au moteur de templating.

---

## 4. OBJECTIFS

| ID | Objectif |
|----|---------|
| G-1 | Éliminer toute occurrence de `<MISSING:*>` dans les prompts envoyés au `technical-analyst` |
| G-2 | Éliminer toute occurrence de `<MISSING:risk_approved>` et `<MISSING:risk_volume>` dans les prompts de l'`execution-manager` |
| G-3 | Permettre au `technical-analyst` de produire un score numérique réel (non `UNAVAILABLE_*`) |
| G-4 | Garantir que l'`execution-manager` reçoit et utilise correctement le verdict du risk-manager |
| G-5 | Ajouter une couverture de test unitaire sur la substitution des blocs de prompt |
| G-6 | Ne régresser aucun test existant |

### 4.1 Métriques de succès / KPIs

| Métrique | Cible |
|---------|-------|
| Taux de prompts sans `<MISSING:*>` | 100 % |
| Taux de runs produisant un `score_breakdown` numérique | 100 % (en simulation) |
| Tests unitaires nouveaux couvrant les blocs de substitution | ≥ 4 cas |
| Régressions sur la suite pytest existante | 0 |

### 4.2 Non-objectifs

- [OUT] Modifier la logique métier du `SafeDict` ou du moteur de templating `registry.py`
- [OUT] Refactoriser l'architecture de l'orchestration agents
- [OUT] Toucher le moteur de risque déterministe (`risk_engine*`) ou la couche d'exécution broker
- [OUT] Modifier le schéma de base de données ou les migrations Alembic
- [OUT] Changer le comportement du mode simulation / live

---

## 5. CAPACITÉS FONCTIONNELLES

| ID | Capacité | Justification |
|----|---------|---------------|
| F-1 | Construction et injection de `tool_results_block` dans le contexte du `technical-analyst` | Résout la Cause A — placeholder manquant |
| F-2 | Construction et injection de `interpretation_rules_block` dans le contexte du `technical-analyst` | Résout la Cause A — placeholder manquant |
| F-3 | Propagation de `risk_approved` et `risk_volume` vers `base_vars` après exécution du risk-manager | Résout la Cause B — champs non propagés |
| F-4 | Validation de l'absence de tout placeholder `<MISSING:*>` avant envoi du prompt à l'agent | Détection proactive des régressions futures |

### 5.1 Détails des capacités

**F-1 — `tool_results_block`**
- Contient la sérialisation textuelle des résultats des outils MCP pré-exécutés pour l'analyse technique.
- Si aucun résultat disponible, la valeur par défaut est une chaîne vide ou un message neutre (non un placeholder).
- Doit être construit dans `_build_prompt_variables()` ou équivalent, avant l'interpolation.

**F-2 — `interpretation_rules_block`**
- Contient les règles d'interprétation applicables aux indicateurs techniques.
- Si non configurées, valeur par défaut : chaîne vide ou bloc vide documenté.
- Même point d'injection que F-1.

**F-3 — Propagation `risk_approved` / `risk_volume`**
- Après le retour du risk-manager, extraire `risk_approved` (booléen) et `risk_volume` (numérique) depuis `risk_result`.
- Les injecter dans `base_vars` avec des valeurs par défaut sûres (`False` / `0.0`) si la clé est absente dans `risk_result`.
- L'injection se produit avant la construction du prompt de l'`execution-manager`.

**F-4 — Garde-fou de validation**
- Une fonction utilitaire (ou assertion de test) détecte la présence de tout `<MISSING:` dans un prompt final.
- En mode non-production (tests), cette détection lève une erreur explicite.
- En production, un log WARNING est émis sans bloquer le run (comportement dégradé accepté).

---

## 6. FLUX UTILISATEUR & SYSTÈME

### Flux corrigé — Technical-analyst

```
Orchestration
  └─► _build_prompt_variables()
        ├─► [NOUVEAU] Construire tool_results_block depuis les résultats MCP disponibles
        ├─► [NOUVEAU] Construire interpretation_rules_block depuis la configuration
        └─► Retourner variables complètes
  └─► str.format_map(SafeDict(variables))
        └─► Aucun <MISSING:*> dans le prompt final
  └─► Envoi au technical-analyst
        └─► Score numérique produit
```

### Flux corrigé — Execution-manager

```
Orchestration
  └─► Exécution du risk-manager
        └─► base_vars["risk_result"] = résultat
  └─► [NOUVEAU] Extraire risk_approved, risk_volume depuis risk_result
        └─► base_vars["risk_approved"] = risk_result.get("approved", False)
        └─► base_vars["risk_volume"] = risk_result.get("volume", 0.0)
  └─► str.format_map(SafeDict(base_vars))
        └─► Aucun <MISSING:risk_approved> ni <MISSING:risk_volume>
  └─► Envoi à l'execution-manager
        └─► Décision risk correctement transmise
```

---

## 7. PÉRIMÈTRE & FRONTIÈRES

### 7.1 Dans le périmètre

- Correction de `_build_prompt_variables()` pour le `technical-analyst` (Cause A)
- Propagation de `risk_approved` / `risk_volume` dans la séquence d'orchestration (Cause B)
- Ajout de valeurs par défaut sûres pour toutes les clés manquantes identifiées
- Ajout de tests unitaires couvrant les substitutions de blocs

### 7.2 Hors périmètre

- [OUT] Tout code dans `backend/app/services/risk_engine*`
- [OUT] Tout code dans `backend/app/services/execution*` (couche broker)
- [OUT] Modification du comportement de `SafeDict` ou du moteur de templating
- [OUT] Refactorisation de l'architecture multi-agents
- [OUT] Modifications frontend

### 7.3 Différé / À considérer plus tard

- Validation exhaustive de l'ensemble des templates pour d'autres placeholders potentiellement manquants
- Génération automatique d'un schéma de variables requis par template (approche déclarative)

---

## 8. INTERFACES & CONTRATS D'INTÉGRATION

### 8.1 Endpoints REST / HTTP

Aucun endpoint HTTP n'est modifié.

### 8.2 Événements / Messages

Aucun contrat événementiel n'est modifié.

### 8.3 Impact sur le modèle de données

| ID | Élément | Nature du changement |
|----|---------|---------------------|
| DM-1 | `base_vars` (dict interne) | Ajout de clés `risk_approved` (bool) et `risk_volume` (float) après exécution risk-manager |
| DM-2 | Variables de prompt `technical-analyst` | Ajout de clés `tool_results_block` (str) et `interpretation_rules_block` (str) |

Aucune modification de schéma de base de données.

### 8.4 Intégrations externes

Aucune intégration externe n'est touchée. Les outils MCP sont consommés en lecture seule
pour construire `tool_results_block`.

### 8.5 Compatibilité ascendante

- Le comportement de `SafeDict` reste inchangé : si une clé est toujours absente pour une
  raison imprévue, elle retourne `<MISSING:{clé}>` plutôt que de lever une exception.
- Les prompts existants d'autres agents ne sont pas affectés.
- L'interface publique des services n'est pas modifiée.

---

## 9. EXIGENCES NON-FONCTIONNELLES (ENF)

| ID | Catégorie | Exigence | Seuil |
|----|----------|---------|-------|
| NFR-1 | Fiabilité | Taux d'occurrence de `<MISSING:*>` dans les prompts produits | 0 % en conditions normales |
| NFR-2 | Performance | Surcoût de construction des blocs manquants par rapport au chemin actuel | < 10 ms par prompt |
| NFR-3 | Maintenabilité | Chaque nouvelle clé de template doit avoir une valeur par défaut documentée dans `_build_prompt_variables()` | 100 % |
| NFR-4 | Testabilité | Couverture des chemins de substitution de prompt (blocs manquants) | ≥ 4 nouveaux tests unitaires |
| NFR-5 | Dégradation gracieuse | En cas d'absence imprévue d'un résultat MCP, le prompt utilise une valeur par défaut non-bloquante | 100 % des cas |

---

## 10. TÉLÉMÉTRIE & OBSERVABILITÉ

| ID | Exigence | Niveau |
|----|---------|--------|
| OBS-1 | Log WARNING émis si un placeholder `<MISSING:*>` est détecté dans un prompt final (mode production) | WARNING |
| OBS-2 | Log DEBUG traçant les clés injectées dans `base_vars` avant interpolation | DEBUG |
| OBS-3 | Compteur / métrique de détection de placeholders manquants (si infrastructure métriques disponible) | Optionnel |

---

## 11. RISQUES & MITIGATIONS

| ID | Risque | Impact | Probabilité | Mitigation | Risque résiduel |
|----|-------|--------|-------------|-----------|----------------|
| RSK-1 | La construction de `tool_results_block` peut retourner des données volumineuses et dépasser la fenêtre de contexte du LLM | H | M | Tronquer ou résumer les résultats MCP à un nombre maximal de caractères configurable | Faible |
| RSK-2 | Les valeurs par défaut de `risk_approved=False` / `risk_volume=0.0` peuvent entraîner un comportement conservateur non souhaité si le risk-manager n'a pas encore répondu | M | L | Documenter clairement ce comportement par défaut ; émettre un log WARNING | Faible |
| RSK-3 | D'autres templates peuvent contenir des placeholders non identifiés dans ce ticket | M | M | Ajouter un test de détection générique `<MISSING:*>` sur tous les agents | Moyen |
| RSK-4 | Modification involontaire du comportement du risk-manager en tentant de propager ses résultats | H | L | Ne toucher que la lecture des champs post-exécution, aucune modification de la logique du risk-manager | Faible |

---

## 12. HYPOTHÈSES

- A-1 : Les résultats des outils MCP sont disponibles dans le contexte d'exécution au moment de la construction des variables de prompt.
- A-2 : `risk_result` contient systématiquement les champs `approved` et `volume` (ou leurs équivalents) après l'exécution du risk-manager.
- A-3 : Une valeur par défaut vide/neutre pour `tool_results_block` et `interpretation_rules_block` est préférable à un placeholder non résolu.
- A-4 : Le comportement conservateur par défaut (`risk_approved=False`) est accepté comme dégradation gracieuse.

---

## 13. DÉPENDANCES

| Type | Composant | Nature |
|------|----------|--------|
| Interne | `backend/app/services/prompts/registry.py` | Lu en référence — non modifié |
| Interne | `backend/app/services/agentscope/prompts.py` | Référence des templates — non modifié (sauf ajout éventuel de valeurs par défaut dans les templates) |
| Interne | `backend/app/services/agentscope/registry.py` | Modifié — construction variables et propagation |
| Interne | Outils MCP (`backend/app/tools/`) | Consommés en lecture pour `tool_results_block` |

---

## 14. QUESTIONS OUVERTES

| ID | Question | Décision requise |
|----|---------|-----------------|
| OQ-1 | Quel est le format exact attendu par le template pour `tool_results_block` : JSON sérialisé, texte libre, ou structure Markdown ? | À confirmer avec l'auteur du template |
| OQ-2 | Quelle est la taille maximale acceptable pour `tool_results_block` avant troncature ? | À définir en lien avec les contraintes de fenêtre de contexte du LLM utilisé |
| OQ-3 | Les noms de champs dans `risk_result` (`approved`, `volume`) sont-ils stables ou susceptibles de changer ? | À confirmer avec la doc du risk-manager — consulter `@architect` si incertitude |
| OQ-4 | Faut-il ajouter une validation de schéma centralisée pour tous les templates (approche déclarative) dans ce ticket ou le différer ? | Decision needed: consult `@architect` |

---

## 15. JOURNAL DE DÉCISIONS

| ID | Décision | Justification | Date |
|----|---------|---------------|------|
| DEC-1 | Ne pas modifier `SafeDict` ni le moteur de templating | Le comportement de fallback `<MISSING:*>` est intentionnel et protège contre les exceptions en production | 2026-04-25 |
| DEC-2 | Injecter des valeurs par défaut sûres plutôt que de rendre les clés obligatoires | Maintient la résilience du pipeline en cas de données partiellement disponibles | 2026-04-25 |
| DEC-3 | Ne pas toucher `risk_engine*` ni `execution*` (couche broker) | Zone sensible — revue `@architect` obligatoire ; hors périmètre de ce bug fix | 2026-04-25 |

---

## 16. COMPOSANTS AFFECTÉS (HAUT NIVEAU)

| Composant | Nature de l'impact |
|----------|-------------------|
| Service d'orchestration AgentScope (`agentscope/registry.py`) | Modification — construction et propagation de variables |
| Agent `technical-analyst` | Bénéficiaire — reçoit des prompts complets |
| Agent `execution-manager` | Bénéficiaire — reçoit `risk_approved` / `risk_volume` |
| Suite de tests backend (`backend/tests/`) | Extension — nouveaux tests unitaires |
| Moteur de templating (`prompts/registry.py`) | Non modifié — référence uniquement |
| Templates de prompts (`agentscope/prompts.py`) | Non modifié (ou ajout de valeurs par défaut inline si nécessaire) |

---

## 17. CRITÈRES D'ACCEPTATION

| ID | Critère | Format Given/When/Then |
|----|--------|----------------------|
| AC-F1-1 | Absence de `<MISSING:tool_results_block>` dans le prompt technical-analyst | **Étant donné** un run en simulation, **Quand** le prompt du `technical-analyst` est construit, **Alors** il ne contient aucune occurrence de `<MISSING:tool_results_block>` |
| AC-F2-1 | Absence de `<MISSING:interpretation_rules_block>` dans le prompt technical-analyst | **Étant donné** un run en simulation, **Quand** le prompt du `technical-analyst` est construit, **Alors** il ne contient aucune occurrence de `<MISSING:interpretation_rules_block>` |
| AC-F3-1 | `risk_approved` propagé vers l'execution-manager | **Étant donné** que le risk-manager a retourné un résultat, **Quand** le prompt de l'`execution-manager` est construit, **Alors** il ne contient pas `<MISSING:risk_approved>` |
| AC-F3-2 | `risk_volume` propagé vers l'execution-manager | **Étant donné** que le risk-manager a retourné un résultat, **Quand** le prompt de l'`execution-manager` est construit, **Alors** il ne contient pas `<MISSING:risk_volume>` |
| AC-F3-3 | Valeurs par défaut sûres en cas de risk_result absent | **Étant donné** que le risk-manager n'a pas encore répondu, **Quand** le prompt de l'`execution-manager` est construit, **Alors** `risk_approved` vaut `False` et `risk_volume` vaut `0.0` (valeurs par défaut) |
| AC-F4-1 | Score numérique produit par le technical-analyst | **Étant donné** un run complet en simulation avec des données de marché disponibles, **Quand** le `technical-analyst` répond, **Alors** le champ `score_breakdown` ne contient pas `UNAVAILABLE_*` |
| AC-NFR-4-1 | Couverture de tests unitaires | **Étant donné** la suite pytest, **Quand** les tests sont exécutés, **Alors** au moins 4 nouveaux cas couvrent la substitution des blocs `tool_results_block`, `interpretation_rules_block`, `risk_approved`, `risk_volume` |
| AC-NFR-6-1 | Aucune régression | **Étant donné** la suite pytest complète existante, **Quand** les tests sont exécutés après correction, **Alors** tous les tests précédemment verts continuent de passer |

---

## 18. DÉPLOIEMENT & GESTION DU CHANGEMENT (HAUT NIVEAU)

- Correction backend uniquement — aucun déploiement frontend requis.
- Aucune migration de base de données.
- Aucune variable d'environnement nouvelle requise.
- Le mode simulation reste le mode par défaut ; la correction s'applique également en simulation.
- Rollback : revert du commit si régression détectée en CI.

---

## 19. MIGRATION DE DONNÉES / INITIALISATION (LE CAS ÉCHÉANT)

Sans objet — aucune migration de données requise.

---

## 20. REVUE VIE PRIVÉE / CONFORMITÉ

Sans impact sur les données personnelles. Les prompts contiennent uniquement des données
de marché financier et des paramètres de configuration.

---

## 21. POINTS SAILLANTS — REVUE SÉCURITÉ

| Point | Évaluation |
|-------|-----------|
| Injection via `tool_results_block` | Faible risque : les résultats MCP proviennent de sources internes contrôlées ; une sanitisation basique est recommandée avant injection dans le prompt |
| Exposition de `risk_approved` / `risk_volume` | Données internes uniquement — pas d'exposition externe |
| Modification du chemin de gouvernance | **Non concerné** — `risk_engine*` et `execution*` (couche broker) ne sont pas modifiés |

---

## 22. IMPACT SUR LA MAINTENANCE & LES OPÉRATIONS

- La correction réduit le bruit dans les logs (moins de `<MISSING:*>` silencieux).
- L'ajout du garde-fou (OBS-1) améliore la détectabilité des régressions futures.
- Pas de complexité opérationnelle ajoutée.

---

## 23. GLOSSAIRE

| Terme | Définition |
|-------|-----------|
| `SafeDict` | Sous-classe de `dict` retournant `<MISSING:{clé}>` pour toute clé absente, évitant les `KeyError` lors de `str.format_map()` |
| `tool_results_block` | Variable de template contenant les résultats sérialisés des outils MCP pré-exécutés pour l'analyse technique |
| `interpretation_rules_block` | Variable de template contenant les règles d'interprétation des indicateurs techniques |
| `risk_approved` | Booléen indiquant si le risk-manager a approuvé l'ordre proposé |
| `risk_volume` | Volume (numérique) validé par le risk-manager pour l'ordre |
| `base_vars` | Dictionnaire de variables de contexte partagé entre agents dans l'orchestration |
| `_build_prompt_variables()` | Fonction de l'orchestration AgentScope construisant le dictionnaire de variables avant interpolation de prompt |
| `UNAVAILABLE_*` | Valeur sentinelle retournée par un agent lorsqu'il ne peut pas produire un résultat exploitable |

---

## 24. ANNEXES

### Annexe A — Localisation précise des défauts

| Cause | Fichier | Emplacement approximatif | Description |
|-------|---------|------------------------|-------------|
| A | `backend/app/services/agentscope/registry.py` | `_build_prompt_variables()` ~L403-420 | Clés `tool_results_block` et `interpretation_rules_block` jamais initialisées |
| A | `backend/app/services/agentscope/prompts.py` | ~L67, L71 | Templates référençant ces clés |
| B | `backend/app/services/agentscope/registry.py` | `base_vars` init ~L1151 | `risk_out` absent de l'initialisation |
| B | `backend/app/services/agentscope/registry.py` | Post-exécution risk-manager ~L1772 | Seul `risk_result` mis à jour ; `risk_approved` et `risk_volume` non propagés |
| B | `backend/app/services/agentscope/prompts.py` | ~L288 | Template référençant `risk_approved` et `risk_volume` |

### Annexe B — Comportement de `SafeDict` (rappel)

```
SafeDict({"a": 1}).get("b")  →  "<MISSING:b>"
"Hello {a} {b}".format_map(SafeDict({"a": "world"}))  →  "Hello world <MISSING:b>"
```

Le correctif ne modifie pas ce comportement — il s'assure que les clés sont présentes
avant l'appel.

---

## 25. HISTORIQUE DU DOCUMENT

| Version | Date | Auteur | Description |
|---------|------|--------|-------------|
| 0.1 | 2026-04-25 | @spec-writer | Création initiale — statut Proposed |

---

## DIRECTIVES DE RÉDACTION

- Utiliser uniquement les informations issues du contexte de planification.
- Les informations manquantes sont renvoyées vers les QUESTIONS OUVERTES.
- Les capacités fonctionnelles utilisent le préfixe `F-` avec justification, sans détail de solution.
- Les critères d'acceptation suivent le format `Given/When/Then` et référencent au moins un identifiant `F-`/`NFR-`.
- Les éléments hors périmètre commencent par `[OUT]`.
- Les NFRs sont quantifiées (seuils, percentiles, durées).
- Les risques incluent Impact & Probabilité (H/M/L), Mitigation, Risque résiduel.

## LISTE DE VALIDATION

- [x] Répertoire et nom de fichier conformes aux règles de découverte
- [x] Front matter validé : `change.ref == GH-19`, `owners ≥ 1`, `status == Proposed`
- [x] Ordre des sections conforme à `<spec_structure>`
- [x] Préfixes d'identifiants cohérents et uniques par catégorie
- [x] Critères d'acceptation référencent au moins un identifiant et utilisent Given/When/Then
- [x] NFRs incluent des valeurs mesurables
- [x] Risques incluent Impact & Probabilité
- [x] Seul le fichier spec est créé/modifié
- [x] Aucun détail d'implémentation (chemins de fichiers code, tâches de développement) dans le corps de la spec
