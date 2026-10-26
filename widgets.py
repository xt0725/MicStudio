from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QColor, QPainter, QPainterPath, QLinearGradient, QPen
from PySide6.QtWidgets import QWidget
import numpy as np

class Meter(QWidget):
    def __init__(self,vertical=False):
        super().__init__()
        self.db=-90
        self.peak=-90
        self.vertical=vertical
        self.setMinimumSize(22,170) if vertical else self.setMinimumHeight(25)
    def set_level(self,db):
        self.db=max(-90,min(0,float(db)))
        self.peak=max(self.db,self.peak-.7)
        self.update()
    def paintEvent(self,event):
        p=QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(),QColor('#11171e'))
        count=40
        value=(self.db+60)/60
        for i in range(count):
            active=i/count<value
            color=('#f06476' if i>35 else '#efc66b' if i>29 else '#66dba5') if active else '#25313a'
            p.setBrush(QColor(color));p.setPen(Qt.NoPen)
            if self.vertical:
                h=self.height()/count
                p.drawRoundedRect(QRectF(2,self.height()-(i+1)*h+1,self.width()-4,max(1,h-2)),1,1)
            else:
                w=self.width()/count
                p.drawRoundedRect(QRectF(i*w+1,3,max(1,w-2),self.height()-6),1,1)
        p.setPen(QColor('#f4f7fa'))
        v=max(0,min(1,(self.peak+60)/60))
        if self.vertical:
            y=self.height()*(1-v)
            p.drawLine(0,int(y),self.width(),int(y))
        else:
            x=self.width()*v
            p.drawLine(int(x),0,int(x),self.height())

class Scope(QWidget):
    def __init__(self,spectrum=False):
        super().__init__()
        self.spectrum_mode=spectrum
        self.data=np.zeros(480)
        self.setMinimumHeight(150)
    def set_data(self,data):
        self.data=data.copy()
        self.update()
    def paintEvent(self,event):
        p=QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(),QColor('#0e151d'))
        p.setPen(QPen(QColor('#24313e'),1))
        for i in range(1,8):
            x=int(self.width()*i/8);p.drawLine(x,0,x,self.height())
        for i in range(1,4):
            y=int(self.height()*i/4);p.drawLine(0,y,self.width(),y)
        path=QPainterPath()
        data=self.data
        if self.spectrum_mode:
            indices=np.geomspace(1,max(2,len(data)-1),100).astype(int)
            values=np.clip((data[indices]+90)/90,0,1)
            coords=[QPointF(i*self.width()/99,(1-v)*(self.height()-12)+6) for i,v in enumerate(values)]
        else:
            coords=[QPointF(i*self.width()/max(1,len(data)-1),self.height()/2-float(v)*self.height()*.45) for i,v in enumerate(data)]
        if coords:
            path.moveTo(coords[0])
            for point in coords[1:]:
                path.lineTo(point)
        p.setPen(QPen(QColor('#70ddbb' if not self.spectrum_mode else '#8daaff'),1.8))
        p.drawPath(path)
        p.setPen(QColor('#8398ac'))
        p.drawText(10,19,'SPECTRE · 20 Hz — 24 kHz' if self.spectrum_mode else 'SIGNAL MICRO · TEMPS RÉEL')
