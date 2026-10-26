"""MicStudio 0.2 — desktop vocal mixer. No fabricated virtual Windows devices."""
import json
import os
import sys
import time
import webbrowser
from dataclasses import asdict, replace
from pathlib import Path
import numpy as np
import sounddevice as sd
from PySide6.QtCore import Qt, QTimer, QSignalBlocker
from PySide6.QtGui import QFont, QIcon, QPixmap, QPainter, QColor
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,
    QLabel,QComboBox,QPushButton,QSlider,QCheckBox,QMessageBox,QGroupBox,QFormLayout,
    QFileDialog,QStackedWidget,QListWidget,QListWidgetItem,QFrame,QScrollArea,QGridLayout,
    QTextEdit,QSpinBox,QSystemTrayIcon,QMenu)
from dsp import Settings, RNNoise, LIMITS, EQ_FREQS, validated_settings
from engine import AudioEngine, Strip
from devices import inventory
from widgets import Meter,Scope

ROOT=Path(getattr(sys,'_MEIPASS',Path(__file__).parent))
CONFIG=Path(os.environ.get('APPDATA',str(Path.home())))/'MicStudio'/'settings-v2.json'
PRESETS={
    'Naturel • neutre':Settings(makeup=0,ratio=2,deesser=10),
    'Discord • voix nette':Settings(gain=1,gate=-46,threshold=-22,ratio=3,eq=(0,-1,-2,-1,0,2,2,0)),
    'Gaming • équipe':Settings(gate=-43,gate_hold=160,threshold=-24,ratio=4,eq=(-2,-1,-2,0,1,3,2,-1)),
    'Roblox • vocal':Settings(gate=-47,threshold=-20,eq=(0,0,-1,-1,0,2,1,0)),
    'Studio • chaleureux':Settings(gate=-53,ratio=2,eq=(2,2,0,-1,0,1,1,0),deesser=35),
    'FIFINE AM8 • départ':Settings(gate=-48,threshold=-20,eq=(0,1,-2,-1,0,2,1,0)),
    'Clavier et ventilateurs':Settings(gate=-42,gate_release=200,ai_strength=100,highpass_hz=100,eq=(-2,-1,-1,0,0,2,1,0)),
}
STYLE='''
QWidget { background:#10161e; color:#dce7f0; font-family:'Segoe UI';font-size:13px; }
QLabel,QCheckBox,QSlider { background:transparent; }
QLabel#brand { font-size:25px;font-weight:800;color:#f6fbff; }
QLabel#heading { font-size:27px;font-weight:700; }
QLabel#muted { color:#90a3b5; }
QLabel#badge { background:#173e34;color:#82e3bc;border-radius:5px;padding:5px; }
QFrame#card,QGroupBox { background:#17212c;border:1px solid #2b3a49;border-radius:10px; }
QGroupBox { margin-top:14px;padding:16px;font-weight:600; }
QGroupBox::title { subcontrol-origin:margin;left:16px;padding:0 5px; }
QListWidget { border:0;background:#121c27;outline:none;padding:8px; }
QListWidget::item { padding:17px 15px;margin:3px;border-radius:7px;color:#a9bbca; }
QListWidget::item:selected { background:#233c46;color:#8ceac3; }
QPushButton { background:#273748;border:1px solid #3b5065;border-radius:6px;padding:10px 16px; }
QPushButton:hover { background:#344d63; }
QPushButton:checked { background:#225a48;border-color:#69cda6;color:#9ef4cf; }
QPushButton#primary { background:#72dcb0;color:#09251c;font-weight:700;border:0; }
QPushButton#danger { background:#713644; }
QComboBox,QSpinBox { background:#101923;border:1px solid #3a4d60;border-radius:5px;padding:8px; }
QSlider::groove:horizontal { height:5px;background:#334657;border-radius:2px; }
QSlider::handle:horizontal { background:#8be9c3;width:13px;margin:-5px 0;border-radius:6px; }
QSlider::groove:vertical { width:6px;background:#334657; }
QSlider::handle:vertical { height:24px;background:#cadce8;margin:0 -8px;border-radius:3px; }
QCheckBox { spacing:8px;padding:4px; }
QCheckBox::indicator { width:16px;height:16px;background:#0d151e;border:1px solid #5d7182;border-radius:3px; }
QCheckBox::indicator:checked { background:#72dcb0; }
QTextEdit { background:#0f1721;border:1px solid #2d4052;border-radius:6px;padding:10px; }
QScrollArea { border:0; }
QToolTip { color:#e9f3fa;background:#233448;border:1px solid #57718b; }
'''

def label(text,style=None):
    w=QLabel(text)
    w.setWordWrap(True)
    if style:w.setObjectName(style)
    return w

def button(text,action,primary=False):
    w=QPushButton(text)
    if primary:w.setObjectName('primary')
    w.clicked.connect(action)
    return w

def page(title,subtitle):
    w=QWidget();l=QVBoxLayout(w);l.setContentsMargins(26,22,26,22);l.setSpacing(15)
    l.addWidget(label(title,'heading'));l.addWidget(label(subtitle,'muted'))
    return w,l

class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('MicStudio — Studio vocal & mixeur')
        self.resize(1230,860);self.setMinimumSize(1000,740)
        self.ai=None;self.ai_error='';self.loading=True;self.hidden_to_tray=False
        self.last_record_error='';self.restart_pending=False
        dll=ROOT/'native'/('rnnoise.dll' if sys.platform=='win32' else 'librnnoise.so')
        try:
            if dll.exists():self.ai=RNNoise(dll)
            else:self.ai_error='Module RNNoise absent de cette installation.'
        except Exception as exc:self.ai_error=str(exc)
        self.engine=AudioEngine(self.ai)
        self.sliders={};self.checks={};self.eq_sliders=[];self.strip_controls=[]
        self.device_combos=[];self.frozen_controls=[]
        root=QWidget();self.setCentralWidget(root);outer=QHBoxLayout(root);outer.setContentsMargins(0,0,0,0);outer.setSpacing(0)
        rail=QWidget();rail.setFixedWidth(205);rl=QVBoxLayout(rail);rl.setContentsMargins(12,24,12,15)
        rl.addWidget(label('MICSTUDIO','brand'));rl.addWidget(label('VOCAL CONTROL · 0.2','muted'))
        self.nav=QListWidget()
        for text in ['Mixeur','Studio micro','Écoute & test','Routage','Périphériques','Profils','Paramètres']:
            self.nav.addItem(text)
        rl.addWidget(self.nav);rl.addWidget(label('By WFCQ\nAudio traité sur ton PC','muted'));outer.addWidget(rail)
        content=QWidget();cl=QVBoxLayout(content);cl.setContentsMargins(0,0,0,10)
        self.stack=QStackedWidget();cl.addWidget(self.stack)
        for make in [self.mixer_page,self.studio_page,self.listen_page,self.routing_page,self.devices_page,self.profiles_page,self.settings_page]:
            w=make();scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setWidget(w);self.stack.addWidget(scroll)
        footer=QHBoxLayout();footer.setContentsMargins(26,8,26,0)
        self.status=label('Prêt à configurer','muted');footer.addWidget(self.status,1)
        self.start_button=button('Démarrer le moteur',self.toggle,True);footer.addWidget(self.start_button)
        cl.addLayout(footer);outer.addWidget(content,1)
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex);self.nav.setCurrentRow(0)
        self.tray=None
        if QSystemTrayIcon.isSystemTrayAvailable():
            pix=QPixmap(32,32);pix.fill(QColor('#72dcb0'));p=QPainter(pix);p.setPen(QColor('#10251b'));p.setFont(QFont('Segoe UI',19,QFont.Bold));p.drawText(pix.rect(),Qt.AlignCenter,'M');p.end()
            self.setWindowIcon(QIcon(pix));self.tray=QSystemTrayIcon(QIcon(pix),self)
            menu=QMenu();menu.addAction('Ouvrir MicStudio',self.show_normal);menu.addAction('Quitter',self.quit_app)
            self.tray.setContextMenu(menu);self.tray.activated.connect(lambda reason:self.show_normal() if reason==QSystemTrayIcon.DoubleClick else None);self.tray.show()
        self.refresh_devices()
        self.apply(Settings(ai=self.ai is not None))
        self.load()
        self.loading=False
        self.changed();self.update_mix()
        self.timer=QTimer(self);self.timer.timeout.connect(self.tick);self.timer.start(33)
    def combo(self):
        w=QComboBox();w.setMinimumWidth(240);w.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon);w.setMinimumContentsLength(24)
        self.device_combos.append(w);self.frozen_controls.append(w);return w
    def mixer_page(self):
        w,l=page('Ton son, sous contrôle.','Quatre sources, deux bus indépendants. A = casque · B = envoi vocal vers les applications.')
        form=QFormLayout();self.input=self.combo();self.monitor=self.combo();self.virtual=self.combo()
        form.addRow('Microphone',self.input);form.addRow('Casque / écoute A',self.monitor);form.addRow('Périphérique virtuel B',self.virtual);l.addLayout(form)
        row=QHBoxLayout();self.listen=QCheckBox('Écouter mon micro et le mix dans le casque');self.listen.toggled.connect(self.update_mix)
        row.addWidget(self.listen);row.addStretch();row.addWidget(button('Écouter maintenant',self.listen_now,True));l.addLayout(row)
        strips=QHBoxLayout()
        for i,(name,desc) in enumerate([('MICRO','Voix traitée'),('AUX 1','Jeu / entrée audio'),('AUX 2','Chat / entrée audio'),('LECTEUR','Musique / soundboard')]):
            card=QFrame();card.setObjectName('card');box=QVBoxLayout(card);box.setContentsMargins(17,17,17,17)
            box.addWidget(label(name));box.addWidget(label(desc,'muted'))
            m=Meter(True);f=QSlider(Qt.Vertical);f.setRange(-60,12);f.setValue(0)
            meterrow=QHBoxLayout();meterrow.addStretch();meterrow.addWidget(f);meterrow.addSpacing(16);meterrow.addWidget(m);meterrow.addStretch();box.addLayout(meterrow)
            val=label('0 dB');val.setAlignment(Qt.AlignCenter);box.addWidget(val)
            mute=QPushButton('MUTE');mute.setCheckable(True);solo=QPushButton('SOLO');solo.setCheckable(True)
            buttons=QHBoxLayout();buttons.addWidget(mute);buttons.addWidget(solo);box.addLayout(buttons)
            routes=QHBoxLayout();a=QCheckBox('A');a.setChecked(True);b=QCheckBox('B');b.setChecked(i==0);routes.addWidget(a);routes.addWidget(b);box.addLayout(routes)
            for control in [mute,solo,a,b]:control.toggled.connect(self.update_mix)
            f.valueChanged.connect(lambda n,v=val:v.setText(f'{n:+d} dB'));f.valueChanged.connect(self.update_mix)
            self.strip_controls.append((f,m,mute,solo,a,b));strips.addWidget(card)
        l.addLayout(strips)
        row=QHBoxLayout();self.bus_meters=[]
        for name in ['A · CASQUE','B · VOCAL']:
            c=QGroupBox(name);b=QVBoxLayout(c);meter=Meter();b.addWidget(meter);volume=QSlider(Qt.Horizontal);volume.setRange(-60,6);volume.setValue(-9 if name.startswith('A') else 0);b.addWidget(volume)
            value=label(f'{volume.value()} dB');b.addWidget(value);volume.valueChanged.connect(lambda n,v=value:v.setText(f'{n:+d} dB'));volume.valueChanged.connect(self.update_mix)
            self.bus_meters.append((meter,volume));row.addWidget(c)
        l.addLayout(row);return w
    def control(self,form,key,text,lo=None,hi=None):
        if lo is None:lo,hi=LIMITS[key]
        row=QWidget();rl=QHBoxLayout(row);rl.setContentsMargins(0,0,0,0)
        slider=QSlider(Qt.Horizontal);slider.setRange(int(lo),int(hi));v=QSpinBox();v.setRange(int(lo),int(hi));v.setFixedWidth(83)
        slider.valueChanged.connect(v.setValue);v.valueChanged.connect(slider.setValue);slider.valueChanged.connect(self.changed)
        rl.addWidget(slider,1);rl.addWidget(v);self.sliders[key]=slider;form.addRow(text,row)
    def check(self,form,key,text):
        c=QCheckBox(text);self.checks[key]=c;c.toggled.connect(self.changed);form.addRow(c);return c
    def studio_page(self):
        w,l=page('Studio micro','La chaîne : gain → coupe-bas → RNNoise → EQ → dé-esseur → gate → compression → limiteur.')
        grid=QGridLayout();l.addLayout(grid)
        def group(title,r,c):
            g=QGroupBox(title);f=QFormLayout(g);grid.addWidget(g,r,c);return f
        f=group('01 · Noise Clean AI',0,0)
        self.ai_check=self.check(f,'ai','Activer la réduction neuronale RNNoise');self.ai_check.setEnabled(self.ai is not None)
        f.addRow(label('Modèle embarqué · local · sans compte' if self.ai else self.ai_error,'badge' if self.ai else 'muted'))
        self.control(f,'ai_strength','Intensité (%)');self.control(f,'gain','Gain entrée (dB)')
        f=group('02 · Nettoyage de la voix',0,1)
        self.check(f,'highpass','Activer le coupe-bas');self.control(f,'highpass_hz','Fréquence (Hz)');self.control(f,'deesser','Dé-esseur (%)')
        f=group('03 · Noise gate',1,0)
        for k,t in [('gate','Seuil (dBFS)'),('gate_attack','Attaque (ms)'),('gate_hold','Maintien (ms)'),('gate_release','Relâchement (ms)')]:self.control(f,k,t)
        f=group('04 · Dynamique',1,1)
        for k,t in [('threshold','Seuil (dBFS)'),('ratio','Ratio :1'),('comp_attack','Attaque (ms)'),('comp_release','Relâchement (ms)'),('makeup','Gain sortie (dB)'),('ceiling','Plafond limiteur (dBFS)')]:self.control(f,k,t)
        eq=QGroupBox('05 · Égaliseur 8 bandes · ±12 dB');row=QHBoxLayout(eq)
        for freq in EQ_FREQS:
            col=QVBoxLayout();v=label('0');v.setAlignment(Qt.AlignCenter);col.addWidget(v);s=QSlider(Qt.Vertical);s.setRange(-12,12);s.setMinimumHeight(130);col.addWidget(s,0,Qt.AlignHCenter)
            t=label(f'{freq/1000:g}k' if freq>=1000 else str(freq));t.setAlignment(Qt.AlignCenter);col.addWidget(t)
            s.valueChanged.connect(lambda n,v=v:v.setText(f'{n:+d}'));s.valueChanged.connect(self.changed);self.eq_sliders.append(s);row.addLayout(col)
        l.addWidget(eq)
        row=QHBoxLayout();self.bypass=QCheckBox('Bypass des effets');self.checks['bypass']=self.bypass;self.bypass.toggled.connect(self.changed)
        self.mute=QCheckBox('Couper le micro à la source');self.checks['mute']=self.mute;self.mute.toggled.connect(self.changed)
        row.addWidget(self.bypass);row.addWidget(self.mute);self.dynamics=label('Réduction : 0 dB');row.addWidget(self.dynamics);l.addLayout(row)
        return w
    def listen_page(self):
        w,l=page('Écoute & test','Entends le signal traité au casque et observe les vrais niveaux du micro en temps réel.')
        l.addWidget(button('Activer l’écoute et démarrer',self.listen_now,True))
        self.scope=Scope();self.spectrum=Scope(True);l.addWidget(self.scope);l.addWidget(self.spectrum)
        row=QHBoxLayout();self.input_meter=Meter();self.output_meter=Meter();row.addWidget(label('BRUT'));row.addWidget(self.input_meter,1);row.addWidget(label('TRAITÉ'));row.addWidget(self.output_meter,1);l.addLayout(row)
        self.level_text=label('Entrée −90 dBFS · Sortie −90 dBFS');l.addWidget(self.level_text)
        g=QGroupBox('Enregistrement comparatif');box=QVBoxLayout(g)
        box.addWidget(label('WAV stéréo : canal gauche = micro brut, canal droit = voix traitée. Aucun enregistrement automatique.','muted'))
        self.record_button=button('Enregistrer un test WAV',self.record);box.addWidget(self.record_button);l.addWidget(g)
        g=QGroupBox('Lecteur audio / soundboard');box=QVBoxLayout(g);self.file_label=label('Aucun fichier chargé');box.addWidget(self.file_label)
        row=QHBoxLayout();row.addWidget(button('Charger WAV / FLAC / OGG',self.open_audio));self.play_button=button('Lecture / pause',self.play_audio);row.addWidget(self.play_button)
        row.addWidget(button('Revenir au début',self.rewind_audio));self.loop=QCheckBox('Boucler');self.loop.toggled.connect(lambda v:setattr(self.engine,'loop',v));row.addWidget(self.loop);box.addLayout(row)
        self.player_text=label('00:00 / 00:00','muted');box.addWidget(self.player_text);l.addWidget(g)
        l.addWidget(label('Le volume A commence à −9 dB. Utilise un casque pour éviter le larsen. Le Bluetooth peut ajouter une latence importante.','muted'))
        l.addStretch();return w
    def routing_page(self):
        w,l=page('Routage A / B','Choisis les sources envoyées dans ton casque et celles qui seront entendues par les autres.')
        form=QFormLayout();self.aux1=self.combo();self.aux2=self.combo();form.addRow('AUX 1 · jeu / source',self.aux1);form.addRow('AUX 2 · chat / source',self.aux2);l.addLayout(form)
        l.addWidget(label('AUX 1 et AUX 2 capturent des entrées audio existantes. Pour une application, dirige sa sortie vers un câble virtuel distinct dans le mélangeur Windows.','muted'))
        self.routing_text=QTextEdit();self.routing_text.setReadOnly(True);self.routing_text.setMinimumHeight(190);l.addWidget(self.routing_text)
        l.addWidget(button('Ouvrir le mélangeur Windows',lambda:self.open_windows('ms-settings:apps-volume')))
        g=QGroupBox('Entrée / sortie virtuelle MicStudio');box=QVBoxLayout(g)
        box.addWidget(label('Le moteur n’installe pas de pilote audio. Aucun périphérique MicStudio n’est créé dans Windows.','muted'))
        box.addWidget(label('Pour utiliser le bus B dès maintenant : sortie B = CABLE Input ; micro Discord / Roblox = CABLE Output. Le pilote VB-CABLE doit être installé séparément depuis son éditeur.'))
        row=QHBoxLayout();row.addWidget(button('Site officiel VB-CABLE',lambda:webbrowser.open('https://vb-audio.com/Cable/')));row.addWidget(button('Panneau audio Windows',lambda:self.open_windows('mmsys.cpl')));box.addLayout(row)
        box.addWidget(label('Des noms personnalisés peuvent être définis dans les propriétés Windows d’un câble existant. Cela renomme ses points audio ; cela ne crée pas un nouveau pilote.','muted'))
        l.addWidget(g);l.addStretch();return w
    def devices_page(self):
        w,l=page('Périphériques connectés','Une seule liste WASAPI, sans les doublons MME et DirectSound.')
        self.bluetooth_only=QCheckBox('Bluetooth uniquement (conserver les câbles virtuels)');self.bluetooth_only.toggled.connect(self.refresh_devices);l.addWidget(self.bluetooth_only)
        l.addWidget(label('Par défaut, les micros USB comme ton AM8 et les casques actifs restent disponibles. Le filtre Bluetooth s’appuie sur les noms exposés par Windows.','muted'))
        self.refresh_button=button('Actualiser les périphériques',self.refresh_devices);self.frozen_controls.append(self.refresh_button);self.frozen_controls.append(self.bluetooth_only);l.addWidget(self.refresh_button)
        self.device_text=QTextEdit();self.device_text.setReadOnly(True);l.addWidget(self.device_text)
        l.addWidget(label('Si un périphérique disparaît, le moteur s’arrête et affiche une erreur. Reconnecte-le puis actualise et redémarre. Aucun basculement automatique vers des enceintes.','muted'))
        l.addWidget(button('Réglages audio Windows',lambda:self.open_windows('ms-settings:sound')));l.addStretch();return w
    def profiles_page(self):
        w,l=page('Profils vocaux','Des points de départ modifiables. Tes réglages restent enregistrés localement.')
        self.presets=QComboBox();self.presets.addItems(PRESETS);l.addWidget(self.presets)
        l.addWidget(button('Appliquer ce profil',lambda:self.apply(PRESETS[self.presets.currentText()]),True))
        l.addWidget(button('Exporter mon profil JSON',self.export_profile));l.addWidget(button('Importer un profil JSON',self.import_profile))
        l.addWidget(label('Un profil n’est pas une calibration du micro. Positionne le micro à 10–15 cm, évite de saturer à l’entrée, puis ajuste le gate et l’égaliseur.','muted'));l.addStretch();return w
    def settings_page(self):
        w,l=page('Paramètres & diagnostic','Priorité à une voix stable. Change les périphériques et le tampon moteur arrêté.')
        f=QFormLayout();self.latency=QComboBox();self.latency.addItems(['Stable','Réactif']);f.addRow('Tampon audio',self.latency);self.frozen_controls.append(self.latency)
        self.tray_setting=QCheckBox('Réduire dans la zone de notification à la fermeture');f.addRow(self.tray_setting);l.addLayout(f)
        l.addWidget(label('48 kHz · voix mono · blocs de 10 ms · bus dupliqués en stéréo. La latence mesurée du matériel s’ajoute à RNNoise, aux files de lecture, au Bluetooth et au jeu.','muted'))
        self.diagnostic=QTextEdit();self.diagnostic.setReadOnly(True);l.addWidget(self.diagnostic)
        l.addWidget(button('Exporter le diagnostic',self.export_diagnostic))
        l.addWidget(label('Noise Clean AI utilise RNNoise de Xiph. ClearCast et Sonar appartiennent à SteelSeries. MicStudio est un logiciel indépendant.','muted'));l.addStretch();return w
    def open_windows(self,target):
        if sys.platform=='win32':
            if target=='mmsys.cpl':
                import subprocess;subprocess.Popen(['control.exe','mmsys.cpl'])
            else:os.startfile(target)
    def refresh_devices(self,*_):
        if self.engine.running:return
        old=[c.currentText() for c in self.device_combos]
        try:
            # Reinitialize only with no open streams to discover hotplug changes.
            sd._terminate();sd._initialize()
            self.catalog=inventory(self.bluetooth_only.isChecked())
            groups=[(self.input,[d for d in self.catalog if d.capture and not d.virtual]),
                (self.monitor,[d for d in self.catalog if d.render and not d.virtual]),
                (self.virtual,[d for d in self.catalog if d.render and d.virtual]),
                (self.aux1,[d for d in self.catalog if d.capture]),(self.aux2,[d for d in self.catalog if d.capture])]
            for combo,items in groups:
                previous=combo.currentText();combo.clear();combo.addItem('Non sélectionné',None)
                for d in items:combo.addItem(d.name,d.id)
                index=combo.findText(previous)
                if index>=0:combo.setCurrentIndex(index)
            # Choose Windows default physical microphone/headphones when available.
            default=sd.default.device
            for combo,device in [(self.input,default[0]),(self.monitor,default[1])]:
                if combo.currentIndex()==0:
                    i=combo.findData(device)
                    if i<0 and combo.count()>1:i=1
                    if i>=0:combo.setCurrentIndex(i)
            if self.virtual.count()>1 and self.virtual.currentIndex()==0:
                i=next((i for i in range(1,self.virtual.count()) if 'cable input' in self.virtual.itemText(i).lower()),1)
                self.virtual.setCurrentIndex(i)
            self.device_text.setPlainText('\n'.join(f"{'MIC' if d.capture else 'OUT'}  {d.name}  {'[virtuel]' if d.virtual else ''}" for d in self.catalog) or 'Aucun périphérique disponible avec ce filtre.')
        except Exception as exc:self.device_text.setPlainText('Impossible de lire les périphériques : '+str(exc))
    def changed(self,*_):
        if self.loading:return
        values={k:s.value() for k,s in self.sliders.items()}
        values.update({k:c.isChecked() for k,c in self.checks.items()});values['eq']=tuple(s.value() for s in self.eq_sliders)
        self.engine.settings=Settings(**values)
    def apply(self,s):
        was=self.loading;self.loading=True
        for k,v in self.sliders.items():v.setValue(int(getattr(s,k)))
        for k,v in self.checks.items():v.setChecked(bool(getattr(s,k)) and (k!='ai' or self.ai is not None))
        for slider,value in zip(self.eq_sliders,s.eq):slider.setValue(int(value))
        self.loading=was
        # Always update the immutable DSP snapshot, including initial construction.
        self.engine.settings=replace(s,ai=s.ai and self.ai is not None)
        if not was:self.changed()
    def update_mix(self,*_):
        if not hasattr(self,'bus_meters') or len(self.strip_controls)<4:return
        self.engine.strips=tuple(Strip(f.value(),mute.isChecked(),solo.isChecked(),a.isChecked(),b.isChecked()) for f,m,mute,solo,a,b in self.strip_controls)
        self.engine.monitor_enabled=self.listen.isChecked()
        self.engine.monitor_volume=self.bus_meters[0][1].value();self.engine.broadcast_volume=self.bus_meters[1][1].value()
    def toggle(self):
        if self.engine.running:self.stop();return
        try:
            self.changed();self.update_mix()
            # No auxiliary source may equal the receiving side of the selected bus B cable.
            # Explicit confirmation on feedback risk instead of silently opening it.
            selected=self.virtual.currentText().lower()
            for c in (self.aux1,self.aux2):
                if c.currentData() is not None and 'cable input' in selected and 'cable output' in c.currentText().lower():
                    raise ValueError('Boucle audio : AUX ne doit pas reprendre CABLE Output si le bus B envoie dans CABLE Input.')
            self.engine.start(self.input.currentData(),self.monitor.currentData(),self.virtual.currentData(),self.aux1.currentData(),self.aux2.currentData(),'low' if self.latency.currentIndex()==1 else 'high')
            for c in self.frozen_controls:c.setEnabled(False)
            self.start_button.setText('Arrêter le moteur');self.start_button.setObjectName('danger');self.start_button.style().polish(self.start_button)
        except Exception as exc:QMessageBox.warning(self,'Audio',str(exc)+'\nVérifie la connexion et la compatibilité du mode audio 48 kHz.')
    def stop(self):
        self.engine.stop()
        for c in self.frozen_controls:c.setEnabled(True)
        self.start_button.setText('Démarrer le moteur');self.start_button.setObjectName('primary');self.start_button.style().polish(self.start_button)
        self.record_button.setText('Enregistrer un test WAV')
    def listen_now(self):
        if self.monitor.currentData() is None:
            QMessageBox.warning(self,'Écoute','Choisis ton casque dans le mixeur.');self.nav.setCurrentRow(0);return
        self.listen.setChecked(True)
        if not self.engine.running:self.toggle()
        self.nav.setCurrentRow(2)
    def record(self):
        if self.engine.recording:
            self.engine.stop_recording();self.record_button.setText('Enregistrer un test WAV');return
        if not self.engine.running:
            QMessageBox.information(self,'Test micro','Démarre le moteur avant d’enregistrer.');return
        name,_=QFileDialog.getSaveFileName(self,'Enregistrer le test','MicStudio-test.wav','WAV (*.wav)')
        if name:
            try:self.engine.start_recording(name);self.record_button.setText('Arrêter et sauvegarder le test')
            except Exception as exc:QMessageBox.warning(self,'Enregistrement',str(exc))
    def open_audio(self):
        name,_=QFileDialog.getOpenFileName(self,'Ouvrir un son','','Audio (*.wav *.flac *.ogg)')
        if name:
            try:self.engine.load_file(name);self.file_label.setText(Path(name).name)
            except Exception as exc:QMessageBox.warning(self,'Lecteur',str(exc))
    def play_audio(self):
        if not len(self.engine.player):QMessageBox.information(self,'Lecteur','Charge d’abord un fichier audio.');return
        if self.engine.player_position>=len(self.engine.player):self.engine.player_position=0
        self.engine.playing=not self.engine.playing
    def rewind_audio(self):self.engine.player_position=0
    def export_profile(self):
        name,_=QFileDialog.getSaveFileName(self,'Exporter le profil','MicStudio-profil.json','JSON (*.json)')
        if name:
            try:Path(name).write_text(json.dumps(asdict(self.engine.settings),indent=2),encoding='utf-8')
            except OSError as exc:QMessageBox.warning(self,'Profil',str(exc))
    def import_profile(self):
        name,_=QFileDialog.getOpenFileName(self,'Importer le profil','','JSON (*.json)')
        if name:
            try:self.apply(validated_settings(json.loads(Path(name).read_text(encoding='utf-8'))))
            except (OSError,ValueError,TypeError) as exc:QMessageBox.warning(self,'Profil',str(exc))
    def export_diagnostic(self):
        name,_=QFileDialog.getSaveFileName(self,'Exporter diagnostic','MicStudio-diagnostic.json','JSON (*.json)')
        if name:
            try:Path(name).write_text(self.diagnostic.toPlainText(),encoding='utf-8')
            except OSError as exc:QMessageBox.warning(self,'Diagnostic',str(exc))
    def tick(self):
        engine=self.engine
        if engine.running:
            if engine.error or any(not s.active for s in engine.streams):
                reason=engine.error or 'Périphérique déconnecté ou flux arrêté.';self.stop();self.status.setText('Arrêt : '+reason);return
            self.status.setText(f'EN DIRECT · 48 kHz · RNNoise {"ON" if engine.settings.ai and self.ai else "OFF"} · incidents {engine.status_events}')
        elif not self.status.text().startswith('Arrêt :'):self.status.setText('Moteur arrêté · prêt à démarrer')
        for (_,m,*_),db in zip(self.strip_controls,engine.levels):m.set_level(db if engine.running else -90)
        for (m,_),db in zip(self.bus_meters,engine.bus_levels):m.set_level(db if engine.running else -90)
        p=engine.processor
        self.input_meter.set_level(p.input_db if engine.running else -90);self.output_meter.set_level(p.output_db if engine.running else -90)
        self.level_text.setText(f'Entrée {p.input_db:.1f} dBFS · Sortie {p.output_db:.1f} dBFS'+(' · SATURATION EN ENTRÉE : baisse le gain matériel' if p.clipping else ''))
        self.dynamics.setText(f'Compression : −{p.reduction:.1f} dB · gate {p.gate_gain*100:.0f}%')
        if self.stack.currentIndex()==2:self.scope.set_data(engine.wave);self.spectrum.set_data(engine.spectrum)
        if self.stack.currentIndex()==6:
            try:self.diagnostic.setPlainText(json.dumps({**engine.diagnostics(),'ai':bool(self.ai),'ai_error':self.ai_error},indent=2))
            except Exception:pass
        if self.stack.currentIndex()==3:
            lines=[]
            for name,strip in zip(['MICRO','AUX 1','AUX 2','LECTEUR'],engine.strips):
                lines.append(f'{name:10} → '+('A · casque  ' if strip.monitor else '')+('B · vocal' if strip.broadcast else '')+('  [MUET]' if strip.mute else ''))
            self.routing_text.setPlainText('\n\n'.join(lines))
        if engine.record_error and engine.record_error!=self.last_record_error:
            self.last_record_error=engine.record_error;self.record_button.setText('Enregistrer un test WAV');QMessageBox.warning(self,'Enregistrement',engine.record_error)
        def duration(n):return f'{int(n)//60:02}:{int(n)%60:02}'
        self.player_text.setText(f'{duration(engine.player_position/48000)} / {duration(len(engine.player)/48000)}'+(' · lecture' if engine.playing else ' · pause'))
    def load(self):
        try:
            d=json.loads(CONFIG.read_text(encoding='utf-8'));self.apply(validated_settings(d['settings']))
            for combo,name in zip(self.device_combos,d.get('devices',[])):
                i=combo.findText(name)
                if i>=0:combo.setCurrentIndex(i)
            for controls,data in zip(self.strip_controls,d.get('strips',[])):
                strip=Strip(**data);f,m,mute,solo,a,b=controls;f.setValue(int(strip.gain));mute.setChecked(strip.mute);solo.setChecked(strip.solo);a.setChecked(strip.monitor);b.setChecked(strip.broadcast)
            self.bus_meters[0][1].setValue(int(d.get('monitor_volume',-9)));self.bus_meters[1][1].setValue(int(d.get('broadcast_volume',0)))
            self.latency.setCurrentIndex(1 if d.get('latency')=='Réactif' else 0);self.tray_setting.setChecked(bool(d.get('tray',False)))
            # Listening always requires explicit action after launch.
        except (OSError,ValueError,TypeError,KeyError):pass
    def save(self):
        try:
            CONFIG.parent.mkdir(parents=True,exist_ok=True);temp=CONFIG.with_suffix('.tmp')
            temp.write_text(json.dumps({'settings':asdict(self.engine.settings),'devices':[c.currentText() for c in self.device_combos],
                'strips':[asdict(s) for s in self.engine.strips],'monitor_volume':self.engine.monitor_volume,'broadcast_volume':self.engine.broadcast_volume,
                'tray':self.tray_setting.isChecked(),'latency':self.latency.currentText()},indent=2),encoding='utf-8');temp.replace(CONFIG)
        except OSError:pass
    def show_normal(self):self.showNormal();self.raise_();self.activateWindow()
    def quit_app(self):self.hidden_to_tray=True;self.close()
    def closeEvent(self,event):
        self.save()
        if self.tray and self.tray_setting.isChecked() and not self.hidden_to_tray:
            self.hide();event.ignore();return
        self.timer.stop();self.stop()
        if self.ai:self.ai.close()
        if self.tray:self.tray.hide()
        event.accept()

if __name__=='__main__':
    app=QApplication(sys.argv);app.setStyle('Fusion');app.setStyleSheet(STYLE)
    window=Window();window.show();sys.exit(app.exec())
