import urllib.request, urllib.parse, urllib.error
import json
import time
import hmac
import hashlib
import base64
import requests
try:
    import secrets
    haveSecrets = True
except ImportError:
    import random
    import string
    haveSecrets = False

MAX_TRY = 3

class Api(object):

    def __init__(self, key, secret):
        self.session = requests.Session()
        self.key = key
        self.secret = base64.b64decode(secret + '=' * (-len(secret) % 4))
        self.public = ['GetCurrencies', 'GetTradePairs', 'GetMarkets',
                       'GetMarket', 'GetMarketHistory', 'GetMarketOrders', 'GetMarketOrderGroups']
        self.private = ['GetBalance', 'GetDepositAddress', 'GetOpenOrders',
                        'GetTradeHistory', 'GetTransactions', 'SubmitTrade',
                        'CancelTrade', 'SubmitTip', 'SubmitWithdraw', 'SubmitTransfer']

    def api_query(self, feature_requested, get_parameters=None, post_parameters=None, retry=0):
        if feature_requested in self.private:
            url = "https://www.cryptopia.co.nz/Api/" + feature_requested
            post_data = json.dumps(post_parameters)
            headers = self.secure_headers(url=url, post_data=post_data)
            self.session.cookies.clear()
            req = self.session.post(url, data=post_data, headers=headers)
            if req.status_code != 200:
                try:
                    req.raise_for_status()
                except requests.exceptions.RequestException as ex:
                    retry += 1
                    if retry <= MAX_TRY:
                        return self.api_query(feature_requested, get_parameters=get_parameters, post_parameters=post_parameters, retry=retry)
                    else:
                        return None, "Status Code : " + str(ex)
            try:
                req = req.json()
            except ValueError:
                retry += 1
                if retry <= MAX_TRY:
                    return self.api_query(feature_requested, get_parameters=get_parameters, post_parameters=post_parameters, retry=retry)
                else:
                    return None, "Server Response : " + req.text
            if 'Success' in req and req['Success'] is True:
                result = req['Data']
                error = None
            else:
                result = None
                error = req['Error'] if 'Error' in req else 'Unknown Error'
            return (result, error)

        elif feature_requested in self.public:
            url = "https://www.cryptopia.co.nz/Api/" + feature_requested + "/" + \
                  ('/'.join(i for i in list(get_parameters.values())
                           ) if get_parameters is not None else "")
            self.session.cookies.clear()
            req = self.session.get(url, params=get_parameters)
            if req.status_code != 200:
                try:
                    req.raise_for_status()
                except requests.exceptions.RequestException as ex:
                    retry += 1
                    if retry <= MAX_TRY:
                        return self.api_query(feature_requested, get_parameters=get_parameters, post_parameters=post_parameters, retry=retry)
                    else:
                        return None, "Status Code : " + str(ex)
            try:
                req = req.json()
            except ValueError:
                retry += 1
                if retry <= MAX_TRY:
                    return self.api_query(feature_requested, get_parameters=get_parameters, post_parameters=post_parameters, retry=retry)
                else:
                    return None, "Server Response : " + req.text
            if 'Success' in req and req['Success'] is True:
                result = req['Data']
                error = None
            else:
                result = None
                error = req['Error'] if 'Error' in req else 'Unknown Error'
            return (result, error)
        else:
            return None, "Unknown feature"

    def get_currencies(self):
        return self.api_query(feature_requested='GetCurrencies')

    def get_tradepairs(self):
        return self.api_query(feature_requested='GetTradePairs')

    def get_markets(self):
        return self.api_query(feature_requested='GetMarkets')

    def get_market(self, market):
        return self.api_query(feature_requested='GetMarket',
                              get_parameters={'market': market})

    def get_history(self, market):
        return self.api_query(feature_requested='GetMarketHistory',
                              get_parameters={'market': market})

    def get_orders(self, market):
        return self.api_query(feature_requested='GetMarketOrders',
                              get_parameters={'market': market})

    def get_ordergroups(self, markets):
        return self.api_query(feature_requested='GetMarketOrderGroups',
                              get_parameters={'markets': markets})

    def get_balance(self, currency):
        result, error = self.api_query(feature_requested='GetBalance',
                                       post_parameters={'Currency': currency})
        if error is None:
            result = result[0]
        return (result, error)

    def get_openorders(self, market):
        return self.api_query(feature_requested='GetOpenOrders',
                              post_parameters={'Market': market})

    def get_deposit_address(self, currency):
        return self.api_query(feature_requested='GetDepositAddress',
                              post_parameters={'Currency': currency})

    def get_tradehistory(self, market):
        return self.api_query(feature_requested='GetTradeHistory',
                              post_parameters={'Market': market})

    def get_transactions(self, transaction_type):
        return self.api_query(feature_requested='GetTransactions',
                              post_parameters={'Type': transaction_type})

    def submit_trade(self, market, trade_type, rate, amount):
        return self.api_query(feature_requested='SubmitTrade',
                              post_parameters={'Market': market,
                                               'Type': trade_type,
                                               'Rate': rate,
                                               'Amount': amount})

    def cancel_trade(self, trade_type, order_id, tradepair_id):
        return self.api_query(feature_requested='CancelTrade',
                              post_parameters={'Type': trade_type,
                                               'OrderID': order_id,
                                               'TradePairID': tradepair_id})

    def submit_tip(self, currency, active_users, amount):
        return self.api_query(feature_requested='SubmitTip',
                              post_parameters={'Currency': currency,
                                               'ActiveUsers': active_users,
                                               'Amount': amount})

    def submit_withdraw(self, currency, address, amount):
        return self.api_query(feature_requested='SubmitWithdraw',
                              post_parameters={'Currency': currency,
                                               'Address': address,
                                               'Amount': amount})

    def submit_transfer(self, currency, username, amount):
        return self.api_query(feature_requested='SubmitTransfer',
                              post_parameters={'Currency': currency,
                                               'Username': username,
                                               'Amount': amount})

    def secure_headers(self, url, post_data):
        if haveSecrets:
            nonce = str(time.time()) + secrets.token_urlsafe(16)
        else:
            nonce = str(time.time()) +  ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(16))
        md5 = hashlib.md5()
        md5.update(post_data.encode('utf-8'))
        rcb64 = base64.b64encode(md5.digest()).decode('utf-8')
        signature = self.key + "POST" + urllib.parse.quote_plus(url).lower() + nonce + rcb64
        sign = base64.b64encode(hmac.new(self.secret, signature.encode('utf-8'), hashlib.sha256).digest())
        header_value = "amx " + self.key + ":" + sign.decode('utf-8') + ":" + nonce
        return {'Authorization': header_value, 'Content-Type': 'application/json; charset=utf-8', "Cookie":None}
