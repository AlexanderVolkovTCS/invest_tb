import time

from datetime import datetime, timedelta, timezone, tzinfo
from tqdm.auto import tqdm
import keyring
from tinkoff.invest import CandleInterval, Client, Quotation
from tinkoff.invest.utils import now
from joblib import Parallel, delayed
from tinkoff.invest.utils import quotation_to_decimal
from typing import List
import feedparser
import re
import pandas as pd
import pymorphy2
from googletrans import Translator
import numpy as np
import pytz

from Collect_data.sql_supporter.sql_sup import Sqler

TOKEN = keyring.get_password('TOKEN', 'INVEST')
SANDBOX_TOKEN = keyring.get_password('TOKEN', 'SANDBOX')
sandbox_account_id = keyring.get_password('ACCOUNT_ID', 'SANDBOX')


def cleanhtml(raw_html):
    pattern = re.compile('<.*?>')
    cleantext = re.sub(pattern, '', raw_html)
    return cleantext


class DataCollector:
    def __init__(self, token=None, sources=None, user='nikolay'):
        if sources is None:
            sources = ['https://moex.com/export/news.aspx?cat=100', 'https://www.finam.ru/analysis/conews/rsspoint']
        self.token = token
        self.client = Client(token=token)
        self.USER = user
        self.SQL_PASS = keyring.get_password('SQL', self.USER)
        self.sources = sources

    def get_shares_info(self):
        with self.client as client:
            shares = client.instruments.shares().instruments
            figi = []
            ticker = []
            class_code = []
            isin = []
            lot = []
            currency = []
            klong = []
            kshort = []
            dlong = []
            dshort = []
            dlong_min = []
            dshort_min = []
            short_enabled_flag = []
            name = []
            exchange = []
            ipo_date = []
            issue_size = []
            country_of_risk = []
            country_of_risk_name = []
            sector = []
            issue_size_plan = []
            nominal = []
            trading_status = []
            otc_flag = []
            buy_available_flag = []
            sell_available_flag = []
            div_yield_flag = []
            share_type = []
            min_price_increment = []
            api_trade_available_flag = []
            uid = []
            real_exchange = []
            for share in shares:
                figi.append(share.figi)
                ticker.append(share.ticker)
                class_code.append(share.class_code)
                isin.append(share.isin)
                lot.append(share.lot)
                currency.append(share.currency)
                klong.append(quotation_to_decimal(share.klong))
                kshort.append(quotation_to_decimal(share.kshort))
                dlong.append(quotation_to_decimal(share.dlong))
                dshort.append(quotation_to_decimal(share.dshort))
                dlong_min.append(quotation_to_decimal(share.dlong_min))
                dshort_min.append(quotation_to_decimal(share.dshort_min))
                short_enabled_flag.append(quotation_to_decimal(share.dshort_min))
                name.append(share.name)
                exchange.append(share.exchange)
                ipo_date.append(share.ipo_date)
                issue_size.append(share.issue_size)
                country_of_risk.append(share.country_of_risk)
                country_of_risk_name.append(share.country_of_risk_name)
                sector.append(share.sector)
                issue_size_plan.append(share.issue_size_plan)
                nominal.append(quotation_to_decimal(Quotation(share.nominal.units, share.nominal.nano)))
                trading_status.append(share.trading_status)
                otc_flag.append(share.otc_flag)
                buy_available_flag.append(share.buy_available_flag)
                sell_available_flag.append(share.sell_available_flag)
                div_yield_flag.append(share.div_yield_flag)
                share_type.append(share.share_type)
                min_price_increment.append(quotation_to_decimal(share.min_price_increment))
                api_trade_available_flag.append(share.api_trade_available_flag)
                uid.append(share.uid)
                real_exchange.append(share.real_exchange)
            d = {'figi': figi, 'ticker': ticker, 'class_code': class_code, 'isin': isin, 'lot': lot,
                 'currency': currency,
                 'klong': klong, 'kshort': kshort, 'dlong': dlong, 'dshort': dshort, 'dlong_min': dlong_min,
                 'dshort_min': dshort_min, 'short_enabled_flag': short_enabled_flag, 'name': name,
                 'exchange': exchange, 'ipo_date': ipo_date, 'issue_size': issue_size, 'nominal': nominal,
                 'trading_status': trading_status, 'otc_flag': otc_flag, 'buy_available_flag': buy_available_flag,
                 'sell_available_flag': sell_available_flag, 'div_yield_flag': div_yield_flag,
                 'share_type': share_type, 'min_price_increment': min_price_increment,
                 'api_trade_available_flag': api_trade_available_flag, 'uid': uid, 'real_exchange': real_exchange
                 }
            shares = pd.DataFrame(d)
        return shares

    @staticmethod
    def create_dataset(list_candels: List = None, figi: str = None) -> pd.DataFrame:
        times = []
        opens = []
        closes = []
        highs = []
        lows = []
        volumes = []
        is_completes = []
        for candle in list_candels:
            highs.append(quotation_to_decimal(candle.high))
            lows.append(quotation_to_decimal(candle.low))
            opens.append(quotation_to_decimal(candle.open))
            closes.append(quotation_to_decimal(candle.close))
            volumes.append(candle.volume)
            times.append(candle.time)
            is_completes.append(candle.is_complete)
        df = pd.DataFrame(
            {'figi': figi, 'time': times, 'open': opens, 'close': closes, 'high': highs, 'low': lows, 'volume': volumes,
             'is_complete': is_completes})
        return df

    def get_all_candles_day(self, idx, interval, start):

        start = datetime(*start)
        tmp_df = []
        candles = []
        errors = {}
        f = []
        l = []
        with self.client as client:
            for y in range(now().year - start.year + 1):
                if y == 22:
                    try:
                        candle = client.market_data.get_candles(figi=idx,
                                                                from_=datetime(2022, 1, 1),
                                                                to=now(),
                                                                interval=CandleInterval(interval)).candles
                        candles.append(candle)
                    except:
                        f.append(idx)
                        l.append(y)
                else:
                    try:
                        candle = client.market_data.get_candles(figi=idx,
                                                                from_=datetime(start.year + y, start.month, start.day),
                                                                to=datetime(start.year + y + 1, start.month, start.day),
                                                                interval=CandleInterval(5)).candles
                        candles.append(candle)
                    except:
                        f.append(idx)
                        l.append(y)

        for c in candles:
            tmp_df.append(self.create_dataset(c, idx))
        errors['figi'] = f
        errors['y'] = l
        return tmp_df, errors

    def get_all_candles_min(self, idx, interval, start):
        start = datetime(*start)
        tmp_df = []
        candles = []
        good_days = []
        n = datetime(datetime.now().date().year, datetime.now().date().month, datetime.now().date().day)
        delta = n - start
        with Client(token=self.token) as client:
            while len(good_days) != int(delta.total_seconds() / 86400):
                for d in range(int(delta.total_seconds() / 86400)):
                    if d not in good_days:
                        try:
                            candle = client.market_data.get_candles(figi=idx,
                                                                    from_=start + timedelta(days=d),
                                                                    to=start + timedelta(days=d + 1),
                                                                    interval=CandleInterval(interval)).candles
                            candles.append(candle)  # 86400

                            good_days.append(d)

                        except:
                            continue
        for c in candles:
            tmp_df.append(self.create_dataset(c, idx))
        return tmp_df

    def create_shares_parquet(self, fn):
        figi = self.get_shares_info().figi.values
        # figi = shares.figi.values
        good_figi = []
        while len(good_figi) != len(figi):
            for idx in tqdm(figi):
                df, errors = fn(idx)
                good_figi.append(idx)
                time.sleep(1)
                df = pd.concat(df, ignore_index=True)
                df.to_parquet(f'Shares/2022_now/{idx}.parquet')
                errors = pd.DataFrame(errors)
                errors.to_parquet(f'Shares/2022_now/{idx}_err.parquet')

    def make_ru_news_dataset(self, sql=False):
        def make_date(entry):
            mon = entry.published_parsed.tm_mon
            day = entry.published_parsed.tm_mday
            year = entry.published_parsed.tm_year
            hour = entry.published_parsed.tm_hour
            min = entry.published_parsed.tm_min
            dates = [mon, day, year, hour, min]
            for i in range(len(dates)):
                if dates[i] < 10:
                    dates[i] = str(0) + str(dates[i])
            mon, day, year, hour, min = dates
            return f'{year}-{mon}-{day} {hour}:{min}'

        def is_cyrillic(name):
            lower = set('абвгдеёжзийклмнопрстуфхцчшщъыьэюя')
            return lower.intersection(name.lower()) != set()

        def get_cases(name: str, currency):
            morph = pymorphy2.MorphAnalyzer()
            if is_cyrillic(name):
                lex = morph.parse(name)[0].lexeme
                lexemes = [word[0] + "|" + word[0].capitalize() + "|" for word in lex]
            elif currency == 'rub':
                translator = Translator()
                rus_name = translator.translate(name, src='en', dest='ru').text
                rus_lex = morph.parse(rus_name)[0].lexeme
                en_lex = [name + "'s|"]
                rus_lexemes = [word[0] + "|" + word[0].capitalize() + "|" for word in rus_lex]
                lexemes = rus_lexemes + en_lex
                time.sleep(5)
            else:
                lexemes = [name, name + "'s|"]
            return ''.join(lexemes)

        def target_builder(name: str, ticker: str, currency):
            ru_dict = {"Fix Price Group": "Фикс Прайс", "O'Key": "О'КЕЙ",
                       "Ozon Holdings PLC": "Озон", "Polymetal": "Полиметалл",
                       "QIWI": "Киви", "TCS Group": "Тинькофф",
                       "VK": "ВКонтакте"}
            if name in ru_dict:
                return f"{name}|{ticker}|" + get_cases(ru_dict[name], currency)
            else:
                return f"{name}|{ticker}" + get_cases(name, currency)

        def take_news(sources, target):
            titles = []
            summary = []
            dates = []
            target_pattern = re.compile(target)
            s = []
            for source in sources:
                NewsFeed = feedparser.parse(source)
                entries = NewsFeed.entries
                for entry in entries:
                    title = cleanhtml(entry.title)
                    try:
                        text = cleanhtml(entry.content[0].value)
                    except:
                        text = cleanhtml(entry.summary)
                    raw = title + ' ' + text
                    if re.search(target_pattern, raw):
                        titles.append(' '.join(title.replace('&quot;', '').replace('&n;', '').split()))
                        dates.append(make_date(entry))
                        summary.append(' '.join(text.replace('&quot;', '').replace('&n;', '').split()))
                        if 'moex' in source:
                            s.append('moex')
                        else:
                            s.append('finam')

            titles = pd.DataFrame({'name': target.split('|')[0], 'date': dates, 'source': s, 'title': titles,
                                   'summary': summary})
            return titles

        sqler = Sqler(user=self.USER, password=self.SQL_PASS)

        figi = sqler.read_sql("""SELECT DISTINCT name,ticker,currency from shares_info""").collect()
        targets = Parallel(n_jobs=-1)(
            delayed(target_builder)(row.name, row.ticker, row.currency) for row in tqdm(figi) if row.currency == 'rub')
        t = Parallel(n_jobs=-1)(delayed(take_news)(self.sources, target) for target in tqdm(targets))
        df = pd.concat(t)
        if sql:
            sqler.create_table(df, 'ru_feeds')

        return df

    def data_updater(self):

        sqler = Sqler(user=self.USER, password=self.SQL_PASS)
        shares = self.get_shares_info()
        ru_figi = shares[shares['currency'] == 'rub'].figi
        last_day = sqler.get_last_date('candles_day_rus').collect()[0].min  # 5
        last_hour = sqler.get_last_date('candles_hour_rus').collect()[0].min  # 4
        last_15min = sqler.get_last_date('candles_15min_rus').collect()[0].min  # 3
        last_5min = sqler.get_last_date('candles_5min_rus').collect()[0].min  # 2
        last_1min = sqler.get_last_date('candles_1min_rus').collect()[0].min  # 1
        idx_to_table = {5:'candles_day_rus',4:'candles_hour_rus',3:'candles_15min_rus',2:'candles_5min_rus',1:'candles_1min_rus'}
        idx_to_frame = {5: last_day, 4: last_hour, 3: last_15min, 2: last_5min, 1: last_1min}
        delta_to_frame = {5: timedelta(days=1), 4: timedelta(hours=1), 3: timedelta(minutes=15),
                          2: timedelta(minutes=5), 1: timedelta(minutes=1)}
        debug = {5:'day',4:'hour',3:'15min',2:'5min',1:'1min'}
        while True:
            for i in range(1, 6):
                for idx in tqdm(ru_figi):
                    time_in_db = sqler.get_last_date_by_figi(idx,idx_to_table.get(i)).collect()[0].max
                    if time_in_db:
                        tzdata = pytz.timezone('Europe/Moscow')
                        time_in_db = tzdata.localize(time_in_db)
                        if now() - time_in_db > delta_to_frame.get(i):
                            try:
                                with Client(token=self.token) as client:
                                    candle = client.market_data.get_candles(figi=idx,from_=time_in_db,to=time_in_db+timedelta(days=1),interval=i).candles
                                    pd_df = self.create_dataset(candle,idx)
                                    print(pd_df)
                                    if not pd_df.empty:
                                        pd_df.is_complete = pd_df.is_complete.apply(int)
                                        sqler.insert(df=pd_df,table=idx_to_table.get(i))
                            except:
                                time.sleep(60)

                            # candles = []
                            # with Client(token=self.token) as client:
                            #     n = datetime(datetime.now().date().year, datetime.now().date().month,
                            #                  datetime.now().date().day)
                            #     n = tzdata.localize(n)
                            #     delta = n - time_in_db
                            #     good_days = []
                            #     while len(good_days) != int(delta.total_seconds() / 86400):
                            #         for d in range(int(delta.total_seconds() / 86400)):
                            #             if d not in good_days:
                            #                 try:
                            #                     candle = client.market_data.get_candles(figi=idx,
                            #                                                             from_=time_in_db + timedelta(days=d),
                            #                                                             to=time_in_db + timedelta(
                            #                                                                 days=d + 1),
                            #                                                             interval=CandleInterval(
                            #                                                                 i)).candles
                            #                     good_days.append(d)
                            #                     candles.append(candle)
                            #
                            #
                            #
                            #                 except:
                            #                     continue
                            #         df = pd.DataFrame()
                            #         for c in candles:
                            #             tmp_df = self.create_dataset(c,idx)
                            #             if not tmp_df.empty:
                            #                 df = pd.concat([df,tmp_df])
                            #                 df.to_parquet(f'debug/{idx}_{debug.get(i)}_from_{time_in_db.date()}_to{now().date()}.parquet')




dc = DataCollector(token=TOKEN)
dc.data_updater()
