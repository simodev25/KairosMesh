---
change:
  ref: GH-29
  type: implementation-plan
  status: Proposed
---

# PLAN D'IMPLÉMENTATION — GH-29 : Versionnage des skills d'agents

## Contraintes

- Max 2h par tâche
- Max 3 fichiers modifiés par commit
- Commande test : `cd backend && pytest -q`
- Commande build frontend : `cd frontend && npm run build`

---

## Phase 1 — Modèle et schéma DB (effort : ~1h30)

- [x] **1.1** Créer le modèle SQLAlchemy `AgentSkill` (ajout `backend/app/db/models/agent_skill.py`, contraintes+index implémentés)
  - Fichier : `backend/app/db/models/agent_skill.py`
  - Colonnes : id, agent_name, version, is_active, skills (JSON), notes, created_by_id, created_at, updated_at
  - Contrainte unique : (agent_name, version)
  - Index : agent_name + is_active
  - Effort : 30 min

- [x] **1.2** Enregistrer le modèle dans `__init__.py` (import + `__all__` mis à jour)
  - Fichier : `backend/app/db/models/__init__.py`
  - Effort : 10 min

- [x] **1.3** Créer les schemas Pydantic (ajout `backend/app/schemas/agent_skill.py`, validations max 12/max 500)
  - Fichier : `backend/app/schemas/agent_skill.py`
  - Schemas : `AgentSkillCreateRequest`, `AgentSkillOut`, `AgentSkillListOut`
  - Validation : max 12 skills, max 500 chars par skill
  - Effort : 30 min

---

## Phase 2 — Service CRUD + versioning (effort : ~2h)

- [ ] **2.1** Créer le service `AgentSkillsService`
  - Fichier : `backend/app/services/skills/__init__.py`
  - Fichier : `backend/app/services/skills/service.py`
  - Méthodes : `get_active()`, `list_versions()`, `create_version()`, `activate()`, `seed_defaults()`
  - Pattern identique à `PromptTemplateService`
  - Effort : 1h30

- [ ] **2.2** Écrire les tests unitaires du service
  - Fichier : `backend/tests/unit/test_agent_skills_service.py`
  - Couvre : T-SVC-01 à T-SVC-10
  - Effort : 1h

---

## Phase 3 — Migration Alembic + data migration (effort : ~1h30)

- [ ] **3.1** Créer la migration Alembic
  - Fichier : `backend/alembic/versions/0014_agent_skills_table.py`
  - Opérations : CREATE TABLE + data migration depuis connector_configs.settings.agent_skills
  - Pour chaque agent dans le JSON : INSERT version=1, is_active=True
  - Effort : 1h

- [ ] **3.2** Tester la migration (up et down)
  - Vérifier : 12 rows créées, données correctes
  - Effort : 30 min

---

## Phase 4 — API REST (effort : ~1h30)

- [ ] **4.1** Créer les routes REST
  - Fichier : `backend/app/api/routes/agent_skills.py`
  - Endpoints :
    - `GET /api/v1/agents/{agent_name}/skills` — liste versions (filtre active_only)
    - `POST /api/v1/agents/{agent_name}/skills` — nouvelle version (Admin)
    - `POST /api/v1/agents/{agent_name}/skills/{skill_id}/activate` — activer (Admin)
    - `GET /api/v1/agents/catalog` — liste agents avec info skills
  - Effort : 1h

- [ ] **4.2** Enregistrer les routes dans le router
  - Fichier : `backend/app/api/router.py`
  - Effort : 10 min

- [ ] **4.3** Écrire les tests API
  - Fichier : `backend/tests/unit/test_agent_skills_api.py`
  - Couvre : T-API-01 à T-API-08
  - Effort : 1h

---

## Phase 5 — Adaptation de `resolve_skills()` (effort : ~1h30)

- [ ] **5.1** Modifier `AgentModelSelector.resolve_skills()`
  - Fichier : `backend/app/services/llm/model_selector.py`
  - Changement : lire depuis table `agent_skills` au lieu de `settings.agent_skills`
  - Conserver le fallback SKILL.md si table vide pour l'agent
  - Adapter le cache (TTL séparé ou invalidation)
  - Effort : 1h

- [ ] **5.2** Adapter les tests de `model_selector`
  - Fichier : `backend/tests/unit/test_agent_model_selector.py`
  - Mocker la nouvelle table au lieu de `settings.agent_skills`
  - Effort : 30 min

---

## Phase 6 — Seed au startup (effort : ~1h)

- [ ] **6.1** Modifier `main.py` : remplacer bootstrap par seed
  - Fichier : `backend/app/main.py`
  - Supprimer l'appel à `bootstrap_agent_skills_into_settings()`
  - Ajouter `AgentSkillsService.seed_defaults(db)` au startup
  - Le seed lit les fichiers SKILL.md et crée version 1 si la table est vide pour l'agent
  - Effort : 30 min

- [ ] **6.2** Écrire les tests de seed
  - Fichier : `backend/tests/unit/test_agent_skills_seed.py`
  - Couvre : T-SEED-01, T-SEED-02
  - Effort : 30 min

---

## Phase 7 — Backward compatibility connectors (effort : ~45 min)

- [ ] **7.1** Adapter GET /connectors pour servir skills depuis nouvelle table
  - Fichier : `backend/app/api/routes/connectors.py`
  - Dans le GET : lire les skills actives depuis `agent_skills` et les injecter dans `settings.agent_skills` de la réponse
  - Retirer la normalisation `_normalize_agent_skills()` et le bootstrap dans cette route
  - Effort : 30 min

- [ ] **7.2** Adapter les tests connectors
  - Fichier : `backend/tests/unit/test_connectors_settings_sanitization.py`
  - Retirer les assertions sur `agent_skills` dans settings comme source de vérité
  - Effort : 15 min

---

## Phase 8 — Suppression du bootstrap (effort : ~45 min)

- [ ] **8.1** Supprimer `skill_bootstrap.py`
  - Fichier à supprimer : `backend/app/services/llm/skill_bootstrap.py`
  - Effort : 5 min

- [ ] **8.2** Supprimer les variables d'env bootstrap
  - Fichiers : `backend/app/core/config.py`, `backend/.env`, `backend/.env.example`, `.env.prod.example`
  - Retirer : `AGENT_SKILLS_BOOTSTRAP_FILE`, `AGENT_SKILLS_BOOTSTRAP_MODE`, `AGENT_SKILLS_BOOTSTRAP_APPLY_ONCE`
  - Effort : 15 min

- [ ] **8.3** Supprimer/adapter les tests du bootstrap
  - Fichier à supprimer : `backend/tests/unit/test_skill_bootstrap.py`
  - Effort : 5 min

- [ ] **8.4** Nettoyer les imports et références
  - Fichiers : tout import de `skill_bootstrap` dans le codebase
  - Effort : 15 min

---

## Phase 9 — Adaptation frontend (effort : ~2h)

- [ ] **9.1** Ajouter le service API skills dans le frontend
  - Fichier : `frontend/src/services/api.ts` (ou nouveau fichier dédié)
  - Fonctions : `getAgentSkills()`, `createSkillVersion()`, `activateSkill()`
  - Effort : 30 min

- [ ] **9.2** Adapter ConnectorsPage pour utiliser la nouvelle API
  - Fichier : `frontend/src/pages/ConnectorsPage.tsx`
  - Remplacer la lecture de `settings.agent_skills` par appel à la nouvelle API
  - Remplacer l'écriture via PUT connector par POST nouvelle version
  - Effort : 1h30

- [ ] **9.3** Vérifier le build frontend
  - Commande : `cd frontend && npm run build`
  - Effort : 10 min

---

## Phase 10 — Tests de non-régression et cleanup (effort : ~1h)

- [ ] **10.1** Exécuter la suite de tests complète backend
  - Commande : `cd backend && pytest -q`
  - Corriger les échecs résiduels
  - Effort : 30 min

- [ ] **10.2** Vérifier le lint `test_no_french_in_production.py`
  - Adapter si `agent-skills.json` est conservé ou supprimé
  - Effort : 15 min

- [ ] **10.3** Cleanup final
  - Supprimer `agent_skills_bootstrap_meta` du JSON connector si plus utilisé
  - Vérifier qu'aucun import cassé ne subsiste
  - Effort : 15 min

---

## Résumé des phases

| Phase | Description | Effort estimé |
|-------|-------------|---------------|
| 1 | Modèle et schéma DB | 1h30 |
| 2 | Service CRUD + versioning | 2h |
| 3 | Migration Alembic + data | 1h30 |
| 4 | API REST | 1h30 |
| 5 | Adaptation resolve_skills() | 1h30 |
| 6 | Seed au startup | 1h |
| 7 | Backward compat connectors | 45 min |
| 8 | Suppression bootstrap | 45 min |
| 9 | Adaptation frontend | 2h |
| 10 | Non-régression et cleanup | 1h |
| **TOTAL** | | **~14h (2-3 jours)** |

---

## Ordre des commits recommandé

1. Phase 1 (modèle + schemas)
2. Phase 2 (service + tests)
3. Phase 3 (migration Alembic)
4. Phase 4 (API + tests)
5. Phase 5 (adaptation model_selector + tests)
6. Phase 6 (seed startup + tests)
7. Phase 7 (backward compat connectors)
8. Phase 8 (suppression bootstrap)
9. Phase 9 (frontend)
10. Phase 10 (non-régression + cleanup)
