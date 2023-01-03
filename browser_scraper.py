import os
import re
import csv
import random
import gspread
import paramiko
import datetime
import urllib.parse
from time import sleep
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.select import Select
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome import service as fs
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException 
from fake_useragent import UserAgent
from webdriver_manager.chrome import ChromeDriverManager
from oauth2client.service_account import ServiceAccountCredentials

# Logger setting
from logging import getLogger, FileHandler, DEBUG
logger = getLogger(__name__)
today = datetime.datetime.now()
os.makedirs('./log', exist_ok=True)
handler = FileHandler(f'log/{today.strftime("%Y-%m-%d")}_result.log', mode='a')
handler.setLevel(DEBUG)
logger.setLevel(DEBUG)
logger.addHandler(handler)
logger.propagate = False

### functions ###
def launch_driver():
    url = "https://www.google.co.jp/"

    ua = UserAgent()

    options = Options()
#    options.add_argument('--headless')
    options.add_argument(f'user-agent={ua.chrome}')

    chrome_service = fs.Service(executable_path=ChromeDriverManager().install())
    driver = webdriver.Chrome(service=chrome_service, options=options)
    driver.get(url)
    driver.maximize_window()
    return driver

def check_exists_by_class_name(driver, class_name):
    try:
        driver.find_element(By.CLASS_NAME, class_name)
    except NoSuchElementException:
        return False
    return True

def check_exists_by_xpath(driver, xpath):
    try:
        driver.find_element(By.XPATH, xpath)
    except NoSuchElementException:
        return False
    return True

def get_scraping_info(sheet):
    time = sheet.acell('E1').value
    m = re.match(r'[0-9]*', time)
    if not m:
        time = 3
    else:
        time = int(m.group())

    data = sheet.get_all_values()
    data.pop(0)

    return time, data

def browser_scraper(driver, url, filename, time):
    wait = WebDriverWait(driver=driver, timeout=60)
    try:
        driver.get(url)
        wait.until(EC.presence_of_all_elements_located)

        sleep(time)

        with open(f"output/{filename}", "w", encoding="utf-8") as handle:
            handle.write(driver.page_source)
        
        return True
    except Exception as err:
        logger.error(f'browser_scraper: {err}')
        return False


### main_script ###
if __name__ == '__main__':
    os.environ["PYTHONUTF8"] = '1'
    config = {
        'host': os.environ["BROWSER_SCRAPER_HOST"],
        'username': os.environ["BROWSER_SCRAPER_USER"],
        'password': os.environ["BROWSER_SCRAPER_PASS"],
        'port': 22,
        'src': './output/',
        'dst': os.environ["BROWSER_SCRAPER_DST"]
    }
    SPREADSHEET_ID = os.environ["BROWSER_SCRAPER_SSID"]
    scope = ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']
    credentials = ServiceAccountCredentials.from_json_keyfile_name('spreadsheet.json', scope)
    gc = gspread.authorize(credentials)
    sheet = gc.open_by_key(SPREADSHEET_ID).worksheet('Parameter')

    try:
        logger.info('\n------ Start ------\n')
        time, data = get_scraping_info(sheet)
        logger.info(f'待機時間: {time}, URL数: {len(data)}')

        if len(data) <= 0:
            exit(0)

        driver = launch_driver()

        for i, d in enumerate(data):
            if not d[0] or not d[1]:
                continue
            if not d[2]:
                hypertext = f'=ARRAYFORMULA(HYPERLINK("http://tsuyoshikashiwazaki.net/browser/"&B{2+i}))'
                sheet.update_cell(2+i, 3, hypertext)
            logger.debug(f'{datetime.datetime.now().strftime("%m/%d %H:%M")}: {d[0]}')

            status = browser_scraper(driver, d[0], d[1], time)
            if status:
                with paramiko.SSHClient() as ssh:
                    try:
                        ssh.set_missing_host_key_policy(paramiko.WarningPolicy())
                        ssh.connect(config['host'], 
                            port = config['port'],
                            username = config['username'],
                            password = config['password'])

                        sftp_con = ssh.open_sftp() 
                        sftp_con.put(f"{config['src']}{d[1]}", f"{config['dst']}{d[1]}")
                    except Exception as err:
                        logger.debug(f'ssh: {err}')
        
        sheet.update_acell('F1', today.strftime('%m/%d %H:%M'))
        
        driver.close()
        driver.quit()
        logger.info('\n------  End  ------\n')

    except Exception as err:
        driver.close()
        driver.quit()
        logger.error(f'browser_scraper: {err}')
        exit(1)