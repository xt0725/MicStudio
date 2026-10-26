import os
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from unittest.mock import patch
from PySide6.QtWidgets import QApplication,QMessageBox
from app import Window,PRESETS,STYLE
from devices import Device
app=QApplication([]);app.setStyle('Fusion');app.setStyleSheet(STYLE)
QMessageBox.warning=lambda *a,**k:QMessageBox.Ok
# Deterministic virtual endpoint inventory for layout and event wiring tests.
with patch('app.inventory',return_value=[Device(0,'FIFINE AM8',True,False,False,False,1,48000),Device(1,'Casque Bluetooth connecté',False,True,False,True,2,48000),Device(2,'CABLE Input',False,True,True,False,2,48000)]):
    window=Window()
for settings in PRESETS.values():
    window.apply(settings)
    assert window.engine.settings.eq==settings.eq
assert window.stack.count()==7
if os.environ.get('MICSTUDIO_REQUIRE_AI'):assert window.ai,window.ai_error
window.show();app.processEvents()
output=Path('qa');output.mkdir(exist_ok=True)
for i,name in [(0,'mixer'),(1,'studio'),(2,'listen'),(3,'routing')]:
    window.nav.setCurrentRow(i);app.processEvents();window.grab().save(str(output/f'{name}.png'))
window.strip_controls[0][2].setChecked(True)
assert window.engine.strips[0].mute
window.strip_controls[0][5].setChecked(False)
assert not window.engine.strips[0].broadcast
window.tray_setting.setChecked(False);window.close()
print('UI: seven tabs, presets, routes, mute, screenshots and clean shutdown OK')
