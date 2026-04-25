# OpenCode Usage

## Arborescence OpenCode

- Config: `.opencode/opencode.jsonc`
- Agents: `.opencode/agent/*.md`
- Commandes: `.opencode/command/*.md`
- Skills: `.opencode/skills/<skill>/SKILL.md`
- Skills projet générés: `.opencode/skills/project/<skill>/SKILL.md`

## Extension V1.1

- `/generate-project-skills` (génère des skills spécifiques au repository)

## Exécution standard (delivery)

1. `/bootstrap` (première initialisation projet)
2. `/plan-change GH-123`
3. `/write-spec GH-123`
4. `/write-test-plan GH-123`
5. `/write-plan GH-123`
6. `/run-plan GH-123`
7. `/review GH-123`
8. `/check` (ou `/check-fix`)
9. `/sync-docs GH-123`
10. `/commit`
11. `/pr`

## Règles d’utilisation

- Les arguments de commande transportent `workItemRef` et directives.
- Les commandes écrivent uniquement les artefacts attendus.
- Les skills sont appliqués par l’agent responsable de la phase.

## Débogage de workflow

- Si échec de quality gate: `/check-fix`
- Si feedback review externe: relancer `/review` puis `/run-plan`
- Si divergence docs/code: `/sync-docs`
