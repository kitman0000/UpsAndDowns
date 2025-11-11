import yfinance as yf
from decimal import Decimal


def get_stock_last_price(stock):
    '''
        Return price, tradeable
    '''

    ticket = yf.Ticker(stock)

    df = ticket.history(period="1y",interval="1mo", prepost=True)
    price = round(df.Close.iloc[-1], 2)
    price = Decimal(str(price))
    
    return price, ticket.info['tradeable']

market_price = get_stock_last_price("BTC-USD")
market_price = Decimal(market_price[0])

price = Decimal(market_price)

pass
