# Operating Model V1

## Principes

- Spec-driven delivery: une spec validée précède l’implémentation.
- Traçabilité: toute action est rattachée à un `workItemRef`.
- Gates explicites: passage de phase conditionné par preuves.
- Vérification avant annonce: aucune déclaration de réussite sans exécution réelle.

## Modèle de pilotage

### Entrée

- ticket/backlog identifié (`workItemRef`)
- contexte produit et contraintes connues

### Processus

1. Cadrage interactif (`@pm`, skill `brainstorming`)
2. Production spec (`@spec-writer`)
3. Production test plan (`@test-plan-writer`)
4. Production implementation plan (`@plan-writer`, skill `writing-plans`)
5. Exécution plan (`@coder`, skill `test-driven-development`)
6. Review locale (`@reviewer`, skill `requesting-code-review`)
7. Gates qualité (`@runner` + `@fixer`, skill `systematic-debugging`)
8. Sync documentation (`@doc-syncer`)
9. Commit (`@committer`)
10. PR (`@pr-manager`, skill `finishing-a-development-branch`)

### Sortie

- branche prête à review humaine
- PR ouverte et description alignée
- artefacts de changement à jour

## Contrôles

- Voir [change-lifecycle](../governance/lifecycle/change-lifecycle.md)
- Voir [stage-gates](../governance/lifecycle/stage-gates.md)
- Voir politiques `governance/policies/*.yaml`
