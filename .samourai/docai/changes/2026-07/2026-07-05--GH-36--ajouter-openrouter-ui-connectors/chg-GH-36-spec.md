# Spécification pour GH-36 - Ajouter OpenRouter dans l'UI Connectors

## Problème/But
Ajouter le support d'OpenRouter comme fournisseur LLM dans l'interface de configuration des connecteurs.

## Scope/Non-goals
- Scope : Ajout de l'option OpenRouter dans l'UI existante
- Non-goals : Implémentation du backend pour OpenRouter (déjà fait dans GH-34)

## Critères d'acceptation
1. OpenRouter apparaît dans la liste des fournisseurs LLM
2. Le champ API_KEY pour OpenRouter est disponible dans l'onglet Security
3. Les valeurs par défaut sont correctement configurées
4. Le build frontend passe sans erreur

## Définition de Done
- Tous les critères d'acceptation sont validés
- Les modifications sont committées sur la branche feat/GH-36
- Le build frontend passe sans erreur

## Risques/Cas limites
- Aucun risque identifié - modification frontend uniquement