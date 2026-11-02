# OpenReMouse

*[English version](README.md)*

Enregistreur / lecteur de macros souris + clavier, open source (MIT), pour Windows.
Écrit from scratch à partir du comportement observable de ReMouse ; aucun code de ReMouse n'est repris.

## Lancer

```
pip install -r requirements.txt
python -m openremouse
```

Python 3.10+ (testé en 3.12). Seule dépendance : `pynput`.

**Version autonome (.exe)** : lancer `build.bat` (installe PyInstaller et produit `dist\OpenReMouse.exe`, ~12 Mo, sans console,
aucun Python requis pour l'utiliser). Un .exe PyInstaller non signé peut être signalé à tort par certains antivirus / SmartScreen.

**Mode sombre** : case « Mode sombre » en bas à droite (suit le thème Windows au premier lancement, puis mémorise ton choix dans
`%APPDATA%\OpenReMouse\settings.json`).

**Langue** : liste « Langue » à côté du mode sombre (français / English). Au premier lancement, la langue d'affichage de Windows est utilisée.

## Onglet « Macro »

- **F10** : démarrer / arrêter l'enregistrement. **F9** : lancer / arrêter la lecture.
- **Éditeur** : *Ajouter ▾* (menu par catégorie), *Modifier* (ou double-clic), *Dupliquer*, *Supprimer*, *Monter / Descendre*, Ctrl+S.
- Dans les dialogues avec coordonnées, **« Viser à l'écran… »** permet de cliquer sur l'écran pour remplir X, Y (et la couleur du pixel).
- Les mouvements enregistrés se modifient en bloc : décalage X/Y et multiplicateur de durée.

## Actions disponibles

| Catégorie | Actions |
|---|---|
| Souris | clic (gauche/droit/milieu), mouvements enregistrés |
| Clavier | touche, combinaison (`ctrl+shift+s`), saisie de texte |
| Temps | délai |
| Couleur | attendre qu'un pixel prenne (ou quitte) une couleur, avec tolérance et délai max |
| Fenêtres | activer, fermer, faire clignoter, attendre ouverture / activation / désactivation / fermeture |
| Contrôles | cliquer, activer, désactiver, focus, afficher, masquer un bouton / case… par son texte ou `class:Button` |
| Fichiers | copier, supprimer, ouvrir un programme ou un fichier |
| Internet | ouvrir un site, télécharger, vérifier la connexion |
| Système | message, terminer un processus, attendre un processus, éteindre / redémarrer / déconnecter / annuler |

Les fenêtres se désignent par un morceau du titre (insensible à la casse) ou `class:NomDeClasse`.
Une action en échec (fenêtre introuvable, fichier absent…) **arrête** la macro et affiche l'erreur dans la barre d'état,
pour ne pas enchaîner des étapes qui dépendent de la précédente. Les attentes ont l'option *Si le délai est dépassé : stop / continue*.
`Shutdown` a un délai de 30 s par défaut et une action `cancel`.

## Onglet « Tâches planifiées »

Une tâche = une macro + un ou plusieurs de :

- **Raccourci clavier** propre à la macro (`ctrl+alt+1`, `f5`, `shift+a`, `ctrl+num5`…), actif même si OpenReMouse est en arrière-plan.
  Plusieurs tâches peuvent avoir chacune leur raccourci ; réappuyer sur le raccourci d'une macro en cours l'arrête.
  Les raccourcis sont reconnus par code de touche physique, donc ils marchent sur AZERTY comme sur QWERTY
  (`ctrl+alt+1` = la touche « &/1 »). F9 et F10 sont réservés ; un raccourci déjà pris est ignoré avec un message.
- **Planification** : `once` (une fois, puis la tâche se désactive), `daily` (chaque jour à HH:MM), `interval` (toutes les N secondes).
- **Déclencheur** : à l'apparition d'une fenêtre (titre) ou d'un processus (nom).

Règles : une seule macro tourne à la fois (une tâche qui tombe pendant ce temps est ignorée, avec un message) ;
`once` / `daily` ne se déclenchent que si OpenReMouse était déjà ouvert avant l'heure (lancer l'app à 15 h ne rejoue pas la tâche de 9 h) ;
les déclencheurs ne partent que sur l'apparition (pas si la fenêtre était déjà là au démarrage).
Tout ne fonctionne que tant qu'OpenReMouse est ouvert (réduire la fenêtre suffit). Configuration : `%APPDATA%\OpenReMouse\tasks.json`.

## Format `.rms`

Texte brut, une action par ligne. Compatible avec les macros souris de ReMouse.

```
{Delay 0.50}
{RMouse down (225,202)}
{Movements (0.36:226:192|0.05:254:192)}      délai:x:y
{Key down a}                                 syntaxe clavier propre à OpenReMouse
{WaitColor x=100 y=200 color=FF0000 tolerance=10 until=present timeout=30 on_timeout=stop}
{WinActivate title="Bloc-notes"}
```

Les actions étendues sont des lignes `{Nom clé=valeur ...}` (valeurs entre guillemets si espaces ; `\"`, `\\`, `\n` échappés).
Les lignes inconnues sont conservées telles quelles et ignorées à la lecture.

## Tests

```
python -m unittest discover tests
```

## Limites connues

- Les « contrôles » sont les contrôles Windows natifs (boutons, cases, champs standard). Les applications qui dessinent
  elles-mêmes leur interface (navigateurs, Electron, Qt/WPF personnalisés) n'exposent pas de contrôles : utiliser clics + attente de couleur.
- Pour piloter une fenêtre lancée en administrateur, lancer OpenReMouse en administrateur.
- La syntaxe clavier `.rms` n'est pas vérifiée contre celle de ReMouse (les démos n'en contiennent pas).
