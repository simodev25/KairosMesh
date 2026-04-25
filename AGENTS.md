# AGENTS

Référence opérationnelle de la V1 pour OpenCode, avec extension V1.1 ciblée sur les skills projet.

## Cycle de delivery

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

## Règles de fonctionnement

- `@pm` orchestre, ne code pas.
- `@coder` implémente selon `chg-<workItemRef>-plan.md`.
- `@reviewer` valide contre spec + plan + règles repo.
- `@runner` exécute et journalise; `@fixer` corrige en mode root-cause.
- `@doc-syncer` met à jour la vérité documentaire courante.
- `@committer` fait un seul Conventional Commit.
- `@pr-manager` crée/met à jour la PR et s’arrête avant merge.

## Agents complémentaires

- `@architect`
- `@designer`
- `@editor`
- `@external-researcher`
- `@image-generator`
- `@image-reviewer`
- `@review-feedback-applier`
- `@toolsmith`

## Skills comportementaux obligatoires

Les agents doivent appliquer les skills sélectionnés dans `.opencode/skills/` selon le contexte:

- cadrage: `brainstorming`
- planification: `writing-plans`
- implémentation: `test-driven-development`
- debug: `systematic-debugging`
- review: `requesting-code-review`, `receiving-code-review`
- clôture: `verification-before-completion`, `finishing-a-development-branch`
- parallélisation: `dispatching-parallel-agents`

## Activation des skills projet générés

Les skills créés dans `.opencode/skills/project/` via `/generate-project-skills` doivent être utilisés automatiquement selon la phase:

- `/run-plan`: appliquer les skills projet pertinents pour implémentation/test/build/debug/architecture locale.
- `/review`: appliquer les skills projet pertinents pour review/règles locales/zones sensibles.
- `/check` et `/check-fix`: appliquer les skills projet pertinents pour quality gates, CI, build et test.

Règles d’activation:

1. scanner `.opencode/skills/project/*/SKILL.md` au démarrage de la commande,
2. sélectionner jusqu’à 2 skills les plus pertinents au contexte,
3. exécuter la commande en respectant ces skills comme contraintes locales,
4. si aucun skill pertinent n’est trouvé, continuer avec les skills génériques uniquement.

## Artifacts standards

- Spécification: `doc/changes/<yyyy-mm>/<yyyy-mm-dd>--<workItemRef>--<slug>/chg-<workItemRef>-spec.md`
- Plan implémentation: `.../chg-<workItemRef>-plan.md`
- Plan de test: `.../chg-<workItemRef>-test-plan.md`
- Notes PM: `.../chg-<workItemRef>-pm-notes.yaml`

## Commandes V1

- `/bootstrap`
- `/plan-change`
- `/write-spec <workItemRef>`
- `/write-test-plan <workItemRef>`
- `/write-plan <workItemRef>`
- `/run-plan <workItemRef>`
- `/review <workItemRef>`
- `/check`
- `/check-fix`
- `/sync-docs <workItemRef>`
- `/commit`
- `/pr`

## Extension V1.1

- `/generate-project-skills` (génération de skills projet dans `.opencode/skills/project/`)
