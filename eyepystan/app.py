#----------------------------------------------------------------------
# Copyright 2017 Marco Inacio <pythonpackages@marcoinacio.com>
#
#This program is free software: you can redistribute it and/or modify
#it under the terms of the GNU General Public License as published by
#the Free Software Foundation, version 3 of the License.

#This program is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.    See the
#GNU General Public License for more details.

#You should have received a copy of the GNU General Public License
#along with this program. If not, see <http://www.gnu.org/licenses/>.
#----------------------------------------------------------------------

import pkg_resources
from collections import OrderedDict
import pandas as pd
import numpy as np
import socket
import random
import pystan
from statsmodels.tsa.stattools import acf, pacf

from bokeh import models
from bokeh.models.callbacks import CustomJS
from bokeh import layouts

import jinja2
import yaml

from tornado.ioloop import IOLoop
from tornado.web import RequestHandler

from bokeh.application import Application
from bokeh.application.handlers import FunctionHandler
from bokeh.embed import autoload_server
from bokeh.plotting import figure
from bokeh.server.server import Server
from bokeh.themes import Theme
from bokeh.util.browser import view

class App:
    def __init__(self, sfit, smodel):
        self.sfit = sfit
        self.smodel = smodel
        self.configs = dict()
        self.configs["acf_select"] = []

    def copy(self):
        new = App(sfit, smodel)
        new.configs = dict(self.config)
        return new

    def run(self):
        class IndexHandler(RequestHandler):
            def get(self):
                env = jinja2.Environment()

                template = "data/template.html"
                template = pkg_resources.resource_string(__name__,
                                                         template)
                template = env.from_string(template.decode("utf8"))

                jquery = "data/jquery.js"
                jquery = pkg_resources.resource_string(__name__, jquery)
                jquery = jquery.decode("utf8")

                script = autoload_server(url=server_url + '/eyeapp')
                self.write(template.render(script=script, jquery=jquery,
                                           template="Tornado"))

        def modify_doc(doc):

            colors = ["#00FFFF", "#7FFF00", "#B8860B", "#00BFFF",
                      "#8B008B", "#FF1493"]
            #ACF -- begin
            acf_container = layouts.column()
            def acf_change(attr, old, new):
                children = []
                if len(new):
                    for val in new:
                        data = pefit[val].apply(lambda x: pd.Series(acf(x, nlags=20)))
                        plot = figure(y_range=(0, 1.05),
                                      title="ACF for " + val)
                        base = np.array(range(20))
                        ncol = data.columns.size
                        width = .5 / ncol
                        for i in range(ncol):
                            plot.vbar(x=base+i*width, width=width,
                                      bottom=0, top=data[i],
                                      color=colors[i])
                        children.append(plot)
                acf_container.children = children
                self.configs["acf_select"] = list(new)

            acf_select = models.MultiSelect(options=fnames)
            acf_select.on_change('value', acf_change)
            acf_select.value = self.configs["acf_select"]
            #ACF -- end


            #Close app -- begin
            def close_app():
                io_loop.stop()

            js_close_app = CustomJS(args=dict(), code="""
            $("#disabler").css("display", "Block");
            """)

            button_close = models.Button(label="Save and Close",
                                         css_classes=["closebutton"])
            button_close.on_click(close_app)
            button_close.callback = js_close_app
            #Close app -- end


            doc.add_root(layouts.column(button_close, acf_select,
                                        acf_container))

            doc.theme = Theme(json=yaml.load("""
                attrs:
                    Figure:
                        background_fill_color: "#EEEEEE"
                        outline_line_color: white
                        toolbar_location: right
                        height: 500
                        width: 800
                    Grid:
                        grid_line_dash: [6, 4]
                        grid_line_color: white
            """))

        fnames = list(self.sfit.flatnames)
        fnames.append("log probability")
        efit = self.sfit.extract(permuted=False)
        pefit = OrderedDict()
        for idx in range(len(fnames)):
            pefit[fnames[idx]] = pd.DataFrame(efit[:, :, idx])

        eye_app = Application(FunctionHandler(modify_doc))

        #Choose random server port
        isclosed = False
        while not isclosed:
            port = random.randint(30000, 60000)
            conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            isclosed = conn.connect_ex(('127.0.0.1', port))
            conn.close()

        io_loop = IOLoop.current()
        server = Server({'/eyeapp': eye_app}, io_loop=io_loop,
                        extra_patterns=[('/', IndexHandler)], port=port)
        server.start()

        server_url = 'http://localhost:' + str(port)
        print('Opening EyePyStan App on ' + server_url)
        io_loop.add_callback(view, server_url)

        io_loop.start()

        return self

    def __getstate__(self):
        d = OrderedDict(self.__dict__)

        #Ensure that self.smodel will be pickled first
        d.move_to_end("sfit")
        return d
