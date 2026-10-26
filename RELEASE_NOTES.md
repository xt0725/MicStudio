## MicStudio 0.2 — refonte studio vocal
Télécharger **MicStudio-Setup-0.2.0.exe**. Python n’est pas requis.

- Sept onglets : Mixeur, Studio micro, Écoute & test, Routage, Périphériques, Profils, Paramètres.
- Réduction neuronale **RNNoise réellement embarquée** et réglable, traitement local.
- Écoute du micro au casque avec vrais vu-mètres, forme d’onde et spectre.
- Quatre sources : micro, deux auxiliaires et lecteur audio ; deux bus A/B, mute, solo, volumes et routage.
- EQ huit bandes, coupe-bas, dé-esseur, gate avec timings, compresseur avec timings et compensation, limiteur.
- Test WAV brut/traité, profils JSON, sept presets, mode zone de notification et diagnostic.
- Liste WASAPI sans doublons MME/DirectSound et filtre Bluetooth par nom.

### Utilisation
Choisir micro et casque dans Mixeur, puis **Écouter maintenant**. Pour les autres applications : un câble virtuel externe est nécessaire ; B = CABLE Input, micro Discord/Roblox = CABLE Output.

### Limites explicites
Aucun pilote virtuel MicStudio n’est fourni : aucune entrée/sortie Windows n’est créée. Le filtre Bluetooth dépend des noms de périphériques. AUX capture des entrées existantes, pas les processus automatiquement. L’audio est mixé en mono et dupliqué en stéréo. ClearCast est une technologie SteelSeries et n’est pas inclus. Installateur non signé ; les tests automatiques ne valident pas la qualité ou la compatibilité sur chaque matériel réel.
