from cogenircapp.tests import *

class TestIrcController(TestController):

    def test_index(self):
        response = self.app.get(url_for(controller='irc'))
        # Test response...
