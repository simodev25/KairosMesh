# Artifacts Convention

## Format de référence

`doc/changes/YYYY-MM/YYYY-MM-DD--<workItemRef>--<slug>/`

## Fichiers obligatoires

- `chg-<workItemRef>-spec.md`
- `chg-<workItemRef>-plan.md`
- `chg-<workItemRef>-test-plan.md`
- `chg-<workItemRef>-pm-notes.yaml`

## Principes

- Un seul `workItemRef` par dossier de changement.
- Les artefacts sont la source de vérité opérationnelle du changement.
- La doc système (`doc/spec/**`) est la vérité produit courante après `/sync-docs`.
