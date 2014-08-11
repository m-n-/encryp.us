from tornado.ioloop import IOLoop
from tornado.concurrent import Future
from tornado.web import RequestHandler, Application, url
import tornado.httputil
import base64
import json
from datetime import datetime, date
from Crypto.Cipher import AES
import tornado.autoreload
import redis

redis_server = redis.Redis("localhost")
message_futures = []

# this defines a global function to reload the json data when needed
def loadjson():
    with open('static/data.json') as f:
        jsondata = json.load(f)
    return jsondata


# class decrypts the message object contents
class decrypt_msg(object):

    def __init__(self, msg):
        self.name = msg['name']
        self.time = msg['time']
        self.msg = msg['message']
        # message = base64.b64decode(msg['message'])
        # self.msg = obj.decrypt(message).decode("utf-8")


# loads json data and append decrypted information to an array and return
# it for the templates to use
def append_messages():
    json_data = loadjson()
    messages = []

    for data in json_data['messages']:
        messages.append(decrypt_msg(data))

    return messages


class BaseHandler(tornado.web.RequestHandler):

    '''BaseHandler checks that user cookie is set'''

    def get_current_user(self):
        return self.get_secure_cookie("user")


class MessageHandler(BaseHandler):

    '''MessageHandler handles each message'''
    @tornado.web.authenticated
    @tornado.web.asynchronous
    def get(self):
        future = Future()
        future.add_done_callback(self.render_now)
        message_futures.append(future)

    def render_now(self, future):
        self.render("home.html", title="Home Page",
                    username=self.current_user, messages=append_messages())
        # self.finish()


class MainHandler(BaseHandler):

    '''MainHandler shows the chat application @ home.html'''
    @tornado.web.authenticated
    def get(self):
        self.render("home.html", title="Home Page",
                    username=self.current_user, messages=append_messages())

    def post(self):
        msg = self.get_argument("message")
        time = datetime.now().strftime("%Y-%m-%d %H:%M")

        with open('static/data.json') as f:
            data = json.load(f)

        data['messages'].append({'name': self.current_user.decode("utf-8"),
                                 'message': msg, #encrypted_msg
                                 'time': time})

        with open('static/data.json', 'w') as f:
            json.dump(data, f)

        for f in message_futures:
            f.set_result(None)

        message_futures[:] = []


class TestHandler(BaseHandler):
	def get(self):
		username = redis_server.hget("user-evilghost", "password")
		self.render("test.html", title="Account Page", username=username)

class CreateUserHandler(BaseHandler):

    '''This handler shows account information and will allow user to modify'''
    @tornado.web.authenticated
    def post(self):
    	get_un = self.get_argument("username")
    	get_pw = self.get_argument("password")

    	redis_server.hmset("user-" + get_un, {"username":get_un, "password":get_pw})


class LoginHandler(BaseHandler):

    '''This handler shows the login page if user is not logged in'''

    def get(self):
        next_page = self.get_argument("next", default="/")
        if self.current_user:
            self.redirect(next_page)
        else:
            self.render("login.html", title="Login Page",
                        error=None, next_page=next_page)

    # post will make sure that user and password combination are valid
    def post(self):
        get_pw = self.get_argument("password")
        get_un = self.get_argument("username")
        next_page = self.get_argument("next_page", default="/")

        if redis_server.hget("user-" + get_un, "password") is None:
        	self.render("login.html", title="Login Page",
                        error="user does not exist", next_page=next_page)
        else:
        	expected_pw = redis_server.hget("user-" + get_un, "password").decode("utf-8")
        
        if get_pw == expected_pw:
            self.set_secure_cookie("user", get_un)
            self.redirect(next_page)
        else: 
            self.render("login.html", title="Login Page",
                        error="password is wrong", next_page=next_page)



class LogoutHandler(BaseHandler):

    '''This handler clears the user cookie'''
    @tornado.web.authenticated
    def get(self):
        self.clear_cookie("user")
        self.redirect("/")


def make_app():
    '''this is the main application function'''
    app = Application([
        url(r"/", MainHandler),
        url(r"/test", TestHandler),
        url(r"/message", MessageHandler),
        url(r"/createuser", CreateUserHandler),
        url(r"/login", LoginHandler),
        url(r"/logout", LogoutHandler)
    ],
        template_path="templates",
        static_path="static",
        login_url="login",
        cookie_secret="ajfhafaj8r7w73d872")
    app.listen(8888)
    tornado.autoreload.start()
    tornado.autoreload.watch("static/main.js")
    tornado.autoreload.watch("static/main.css")
    tornado.autoreload.watch("templates/")
    IOLoop.current().start()


if __name__ == "__main__":
    make_app()
