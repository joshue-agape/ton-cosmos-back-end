# Documentation Technique : AuthMiddleware

## Introduction
Ce module implémente un middleware de sécurité pour les applications basées sur le framework FastAPI. Son rôle est d'assurer l'interception, l'analyse et la validation des droits d'accès pour chaque requête HTTP entrante vers les ressources protégées de l'API.

## Principes de Fonctionnement
Le middleware opère selon une logique de filtrage séquentielle :

1.  **Exemption des Requêtes de Pré-vérification** : Les requêtes avec la méthode `OPTIONS` (CORS) sont autorisées sans traitement supplémentaire.
2.  **Gestion des Chemins Publics** : Les routes explicitement définies comme publiques ainsi que la documentation technique (Swagger UI, ReDoc) sont ignorées par le processus d'authentification.
3.  **Analyse du Header d'Autorisation** : Le middleware exige la présence d'un header `Authorization` utilisant le schéma `Bearer`.
4.  **Identification via Jeton de Rafraîchissement** : L'identité de l'utilisateur est extraite d'un jeton de rafraîchissement présent dans les cookies de la requête.
5.  **Validation Dynamique** : Le middleware interroge la base de données pour confirmer l'existence de l'utilisateur et récupère une clé secrète spécifique (`client_secret`) pour valider le jeton d'accès final.

## Architecture Technique
L'implémentation repose sur les composants suivants :
* **BaseHTTPMiddleware** : Classe parente fournie par Starlette pour l'extension des fonctionnalités de traitement de requêtes.
* **JWT Service** : Service responsable du décodage et de la validation cryptographique des jetons.
* **AdminRepository** : Couche d'accès aux données pour la vérification de l'intégrité des comptes utilisateurs.

## Configuration
Lors de l'instanciation, le middleware requiert :
- `app` : L'instance de l'application FastAPI.
- `jwt_service` : Une instance valide du service de gestion des jetons.
- `public_paths` : Une liste optionnelle de chaînes de caractères définissant les points de terminaison accessibles sans authentification.

## Webographie
Pour approfondir les concepts de sécurité et les technologies utilisés dans ce fichier, veuillez consulter les ressources suivantes :

* [Documentation officielle de FastAPI - Middleware](https://fastapi.tiangolo.com/tutorial/middleware/)
* [Spécifications du standard JSON Web Token (RFC 7519)](https://datatracker.ietf.org/doc/html/rfc7519)
* [Guide Starlette sur les Middlewares](https://www.starlette.io/middleware/)
* [OWASP - Cheat Sheet sur l'Authentification](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)

---
*Document produit pour le suivi technique du projet.*