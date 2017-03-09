from fractalis.data.etlhandler import ETLHandler


class TestHandler(ETLHandler):

    _handler = 'test'

    def _heartbeat(self):
        pass

    def _get_token_for_credentials(self, server: str,
                                   user: str, passwd: str) -> str:
        pass
