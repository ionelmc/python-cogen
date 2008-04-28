from chatapp.tests import *

class TestChatController(TestController):

    def test_index(self):
        response = self.app.get(url_for(controller='chat'))
        # Test response...
