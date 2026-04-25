# PR Instructions — Kairos Mesh

> **Langue :** Tous les titres et descriptions de PR sont rédigés en **français**.

Ce fichier configure la façon dont l'agent `@pr-manager` interagit avec GitHub
pour créer et mettre à jour les Pull Requests.

---

## 1. Plateforme

| Paramètre | Valeur |
|-----------|--------|
| Plateforme | GitHub |
| Repo | `simodev25/MultiAgentTrading` |
| Méthode d'accès | `gh` CLI |
| Instance | Cloud (github.com) |

---

## 2. Référence des opérations

| Opération | Commande |
|-----------|----------|
| Créer une PR | `gh pr create --title "<titre>" --body "<corps>"` |
| Mettre à jour le titre/corps | `gh pr edit <number> --title "<titre>" --body "<corps>"` |
| Consulter une PR | `gh pr view <number>` |
| Lister les PRs ouvertes | `gh pr list` |
| Vérifier le statut CI | `gh pr checks <number>` |
| Fermer une PR | `gh pr close <number>` |

---

## 3. Convention de titre de PR

Format : `<type>(<scope>): <description en français>`

Exemples :
- `feat(governance): ajouter plafond de risque dynamique`
- `fix(agents): corriger le timeout de l'agent Trader`
- `refactor(backend): extraire le service d'exécution`

---

## 4. Template de corps de PR

```markdown
## Résumé

<1-3 bullets décrivant le changement>

## Changements

<liste des fichiers / composants modifiés>

## Tests

- [ ] `cd backend && pytest` — passé
- [ ] `cd frontend && npm run build` — passé

## Références

Closes #<numéro-issue>
```

---

## 5. Règles `@pr-manager`

- Créer la PR sur la branch `chg/<workItemRef>/<slug>` vers `main`.
- Inclure `Closes #<number>` pour lier automatiquement l'issue.
- Ne jamais merger — s'arrêter après création/mise à jour de la PR.
- Si les checks CI échouent, signaler à `@runner` et ne pas merger.
- Les PRs touchant la couche gouvernance (`governance` label) doivent mentionner
  explicitement dans le corps : "⚠️ Impact moteur de risque — revue `@architect` requise".
