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

#----------------------------------------------------------------------
# This file is based on the example of:
# http://matplotlib.org/examples/user_interfaces/embedding_webagg.html
# which has the following Copyright: "Copyright (c) 2012-2013 Matplotlib
# Development Team; All Rights Reserved".
# See http://matplotlib.org/users/license.html for license agreement.
#----------------------------------------------------------------------
import io
import socket
import random
import webbrowser
import json
from collections import OrderedDict
import pkg_resources
import re

import tornado
import tornado.web
import tornado.httpserver
import tornado.ioloop
import tornado.websocket

import matplotlib
from matplotlib.backends.backend_webagg_core import (
    FigureManagerWebAgg, new_figure_manager_given_figure)
from matplotlib.figure import Figure

import pystan
import numpy as np

class App:
    def __init__(self, sfit, smodel):
        self.sfit = sfit
        self.smodel = smodel
        self.configs = dict()
        self.configs["acf_select"] = []

    def copy(self):
        new = App(sfit, smodel)
        new.configs = self.config.copy()
        return new

    def run(self):
        class FigController:
            def __init__(self):
                None

            def test_figure(self):
                fig = Figure()
                a = fig.add_subplot(111)
                t = np.arange(0.0, 3.0, 0.01)
                s = np.sin(2 * np.pi * t)
                a.plot(t, s)
                self.figure = fig
                self.manager = new_figure_manager_given_figure(
                    id(fig), fig)

            def test_figure2(self):
                fig = Figure()
                a = fig.add_subplot(111)
                t = np.arange(0.0, 3.0, 0.01)
                s = np.sin(4 * np.pi * t)
                a.plot(t, s)
                self.figure = fig
                self.manager = new_figure_manager_given_figure(
                    id(fig), fig)

        class MyApplication(tornado.web.Application):
            class MainPage(tornado.web.RequestHandler):
                """
                Serves the main HTML page.
                """

                def get(self):
                    ws_uri = "ws://{req.host}/".format(req=self.request)

                    template = "data/template.html"
                    template = pkg_resources.resource_string(__name__,
                                                             template)
                    template = template.decode("utf8")

                    content = template % {
                        "ws_uri": ws_uri}
                    self.write(content)

            class QueryParameters(tornado.web.RequestHandler):
                """
                Return json encoded fnames.
                """
                def get(self):
                    gfnames = OrderedDict()
                    regm = r"(.*)\[.+\]"
                    for par in fnames:
                        if re.fullmatch(regm, par) is None:
                            keyname = "Univariate"
                        else:
                            keyname = re.sub(regm, r"\1", par)
                        if keyname not in gfnames.keys():
                            gfnames[keyname] = []
                        gfnames[keyname].append(par)
                    self.write(tornado.escape.json_encode(gfnames))

            class PlotChange(tornado.web.RequestHandler):
                """
                Serves the main HTML page.
                """

                def post(self):
                    fig_controller = self.application.fig_controller
                    change_to = self.get_argument('change_to', '')
                    if change_to == "test":
                        fig_controller.test_figure()
                    else:
                        fig_controller.test_figure2()
                    self.write(str(id(fig_controller.figure)))

            class CloseApp(tornado.web.RequestHandler):
                """
                Close the application
                """

                def get(self):
                    tornado.ioloop.IOLoop.current().stop()

            class MplJs(tornado.web.RequestHandler):
                """
                Serves the generated matplotlib javascript file.  The content
                is dynamically generated based on which toolbar functions the
                user has defined.  Call `FigureManagerWebAgg` to get its
                content.
                """

                def get(self):
                    self.set_header('Content-Type', 'application/javascript')
                    js_content = FigureManagerWebAgg.get_javascript()

                    self.write(js_content)

            class Download(tornado.web.RequestHandler):
                """
                Handles downloading of the figure in various file formats.
                """

                def get(self, fmt):
                    manager = self.application.fig_controller.manager

                    mimetypes = {
                        'ps': 'application/postscript',
                        'eps': 'application/postscript',
                        'pdf': 'application/pdf',
                        'svg': 'image/svg+xml',
                        'png': 'image/png',
                        'jpeg': 'image/jpeg',
                        'tif': 'image/tiff',
                        'emf': 'application/emf'
                    }

                    self.set_header('Content-Type', mimetypes.get(fmt, 'binary'))

                    buff = io.BytesIO()
                    manager.canvas.print_figure(buff, format=fmt)
                    self.write(buff.getvalue())

            class WebSocket(tornado.websocket.WebSocketHandler):
                supports_binary = True

                def open(self):
                    manager = self.application.fig_controller.manager
                    manager.add_web_socket(self)
                    if hasattr(self, 'set_nodelay'):
                        self.set_nodelay(True)
                    #print("Opened")

                def on_close(self):
                    manager = self.application.fig_controller.manager
                    manager.remove_web_socket(self)
                    #print("Closed")

                def on_message(self, message):
                    message = json.loads(message)
                    if message['type'] == 'supports_binary':
                        self.supports_binary = message['value']
                    else:
                        fig_controller = self.application.fig_controller
                        manager = fig_controller.manager
                        manager.handle_json(message)
                    #print("Message: ", message)

                def send_json(self, content):
                    self.write_message(json.dumps(content))
                    #print("Send json: ", content)

                def send_binary(self, blob):
                    if self.supports_binary:
                        self.write_message(blob, binary=True)
                    else:
                        data_uri = "data:image/png;base64,{0}".format(
                            blob.encode('base64').replace('\n', ''))
                        self.write_message(data_uri)
                    #print("Send binary: ", blob)

            def __init__(self, fig_controller):
                self.fig_controller = fig_controller

                super(MyApplication, self).__init__([
                    (r'/_static/(.*)',
                     tornado.web.StaticFileHandler,
                     {'path': FigureManagerWebAgg.get_static_file_path()}),

                    (r'/_static2/(.*)',
                     tornado.web.StaticFileHandler,
                     {'path': pkg_resources.resource_filename(__name__, "data/")}),

                    ('/', self.MainPage),
                    ('/closeapp', self.CloseApp),
                    ('/plot_change', self.PlotChange),
                    ('/query_parameters', self.QueryParameters),


                    ('/mpl.js', self.MplJs),
                    ('/ws', self.WebSocket),
                    (r'/download.([a-z0-9.]+)', self.Download),
                ])


        fnames = list(self.sfit.flatnames)
        fnames.append("lp__")
        efit = self.sfit.extract(permuted=False)
        pefit = OrderedDict()
        #for idx in range(len(fnames)):
        #    pefit[fnames[idx]] = pd.DataFrame(efit[:, :, idx])

        #Choose random server port
        isclosed = False
        while not isclosed:
            port = random.randint(30000, 60000)
            conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            isclosed = conn.connect_ex(('127.0.0.1', port))
            conn.close()
        server_url = 'http://localhost:' + str(port)

        fig_controller = FigController()
        application = MyApplication(fig_controller)

        http_server = tornado.httpserver.HTTPServer(application)
        http_server.listen(port)

        print("Opened at " + server_url)
        webbrowser.open_new_tab(server_url)

        tornado.ioloop.IOLoop.instance().start()

    def __getstate__(self):
        d = OrderedDict(self.__dict__)

        #Ensure that self.smodel will be pickled first
        d.move_to_end("sfit")
        return d
