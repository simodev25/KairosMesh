# AGENTS — Kairos Mesh

Référence opérationnelle ADOS V1 pour le projet **Kairos Mesh**.

> **Politique de langue :** Tous les agents communiquent **exclusivement en français**.
> Les artefacts générés (specs, plans, messages de commit, PR) sont rédigés en français.

---

## Présentation du projet

Kairos Mesh est un système de recherche de trading open-source piloté par 8 agents IA
spécialisés. Il orchestre un pipeline déterministe à 4 phases :

1. **Analyse** — 3 agents parallèles : indicateurs techniques, sentiment news, contexte macro
2. **Débat** — chercheur haussier vs baissier, modéré par l'agent Trader
3. **Décision** — l'agent Trader produit BUY / SELL / HOLD avec entrée, SL et TP
4. **Gouvernance** — moteur de risque déterministe + préflight avant tout ordre

**Important :** Le mode simulation est le mode par défaut. Le trading live est désactivé
par défaut (`ALLOW_LIVE_TRADING=false`).

---

## Structure du monorepo

```
MultiAgentTrading/
├── backend/          # Python · FastAPI · AgentScope · MCP tools
│   ├── app/          # Code applicatif principal
│   │   ├── agents/   # 8 agents IA (AgentScope)
│   │   ├── api/      # Endpoints FastAPI
│   │   ├── models/   # SQLAlchemy models
│   │   ├── services/ # Business logic & pipeline
│   │   └── tools/    # 18 outils MCP
│   ├── tests/        # pytest
│   └── alembic/      # Migrations DB
├── frontend/         # React · TypeScript · Vite · MUI · Tailwind
│   ├── src/
│   └── tests/        # Playwright E2E
├── infra/            # Docker · Helm
│   ├── docker/
│   └── helm/
├── docs/             # Documentation opérationnelle
└── doc/              # Artefacts ADOS (specs, plans, changes)
```

---

## Stack technique

| Couche | Technologies |
|--------|-------------|
| Backend | Python, FastAPI, SQLAlchemy, Alembic, Celery, Redis |
| Agents IA | AgentScope, LangChain, Ollama, MCP (fastmcp) |
| Frontend | React, TypeScript, Vite, MUI, TailwindCSS |
| Infra | Docker Compose, Helm |
| Tests | pytest (backend), Playwright (frontend E2E) |
| Broker | MetaAPI (paper & live — désactivé par défaut) |

---

## Cycle de delivery ADOS

0. `onboarding` (si nécessaire) → `@bootstrapper`
1. `clarify_scope` → `@pm`
2. `specification` → `@spec-writer`
3. `test_planning` → `@test-plan-writer`
4. `implementation_planning` → `@plan-writer`
5. `implementation` → `@coder`
6. `review` → `@reviewer`
7. `quality_gates` → `@runner` puis `@fixer` si échec
8. `docs_sync` → `@doc-syncer`
9. `commit` → `@committer`
10. `pr_creation` → `@pr-manager`

---

## Règles de fonctionnement

- `@pm` orchestre depuis `.ai/agent/pm-instructions.md` — ne code pas.
- `@coder` implémente selon `chg-<workItemRef>-plan.md` ; ne modifie pas le moteur de risque sans validation `@architect`.
- `@reviewer` valide contre spec + plan + règles repo, avec attention particulière sur la couche gouvernance.
- `@runner` exécute `pytest` et journalise ; `@fixer` corrige en mode root-cause.
- `@doc-syncer` met à jour la vérité documentaire courante.
- `@committer` fait un seul Conventional Commit (en français).
- `@pr-manager` crée/met à jour la PR via `gh` CLI et s'arrête avant merge.

### Zones sensibles — revue obligatoire par `@architect`

- `backend/app/services/risk_engine*` — moteur de risque déterministe
- `backend/app/services/execution*` — couche d'exécution broker
- Tout changement touchant `ALLOW_LIVE_TRADING`

---

## Agents complémentaires

- `@architect` — décisions architecturales, ADR
- `@designer` — UI/UX dashboard React
- `@editor` — copywriting, traduction
- `@external-researcher` — recherche externe (MCP context7, perplexity)
- `@image-reviewer` — analyse screenshots dashboard
- `@review-feedback-applier` — application feedback PR

---

## Skills comportementaux obligatoires

Les agents appliquent les skills de `.opencode/skills/` selon le contexte :

| Phase | Skill |
|-------|-------|
| Cadrage | `brainstorming` |
| Planification | `writing-plans` |
| Implémentation | `test-driven-development` |
| Debug | `systematic-debugging` |
| Review | `requesting-code-review`, `receiving-code-review` |
| Clôture | `verification-before-completion`, `finishing-a-development-branch` |
| Parallélisation | `dispatching-parallel-agents` |

## Activation des skills projet générés

Les skills créés dans `.opencode/skills/project/` via `/generate-project-skills` doivent être utilisés automatiquement selon la phase :

- `/run-plan` : appliquer les skills projet pertinents pour implémentation/test/build/debug/architecture locale.
- `/review` : appliquer les skills projet pertinents pour review/règles locales/zones sensibles.
- `/check` et `/check-fix` : appliquer les skills projet pertinents pour quality gates, CI, build et test.

Règles d'activation :

1. Scanner `.opencode/skills/project/*/SKILL.md` au démarrage de la commande.
2. Sélectionner jusqu'à 2 skills les plus pertinents au contexte.
3. Exécuter la commande en respectant ces skills comme contraintes locales.
4. Si aucun skill pertinent n'est trouvé, continuer avec les skills génériques uniquement.

---

## Quality gates

Avant tout merge, les gates suivants doivent passer :

```bash
# Backend
cd backend && pytest

# Frontend (build de production)
cd frontend && npm run build
```

---

## Artefacts standards

| Artefact | Chemin |
|----------|--------|
| Spécification | `doc/changes/<yyyy-mm>/<yyyy-mm-dd>--<workItemRef>--<slug>/chg-<workItemRef>-spec.md` |
| Plan d'implémentation | `.../chg-<workItemRef>-plan.md` |
| Plan de test | `.../chg-<workItemRef>-test-plan.md` |
| Notes PM | `.../chg-<workItemRef>-pm-notes.yaml` |

---

## Commandes ADOS

`/bootstrap` · `/plan-change` · `/write-spec` · `/write-test-plan` · `/write-plan`
`/run-plan` · `/review` · `/check` · `/check-fix` · `/sync-docs` · `/commit` · `/pr`
`/generate-project-skills`
