# Generate Project Skills

## Pourquoi cette commande existe

La V1 couvre le delivery end-to-end avec des agents et des skills génériques.
La commande `/generate-project-skills` ajoute une couche V1.1 ciblée:

- détecter les conventions locales du repository,
- générer un petit nombre de skills projet utiles,
- stocker ces skills dans `.opencode/skills/project/`.

Objectif: accélérer l’exécution dans un repo donné, sans refonte globale du kit.

## Commande

```text
/generate-project-skills [directives]
```

Directives supportées:

- `dry run` / `preview only`: analyse sans écriture
- `refresh`: autorise l’écrasement des skills projet existants
- `max=<n>`: limite de génération (1..3, défaut 3)
- `focus=<csv>`: priorités (`run,test,architecture,build,review,debug,migration,ci`)

## Sources inspectées

La commande s’appuie sur les signaux les plus utiles du repo:

- `README*`
- `docs/**`
- `scripts/**`
- `Makefile`
- `package.json`
- `pyproject.toml`
- CI (`.github/workflows/**`, `.gitlab-ci.yml`, etc.)
- arborescence et conventions visibles

## Règles de génération

- Générer peu de skills (2-3, jamais plus de 3)
- Favoriser la valeur opérationnelle immédiate
- Exiger des ancrages concrets (fichiers, commandes, conventions locales)
- Éviter tout contenu vague ou générique

## Format attendu d’un skill projet

Chemin:

```text
.opencode/skills/project/<skill-name>/SKILL.md
```

Contenu minimal:

- front matter `name`, `description`
- `## When to use`
- `## Inputs`
- `## Procedure`
- `## Validation`
- `## Source Anchors`

## Exemples d’usage

```text
/generate-project-skills
/generate-project-skills max=2
/generate-project-skills dry run
/generate-project-skills refresh focus=test,ci
```

## Quand les skills sont utilisés

Après génération, les skills projet sont consommés automatiquement par:

- `/run-plan` (implémentation, test, build, debug, conventions locales),
- `/review` (règles de review locales et zones sensibles),
- `/check` et `/check-fix` (quality gates, CI, build, test).

Comportement standard:

1. la commande scanne `.opencode/skills/project/*/SKILL.md`,
2. elle sélectionne jusqu’à 2 skills pertinents,
3. elle applique ces skills comme contraintes locales d’exécution.

## Bonnes pratiques

- Lancer une première passe après `/bootstrap` sur un nouveau projet.
- Relancer quand le workflow projet change significativement (CI, build, conventions).
- Garder les skills projet courts, précis, et maintenus comme documentation active.
