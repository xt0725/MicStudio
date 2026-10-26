# MicStudio 0.2 — Studio vocal & mixeur Windows

Refonte de l’application : sept onglets, quatre sources et deux bus A/B. RNNoise embarqué, vrais vu-mètres, écoute au casque, signal et spectre, test WAV comparatif, lecteur audio, profils, paramètres détaillés, mode zone de notification.

## Installer et entendre le micro
Télécharger `MicStudio-Setup-0.2.0.exe` dans Releases. Python n’est pas nécessaire.

1. Dans **Mixeur**, choisir le microphone et le casque connectés.
2. Cliquer **Écouter maintenant** : le moteur démarre et l’onglet Écoute affiche le signal réel.
3. Ajuster le volume du bus A. Utiliser un casque, pas des enceintes proches du micro.
4. Dans **Studio micro**, activer RNNoise et régler la chaîne : gain, coupe-bas, EQ 8 bandes, dé-esseur, gate, compression et limiteur. Les effets s’appliquent immédiatement.
5. Le profil FIFINE AM8 est un point de départ, pas une calibration du matériel.

## Pour Discord, Roblox et les jeux
MicStudio ne possède **pas de pilote audio virtuel signé**. Il ne crée pas de nouvelle entrée/sortie Windows. C’est une limite explicite de cette version. Les pilotes virtuels de Sonar et Voicemeeter ne sont pas redistribués.

Pour utiliser le résultat dès maintenant : installer séparément un câble virtuel compatible, par exemple depuis le site officiel https://vb-audio.com/Cable/ (droits administrateur et redémarrage éventuellement nécessaires). Dans MicStudio, sélectionner **CABLE Input** comme périphérique virtuel B. Dans Discord/Roblox, sélectionner **CABLE Output** comme microphone. Activer B sur la tranche MICRO. Les noms input/output du câble sont inversés du point de vue des applications.

Les points audio d’un câble existant peuvent être renommés dans les propriétés audio Windows. Le nom ne change pas le pilote et ne crée pas un nouveau périphérique MicStudio. Une véritable paire MicStudio autonome nécessite le développement, les tests et la signature Microsoft d’un pilote, ou un accord de distribution avec un éditeur de pilote signé. Aucun mode test de Windows ni désactivation de protection n’est requis ou proposé.

## Mixeur
- MICRO : voix traitée.
- AUX 1 et AUX 2 : entrées physiques ou sorties de câbles virtuels existants.
- LECTEUR : WAV, FLAC ou OGG, lecture/pause, retour au début, boucle (20 minutes maximum, chargé en mémoire).
- Chaque tranche : gain, MUTE, SOLO, routage A/B.
- Bus A : écoute au casque, volume indépendant et interrupteur d’écoute.
- Bus B : mix destiné aux autres applications, volume indépendant.

Pour séparer jeu et chat, utiliser des câbles distincts et choisir leurs entrées audio dans le routage. Le bouton Windows ouvre le mélangeur par application. Pas de capture automatique par processus ni de création de bus Windows par cette application. AUX reprend des sources mono ; les sorties dupliquent ce mix sur les canaux stéréo.

## Liste des périphériques / Bluetooth
La liste Windows est limitée à WASAPI : les alias MME et DirectSound sont masqués. Les sélecteurs séparent micro physique, casque et câbles virtuels. Le filtre Bluetooth est disponible dans Périphériques ; l’identification utilise les noms exposés par le pilote et peut manquer un modèle dont le nom n’indique pas son type. Par défaut les micros USB restent visibles. Le mode audio mains libres d’un casque Bluetooth peut dégrader la qualité et la latence : ce n’est pas compensable par l’EQ.

Le moteur travaille en 48 kHz et demande la conversion de fréquence WASAPI en mode partagé. Les périphériques doivent accepter cette négociation. En cas de déconnexion : arrêt explicite, actualiser puis redémarrer. Aucun basculement automatique vers des enceintes.

## Traitement et précision
RNNoise Xiph v0.1 (révision `cdf196b1e9de2f8ff1003328ebf9a4316477429d`) est compilé depuis ses sources avec modèle intégré, sans téléchargement au lancement. Traitement local, sans compte. Il ne s’agit pas de ClearCast : aucune affiliation à SteelSeries.

Le gate réduit le bruit entre les phrases. RNNoise agit aussi pendant la parole mais peut atténuer certains sons vocaux. Intensité réglable par mélange du signal traité et du signal sec retardé. Égaliseur paramétrique à huit fréquences fixes, dé-esseur basé sur l’énergie des sifflantes, gate avec attaque/maintien/relâchement, compression avec attaque/relâchement et compensation, limiteur de crête par bloc. Pas de suppression d’écho acoustique, de pitch-shifter ni de garantie de son professionnel pour tout matériel.

Le moteur Python utilise des blocs de 10 ms, des files bornées et une légère correction de dérive entre horloges. La latence de bout en bout comprend les blocs RNNoise, environ 30 ms de préremplissage des sorties, les tampons matériels, Bluetooth et les applications. Le diagnostic expose la charge, les événements audio et les défauts de tampon ; il ne prétend pas mesurer la latence de bout en bout. Le mode Réactif peut provoquer plus de décrochages.

## Enregistrement et données
Écoute & test enregistre uniquement à la demande : WAV stéréo, brut à gauche, traité à droite. Les réglages sont stockés dans `%APPDATA%/MicStudio/settings-v2.json` ; l’écoute ne s’active jamais automatiquement au lancement. Les profils DSP sont importables/exportables en JSON avec validation des valeurs. Le diagnostic exporté peut contenir des messages d’erreur et des informations audio locales.

## Compilation Windows x64
Le workflow GitHub Actions compile RNNoise puis l’application, teste le DSP et l’IA native, ouvre les sept onglets, installe/lance/désinstalle le produit, et publie une préversion avec SHA-256. Le binaire n’est pas signé.

Pour compiler localement : Python 3.12 x64, CMake, Visual Studio C++ et Inno Setup 6 ; récupérer RNNoise à la révision ci-dessus dans `third_party/rnnoise`, exécuter `cmake -S native -B native/build -A x64`, `cmake --build native/build --config Release`, copier `native/build/Release/rnnoise.dll` dans `native/`, puis `build.ps1`.

`python -m unittest discover -s tests -v` ; `QT_QPA_PLATFORM=offscreen python tests/smoke_ui.py` (syntaxe d’environnement à adapter à PowerShell). Avec `MICSTUDIO_REQUIRE_AI=1`, les tests échouent si le module natif est absent. Les essais synthétiques ne remplacent pas les tests sur un vrai micro, casque Bluetooth et client vocal.

## Notices
La licence RNNoise est incluse dans l’installation. Ses sources exactes et licences sont accessibles dans le dépôt amont référencé. PySide6/Qt sont distribués comme bibliothèques dynamiques ; leurs licences et celles des dépendances sont dans les distributions correspondantes. Les composants tiers conservent leurs licences. Aucun pilote tiers n’est inclus.
