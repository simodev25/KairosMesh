# Plan d'implémentation pour GH-36 - Ajouter OpenRouter dans l'UI Connectors

## Phases
1. **Phase 1: Préparation**
   - Création des fichiers artifacts (spec, test-plan, pm-notes)
   - Validation des chemins et branches

2. **Phase 2: Modifications frontend**
   - Mise à jour du type LlmProvider
   - Ajout d'OpenRouter dans la liste des fournisseurs
   - Ajout du champ API_KEY dans l'onglet Security
   - Mise à jour des fonctions utilitaires

3. **Phase 3: Validation**
   - Vérification visuelle des modifications
   - Exécution du build frontend

## Étapes détaillées
### Phase 2
1. Mettre à jour le type LlmProvider pour inclure 'openrouter'
2. Ajouter 'openrouter' dans la liste LLM_PROVIDERS
3. Ajouter la condition pour 'openrouter' dans normalizeLlmProvider
4. Ajouter la valeur par défaut 'openrouter/auto' dans defaultModelForProvider
5. Mettre à jour SecretFieldKey et EMPTY_SECRET_FIELDS
6. Ajouter OPENROUTER_API_KEY dans hydrateSecretFields
7. Mettre à jour le tableau dans saveSecrets
8. Ajouter le bloc UI pour OPENROUTER_API_KEY

### Phase 3
1. Vérifier visuellement chaque modification
2. Exécuter `npm run build` dans le dossier frontend

## Livrables
- Fichiers modifiés : ConnectorsPage.tsx
- Build frontend réussi