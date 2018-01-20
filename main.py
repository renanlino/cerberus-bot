from cryptopia import Api
import json
import time
import sys
from cryptoThreads import *
import threading
import copy
from datetime import datetime
import signal

def readSecrets():
    try:
        secretsFile = open("secrets.json", "r")
    except IOError:
        print("[X] Erro ao abrir arquivo secrets.json")
        secretsAssistant()
        return readSecrets()
    try:
        secretsObj = json.load(secretsFile)
    except ValueError:
        print("[X] Erro ao parsear o conteúdo de secrets.json")
        return {}
    secretsFile.close()
    return secretsObj

def secretsAssistant():
    print("Esse assistente vai te guiar pelo processo")
    print("de configuração da API da Cryptopia.")
    print()
    print("1) Faça login na sua conta pelo link https://www.cryptopia.co.nz/Login")
    print("2) Acesse as configurações de segurança em https://www.cryptopia.co.nz/Security")
    print("3) Digite seu PIN e clique em Unlock")
    print("4) Em 'API Settings', marque 'Enable API'")
    print("5) Para sua segurança, NÃO MARQUE 'Enable Withdraw'")
    print()
    api_key = input("Cole o valor do campo 'Api Key': ")
    api_secret = input("Cole o valor do campo 'Api Secret': ")
    print("6) Clique em 'Save Changes'")
    input("Pressione ENTER para continuar")
    print()
    print("[!][!][!] ATENÇÃO [!][!][!]")
    print("Este programa vai criar um arquivo local com os seus")
    print("dados de acesso à API da Cryptopia.")
    print("Mantenha esse arquivo em segurança e jamais compartilhe")
    print("seu conteúdo!")
    input("Pressione ENTER para salvar e continuar")

    try:
        secretsFile = open("secrets.json", "w")
    except IOError:
        print("[X] Não foi possível gravar os dados de acesso!")

    secretsObj = {"cryptopia":{"api_key":api_key, "api_secret":api_secret}}
    json.dump(secretsObj, secretsFile)
    secretsFile.close()

def waitForSignal(pumpBalance, pumpRate, targetRate):
    print()
    print("============== ESPERANDO SINAL ==============")
    print()
    print("Valor disponível: %f%s" %(pumpBalance, BASE_COIN))
    print("Preço de Entrada: %.3f%% do ASK" %(100*pumpRate))
    print("Alvo de Saída: %.3f%%" %(100*(targetRate-1)))
    print()
    if LIVE:
        print("[!] ATENÇÃO: Ao fornecer o código da moeda as ordens serão colocadas automaticamente")
    else:
        print("[!] MODO DE TESTES ATIVADO: As ordens NÃO serão enviadas.")
    print()


    coinCodes = input("Digite o CÓDIGO da moeda: ")

    coinCodes = coinCodes.split(" ")
    mktsUpdater.lock.acquire()
    for coinCode in coinCodes:

        coinCode = coinCode.upper().replace(" ","")
        marketCode = coinCode + "/" + BASE_COIN

        mkt = copy.deepcopy( mktsUpdater.markets[marketCode] )

        marketID = str(mkt["TradePairId"])
        print(marketCode)
        print("\tASK: %f" %(mkt["AskPrice"]))
        print("\tBID: %f" %(mkt["BidPrice"]))
        print("\tCNG: %.2f%%" %(mkt["Change"]))

        buyRate = mkt["AskPrice"]*pumpRate
        numCoins = pumpBalance / (len(coinCodes)*buyRate)

        pdAgent = operator(api_key, api_secret, marketCode, numCoins, buyRate, LIVE, targetRate, marketID)
        threads.append(pdAgent)
        pdAgent.start()

    mktsUpdater.lock.release()
    mktsUpdater.stopRunning.set()

def setup():

    global LIVE

    print("Obtendo saldo...")
    balance_obj, error = exchange.get_balance(BASE_COIN)
    if error is None:
        print("%s:" %(BASE_COIN))
        print("\tTOTAL: %f" %(balance_obj["Total"]) )
        print("\tDISPO: %f" %(balance_obj["Available"]) )
    else:
        print("[X] " + error)
        return

    print()
    print("============== CONFIGURAÇÃO DO PUMP ==============")
    print()

    liveMode = input("Digite 'LIVE' para sair do modo de testes: ")
    if liveMode == "LIVE":
        LIVE = True
        print("\t[!] MODO DE TESTES DESATIVADO")

    pumpBalance = float(input("Digite O VALOR PERCENTUAL que será aplicado no pump: "))/100
    pumpBalance = balance_obj["Available"]*pumpBalance*(1-EX_FEE)
    print("\tVocê entrará no pump com %f %s (descontadas as taxas)" %(pumpBalance, BASE_COIN))

    pumpRate = input("ACRÉSCIMO PERCENTUAL sobre o preço de compra (padrão = 0): ")
    if pumpRate == "":
        pumpRate = 0
    pumpRate = 1 + float(pumpRate)/100

    targetRate = input("ACRÉSCIMO PERCENTUAL ALVO (padrão = 30): ")
    if targetRate == "":
        targetRate = 30
    targetRate = 1 + float(targetRate)/100

    waitForSignal(pumpBalance, pumpRate, targetRate)

"""""
CONFIGURAÇÃO E INICIALIZAÇÃO
"""""

LIVE = False
BASE_COIN = "BTC"
EX_FEE = 0.2/100
threads = []

if "-check" in sys.argv:
    checkPump = True
else:
    checkPump = False

secrets = readSecrets()
if secrets == {}:
    sys.exit(1)

print("[+] Configurando credenciais de acesso...")
api_key = secrets["cryptopia"]["api_key"]
api_secret = secrets["cryptopia"]["api_secret"]

exchange = Api(api_key, api_secret)

mktsUpdater = marketsUpdate(api_key, api_secret)
threads.append(mktsUpdater)
mktsUpdater.start()

print("[+] Obtendo mercados...")
while(not mktsUpdater.success.is_set()):
    time.sleep(0.1)

setup()
