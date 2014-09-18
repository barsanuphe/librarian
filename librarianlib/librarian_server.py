from http.server import HTTPServer, SimpleHTTPRequestHandler
import os
import threading
from urllib.parse import quote, unquote


class LibrarianServer(HTTPServer):
    def __init__(self, server_address, RequestHandlerClass,
                 allowed, library_dir, collections_json):
        HTTPServer.__init__(self, server_address, RequestHandlerClass)
        self.allowed = allowed
        # to make sure all goes well later when splitting and joining
        if not library_dir.endswith("/"):
            library_dir += "/"
        self.allowed_relative = [el.split(library_dir)[1] for el in allowed]
        self.library_dir = library_dir
        self.collections_json = collections_json


class LibrarianHandler(SimpleHTTPRequestHandler):

    def do_GET(self):
        clean_path = unquote(self.path[1:])
        if clean_path == "index":
            print("Sending index of filtered ebooks...")
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            text = "|".join(self.server.allowed_relative)
            self.wfile.write(text.encode("utf8"))
        elif clean_path in self.server.allowed_relative or \
                clean_path == "collections.json":
            super(LibrarianHandler, self).do_GET()
        elif clean_path == "LibrarianServer::shutdown":
            # return response and shutdown the server
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write("Shutting down server.".encode("utf8"))
            print("Shutting down server.")
            assassin = threading.Thread(target=self.server.shutdown)
            assassin.daemon = True
            assassin.start()
        else:
            return self.send_error(404, 'File Not Found: %s' % clean_path[1:])

    def translate_path(self, path):
        clean_path = unquote(self.path[1:], encoding='utf-8')
        if clean_path == "collections.json":
            print("Sending collections...")
            return self.server.collections_json
        else:
            print("Sending %s..." % clean_path)
            # add library dir to path to actually retrieve the file
            return os.path.join(self.server.library_dir, clean_path)

    def log_message(self, format, *args):
        # muting default output
        return


if __name__ == "__main__":
    try:
        library_dir = ""
        allowed = [""]
        port = 8080
        server = LibrarianServer(('IP', port), LibrarianHandler, allowed,
                                 library_dir)
        server.serve_forever()

    except KeyboardInterrupt:
        server.shutdown()
        server.socket.close()
