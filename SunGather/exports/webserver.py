from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from version import __version__
from urllib.parse import parse_qs, urlparse

import json
import logging
import urllib

logger = logging.getLogger(__name__)
#logger.setLevel(logging.DEBUG)

class export_webserver(object):
    html_body = "Pending Data Retrieval"
    metrics = ""
    req = None

    def __init__(self):
        False

    # Configure Webserver
    def configure(self, config, inverter):
        logger.debug("Webserver.configure() called...")
        try:
            self.webServer = HTTPServer(('', config.get('port',8080)), MyServer)
            self.t = Thread(target=self.webServer.serve_forever)
            self.t.daemon = True    # Make it a deamon, so if main loop ends the webserver dies
            self.t.start()
            logger.info(f"Webserver: Configured")
        except OSError as exc:
            if exc.args[0] != 98:
              raise
            logger.info("  address already in use...")
            url = "http://localhost:"+str(config.get('port',8080))
            req = urllib.request.Request(url+"/ping")
            resp = urllib.request.urlopen(req)
            if (resp.status == 200):
              logger.info("  received a ping!")
              self.req = {}
              url = url + "/publish"
              self.req['url'] = url
              self.req['inverter'] = inverter
              fullConfig={'config':inverter.client_config}
              for key,value in inverter.inverter_config:
                fullConfig['config'][key] = value
              data = json.dumps(fullConfig).encode('utf-8')
              #logger.debug(f"  sending {data}")
              req = urllib.request.Request(url, method='POST')
              req.add_header('Content-Type','application/json')
              resp = urllib.request.urlopen(req, data)
              if (resp.status == 200):
                # successful initialisation with the running server
                return True
              logger.info("  failed to sync with the server")
              return False
            else:
              logger.info("  no ping response, cannot be reused!")
              return False
        except Exception as err:
            logger.error(f"Webserver: Error: {err}")
            return False
        pending_config = False
        config_body = f"""
            <h3>SunGather v{__version__}</h3></p>
            <h4>Configuration changes require a restart to take effect!</h4>    
            <form action="/config">
            <label>Inverter Settings:</label><br>
            <table><tr><th>Option</th><th>Setting</th><th>Update?</th></tr>
            """
        for setting, value in inverter.client_config.items():
            config_body += f'<tr><td><label for="{str(setting)}">{str(setting)}:</label></td>'
            config_body += f'<td><input type="text" id="{str(setting)}" name="{str(setting)}" value="{str(value)}"></td>'
            config_body += f'<td><input type="checkbox" id="update_{str(setting)}" name="update_{str(setting)}" value="False"></td></tr>'
        for setting, value in inverter.inverter_config.items():
            config_body += f'<tr><td><label for="{str(setting)}">{str(setting)}:</label></td>'
            config_body += f'<td><input type="text" id="{str(setting)}" name="{str(setting)}" value="{str(value)}"></td>'
            config_body += f'<td><input type="checkbox" id="update_{str(setting)}" name="update_{str(setting)}" value="False"></td></tr>' 
        #config_body += f'</table><input type="submit" value="Submit"></form>'
        config_body += f'</table>Currently ReadOnly, No save function yet :(</form>'
        export_webserver.config = config_body
        export_webserver.addon = {} # ensure addon is functional
        return True

    def publish(self, inverter):
      logger.debug("Webserver.publish() called...")
      if (self.req == None):
        json_array={"registers":{}, "client_config":{}, "inverter_config":{}}
        metrics_body = ""
        main_body = f"""
            <h3>SunGather v{__version__}</h3></p>
            <h4>Need Help? <href a='https://github.com/bohdan-s/SunGather'>https://github.com/bohdan-s/SunGather</a></h4></p>
            <h4>NEW HomeAssistant Add-on: <href a='https://github.com/bohdan-s/hassio-repository'>https://github.com/bohdan-s/SunGather</a></h4></p>
            """
        main_body += "<table><tr><th>Address</th><th>Register</th><th>Value</th></tr>"
        for register, value in inverter.latest_scrape.items():
            main_body += f"<tr><td>{str(inverter.getRegisterAddress(register))}</td><td>{str(register)}</td><td>{str(value)} {str(inverter.getRegisterUnit(register))}</td></tr>"
            metrics_body += f"{str(register)}{{address=\"{str(inverter.getRegisterAddress(register))}\", unit=\"{str(inverter.getRegisterUnit(register))}\"}} {str(value)}\n"
            json_array["registers"][str(inverter.getRegisterAddress(register))]={"register": str(register), "value":str(value), "unit": str(inverter.getRegisterUnit(register))}
        main_body += f"</table><p>Total {len(inverter.latest_scrape)} registers"

        main_body += "</p></p><table><tr><th>Configuration</th><th>Value</th></tr>"
        for setting, value in inverter.client_config.items():
            main_body += f"<tr><td>{str(setting)}</td><td>{str(value)}</td></tr>"
            json_array["client_config"][str(setting)]=str(value)
        for setting, value in inverter.inverter_config.items():
            main_body += f"<tr><td>{str(setting)}</td><td>{str(value)}</td></tr>"
            json_array["inverter_config"][str(setting)]=str(value)
        main_body += f"</table></p>"

        export_webserver.main = main_body
        export_webserver.metrics = metrics_body
        export_webserver.json = json.dumps(json_array)
        return True

      else:
        # use req to POST values to the server
        logger.debug("Attempting to publish using POST to the server")
        payload = { 'inverter_config': inverter.inverter_config }
        payload['client_config'] = inverter.client_config
        payload['scrape'] = []
        for register, value in inverter.latest_scrape.items():
          payload['scrape'].append({'address':inverter.getRegisterAddress(register), 'name': register, 'value':value, 'unit':inverter.getRegisterUnit(register)})

        debgText = json.dumps(payload)
        #logger.debug(f" publishings json: {debgText}")
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(self.req['url'], method='POST')
        req.add_header('Content-Type','application/json')
        status = 0
        try:
          resp = urllib.request.urlopen(req, data)
          status = resp.status
        except Exception as ex:
          logger.error(f"Exception encountered: {ex}")
          return False
        if status == 200:
          logger.debug("data sent to server")
          return True

      return False



class MyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        logger.debug("do_GET called...")
        if self.path.startswith('/ping'):
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(bytes("<html><head><title>PONG</title></head>", "utf-8"))
            html = f"<body>SunGather Export WebServer v{__version__}</body></html>"
            self.wfile.write(bytes(html,"utf-8"))
        elif self.path.startswith('/metrics'):
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(bytes(export_webserver.metrics, "utf-8"))
            for addon in export_webserver.addon:
              if 'metrics' in export_webserver.addon[addon]:
                self.wfile.write(bytes(export_webserver.addon[addon]['metrics'],'utf-8'))
        elif self.path.startswith('/config'):
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(bytes(export_webserver.config, "utf-8"))
            for addon in export_webserver.addon:
              if 'config' in export_webserver.addon[addon]:
                self.wfile.write(bytes(export_webserver.addon[addon]['config'], 'utf-8'))
            parsed_data = parse_qs(urlparse(self.path).query)
            logger.info(f"{parsed_data}")
        elif self.path.startswith('/json'):
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(bytes(export_webserver.json, "utf-8"))
            for addon in export_webserver.addon:
              if 'json' in export_webserver.addon[addon]:
                self.wfile.write(bytes(export_webserver.addon[addon]['json'],"utf-8"))
        else:
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(bytes("<html><head><title>SunGather</title>", "utf-8"))
            self.wfile.write(bytes("<meta charset='UTF-8'><meta http-equiv='refresh' content='15'>", "utf-8"))
            self.wfile.write(bytes('<style media = "all"> body { background-color: black; color: white; } @media screen and (prefers-color-scheme: light) { body { background-color: white; color: black; } } </style>', "utf-8"))
            self.wfile.write(bytes("</head>", "utf-8"))
            self.wfile.write(bytes("<body>", "utf-8"))
            self.wfile.write(bytes(export_webserver.main, "utf-8"))
            for addon in export_webserver.addon:
              self.wfile.write(bytes("<br />", 'utf-8'))
              logger.debug("applying addon to the page")
              self.wfile.write(bytes(export_webserver.addon[addon]['main'],"utf-8"))
              self.wfile.write(bytes(export_webserver.addon[addon]['config'],'utf-8'))
            self.wfile.write(bytes("</table>", "utf-8"))
            self.wfile.write(bytes("</body></html>", "utf-8"))

    def do_POST(self):
        logger.debug("do_POST called...")
        length = int(self.headers['Content-Length'])
        logger.debug(f"  length of data from header is {length}")
        data = self.rfile.read(length).decode('utf-8')
        if self.path.startswith('/publish'):
          logger.info("POST path: /publish")
          #logger.debug(f"  data: {data}")
          #dataType = data.__class__
          #logger.debug(f"  data is {dataType}")
          post_data = json.loads(data)
          #post_data = urllib.parse.parse_qs(self.rfile.read(length).decode('utf-8'))
          logger.info(f"post_data: {post_data}")
          sn=None
          json_array = {}
          config_body=""
          # search for the required items
          if 'inverter_config' in post_data or 'client_config' in post_data:
            config_body = "</p><table><tr><th>Configuration</th><th>Value</th></tr>"
            if 'client_config' in post_data:
              json_array['client_config']=post_data['client_config']
              for key,value in post_data['client_config'].items():
                config_body += f"<tr><td>{key}</td><td>{value}</td></tr>"
                #if key == "serial_number":
                #  sn=value
            if 'inverter_config' in post_data:
              json_array['inverter_config'] = post_data['inverter_config']
              for key,value in post_data['inverter_config'].items():
                config_body += f"<tr><td>{key}</td><td>{value}</td></tr>"
                if key == "serial_number":
                  sn=value
            config_body += "</table><p>"
  
          self.send_response(200)
          self.end_headers()
          self.wfile.write(json.dumps({'result':"success"}).encode('utf-8'))
          main_body = "</p><table><tr><th>Address</th><th>Register</th><th>Value</th></tr>"
          json_array = { 'registers':{} }
          metrics_body = "----------------------------\n"
          if sn != None and 'scrape' in post_data:
            logger.debug("  sn is not None and scrape found!")
            for item in post_data['scrape']:
              if item['name'] == "serial_number":
                sn = item['value']
              else:
                main_body += f"<tr><td>{str(item['address'])}</td><td>{str(item['name'])}</td><td>{str(item['value'])} {str(item['unit'])}</td></tr>"
                metrics_body += f"{str(item['name'])}{{address=\"{str(item['address'])}\", unit=\"{str(item['unit'])}\"}} {str(item['value'])}\n"
                json_array["registers"][str(item['address'])]={"register": str(item['name']), "value":str(item['value']), "unit": str(item['unit'])}
  
            main_body += f"</table><p>Total {len(post_data['scrape'])} registers"
            if not sn in export_webserver.addon:
              logger.debug(f"  creating addon shell for {sn}")
              export_webserver.addon[sn] = {}
            #logger.debug(f"    adding main: {main_body}")
            export_webserver.addon[sn]['main'] = main_body
            export_webserver.addon[sn]['config'] = config_body
            export_webserver.addon[sn]['metrics'] = metrics_body
            export_webserver.addon[sn]['json'] = json.dumps(json_array)
        elif self.path.startswith('/control'):
            logger.error("POST to /control - Not Implemented")
        else:
            logger.error(f"POST to {self.path} - Not Implemented")

    def log_message(self, format, *args):
        pass
