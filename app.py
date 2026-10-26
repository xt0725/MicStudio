import json
import os
import sys
from dataclasses import asdict
from pathlib import Path
import numpy as np
import sounddevice as sd
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QComboBox, QPushButton, QSlider, QCheckBox,
    QMessageBox, QProgressBar, QGroupBox, QFormLayout, QFileDialog)
from dsp import Processor, Settings, RNNoise

ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).parent))
CONFIG = Path(os.environ.get('APPDATA', str(Path.home()))) / 'MicStudio' / 'settings.json'
PRESETS = {
    'Naturel': Settings(),
    'Studio grave': Settings(gain=2, bass=3, presence=1, gate=-45, threshold=-20),
    'Discord clair': Settings(gain=2, presence=3, gate=-42, threshold=-20, ratio=4),
    'Pièce calme': Settings(gate=-58, ratio=2),
    'Gaming compétitif': Settings(gain=1, presence=4, gate=-40, threshold=-22, ratio=4),
    'Roblox vocal': Settings(gain=2, presence=2, gate=-44, threshold=-18, ratio=3),
    'AM8 • point de départ': Settings(gain=1, bass=1, presence=2, gate=-46, threshold=-20, ratio=3),
}

class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('MicStudio • By WFCQ')
        self.resize(850, 720)
        self.stream = None
        self.ai = None
        self.audio_error = ''
        self.xruns = 0
        self.processor = Processor()
        self.settings = Settings()
        try:
            dll = ROOT / 'native' / 'rnnoise.dll'
            if dll.exists():
                self.ai = RNNoise(dll)
                self.processor.ai = self.ai
        except Exception as exc:
            self.audio_error = f'RNNoise indisponible : {exc}'
        widget = QWidget()
        self.setCentralWidget(widget)
        layout = QVBoxLayout(widget)
        title = QLabel('MicStudio')
        title.setStyleSheet('font-size:32px;font-weight:700;color:#8db6ff')
        layout.addWidget(title)
        layout.addWidget(QLabel('Votre voix. Vos réglages. Traitement local en temps réel.'))
        group = QGroupBox('Périphériques audio')
        form = QFormLayout(group)
        self.input = QComboBox()
        self.output = QComboBox()
        form.addRow('Microphone', self.input)
        form.addRow('Sortie traitée', self.output)
        refresh = QPushButton('Actualiser les périphériques')
        refresh.clicked.connect(self.devices)
        form.addRow(refresh)
        layout.addWidget(group)
        tip = QLabel('Discord / Roblox : sortie = entrée de votre câble virtuel ;\n'
                     'dans le jeu, micro = sortie de ce câble. Pour écouter, choisissez votre casque.\n'
                     'Utilisez un casque pour éviter le larsen. Aucun pilote virtuel n’est inclus.')
        tip.setWordWrap(True)
        layout.addWidget(tip)
        self.presets = QComboBox()
        self.presets.addItems(PRESETS)
        self.presets.activated.connect(lambda: self.apply(PRESETS[self.presets.currentText()]))
        layout.addWidget(self.presets)
        profile_row = QHBoxLayout()
        for text, action in [('Importer un profil', self.import_profile), ('Exporter ce profil', self.export_profile)]:
            button = QPushButton(text)
            button.clicked.connect(action)
            profile_row.addWidget(button)
        layout.addLayout(profile_row)
        self.sliders = {}
        controls = QGroupBox('Chaîne de traitement')
        form = QFormLayout(controls)
        for key, label, lo, hi in [('gain','Gain (dB)',-12,24), ('bass','Graves (dB)',-9,9),
                ('presence','Présence (dB)',-9,9), ('gate','Gate (dB)',-80,-20),
                ('threshold','Seuil compresseur (dB)',-40,0), ('ratio','Ratio compression',1,8)]:
            row = QWidget()
            box = QHBoxLayout(row)
            slider = QSlider(Qt.Horizontal)
            slider.setRange(lo,hi)
            value = QLabel()
            value.setMinimumWidth(35)
            box.addWidget(slider)
            box.addWidget(value)
            slider.valueChanged.connect(lambda n, v=value: v.setText(str(n)))
            slider.valueChanged.connect(self.changed)
            self.sliders[key] = slider
            form.addRow(label,row)
        self.checks = {}
        for key, label in [('highpass','Coupe-bas 80 Hz'), ('ai','Réduction neuronale RNNoise'),
                           ('bypass','Écouter sans effets'), ('mute','Couper le micro')]:
            check = QCheckBox(label)
            check.toggled.connect(self.changed)
            self.checks[key] = check
            form.addRow(check)
        self.checks['ai'].setEnabled(self.ai is not None)
        if self.ai is None:
            self.checks['ai'].setText('RNNoise indisponible — module natif non installé')
        layout.addWidget(controls)
        self.meters = []
        for label in ['Entrée', 'Sortie']:
            row = QHBoxLayout()
            row.addWidget(QLabel(label))
            bar = QProgressBar()
            bar.setRange(-90,0)
            row.addWidget(bar)
            layout.addLayout(row)
            self.meters.append(bar)
        self.button = QPushButton('Démarrer le traitement')
        self.button.clicked.connect(self.toggle)
        layout.addWidget(self.button)
        self.status = QLabel('Arrêté • 48 kHz • mono • blocs de 10 ms')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.devices()
        self.apply(Settings())
        self.load()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(100)

    def export_profile(self):
        name, _ = QFileDialog.getSaveFileName(self, 'Exporter le profil', 'MicStudio-profil.json', 'JSON (*.json)')
        if name:
            try:
                Path(name).write_text(json.dumps(asdict(self.settings), indent=2), encoding='utf-8')
            except OSError as exc:
                QMessageBox.warning(self, 'Profil', str(exc))

    def import_profile(self):
        name, _ = QFileDialog.getOpenFileName(self, 'Importer le profil', '', 'JSON (*.json)')
        if name:
            try:
                data = json.loads(Path(name).read_text(encoding='utf-8'))
                if not isinstance(data, dict) or set(data) - set(asdict(Settings())):
                    raise ValueError('Format de profil inconnu.')
                for key, value in data.items():
                    if key in self.sliders:
                        lo, hi = self.sliders[key].minimum(), self.sliders[key].maximum()
                        if type(value) not in (int, float) or not lo <= value <= hi:
                            raise ValueError('Valeur de profil hors limites : '+key)
                    elif type(value) is not bool:
                        raise ValueError('Option de profil incorrecte : '+key)
                self.apply(Settings(**data))
            except (OSError, ValueError, TypeError) as exc:
                QMessageBox.warning(self, 'Profil', str(exc))

    def devices(self):
        if self.stream:
            return
        self.input.clear()
        self.output.clear()
        try:
            sd._terminate()
            sd._initialize()
            hosts = sd.query_hostapis()
            for idx, d in enumerate(sd.query_devices()):
                name = f"{d['name']} [{hosts[d['hostapi']]['name']}]"
                if d['max_input_channels']:
                    self.input.addItem(name, idx)
                if d['max_output_channels']:
                    self.output.addItem(name, idx)
        except Exception as exc:
            QMessageBox.warning(self,'Audio',str(exc))

    def apply(self, s):
        for k,v in self.sliders.items():
            v.setValue(int(getattr(s,k)))
        for k,v in self.checks.items():
            v.setChecked(bool(getattr(s,k)) and (k != 'ai' or self.ai is not None))
        self.changed()

    def changed(self, *_):
        self.settings = Settings(**{k:v.value() for k,v in self.sliders.items()},
                                 **{k:v.isChecked() for k,v in self.checks.items()})

    def callback(self, indata, outdata, frames, time, status):
        outdata.fill(0)
        try:
            if status:
                self.xruns += 1
            if frames != 480:
                raise RuntimeError('Taille audio inattendue.')
            y = self.processor.process(indata[:,0], self.settings)
            outdata[:] = y[:,None]
        except Exception as exc:
            self.audio_error = str(exc)
            raise sd.CallbackAbort

    def toggle(self):
        if self.stream:
            self.stop()
            return
        stream = None
        try:
            inp, out = self.input.currentData(), self.output.currentData()
            if inp is None or out is None:
                raise RuntimeError('Sélectionnez un micro et une sortie.')
            channels = min(2, sd.query_devices(out)['max_output_channels'])
            sd.check_input_settings(device=inp,channels=1,samplerate=48000)
            sd.check_output_settings(device=out,channels=channels,samplerate=48000)
            self.audio_error = ''
            self.xruns = 0
            self.processor.reset()
            stream = sd.Stream(device=(inp,out),samplerate=48000,blocksize=480,
                channels=(1,channels),dtype='float32',latency='high',callback=self.callback)
            stream.start()
            self.stream = stream
            self.input.setEnabled(False)
            self.output.setEnabled(False)
            self.button.setText('Arrêter le traitement')
        except Exception as exc:
            if stream:
                stream.close()
            QMessageBox.warning(self,'Impossible de démarrer', str(exc)+'\nEssayez des périphériques du même hôte audio et compatibles 48 kHz.')

    def stop(self):
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        self.input.setEnabled(True)
        self.output.setEnabled(True)
        self.button.setText('Démarrer le traitement')

    def tick(self):
        for bar,db in zip(self.meters,[self.processor.input_db,self.processor.output_db]):
            bar.setValue(max(-90,min(0,int(db))))
            bar.setFormat(f'{db:.1f} dBFS')
        if self.audio_error:
            self.stop()
            self.status.setText('Erreur audio : '+self.audio_error)
            return
        if self.stream:
            if not self.stream.active:
                self.stop()
                self.status.setText('Flux interrompu. Vérifiez les périphériques puis redémarrez.')
            else:
                latency = sum(self.stream.latency)*1000
                self.status.setText(f'Actif • latence audio déclarée {latency:.0f} ms • incidents {self.xruns}')
        else:
            self.status.setText('Arrêté • limiteur de sécurité −0,18 dBFS')

    def load(self):
        try:
            data = json.loads(CONFIG.read_text(encoding='utf-8'))
            self.apply(Settings(**data['settings']))
            for combo,key in [(self.input,'input'),(self.output,'output')]:
                index = combo.findText(data.get(key,''))
                if index >= 0:
                    combo.setCurrentIndex(index)
        except (OSError, ValueError, TypeError, KeyError):
            pass

    def closeEvent(self,event):
        self.stop()
        if self.ai:
            self.ai.close()
        try:
            CONFIG.parent.mkdir(parents=True,exist_ok=True)
            temp = CONFIG.with_suffix('.tmp')
            temp.write_text(json.dumps({'settings':asdict(self.settings),
                'input':self.input.currentText(),'output':self.output.currentText()},indent=2),encoding='utf-8')
            temp.replace(CONFIG)
        except OSError:
            pass
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setStyleSheet('''QWidget{background:#111722;color:#e5eaf2;font-size:13px}
    QGroupBox{border:1px solid #303b50;border-radius:8px;margin-top:12px;padding:12px}
    QPushButton,QComboBox{background:#263750;padding:9px;border-radius:5px}
    QPushButton:hover{background:#36557e} QProgressBar{background:#202c40;border:0;border-radius:4px;text-align:center}
    QProgressBar::chunk{background:#477ed7} QSlider::groove:horizontal{height:5px;background:#35445e}
    QSlider::handle:horizontal{background:#8db6ff;width:14px;margin:-5px 0;border-radius:7px}''')
    window = Window()
    window.show()
    sys.exit(app.exec())
