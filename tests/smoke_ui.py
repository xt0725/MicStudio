import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication, QMessageBox
from app import Window, PRESETS
app = QApplication([])
# Hosted runners may have no audio endpoints.
QMessageBox.warning = lambda *args, **kwargs: QMessageBox.Ok
window = Window()
for settings in PRESETS.values():
    window.apply(settings)
    assert window.settings == settings
window.show()
app.processEvents()
window.close()
print('UI presets and clean shutdown: OK')
