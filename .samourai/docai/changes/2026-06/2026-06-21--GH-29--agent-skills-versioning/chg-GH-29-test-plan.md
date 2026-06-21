---
change:
  ref: GH-29
  type: test-plan
  status: Proposed
---

# TEST PLAN — GH-29 : Versionnage des skills d'agents

## 1. Stratégie de test

### Approche
- **Tests unitaires** : couvrir le nouveau service `AgentSkillsService`, le modèle, les schemas, et l'adaptation de `resolve_skills()`
- **Tests d'intégration API** : valider les endpoints REST (CRUD + activation)
- **Tests de non-régression** : s'assurer que le pipeline d'analyse existant fonctionne sans modification
- **Tests de migration** : valider la migration Alembic (création table + data migration)

### Commande d'exécution
```bash
cd backend && pytest -q
```

### Couverture cible
- ≥ 80 % du nouveau service `AgentSkillsService`
- 100 % des endpoints REST
- 100 % des critères d'acceptation couverts

---

## 2. Matrice de couverture AC → Tests

| AC | Description | Tests |
|----|-------------|-------|
| AC-1 | Table créée avec bonnes colonnes et contraintes | T-MIG-01, T-MOD-01 |
| AC-2 | Migration crée table + migre données | T-MIG-01, T-MIG-02, T-MIG-03 |
| AC-3 | `resolve_skills()` lit depuis nouvelle table | T-SVC-01, T-SVC-02, T-SVC-03 |
| AC-4 | API REST fonctionne | T-API-01 à T-API-08 |
| AC-5 | Frontend build OK | T-FE-01 |
| AC-6 | Seed fonctionne | T-SEED-01, T-SEED-02 |
| AC-7 | Backward compat GET /connectors | T-BWC-01 |
| AC-8 | Tests unitaires service | T-SVC-* |
| AC-9 | Pipeline sans régression | T-REG-01, T-REG-02, T-REG-03 |
| AC-10 | Fallback SKILL.md | T-SVC-04 |

---

## 3. Cas de test détaillés

### 3.1 Modèle et migration (T-MIG-*)

#### T-MIG-01 — Table `agent_skills` existe avec les bonnes colonnes
- **Given** : migration Alembic exécutée
- **When** : inspecter la table `agent_skills`
- **Then** : colonnes `id`, `agent_name`, `version`, `is_active`, `skills` (JSON), `notes`, `created_by_id`, `created_at`, `updated_at` présentes
- **Then** : contrainte unique `(agent_name, version)` active

#### T-MIG-02 — Data migration : skills existantes transférées
- **Given** : `connector_configs.settings.agent_skills` contient des données pour 12 agents
- **When** : migration exécutée
- **Then** : 12 rows dans `agent_skills`, chacune version=1, is_active=True
- **Then** : le contenu `skills` (JSON array) correspond aux données source

#### T-MIG-03 — Data migration idempotente
- **Given** : migration déjà exécutée
- **When** : re-exécution tentée
- **Then** : pas de duplication, pas d'erreur

### 3.2 Service AgentSkillsService (T-SVC-*)

#### T-SVC-01 — get_active retourne la version active
- **Given** : table contient versions 1 (inactive) et 2 (active) pour `technical-analyst`
- **When** : `get_active(db, "technical-analyst")`
- **Then** : retourne version 2 avec is_active=True

#### T-SVC-02 — get_active retourne None si aucune version active
- **Given** : table vide pour `unknown-agent`
- **When** : `get_active(db, "unknown-agent")`
- **Then** : retourne None

#### T-SVC-03 — resolve_skills utilise la nouvelle table
- **Given** : `agent_skills` contient skills pour `trader-agent` version 1 active
- **When** : `AgentModelSelector.resolve_skills(db, "trader-agent")`
- **Then** : retourne les skills de la table (pas du connector JSON)

#### T-SVC-04 — Fallback SKILL.md si table vide
- **Given** : aucune row dans `agent_skills` pour `news-analyst`
- **Given** : fichier `backend/config/skills/news-analyst/SKILL.md` existe
- **When** : `resolve_skills(db, "news-analyst")`
- **Then** : retourne les skills parsées depuis le fichier SKILL.md

#### T-SVC-05 — create_version incrémente le numéro
- **Given** : version max pour `trader-agent` est 3
- **When** : `create_version(db, "trader-agent", skills=[...], notes="test")`
- **Then** : nouvelle row version=4, is_active=False

#### T-SVC-06 — activate désactive les autres versions
- **Given** : `trader-agent` a versions 1 (active), 2, 3
- **When** : `activate(db, skill_id_v3)`
- **Then** : version 1 is_active=False, version 3 is_active=True

#### T-SVC-07 — activate avec id inexistant → erreur
- **When** : `activate(db, 99999)`
- **Then** : raise NotFoundError

#### T-SVC-08 — Validation skills format
- **Given** : skills = "pas un array"
- **When** : `create_version(db, agent, skills)`
- **Then** : raise ValidationError

#### T-SVC-09 — Validation max skills par agent (12)
- **Given** : skills = [13 éléments]
- **When** : `create_version(db, agent, skills)`
- **Then** : raise ValidationError

#### T-SVC-10 — Validation max length par skill (500 chars)
- **Given** : skills = ["a" * 501]
- **When** : `create_version(db, agent, skills)`
- **Then** : raise ValidationError ou troncature documentée

### 3.3 API REST (T-API-*)

#### T-API-01 — GET /api/v1/agents/{name}/skills → liste versions
- **Given** : 3 versions pour `technical-analyst`
- **When** : `GET /api/v1/agents/technical-analyst/skills`
- **Then** : 200, array de 3 objets triés par version desc

#### T-API-02 — GET /api/v1/agents/{name}/skills?active_only=true
- **When** : `GET /api/v1/agents/technical-analyst/skills?active_only=true`
- **Then** : 200, array avec uniquement la version active

#### T-API-03 — POST /api/v1/agents/{name}/skills → créer version
- **Given** : user authentifié admin
- **When** : `POST /api/v1/agents/trader-agent/skills` body={"skills": [...], "notes": "v2"}
- **Then** : 201, nouvelle version créée, is_active=False

#### T-API-04 — POST /api/v1/agents/{name}/skills/{id}/activate
- **Given** : version 2 existe pour `trader-agent`
- **When** : `POST /api/v1/agents/trader-agent/skills/2/activate`
- **Then** : 200, version 2 active, anciennes désactivées

#### T-API-05 — POST skills → erreur 403 si non-admin
- **Given** : user avec rôle ANALYST
- **When** : `POST /api/v1/agents/trader-agent/skills`
- **Then** : 403 Forbidden

#### T-API-06 — GET skills agent inexistant → 200 array vide
- **When** : `GET /api/v1/agents/nonexistent/skills`
- **Then** : 200, array vide (pas 404)

#### T-API-07 — POST activate id inexistant → 404
- **When** : `POST /api/v1/agents/trader-agent/skills/99999/activate`
- **Then** : 404

#### T-API-08 — GET /api/v1/agents/catalog → liste tous les agents avec info skills
- **When** : `GET /api/v1/agents/catalog`
- **Then** : 200, array des 12 agents avec version active, skills count

### 3.4 Backward compatibility (T-BWC-*)

#### T-BWC-01 — GET /connectors inclut agent_skills depuis nouvelle table
- **Given** : skills dans table `agent_skills` pour 12 agents
- **When** : `GET /api/v1/connectors`
- **Then** : response.settings.agent_skills contient les skills (source = nouvelle table)

### 3.5 Seed (T-SEED-*)

#### T-SEED-01 — Seed au startup crée les skills si table vide
- **Given** : table `agent_skills` vide
- **When** : startup application
- **Then** : 12 rows créées (une par agent), version=1, is_active=True
- **Then** : contenu = données des fichiers SKILL.md

#### T-SEED-02 — Seed idempotent
- **Given** : table déjà peuplée (12 rows)
- **When** : startup application
- **Then** : aucune modification, aucune duplication

### 3.6 Non-régression (T-REG-*)

#### T-REG-01 — Pipeline analyse complet fonctionne
- **Given** : skills migrées dans la nouvelle table
- **When** : exécuter un cycle d'analyse single-agent (via benchmark)
- **Then** : l'agent reçoit ses skills correctement, output valide

#### T-REG-02 — Tests existants passent sans modification fonctionnelle
- **When** : `cd backend && pytest -q`
- **Then** : tous les tests passent (certains adaptés mais pas de changement de comportement)

#### T-REG-03 — Frontend build OK
- **When** : `cd frontend && npm run build`
- **Then** : build réussi sans erreur

### 3.7 Frontend (T-FE-*)

#### T-FE-01 — ConnectorsPage affiche skills depuis nouvelle API
- **Given** : skills dans table `agent_skills`
- **When** : ouvrir ConnectorsPage, sélectionner un agent
- **Then** : skills affichées correspondent à la version active de la nouvelle table

---

## 4. Tests existants à adapter

| Fichier | Action |
|---------|--------|
| `test_agent_model_selector.py` | Adapter pour mocker la nouvelle table au lieu de `settings.agent_skills` |
| `test_skill_bootstrap.py` | **Supprimer** — mécanisme n'existe plus |
| `test_connectors_settings_sanitization.py` | Retirer les assertions sur `agent_skills` dans settings |
| `test_prompt_registry.py` | Pas de changement (reçoit toujours une liste de skills) |
| `test_no_french_in_production.py` | Adapter si `agent-skills.json` est supprimé |

---

## 5. Nouveaux fichiers de test à créer

| Fichier | Contenu |
|---------|---------|
| `backend/tests/unit/test_agent_skills_service.py` | T-SVC-01 à T-SVC-10 |
| `backend/tests/unit/test_agent_skills_api.py` | T-API-01 à T-API-08, T-BWC-01 |
| `backend/tests/unit/test_agent_skills_seed.py` | T-SEED-01, T-SEED-02 |
| `backend/tests/unit/test_agent_skills_migration.py` | T-MIG-01 à T-MIG-03 (optionnel si couvert par intégration) |
