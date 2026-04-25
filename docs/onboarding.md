# Onboarding

## 1. Installer le kit Samourai dans le projet cible

### Installation standard

```bash
/path/to/samourai-devkit/scripts/install-samourai.sh --target /path/to/target-project
```

Ce script:

1. installe OpenCode via:
   `curl -fsSL https://opencode.ai/install | bash`
2. copie les artefacts Samourai dans le projet cible
3. crée un état local d’installation dans `.samourai/install/`

### Vérification rapide

Dans le projet cible, vérifier la présence de:

- `.opencode/agent/`
- `.opencode/command/`
- `.opencode/skills/`
- `.opencode/opencode.jsonc`
- `governance/`
- `templates/`
- `.samourai/install/installed-files.txt`

## 2. Comprendre où les fichiers sont copiés

Le script installe les éléments du kit dans:

- `AGENTS.md`
- `docs/operating-model.md`
- `docs/onboarding.md`
- `docs/opencode-usage.md`
- `docs/generate-project-skills.md`
- `governance/lifecycle/*`
- `governance/policies/*`
- `governance/conventions/*`
- `templates/*`
- `.opencode/README.md`
- `.opencode/opencode.jsonc`
- `.opencode/agent/*.md`
- `.opencode/command/*.md`
- `.opencode/skills/*/SKILL.md`
- `.opencode/skills/project/README.md`

## 3. Démarrer un changement

1. Lancer `/bootstrap` pour initialiser l’onboarding agentique du projet.
2. (Optionnel recommandé) lancer `/generate-project-skills` pour créer les skills locaux du repo.
3. Créer/identifier un `workItemRef` (`GH-123`, `PDEV-456`, etc.)
4. Lancer `/plan-change <workItemRef>`
5. Enchaîner `/write-spec`, `/write-test-plan`, `/write-plan`
6. Exécuter `/run-plan <workItemRef>`
7. Valider `/review`, `/check` ou `/check-fix`
8. Lancer `/sync-docs`, `/commit`, `/pr`

## 4. Désinstaller proprement

```bash
/path/to/samourai-devkit/scripts/uninstall-samourai.sh --target /path/to/target-project
```

Le script de désinstallation:

- retire uniquement les fichiers tracés dans `.samourai/install/installed-files.txt`
- nettoie uniquement les dossiers devenus vides
- ne supprime rien de non tracé

Mode prévisualisation:

```bash
/path/to/samourai-devkit/scripts/uninstall-samourai.sh --target /path/to/target-project --dry-run
```

## 5. Discipline minimale

- Pas de code sans plan.
- Pas de plan sans spec.
- Pas de clôture sans preuves de test.
- Pas de PR sans review locale.
