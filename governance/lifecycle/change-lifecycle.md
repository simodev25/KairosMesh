# Change Lifecycle

## Vue d’ensemble

Cycle V1 orienté delivery incrémental, dérivé d’ADOS:

1. Cadrer
2. Spécifier
3. Planifier les tests
4. Planifier l’implémentation
5. Implémenter
6. Revoir
7. Qualifier
8. Synchroniser la doc
9. Committer
10. Ouvrir PR

## Entrées et sorties par phase

### 1) Cadrer (`@pm`)

- Entrée: demande utilisateur + backlog
- Sortie: périmètre clair + `workItemRef`

### 2) Spécifier (`@spec-writer`)

- Entrée: contexte cadré
- Sortie: `chg-<workItemRef>-spec.md`

### 3) Plan de test (`@test-plan-writer`)

- Entrée: spec
- Sortie: `chg-<workItemRef>-test-plan.md`

### 4) Plan d’implémentation (`@plan-writer`)

- Entrée: spec + test plan
- Sortie: `chg-<workItemRef>-plan.md`

### 5) Exécution (`@coder`)

- Entrée: plan validé
- Sortie: code + tâches cochées + preuves d’exécution

### 6) Review (`@reviewer`)

- Entrée: diff + spec + plan
- Sortie: findings (ou validation)

### 7) Quality gates (`@runner`/`@fixer`)

- Entrée: build/test/lint scripts
- Sortie: état qualité final (pass/fail)

### 8) Sync docs (`@doc-syncer`)

- Entrée: changement implémenté
- Sortie: docs système alignées

### 9) Commit (`@committer`)

- Entrée: modifications prêtes
- Sortie: un commit Conventional Commits

### 10) PR (`@pr-manager`)

- Entrée: branche prête
- Sortie: PR ouverte/à jour, prête pour review humaine
