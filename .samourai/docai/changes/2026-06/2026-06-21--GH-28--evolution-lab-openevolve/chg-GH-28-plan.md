---
change:
  ref: GH-28
  type: implementation-plan
  status: Proposed
---

# PLAN D'IMPLÉMENTATION — GH-28 Evolution Lab (Lots C + D)

## Contraintes d'exécution

- Max 2h par tâche.
- Max 3 fichiers modifiés par commit.
- Zone critique interdite sans confirmation: `backend/app/risk/`.
- Ne jamais activer `ALLOW_LIVE_TRADING=true`.
- Validation minimale:
  - `cd backend && pytest -q`
  - `cd frontend && npm run build`

---

## Lot C — Backend (Phases 1 à 8)

### Phase 1 — Modèles DB évolution (effort total ~1h40)

- [ ] **1.1** Créer modèle `EvolutionCampaign`.
  - Fichiers: `backend/app/db/models/evolution_campaign.py`
  - Effort: 35 min

- [ ] **1.2** Créer modèle `EvolutionCandidate`.
  - Fichiers: `backend/app/db/models/evolution_candidate.py`
  - Effort: 30 min

- [ ] **1.3** Créer modèles `EvolutionCandidateEvaluation` + `EvolutionPromotion`.
  - Fichiers: `backend/app/db/models/evolution_candidate_evaluation.py`, `backend/app/db/models/evolution_promotion.py`
  - Effort: 35 min

### Phase 2 — Enregistrement modèles + schémas Pydantic (effort total ~1h45)

- [ ] **2.1** Exporter les nouveaux modèles dans `db/models/__init__.py`.
  - Fichiers: `backend/app/db/models/__init__.py`
  - Effort: 15 min

- [ ] **2.2** Créer schémas campagne (create/list/detail/cancel).
  - Fichiers: `backend/app/schemas/evolution_campaign.py`
  - Effort: 45 min

- [ ] **2.3** Créer schémas candidat/fitness/promote.
  - Fichiers: `backend/app/schemas/evolution_candidate.py`
  - Effort: 45 min

### Phase 3 — Service cœur campagnes/candidats (effort total ~2h)

- [ ] **3.1** Implémenter CRUD campagnes + transitions statut.
  - Fichiers: `backend/app/services/evolution/service.py`
  - Effort: 60 min

- [ ] **3.2** Implémenter listing candidats + fitness series.
  - Fichiers: `backend/app/services/evolution/service.py`
  - Effort: 40 min

- [ ] **3.3** Ajouter gardes bornes coût/calls/iterations.
  - Fichiers: `backend/app/services/evolution/service.py`
  - Effort: 20 min

### Phase 4 — Evaluator + Mutator (effort total ~2h)

- [ ] **4.1** Implémenter `evaluator.py` adaptateur BenchmarkEngine (5 dimensions).
  - Fichiers: `backend/app/services/evolution/evaluator.py`
  - Effort: 60 min

- [ ] **4.2** Implémenter `mutator.py` génération variantes prompts/skills via LLM.
  - Fichiers: `backend/app/services/evolution/mutator.py`
  - Effort: 45 min

- [ ] **4.3** Valider format candidats (rejet invalide).
  - Fichiers: `backend/app/services/evolution/mutator.py`
  - Effort: 15 min

### Phase 5 — Engine orchestration + migration Alembic 0015 (effort total ~2h)

- [ ] **5.1** Implémenter `engine.py` (boucle baseline→générations→évaluations).
  - Fichiers: `backend/app/services/evolution/engine.py`
  - Effort: 60 min

- [ ] **5.2** Créer migration Alembic `0015` pour 4 tables + contraintes/index.
  - Fichiers: `backend/alembic/versions/0015_evolution_lab_tables.py`
  - Effort: 45 min

- [ ] **5.3** Vérifier up/down migration localement.
  - Fichiers: `backend/alembic/versions/0015_evolution_lab_tables.py`
  - Effort: 15 min

### Phase 6 — API Evolution (effort total ~1h45)

- [ ] **6.1** Créer routes API `/api/v1/evolution/*`.
  - Fichiers: `backend/app/api/routes/evolution.py`
  - Effort: 60 min

- [ ] **6.2** Brancher router principal.
  - Fichiers: `backend/app/api/router.py`
  - Effort: 10 min

- [ ] **6.3** Ajouter contrôles RBAC mutation/promotion.
  - Fichiers: `backend/app/api/routes/evolution.py`
  - Effort: 35 min

### Phase 7 — Celery queue evolution (effort total ~1h15)

- [ ] **7.1** Créer task `run_evolution_campaign` + routage queue `evolution`.
  - Fichiers: `backend/app/tasks/evolution.py`
  - Effort: 40 min

- [ ] **7.2** Enregistrer task dans bootstrap Celery.
  - Fichiers: `backend/app/tasks/__init__.py`
  - Effort: 15 min

- [ ] **7.3** Lier service/API au déclenchement task idempotent.
  - Fichiers: `backend/app/services/evolution/service.py`, `backend/app/api/routes/evolution.py`
  - Effort: 20 min

### Phase 8 — Tests backend lot C (effort total ~2h)

- [ ] **8.1** Tests unitaires service/engine/evaluator/mutator.
  - Fichiers: `backend/tests/unit/test_evolution_service.py`, `backend/tests/unit/test_evolution_engine.py`, `backend/tests/unit/test_evolution_evaluator_mutator.py`
  - Effort: 70 min

- [ ] **8.2** Tests API endpoints evolution.
  - Fichiers: `backend/tests/unit/test_evolution_api.py`
  - Effort: 35 min

- [ ] **8.3** Exécuter `cd backend && pytest -q` et documenter résultat.
  - Fichiers: `.samourai/docai/changes/2026-06/2026-06-21--GH-28--evolution-lab-openevolve/chg-GH-28-plan.md`
  - Effort: 15 min

---

## Lot D — Frontend (Phases 9 à 12)

### Phase 9 — Routing + navigation Evolution Lab (effort total ~1h30)

- [ ] **9.1** Ajouter route lazy `/evolution-lab` dans `App.tsx`.
  - Fichiers: `frontend/src/App.tsx`
  - Effort: 25 min

- [ ] **9.2** Ajouter item nav `EVOLUTION_LAB` dans `Layout.tsx`.
  - Fichiers: `frontend/src/components/Layout.tsx`
  - Effort: 20 min

- [ ] **9.3** Créer page conteneur avec 3 tabs.
  - Fichiers: `frontend/src/pages/EvolutionLabPage.tsx`
  - Effort: 45 min

### Phase 10 — Service API frontend + formulaire campagne (effort total ~2h)

- [ ] **10.1** Créer client API evolution (campaigns/candidates/fitness/promote/cancel).
  - Fichiers: `frontend/src/services/evolutionApi.ts`
  - Effort: 50 min

- [ ] **10.2** Implémenter `AgentChip` + `CampaignForm` (defaults 100/50).
  - Fichiers: `frontend/src/components/evolution/AgentChip.tsx`, `frontend/src/components/evolution/CampaignForm.tsx`
  - Effort: 45 min

- [ ] **10.3** Implémenter `BaselinePreview` (prompts + skills depuis API).
  - Fichiers: `frontend/src/components/evolution/BaselinePreview.tsx`
  - Effort: 25 min

### Phase 11 — Visualisation et détails campagne (effort total ~2h)

- [ ] **11.1** Implémenter `CampaignCard` (sparkline + progress + statut).
  - Fichiers: `frontend/src/components/evolution/CampaignCard.tsx`
  - Effort: 35 min

- [ ] **11.2** Implémenter `CampaignDetail` (Recharts fitness + leaderboard + generation log).
  - Fichiers: `frontend/src/components/evolution/CampaignDetail.tsx`
  - Effort: 60 min

- [ ] **11.3** Implémenter `PromptDiffViewer` side-by-side baseline/candidat.
  - Fichiers: `frontend/src/components/evolution/PromptDiffViewer.tsx`
  - Effort: 25 min

### Phase 12 — Promotion UX + validations frontend (effort total ~1h45)

- [ ] **12.1** Implémenter `PromoteButton` avec dialog confirmation.
  - Fichiers: `frontend/src/components/evolution/PromoteButton.tsx`
  - Effort: 35 min

- [ ] **12.2** Gérer états loading/empty/error sur page et composants clés.
  - Fichiers: `frontend/src/pages/EvolutionLabPage.tsx`, `frontend/src/components/evolution/CampaignDetail.tsx`
  - Effort: 40 min

- [ ] **12.3** Vérifier style hacker/terminal + accessibilité clavier/contraste.
  - Fichiers: `frontend/src/pages/EvolutionLabPage.tsx`, `frontend/src/components/evolution/*.tsx`
  - Effort: 20 min

- [ ] **12.4** Exécuter `cd frontend && npm run build` et documenter résultat.
  - Fichiers: `.samourai/docai/changes/2026-06/2026-06-21--GH-28--evolution-lab-openevolve/chg-GH-28-plan.md`
  - Effort: 10 min

---

## Phase finale — Cleanup & clôture technique (effort total ~45 min)

- [ ] **13.1** Vérifier absence d'impact hors scope (risk engine/live trading).
  - Fichiers: audit global
  - Effort: 15 min

- [ ] **13.2** Vérifier cohérence docs de changement (spec/test-plan/plan).
  - Fichiers: `chg-GH-28-spec.md`, `chg-GH-28-test-plan.md`, `chg-GH-28-plan.md`
  - Effort: 15 min

- [ ] **13.3** Préparer note de livraison GH-28 (résultat validations + risques résiduels).
  - Fichiers: `chg-GH-28-plan.md` (Execution log)
  - Effort: 15 min

---

## Plan revision log

- 2026-06-21: version initiale du plan GH-28 structurée en 12 phases (Lot C 1-8, Lot D 9-12) + clôture.
