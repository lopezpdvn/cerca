#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# (C) 2012, Pedro I. López <dreilopz@gmail.com>
#
# This source code is released under the new BSD license, a copy of the
# license is in the distribution directory.

import wx
import sys
import os
import serial
import numpy as np
import matplotlib.font_manager as font_manager
from matplotlib.figure import Figure
from matplotlib.backends.backend_wxagg import \
        FigureCanvasWxAgg as FigureCanvas

# wxWidgets object ID for timer.
TIMER_ID = wx.NewId()

# Select port.
PLATFORM = sys.platform
if 'linux' in PLATFORM:
    PORT = '/dev/ttyS0'
elif 'win32' in PLATFORM:
    PORT = 'COM10'

# Number of data points.
POINTS = 200

START = '\x00'
ACK = '\x03'
OK_STATUS = '\x06'
ERROR = '\x0a'
END = '\x04'

READ = '\x01'
WRITE = '\x0c'
REPORT_STATUS = '\x07'

DISTANCE_SAMPLE = '\x02'
ADC0_SAMPLE = '\x05'
OPMODE = '\x0b'

NORMAL_MODE = '\x08'
SERIAL_MODE = '\x09'

TIME_DELTA = 100
DEBUG = True

class UC(object):
    FACTOR = 5.0 / 1023.0
    '''UC interface object.'''
    CONVERSION = 5.0 / (2**10)
    def __init__( self, port=None ):
        self.port = port

    @property
    def adc0D( self ):
        buff = self.execute_command(READ, ADC0_SAMPLE)
        buff = [ord(i) for i in buff]
        return buff[0] + buff[1] * 255

    @property
    def adc0A(self):
        return self.__class__.FACTOR * self.adc0D

    @property
    def distance(self):
        return 12343.85 * (self.adc0D ** (-1.15))

    @property
    def distanceD( self ):
        buff = self.execute_command(READ, DISTANCE_SAMPLE)
        buff = [ord(i) for i in buff]
        distance = buff[0] + buff[1] * 255
        return distance

    def execute_command( self, *command ):
        command = list(command)
        self.port.write(START)
        assert self.port.read(1) == ACK

        self.port.write(''.join(command))
        n = ord(self.port.read(1))

        buff = []
        for i in range(n):
            buff.append(self.port.read(1))

        self.port.write(ACK)
        self.port.write(END)
        assert self.port.read(1) == ACK

        return buff

    @property
    def status( self ):
        return self.execute_command(REPORT_STATUS)[0]

    @property
    def mode( self ):
        mode = self.execute_command(READ, OPMODE)[0]
        return mode

    def set_mode( self, mode ):
        if mode == SERIAL_MODE:
            self.execute_command(WRITE, OPMODE, SERIAL_MODE)
            assert self.mode == SERIAL_MODE
        elif mode == NORMAL_MODE:
            self.execute_command(WRITE, OPMODE, NORMAL_MODE)
            assert self.mode == NORMAL_MODE

def analog_to_digital(anv):
    anv = float(anv)
    assert (anv >= 0.0) and (anv <= 5.0)
    return int((1023.0/5.0) * anv)

class PlotPanel(wx.Panel):
    def __init__(self, *args, **kwds):
        # begin wxGlade: PlotPanel.__init__
        uc = kwds.pop('uc')
        kwds["style"] = wx.DOUBLE_BORDER|wx.TAB_TRAVERSAL
        wx.Panel.__init__(self, *args, **kwds)

        self.__set_properties()
        self.__do_layout()
        # end wxGlade

        # ``PlotPanel`` size is (600, 400).
        self.figure = Figure(figsize=(6, 4), dpi=100)

        self.ax = self.figure.add_subplot(111)
        self.canvas = FigureCanvas(self, wx.ID_ANY, self.figure)
        #self.ax.set_ylim([0.0, 1023.0])
        self.ax.set_ylim([0.0, 80.0])
        self.ax.set_xlim([0.0, POINTS])
        self.ax.set_autoscale_on(False)  # Disable autoscale.
        self.ax.set_xticks([])
        self.ax.grid(True, animated=True, linewidth=1, antialiased=True,
                     fillstyle='full')
        self.ax.set_title(u'Distance vs time')
        self.ax.set_ylabel('distance (cm)')
        self.ax.set_xlabel('time')

        # Initial empty plot.
        self.distance = [None] * POINTS
        self.distance_plot, = self.ax.plot(range(POINTS), self.distance,
                                          label='Distance')
        self.canvas.draw()

        # Save the clean background - everything but the line is drawn and
        # saved in the pixel buffer background.
        self.bg = self.canvas.copy_from_bbox(self.ax.bbox)

        # Represents UC interfaced through the serial port.
        self.uc = uc

        assert self.uc.port.isOpen()
        assert self.uc.status == OK_STATUS

        self.uc.set_mode(SERIAL_MODE)

        # Take a snapshot of voltage, needed for the update algorithm.
        self.before = self.uc.distance

        wx.EVT_TIMER(self, TIMER_ID, self.onTimer)

        # Initialize the timer.
        self.t = wx.Timer(self, TIMER_ID)

        self.samples = 0

    def __set_properties(self):
        # begin wxGlade: PlotPanel.__set_properties
        self.SetMinSize((600, 400))
        self.SetToolTipString("Distance plot.")
        # end wxGlade

    def __do_layout(self):
        # begin wxGlade: PlotPanel.__do_layout
        pass
        # end wxGlade

    def onTimer(self, evt):
        # Get distance.
        distance = self.uc.distance
        if distance <= 80.0:
            distance_str = str(distance)
        else:
            distance = 80.0
            distance_str = u"OUT OF RANGE"

        mainframe.distance_label.SetLabel(distance_str)

        self.samples += 1

        # Restore the clean background, saved at the beginning.
        self.canvas.restore_region(self.bg)

        # Update data array.
        self.distance = self.distance[1:] + [distance]

        # Update plot.
        self.distance_plot.set_ydata(self.distance)

        # Just draw the "animated" objects.
        self.ax.draw_artist(self.distance_plot)

        # Blit the background with the animated lines.
        self.canvas.blit(self.ax.bbox)

        with open(LOG_FILE_PATH, 'a+') as f:
            f.write("{0},{1}\n".format(str(self.samples * TIME_DELTA),
                                       str(distance)))

# end of class PlotPanel


class MainFrame(wx.Frame):
    def __init__(self, *args, **kwds):
        # begin wxGlade: MainFrame.__init__

        uc = kwds.pop('uc')

        #kwds["style"] = wx.CAPTION|wx.CLOSE_BOX|wx.MINIMIZE_BOX|wx.MAXIMIZE_BOX|wx.SYSTEM_MENU|wx.RESIZE_BORDER|wx.FULL_REPAINT_ON_RESIZE|wx.TAB_TRAVERSAL|wx.CLIP_CHILDREN
        kwds['style'] = (wx.DEFAULT_FRAME_STYLE ^ (wx.RESIZE_BORDER |
                                                 wx.MINIMIZE_BOX |
                                                 wx.MAXIMIZE_BOX))
        kwds['size'] = (650, 600)
        kwds['pos'] = (0, 0)
        wx.Frame.__init__(self, *args, **kwds)
        self.mainPanel = wx.Panel(parent=self)
        self.mainframe_statusbar = self.CreateStatusBar(1, 0)
        self.plot_panel = PlotPanel(self.mainPanel, id=-1, uc=uc)
        self.plot_enable = wx.ToggleButton(self.mainPanel, -1, "TI")
        self.label_1 = wx.StaticText(self.mainPanel, -1, "Writing to file:", style=wx.ALIGN_RIGHT)
        self.filepath_label = wx.StaticText(self.mainPanel, -1, "")
        self.label_2 = wx.StaticText(self.mainPanel, -1, "Distance (cm):",
                                     style=wx.ALIGN_RIGHT)
        self.distance_label = wx.StaticText(self.mainPanel, -1, "TI")

        self.__set_properties()
        self.__do_layout()

        self.Bind(wx.EVT_TOGGLEBUTTON, self.toggle_on_off, self.plot_enable)
        # end wxGlade


    def __set_properties(self):
        # begin wxGlade: MainFrame.__set_properties
        self.SetTitle("cerca")
        self.SetFocus()
        self.mainframe_statusbar.SetStatusWidths([-1])
        # statusbar fields
        mainframe_statusbar_fields = ["[INIT text]"]
        for i in range(len(mainframe_statusbar_fields)):
            self.mainframe_statusbar.SetStatusText(mainframe_statusbar_fields[i], i)
        self.label_1.SetMinSize((180, 20))
        self.filepath_label.SetFont(wx.Font(8, wx.DEFAULT, wx.NORMAL, wx.BOLD, 0, ""))
        self.label_2.SetMinSize((180, 20))
        self.distance_label.SetFont(wx.Font(12, wx.DEFAULT, wx.NORMAL, wx.BOLD, 0, ""))
        # end wxGlade

    def __do_layout(self):
        # begin wxGlade: MainFrame.__do_layout
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        sizer_5 = wx.BoxSizer(wx.HORIZONTAL)
        sizer_4 = wx.BoxSizer(wx.HORIZONTAL)
        sizer_3 = wx.BoxSizer(wx.HORIZONTAL)
        main_sizer.Add((20, 20), 0, wx.ADJUST_MINSIZE, 0)
        sizer_3.Add((20, 20), 0, wx.ADJUST_MINSIZE, 0)
        sizer_3.Add(self.plot_panel, 1, wx.ALL|wx.EXPAND, 0)
        sizer_3.Add((20, 20), 0, wx.ADJUST_MINSIZE, 0)
        main_sizer.Add(sizer_3, 0, wx.EXPAND, 0)
        main_sizer.Add((20, 20), 0, wx.ADJUST_MINSIZE, 0)
        main_sizer.Add(self.plot_enable, 0, wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_CENTER_VERTICAL|wx.ADJUST_MINSIZE, 0)
        main_sizer.Add((20, 20), 0, wx.ADJUST_MINSIZE, 0)
        sizer_4.Add((20, 20), 0, wx.ADJUST_MINSIZE, 0)
        sizer_4.Add(self.label_1, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL|wx.ADJUST_MINSIZE, 0)
        sizer_4.Add((20, 20), 0, wx.ADJUST_MINSIZE, 0)
        sizer_4.Add(self.filepath_label, 0, wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_CENTER_VERTICAL, 0)
        main_sizer.Add(sizer_4, 0, wx.ALL, 0)
        main_sizer.Add((20, 20), 0, wx.ADJUST_MINSIZE, 0)
        sizer_5.Add((20, 20), 0, wx.ADJUST_MINSIZE, 0)
        sizer_5.Add(self.label_2, 0, wx.ALIGN_CENTER_VERTICAL|wx.ADJUST_MINSIZE, 0)
        sizer_5.Add((20, 20), 0, wx.ADJUST_MINSIZE, 0)
        sizer_5.Add(self.distance_label, 0, wx.ALL|wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_CENTER_VERTICAL|wx.ADJUST_MINSIZE, 0)
        main_sizer.Add(sizer_5, 0, wx.ALL, 0)
        main_sizer.Add((20, 20), 0, wx.ADJUST_MINSIZE, 0)
        self.mainPanel.SetSizer(main_sizer)
        main_sizer.Fit(self.mainPanel)
        self.mainPanel.Layout()
        # end wxGlade

    def toggle_on_off(self, event): # wxGlade: MainFrame.<event_handler>
        # Change label (from 'ON' to 'OFF', etc).
        if self.plot_enable.GetValue():
            self.plot_enable.SetLabel('ON')
            self.mainframe_statusbar.SetStatusText(
                u'Serial mode, writing to file {0}'.format(LOG_FILE_PATH),
                                                   0)
            if not self.plot_panel.uc.port.isOpen():
                self.plot_panel.uc.port.open()
            assert self.plot_panel.uc.status == OK_STATUS
            self.plot_panel.uc.set_mode(SERIAL_MODE)

            # Timer.
            self.plot_panel.t.Start(TIME_DELTA)
        else:
            self.plot_enable.SetLabel('OFF')
            self.mainframe_statusbar.SetStatusText(
                u'Normal mode, serial connection closed', 0)

            # Timer.
            self.plot_panel.t.Stop()

            self.plot_panel.uc.set_mode(NORMAL_MODE)

# end of class MainFrame


class Cerca(wx.App):
    def OnInit(self):
        global LOG_FILE_PATH, mainframe

        wx.InitAllImageHandlers()

        available_ports = scan()
        print 'Available ports: {0}'.format(available_ports)
        print 'JUMP'

        msg = u'''\
The application will use a serial port with *8N1* configuration:

- 9600 bauds
- 8 data bits
- No parity
- 1 stop bit

Found serial ports.  Choose the serial port you want to use and press the 'OK'
button, or press 'Cancel' to exit.
'''
        caption = u'Serial port selection'
        dlg = wx.SingleChoiceDialog(None, msg, caption,
                    [i[1] for i in available_ports])
        response = dlg.ShowModal()
        if response == wx.ID_CANCEL:
            print 'Exiting application before configuring serial port.'
            dlg.Destroy()
            return False
        elif response == wx.ID_OK:
            selected_serialport = available_ports[dlg.GetSelection()][0]
        dlg.Destroy()

        try:
            self.sp = serial.Serial(selected_serialport, timeout=1)
        except serial.SerialException as e:
            print 'Error while opening serial port: {0}'.format(e.args)
            return False

        try:
            self.uc = UC(port=self.sp)
        except UCException as e:
            print 'Error while abstracting microcontroller: {0}'.format(e.args)
            return False

        while True:
            LOG_FILE_DIR = wx.DirSelector(message=wx.DirSelectorPromptStr,
                                style=0, pos=wx.DefaultPosition, parent=None)

            if (os.access(LOG_FILE_DIR, os.R_OK) and
                os.access(LOG_FILE_DIR, os.W_OK) and
                os.access(LOG_FILE_DIR, os.X_OK) and
                os.access(LOG_FILE_DIR, os.F_OK)):
                break

        LOG_FILE_NAME = wx.GetTextFromUser(
            message=u"Log filename, with extension.",
            caption="Input Text", parent=None)
        assert isinstance(LOG_FILE_NAME, str) or isinstance(LOG_FILE_NAME, unicode)
        LOG_FILE_PATH = os.path.join(LOG_FILE_DIR, LOG_FILE_NAME)

        with open(LOG_FILE_PATH, 'w') as f:
            f.write("time,distance\n")

        mainframe = MainFrame(None, -1, "", uc=self.uc)
        self.SetTopWindow(mainframe)
        mainframe.Show()

        mainframe.filepath_label.SetLabel(LOG_FILE_PATH)
        mainframe.mainframe_statusbar.SetStatusText(
            u'Normal mode, serial communication not started.', 0)
        mainframe.plot_enable.SetLabel('OFF')
        mainframe.distance_label.SetLabel('0.00')

        return True

    def OnExit(self):
        print 'Closing serial port {0}'.format(self.sp.port)
        self.sp.close()
        print 'Application END.'

def scan():
    available = []
    for i in range(256):
        try:
            s = serial.Serial(i)
            available.append( (i, s.portstr))
            s.close()
        except serial.SerialException:
            pass
    return available

if __name__ == "__main__":
    LOG_FILENAME = 'log'
    if os.path.exists(LOG_FILENAME):
        os.remove(LOG_FILENAME)

    cerca = Cerca(redirect=True, filename=LOG_FILENAME)
    cerca.MainLoop()
