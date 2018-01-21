import threading
import time
from cryptopia import Api
from datetime import datetime
from queue import Queue

class operator(threading.Thread):
    def __init__(self, api_key, api_secret, mktCode, numCoins, buyRate, LIVE, targetRate, marketID):
        threading.Thread.__init__(self)
        self.threads = []
        self.api_key = api_key
        self.api_secret = api_secret
        self.exchange = Api(api_key, api_secret)
        self.marketCode = mktCode
        self.coinCode = mktCode.split("/")[0]
        self.BASE_COIN = mktCode.split("/")[1]
        self.numCoins = numCoins
        self.buyRate = buyRate
        self.LIVE = LIVE
        self.targetRate = targetRate
        self.marketID = marketID
        self.stopRunning = threading.Event()

    def kill_all(self):
        for t in self.threads:
            t.stopRunning.set()

    def run(self):

        mktUpdater = marketUpdate(self.api_key, self.api_secret, self.marketID)
        self.threads.append(mktUpdater)
        mktUpdater.start()

        tradeMonitor = orderMonitor(self.api_key, self.api_secret, self.marketCode)
        self.threads.append(tradeMonitor)
        if LIVE:
            tradeMonitor.start()

        print("[+] Colocando ordem: BUY %.8f %s (rate: %.8f)" %(self.numCoins, self.coinCode, self.buyRate))
        if self.LIVE:
            trade, error = self.exchange.submit_trade(self.marketCode, 'Buy', self.buyRate, self.numCoins)
            if error is not None:
                print("\t[X] " + error)
                self.kill_all()
                return
            else:
                print("\t[!] Ordem lançada")

        while(not self.stopRunning.is_set()):
            if not tradeMonitor.tradeQueue.empty():
                trade = tradeMonitor.tradeQueue.get()
                print("[!] Comprou %.8f %s @ %.8f %s" %(trade[0], self.coinCode, trade[1], self.BASE_COIN))
                sellRate = trade[1]*self.targetRate
                dumper = seller(self.api_key, self.api_secret, self.marketCode, trade[0], sellRate)
                self.threads.append(dumper)
                dumper.start()

        self.kill_all()
        return


class marketsUpdate(threading.Thread):
    def __init__(self, api_key, api_secret):
      threading.Thread.__init__(self)
      self.exchange = Api(api_key, api_secret)
      self.markets = {}
      self.lock = threading.Lock()
      self.stopRunning = threading.Event()
      self.success = threading.Event()

    def run(self):
        while(not self.stopRunning.is_set()):
            markets_obj, error = self.exchange.get_markets()
            if error is None:
                self.lock.acquire()
                self.markets = {}
                for m in markets_obj:
                    label = m["Label"]
                    del m["Label"]
                    self.markets[label] = m
                self.success.set()
                self.lock.release()
            else:
                print("[!] Erro ao obter mercados: ", end="")
                print(error)
            time.sleep(0.5)
        return

class marketUpdate(threading.Thread):
    def __init__(self, api_key, api_secret, mktID):
      threading.Thread.__init__(self)
      self.exchange = Api(api_key, api_secret)
      self.mktID = mktID
      self.market = {}
      self.lock = threading.Lock()
      self.stopRunning = threading.Event()

    def run(self):
        while(not self.stopRunning.is_set()):
            market_obj, error = self.exchange.get_market(self.mktID)
            if error is None:
                self.lock.acquire()
                self.market = market_obj
                self.lock.release()
            time.sleep(0.5)
            print("[!] %s %.8f %+.2f%%" %(self.market["Label"], self.market["AskPrice"], self.market["Change"]))

class orderMonitor(threading.Thread):
    def __init__(self, api_key, api_secret, mktCode):
      threading.Thread.__init__(self)
      self.exchange = Api(api_key, api_secret)
      self.mktCode = mktCode
      self.lock = threading.Lock()
      self.stopRunning = threading.Event()
      self.start_date = datetime.utcnow()
      self.tradeQueue = Queue(10)
      self.processedIDs = []

    def run(self):
        while(not self.stopRunning.is_set()):
            trades_obj, error = self.exchange.get_tradehistory(self.mktCode)
            if error is None:
                for trade in trades_obj:
                    tradeDate = trade["TimeStamp"][0:len(trade["TimeStamp"])-1]
                    if trade["Type"] == "Buy" and datetime.strptime(tradeDate, "%Y-%m-%dT%H:%M:%S.%f") >= self.start_date and trade["TradeId"] not in self.processedIDs:
                        self.tradeQueue.put([trade["Amount"], trade["Rate"]])
                        self.processedIDs.append(trade["TradeId"])
            time.sleep(0.5)

class seller(threading.Thread):
    def __init__(self, api_key, api_secret, mktCode, sellCoins, sellRate):
      threading.Thread.__init__(self)
      self.exchange = Api(api_key, api_secret)
      self.mktCode = mktCode
      self.codeSplit = mktCode.split("/")
      self.sellCoins = sellCoins
      self.sellRate = sellRate
      self.stopRunning = threading.Event()

    def run(self):
        print("[+] Colocando ordem: SELL %.8f %s (rate: %.8f)" %(self.sellCoins, self.codeSplit[0], self.sellRate))
        trade, error = self.exchange.submit_trade(self.mktCode, 'Sell', self.sellRate, self.sellCoins)
        if error is not None:
            print("\t[X] " + error)
        else:
            print("\t[!] Ordem lançada")
