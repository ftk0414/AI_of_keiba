import pickle
import pandas as pd
import numpy as np
import pandas as pd
import time
import datetime
from tqdm.notebook import tqdm
import requests
from bs4 import BeautifulSoup
import re
from urllib.request import urlopen
import xml.etree.ElementTree as et
from lxml import etree
import chromedriver_binary
from selenium.webdriver import Chrome, ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
place_dict = {'札幌':'01','函館':'02','福島':'03','新潟':'04','東京':'05','中山':'06','中京':'07','京都':'08','阪神':'09','小倉':'10'}
R_type_dict = {'芝':'01','ダート':'00','ダ':'00','障':'02','障害':'02'}

def scrape_kaisai_date(from_: str, to_: str):
    """
    yyyy-mmの形式でfrom_とto_を指定すると、間のレース開催日一覧が返ってくる関数。
    to_の月は含まないので注意。
    """
    print('getting race date from {} to {}'.format(from_, to_))
    # 間の年月一覧を作成
    date_range = pd.date_range(start=from_, end=to_, freq="W")
    # 開催日一覧を入れるリスト
    kaisai_date_list = []
    for year, month in tqdm(zip(date_range.year, date_range.month), total=len(date_range)):
        #取得したdate_rangeから、スクレイピング対象urlを作成する。
        #urlは例えば、https://race.netkeiba.com/top/calendar.html?year=2022&month=7 のような構造になっている。
        query = [
            'year=' + str(year),
            'month=' + str(month),
        ]
        url = 'https://race.netkeiba.com/top/calendar.html' + '?' + '&'.join(query)
        html = urlopen(url).read()
        time.sleep(0.1)
        soup = BeautifulSoup(html, "html.parser")
        a_list = soup.find('table', class_='Calendar_Table').find_all('a')
        for a in a_list:
            kaisai_date_list.append(re.findall('(?<=kaisai_date=)\d+', a['href'])[0])
        
        from_ = from_.replace('-', '')
        to_ = to_.replace('-', '')
        kaisai_date_list = [date for date in kaisai_date_list if from_ <= date <= to_]
    return kaisai_date_list
    
def scrape_race_id_list(kaisai_date_list: list,  waiting_time=10):
    """
    開催日をyyyymmddの文字列形式でリストで入れると、レースid一覧が返ってくる関数。
    レース前日準備のためrace_idを取得する際には、from_shutuba=Trueにする。
    ChromeDriverは要素を取得し終わらないうちに先に進んでしまうことがあるので、その場合の待機時間をwaiting_timeで指定。
    """
    race_id_list = []
    options = ChromeOptions()
    driver = Chrome(options=options)
    #画面サイズをなるべく小さくし、余計な画像などを読み込まないようにする
    driver.set_window_size(8, 8)
    print('getting race_id_list')
    for kaisai_date in tqdm(kaisai_date_list):
        try:
            query = [
                'kaisai_date=' + str(kaisai_date)
            ]
            url = 'https://race.netkeiba.com/top/race_list.html' + '?' + '&'.join(query)
            print('scraping: {}'.format(url))
            driver.get(url)
            try:
                # 取得し終わらないうちに先に進んでしまうのを防ぐ
                time.sleep(1)
                a_list = driver.find_element(By.CLASS_NAME, 'RaceList_Box').find_elements(By.TAG_NAME, 'a')
                time.sleep(1)
            except:
                #それでも取得できなかったらもう10秒待つ
                print('waiting more {} seconds'.format(waiting_time))
                time.sleep(waiting_time)
                a_list = driver.find_element(By.CLASS_NAME, 'RaceList_Box').find_elements(By.TAG_NAME, 'a')
            for a in a_list:
                race_id1 = re.findall('(?<=shutuba.html\?race_id=)\d+', a.get_attribute('href'))
                race_id2 = re.findall('(?<=result.html\?race_id=)\d+', a.get_attribute('href'))
                if len(race_id1) > 0:
                    race_id_list.append(race_id1[0])
                if len(race_id2) > 0:
                    race_id_list.append(race_id2[0])
        except Exception as e:
            print(e)
            break
    driver.close()
    return race_id_list

def scrape_race_card_table(race_id_list):
    data = pd.DataFrame()
    for race_id in tqdm(race_id_list):
        url = 'https://race.netkeiba.com/race/shutuba.html?race_id=' + race_id
        df = pd.read_html(url)[0]
        df = df.T.reset_index(level=0,drop=True).T
        
        html = requests.get(url)
        html.encoding = 'EUC-JP'
        soup = BeautifulSoup(html.text,'html.parser')
        
        texts = soup.find('div',attrs={'class':'RaceData01'}).text
        texts = re.findall(r'\w+',texts)
        df['発走時刻'] = [texts[0]+':'+texts[1][:2]] * len(df)
        for text in texts:
            if 'm' in text:
                df['course_len'] = [str(re.findall(r'\d+',text)[0])] * len(df)
            #if text in ['曇','晴','雨','小雨','小雪','雪']:
            #    df['weather'] = [text] * len(df)
            #if text in ['良', '稍重', '重']:
            #    df['ground_state'] = [text] * len(df)
            #if '不' in text:
            #    df['ground_state'] = ['不良'] * len(df)
            #if '稍' in text:
            #    df['ground_state'] = ['稍重'] * len(df)
            if '芝' in text:
                df['R_type'] = ['芝'] * len(df)
            if '障' in text:
                df['R_type'] = ['障害'] * len(df)
            if 'ダ' in text:
                df['R_type'] = ['ダート'] * len(df)
                
        race_num = soup.find('span',attrs={'class':'RaceNum'}).text
        df['R'] = re.findall(r'\w+',race_num) * len(df)
        
        race_name = soup.find('div',attrs={'class':'RaceName'}).text
        df['race_name'] = re.findall(r'\w+',race_name) * len(df)
        
        date = soup.find('dd',attrs={'class':'Active'}).text
        #df['date'] = re.findall(r'\d+/\d+',date)[0]
        df['date'] = re.findall(r'\w+',date)[0]
        
        race_infos2 = soup.find('div',attrs={'class':'RaceData02'}).text
        df['place'] = re.findall(r'\w+',race_infos2)[1]
        df['race_genre'] = re.findall(r'\w+',race_infos2)[3]
        df['race_grade'] = re.findall(r'\w+',race_infos2)[4]
        #df['頭数'] = re.findall(r'\w+',race_infos2)[8]
        
        horse_id_list = []
        horse_td_list = soup.find_all('td',attrs={'class':'HorseInfo'})
        for td in horse_td_list:
            horse_id = re.findall(r'\d+',td.find('a')['href'])[0]
            horse_id_list.append(horse_id)
        
        jockey_id_list = []
        jockey_td_list = soup.find_all('td',attrs={'class':'Jockey'})
        for td in jockey_td_list:
            jockey_id = re.findall(r'\d+',td.find('a')['href'])[0]
            jockey_id_list.append(jockey_id)

        trainer_id_list = []
        trainer_td_list = soup.find_all('td',attrs={'class':'Trainer'})
        for td in trainer_td_list:
            trainer_id = re.findall(r'\d+',td.find('a')['href'])[0]
            trainer_id_list.append(trainer_id)
        
        df["horse_id"] = horse_id_list
        df['jockey_id'] = jockey_id_list
        df["trainer_id"] = trainer_id_list
        df['place_id'] = df['place'].map(place_dict)
        df['course_len_id'] = df['course_len']
        df['R_type_id'] = df['R_type'].map(R_type_dict)
        df['course_id'] = df['place_id']+df['R_type_id']+df['course_len_id']
        df = df[['date','R','race_name','race_genre','race_grade','発走時刻','馬番','枠','horse_id','馬名','性齢','斤量','jockey_id','騎手','course_id','place','course_len','R_type']]
        
        df.index = [race_id]*len(df)
        df['date'] = df.index.str[:4] + '-'+re.findall(r'\w+',date)[0].replace('月','-').replace('日','')
        #df['date'] = df.index.str[:4] +'/'+ df['date']
        df['date'] = pd.to_datetime(df['date'])
        df['date'] = df['date'].map(lambda x:x.date().strftime('%Y-%m-%d'))
        data = data.append(df)
        
        time.sleep(0.1)
        
    return data

now = datetime.datetime.now()
one_week_after = now + datetime.timedelta(weeks=1)
one_week_before = now + datetime.timedelta(weeks=-1)
from_ = str(now.date())
to_ = str(one_week_after.date())
#from_ = str(one_week_before.date())

kaisai_date_list = sorted(list(set(scrape_kaisai_date(from_, to_))))
race_id_list = list(set(scrape_race_id_list(kaisai_date_list)))
print(len(race_id_list))
scrape_race_card_table(race_id_list).to_pickle('race_card_tables.pickle')

kaisai_date_list = pd.to_datetime(kaisai_date_list).astype(str)
with open('kaisai_date_list.txt', 'w') as f:
    for item in kaisai_date_list:
        f.write(str(item) + '\n')



