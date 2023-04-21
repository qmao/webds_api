import traceback
from tornado.web import HTTPError
from tornado.iostream import StreamClosedError


def handle_message(message):
    print(message)
    
class HttpBadRequest(HTTPError):
    def __init__(self, message):
        traceback.print_stack()
        handle_message(message)
        super().__init__(status_code=400, log_message=message)
        
class HttpNotFound(HTTPError):
    def __init__(self, message="Not Found"):
        handle_message(message)
        super().__init__(status_code=404, log_message=message)
        
class HttpBrokenPipe(HTTPError):
    def __init__(self, message):
        print("Oops broken pipe")
        handle_message(message)
        super().__init__(status_code=404, log_message=message)
        
class HttpServerError(HTTPError):
    def __init__(self, message):
        handle_message(message)
        super().__init__(status_code=500, log_message=message)

class HttpStreamClosed(HTTPError):
    def __init__(self, message="stream closed"):
        handle_message(message)
        super().__init__(status_code=404, log_message=message)        

