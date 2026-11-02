"""Two-language UI (French source strings, English translations).

Code keeps the French text as the key: ``tr("Annuler")`` returns "Cancel" when the language is
English, and the text itself otherwise (or when a string has no translation yet).
``tr(fmt, *args)`` translates the template first, then applies ``fmt % args``.
"""
from __future__ import annotations

from . import settings

LANGS = {"fr": "Français", "en": "English"}
_lang = "fr"


def system_lang() -> str:
    """'fr' if the Windows display language is French, else 'en'."""
    try:
        import ctypes
        lid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        return "fr" if (lid & 0x3FF) == 0x0C else "en"
    except Exception:
        return "en"


def load_pref() -> str:
    """Saved choice, else the Windows display language."""
    l = settings.load().get("lang")
    return l if l in LANGS else system_lang()


def set_lang(lang: str, save: bool = True) -> None:
    global _lang
    _lang = lang if lang in LANGS else "en"
    if save:
        settings.save(lang=_lang)


def get_lang() -> str:
    return _lang


def tr(s: str, *args) -> str:
    out = EN.get(s, s) if _lang == "en" else s
    return out % args if args else out


EN = {
    # ---- main window
    "Prêt": "Ready",
    "Macro": "Macro",
    "Tâches planifiées": "Scheduled tasks",
    "Mode sombre": "Dark mode",
    "Langue :": "Language:",
    "Enregistrer (F10)": "Record (F10)",
    "Arrêter (F10)": "Stop (F10)",
    "Lire (F9)": "Play (F9)",
    "Arrêter (F9)": "Stop (F9)",
    "Nouveau": "New",
    "Ouvrir…": "Open…",
    "Enregistrer": "Save",
    "Enregistrer sous…": "Save as…",
    "Répétitions (0 = infini):": "Repeats (0 = infinite):",
    "Vitesse:": "Speed:",
    "Enregistrer les mouvements": "Record movements",
    "Clavier": "Keyboard",
    "Action": "Action",
    "Ajouter ▾": "Add ▾",
    "Ajouter": "Add",
    "Modifier": "Edit",
    "Dupliquer": "Duplicate",
    "Supprimer": "Delete",
    "Tout supprimer": "Delete all",
    "Monter": "Move up",
    "Descendre": "Move down",
    "Supprimer les %d actions de la macro ?": "Delete all %d actions of the macro?",
    "Toutes les actions supprimées": "All actions deleted",
    "Enregistrement…": "Recording…",
    "%d actions enregistrées": "%d actions recorded",
    "Rien à lire : enregistre ou ouvre une macro": "Nothing to play: record or open a macro",
    "Lecture…": "Playing…",
    "macro en cours": "running macro",
    "Nouvelle macro": "New macro",
    "Macro ReMouse": "ReMouse macro",
    "Tous": "All files",
    "Erreur": "Error",
    "%s : %d actions": "%s: %d actions",
    "Enregistré : ": "Saved: ",
    "Raccourci ignoré : ": "Hotkey ignored: ",
    " (déjà utilisé)": " (already used)",
    "Arrêt demandé : ": "Stop requested: ",
    # ---- tasks tab
    "Lancer maintenant": "Run now",
    "Actif": "Active",
    "Nom": "Name",
    "Raccourci": "Hotkey",
    "Planification": "Schedule",
    "Déclencheur": "Trigger",
    "oui": "yes",
    "non": "no",
    "Tâche": "Task",
    "Nouvelle tâche": "New task",
    "Les raccourcis, planifications et déclencheurs ne fonctionnent que tant qu'OpenReMouse est ouvert "
    "(vous pouvez réduire la fenêtre).":
        "Hotkeys, schedules and triggers only work while OpenReMouse is open (you can minimize the window).",
    "Macro (.rms)": "Macro (.rms)",
    "Raccourci clavier (ex. ctrl+alt+1)": "Hotkey (e.g. ctrl+alt+1)",
    "Répétitions (0 = infini)": "Repeats (0 = infinite)",
    "Vitesse": "Speed",
    "Heure (daily : HH:MM — once : AAAA-MM-JJ HH:MM)": "Time (daily: HH:MM — once: YYYY-MM-DD HH:MM)",
    "Intervalle en secondes (interval)": "Interval in seconds (interval)",
    "Titre de fenêtre / nom du processus": "Window title / process name",
    "Activée": "Enabled",
    "une fois, ": "once, ",
    "chaque jour à ": "every day at ",
    "toutes les %d s": "every %d s",
    "fenêtre « %s »": "window \"%s\"",
    "processus %s": "process %s",
    "Erreur (%s) : %s": "Error (%s): %s",
    "Terminé : %s": "Finished: %s",
    "Lancé : %s": "Started: %s",
    "Occupé : « %s » ignorée (une macro tourne déjà)": "Busy: \"%s\" skipped (a macro is already running)",
    # ---- dialogs
    "Clique sur le point à viser — Échap pour annuler": "Click the point to aim at — Esc to cancel",
    "Viser à l'écran…": "Aim on screen…",
    "Annuler": "Cancel",
    "Valeur invalide": "Invalid value",
    "« %s » doit être un nombre.": "\"%s\" must be a number.",
    "Souris": "Mouse",
    "Clic": "Click",
    "Touche": "Key",
    "Temps": "Time",
    "Délai": "Delay",
    "Bouton": "Button",
    "État": "State",
    "Durée (secondes)": "Duration (seconds)",
    "Touche (ex. a, ENTER, F5)": "Key (e.g. a, ENTER, F5)",
    "Décalage X (px)": "X offset (px)",
    "Décalage Y (px)": "Y offset (px)",
    "Multiplicateur de durée (2 = deux fois plus lent)": "Duration multiplier (2 = twice as slow)",
    "Mouvements (%d points)": "Movements (%d points)",
    "Ligne brute": "Raw line",
    "Texte": "Text",
    # ---- actions: categories
    "Couleur": "Color",
    "Fenêtres": "Windows",
    "Contrôles": "Controls",
    "Fichiers": "Files",
    "Système": "System",
    "Internet": "Internet",
    # ---- actions: labels
    "Attendre une couleur": "Wait for a color",
    "Activer une fenêtre": "Activate a window",
    "Fermer une fenêtre": "Close a window",
    "Faire clignoter une fenêtre": "Flash a window",
    "Attendre l'ouverture d'une fenêtre": "Wait for a window to open",
    "Attendre qu'une fenêtre soit active": "Wait for a window to be active",
    "Attendre qu'une fenêtre ne soit plus active": "Wait for a window to be inactive",
    "Attendre la fermeture d'une fenêtre": "Wait for a window to close",
    "Cliquer sur un contrôle": "Click a control",
    "Activer un contrôle": "Enable a control",
    "Désactiver un contrôle": "Disable a control",
    "Donner le focus à un contrôle": "Focus a control",
    "Afficher un contrôle": "Show a control",
    "Masquer un contrôle": "Hide a control",
    "Copier un fichier": "Copy a file",
    "Supprimer un fichier": "Delete a file",
    "Ouvrir un programme / fichier": "Open a program / file",
    "Ouvrir un site web": "Open a website",
    "Télécharger un fichier": "Download a file",
    "Vérifier la connexion internet": "Check internet connection",
    "Afficher un message": "Show a message",
    "Terminer un processus": "Kill a process",
    "Attendre un processus": "Wait for a process",
    "Éteindre / redémarrer": "Shut down / restart",
    "Combinaison de touches": "Key combination",
    "Saisir du texte": "Type text",
    # ---- actions: fields
    "Délai max en secondes (0 = sans limite)": "Max wait in seconds (0 = no limit)",
    "Si le délai est dépassé": "If the wait times out",
    "Couleur (RRGGBB)": "Color (RRGGBB)",
    "Tolérance (0-255)": "Tolerance (0-255)",
    "Attendre que la couleur soit": "Wait until the color is",
    "Titre de la fenêtre (ou class:NomDeClasse)": "Window title (or class:ClassName)",
    "Nombre de clignotements": "Number of flashes",
    "Titre de la fenêtre": "Window title",
    "Texte du contrôle (ou class:Button)": "Control text (or class:Button)",
    "Source": "Source",
    "Destination (fichier ou dossier)": "Destination (file or folder)",
    "Écraser si existe": "Overwrite if it exists",
    "Fichier": "File",
    "Programme ou fichier": "Program or file",
    "Arguments": "Arguments",
    "Attendre la fin du programme": "Wait for the program to finish",
    "Adresse": "Address",
    "Enregistrer dans (fichier ou dossier)": "Save to (file or folder)",
    "Délai réseau en secondes": "Network timeout in seconds",
    "Serveur à joindre (port 443)": "Server to reach (port 443)",
    "Si pas de connexion": "If there is no connection",
    "Message": "Message",
    "Titre": "Title",
    "Nom (ex. notepad.exe)": "Name (e.g. notepad.exe)",
    "Attendre qu'il soit": "Wait until it is",
    "Action ": "Action ",
    "Délai avant exécution (s)": "Delay before running (s)",
    "Touches (ex. ctrl+shift+s)": "Keys (e.g. ctrl+shift+s)",
    "Pause entre caractères (s)": "Pause between characters (s)",
    # ---- runtime errors
    "action inconnue : %s": "unknown action: %s",
    "couleur attendue au format RRGGBB : %r": "color expected as RRGGBB: %r",
    "%s introuvable : %r": "%s not found: %r",
    "Fenêtre": "Window",
    "Contrôle": "Control",
    "touche inconnue : %r": "unknown key: %r",
}
