from typing import List, Optional, Callable, Union
import json
from websockets.sync.client import connect as sync_connect
from yfinance import WebSocket

class CustomWebsocket(WebSocket):
    
    proxy = None
    

    def listen(self, message_handler: Optional[Callable[[dict], None]] = None):
        """
        Start listening to messages from the WebSocket server.

        Args:
            message_handler (Optional[Callable[[dict], None]]): Optional function to handle received messages.
        """
        self.stop = False
        self._connect()

        self.logger.info("Listening for messages...")
        if self.verbose:
            print("Listening for messages...")

        while not self.stop:
            try:
                message = self._ws.recv()
                message_json = json.loads(message)
                encoded_data = message_json.get("message", "")
                decoded_message = self._decode_message(encoded_data)

                if message_handler:
                    try:
                        message_handler(decoded_message)
                    except Exception as handler_exception:
                        self.logger.error("Error in message handler: %s", handler_exception, exc_info=True)
                        if self.verbose:
                            print("Error in message handler:", handler_exception)
                else:
                    print(decoded_message)

            except KeyboardInterrupt:
                if self.verbose:
                    print("Received keyboard interrupt.")
                self.close()
                break

            except Exception as e:
                self.logger.error("Error while listening to messages: %s", e, exc_info=True)
                if self.verbose:
                    print("Error while listening to messages: %s", e)
                break
            
    def _connect(self):
        try:
            if self._ws is None:
                self._ws = sync_connect(self.url, proxy=self.proxy)
                self.logger.info("Connected to WebSocket.")
                if self.verbose:
                    print("Connected to WebSocket.")
        except Exception as e:
            self.logger.error("Failed to connect to WebSocket: %s", e, exc_info=True)
            if self.verbose:
                print(f"Failed to connect to WebSocket: {e}")
            self._ws = None
            raise