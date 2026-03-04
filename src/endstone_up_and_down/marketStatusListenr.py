import time
import threading

import yfinance as yf
from endstone_up_and_down.customWebsocket import CustomWebsocket

class MarketStatusListener():
    def __init__(self, stock_name):
        self.stock_name = stock_name
        self.tradeable = True
        self.last_update_time = time.time()
        self.status_check_thread = None
    
    
    def check_status(self):
        while True:
            time.sleep(30 * 60) # Check every 30 mins
            if time.time() - self.last_update_time > 20 * 60:
                # 20 mins not update, switch to offline mode
                self.tradeable = False
            else:
                self.tradeable = True
            print(self.tradeable)
            
    def start_websocket(self):
        ws = CustomWebsocket()
        def message_handler(message):
            self.last_update_time = time.time()
                
        ws.subscribe(self.stock_name)
        ws.listen(message_handler)
        
    
    def start_listen(self):
        self.status_check_thread = threading.Thread(target=self.check_status)
        self.status_check_thread.start()
        
        self.websocket_listen_thread = threading.Thread(target=self.start_websocket)
        self.websocket_listen_thread.start()
        
        
if __name__ == '__main__':
    listener = MarketStatusListener("NVDA")
    listener.start_listen()