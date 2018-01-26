import threading
import time
from cryptopia import Api
from datetime import datetime, timedelta
from queue import Queue

MIN_TRADE = 0.00050000

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
        self.pumpBalance = self.buyRate*self.numCoins
        self.execEvent = threading.Event()

    def kill_all(self):
        for t in self.threads:
            t.stopRunning.set()

    def run(self):

        mktUpdater = marketUpdate(self.api_key, self.api_secret, self.marketID)
        self.threads.append(mktUpdater)
        mktUpdater.start()

        tradeMonitor = orderMonitor(self.api_key, self.api_secret, self.marketCode)
        self.threads.append(tradeMonitor)
        if self.LIVE:
            tradeMonitor.start()

        self.execEvent.clear()
        pumper = buyer(self.api_key, self.api_secret, self.marketCode, self.numCoins, self.buyRate, self.execEvent)
        self.threads.append(pumper)
        if self.LIVE:
            pumper.start()

        spent = 0
        while(not self.stopRunning.is_set()):
            locked = False
            while not tradeMonitor.tradeQueue.empty():
                tradeMonitor.lock.acquire()
                locked = True
                trade = tradeMonitor.tradeQueue.get()
                print("[!] Comprou %.8f %s @ %.8f %s" %(trade[0], self.coinCode, trade[1], self.BASE_COIN))
                sellRate = trade[1]*self.targetRate
                dumper = seller(self.api_key, self.api_secret, self.marketCode, trade[0], sellRate)
                self.threads.append(dumper)
                dumper.start()
                spent += trade[1]*trade[0]
            if locked:
                tradeMonitor.lock.release()
                foundBuyOrder = False
                if not self.execEvent.is_set():
                    try:
                        orders, error = self.exchange.get_openorders(self.marketCode)
                    except:
                        print("[X] operator: get_openorders exception")
                    if error is None:
                        for order in orders:
                            if order["Type"] == "Buy":
                                foundBuyOrder = True
                    else:
                        foundBuyOrder = True
                        print("[X] operator @ get_openorders: " + error)
                    if not foundBuyOrder and spent + MIN_TRADE < self.pumpBalance:
                        self.pumpBalance -= spent
                        self.numCoins = self.pumpBalance / self.buyRate
                        self.execEvent.clear()
                        pumper = buyer(self.api_key, self.api_secret, self.marketCode, self.numCoins, self.buyRate, self.execEvent)
                        self.threads.append(pumper)
                        pumper.start()

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
        start = time.perf_counter()
        while(not self.stopRunning.is_set()):
            market_obj, error = self.exchange.get_market(self.mktID)
            if error is None:
                self.lock.acquire()
                self.market = market_obj
                self.lock.release()
            end = time.perf_counter()
            elapsedSeconds = end-start
            print("%6.3f [!] %s %.8f %+.2f%%" %(elapsedSeconds, self.market["Label"], self.market["AskPrice"], self.market["Change"]))
            time.sleep(0.5)

class orderMonitor(threading.Thread):
    def __init__(self, api_key, api_secret, mktCode):
      threading.Thread.__init__(self)
      self.exchange = Api(api_key, api_secret)
      self.mktCode = mktCode
      self.lock = threading.Lock()
      self.stopRunning = threading.Event()
      self.start_date = datetime.utcnow() - timedelta(seconds=60)
      self.tradeQueue = Queue(10)
      self.processedIDs = []

    def run(self):
        while(not self.stopRunning.is_set()):
            trades_obj, error = self.exchange.get_tradehistory(self.mktCode)
            if error is None:
                self.lock.acquire()
                for trade in trades_obj:
                    tradeDate = trade["TimeStamp"][0:len(trade["TimeStamp"])-1]
                    if trade["Type"] == "Buy" and datetime.strptime(tradeDate, "%Y-%m-%dT%H:%M:%S.%f") >= self.start_date and trade["TradeId"] not in self.processedIDs:
                        self.tradeQueue.put([trade["Amount"], trade["Rate"]])
                        self.processedIDs.append(trade["TradeId"])
                self.lock.release()
            else:

                print("[X] Order Monitor: " + error)
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
        start = time.perf_counter()
        trade, error = self.exchange.submit_trade(self.mktCode, 'Sell', self.sellRate, self.sellCoins)
        end = time.perf_counter()
        elapsedMilis = int((end-start)*1000)
        if error is not None:
            print("\t[X] seller: " + error)
        else:
            print("\t[!] seller: Ordem lançada (após %dms)" %elapsedMilis )

class buyer(threading.Thread):
    def __init__(self, api_key, api_secret, mktCode, numCoins, buyRate, execEvent):
      threading.Thread.__init__(self)
      self.exchange = Api(api_key, api_secret)
      self.mktCode = mktCode
      self.codeSplit = mktCode.split("/")
      self.numCoins = numCoins
      self.buyRate = buyRate
      self.stopRunning = threading.Event()
      self.execEvent = execEvent

    def run(self):
        print("[+] Colocando ordem: BUY %.8f %s (rate: %.8f)" %(self.numCoins, self.codeSplit[0], self.buyRate))
        start = time.perf_counter()
        trade, error = self.exchange.submit_trade(self.mktCode, 'Buy', self.buyRate, self.numCoins)
        end = time.perf_counter()
        elapsedMilis = int((end-start)*1000)
        if error is not None:
            print("\t[X] buyer: " + error)
        else:
            if trade["OrderId"] is None:
                self.execEvent.set()
                print("\t[!] buyer: Ordem executada (após %dms)" %elapsedMilis )
            else:
                self.execEvent.clear()
                print("\t[!] buyer: Ordem lançada (após %dms)" %elapsedMilis )
