# Calame — site web

Site d'une page pour calame-ia.ch. Fichiers statiques uniquement, aucune dépendance, aucun cookie, aucun traceur, aucune ressource externe (même pas de polices Google).

| Fichier | Rôle |
|---|---|
| `index.html` | Le site complet (texte + mise en page) |
| `favicon.svg` | Petite icône affichée dans l'onglet du navigateur |

Taille totale : environ 25 Ko (limite Web Starter : 10 Mo).

## Avant de publier

Dans `index.html`, en bas, la section **Mentions légales** contient des espaces réservés surlignés en jaune :
`[Prénom Nom]`, `[Rue et numéro], [NPA] Genève`, `[CHE-xxx.xxx.xxx, ou ligne à supprimer]`.
Ils doivent être remplis (ou la ligne IDE supprimée) avant la mise en ligne, puis retirer les balises `<span class="placeholder">`.

## Voir le site sur son ordinateur

Double-cliquer sur `index.html` : il s'ouvre dans le navigateur.

## Publier sur Infomaniak (Web Starter)

1. Se connecter sur https://manager.infomaniak.com
2. Ouvrir **Web & Domaine** → **Hébergements web**, puis cliquer sur l'hébergement de calame-ia.ch.
3. Ouvrir le **Gestionnaire de fichiers** (FTP Manager).
4. Aller dans le dossier racine du site (en général `web`).
5. S'il y a une page d'accueil par défaut d'Infomaniak (`index.html`), la remplacer.
6. Téléverser `index.html` et `favicon.svg` (glisser-déposer).
7. Ouvrir https://calame-ia.ch dans un navigateur (et sur son téléphone) pour vérifier.

Les intitulés exacts du Manager Infomaniak peuvent varier légèrement selon les mises à jour.
