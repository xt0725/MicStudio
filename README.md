# MicStudio 0.1.0 — By WFCQ

Première version de développement Windows, interface française. Traitement local : gain, coupe-bas 80 Hz, graves, présence, gate progressif, compression, limiteur, mute et écoute sans effets. Sept presets (dont Gaming, Roblox et point de départ FIFINE AM8), import/export JSON des profils,, vu-mètres et sauvegarde locale automatique.

## État réel
Le code et la recette d’installateur sont fournis. Aucun exécutable Windows compilé ou validé sur matériel n’est inclus. Cette version ne remplace pas encore un mixeur multipiste comme Voicemeeter : une entrée micro, une sortie traitée. Pas de suppression d’écho acoustique, de mélange par application, de pilote virtuel intégré ni de garantie temps réel dur. Python et le système audio peuvent produire des décrochages ; le compteur les affiche. La latence affichée est celle déclarée par PortAudio, hors câble virtuel et autres applications.

## Démarrer sous Windows 10/11 x64
1. Installer Python 3.12 x64.
2. Dans ce dossier : `py -3 -m venv .venv`, puis `.venv\Scripts\python -m pip install -r requirements.txt`.
3. Lancer `.venv\Scripts\python app.py`.
4. Choisir le micro et une sortie, de préférence sur le même hôte audio. Le couple doit accepter 48 kHz. Les micros USB, jack et interfaces reconnus par Windows sont visés ; la compatibilité universelle n’est pas garantie. Les périphériques Bluetooth peuvent être limités par leur profil audio.
5. Pour écouter : sortie = casque. Ne pas utiliser d’enceintes à côté du micro.
6. Pour Discord/Roblox : installer séparément un câble virtuel de confiance (par exemple VB-CABLE depuis https://vb-audio.com/Cable/). Sortie MicStudio = CABLE Input ; entrée micro de l’application = CABLE Output. Le pilote tiers n’est ni inclus ni installé automatiquement.
7. Éviter d’empiler plusieurs gates et suppressions de bruit. Arrêter le traitement avant de débrancher un périphérique.

## RNNoise : intégration optionnelle, module non fourni
Ce projet utilise l’API RNNoise de Xiph (https://github.com/xiph/rnnoise). Il ne contient aucun composant ClearCast ou Sonar. Pour activer le bouton neuronal, compiler une DLL Windows x64 de RNNoise, avec modèle par défaut embarqué et API C exportée, puis placer `rnnoise.dll` et ses dépendances dans `native/` avant la compilation. La DLL doit exposer `rnnoise_create`, `rnnoise_destroy`, `rnnoise_get_frame_size`, `rnnoise_process_frame` et accepter des blocs de 480 valeurs flottantes à 48 kHz (échelle PCM 16 bits). Sans DLL, les effets classiques restent disponibles et l’IA est désactivée explicitement. L’intégration native nécessite un test Windows ; aucune efficacité IA n’a été mesurée ici.

Respecter la licence RNNoise et celles de ses dépendances lors de toute redistribution ; joindre les notices et licences de toutes les bibliothèques, notamment Qt/PySide6. Ne pas ajouter une DLL non vérifiée téléchargée sur un site tiers.

## Construire l’installateur personnalisé
Installer Inno Setup 6 depuis https://jrsoftware.org/isinfo.php puis exécuter `./build.ps1` dans PowerShell. Résultat attendu : `release/MicStudio-Setup-0.1.0.exe`. Assistant FR/EN avec accueil personnalisé, installation par utilisateur, menu Démarrer, raccourci Bureau facultatif et désinstallation. Le binaire n’est pas signé. Le workflow GitHub Actions `Windows installer` permet aussi une compilation manuelle une fois le projet poussé à la racine d’un dépôt. Aucun dépôt n’a été créé automatiquement.

## Validation
`python -m unittest discover -s tests -v`

Tests synthétiques du silence, du mute, de la sécurité de niveau, du gate, de la compression et du bypass. Restent à vérifier sur Windows : périphériques WASAPI/MME, latence réelle, stabilité longue durée, RNNoise et installation/désinstallation.

## Conseils de réglage vocal
Commencer sans effets, parler à environ 10–15 cm et régler le gain matériel pour éviter toute saturation en entrée. Le preset AM8 est un point de départ, pas une calibration mesurée. Monter le gate juste au-dessus du bruit au repos ; trop haut, il coupe les mots faibles. La compression stabilise le volume ; trop forte, elle accentue les défauts. Les graves ne changent pas la hauteur de la voix. Pour réduire le bruit pendant la parole, le gate ne suffit pas : il faut activer un moteur neuronal disponible ou traiter la source du bruit.
