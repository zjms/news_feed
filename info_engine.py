# --*-- coding: utf-8 --*--

import os
import sys

from utils.log import NOTICE, log, ERROR, RECORD

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__),".."))
sys.path.append(BASE_DIR)

import time
import random
from config import CELERY_BROKER, CELERY_BACKEND, CRAWL_INTERVAL
from db_access import *
from utils.blacklist import blacklist_site, blacklist_company
from utils.content_process import complement_url, check_content
from utils.diff import diff_file
from utils.html_downloader import crawl
from bs4 import BeautifulSoup
from celery import Celery


celery_app = Celery('info_engine', broker=CELERY_BROKER, backend=CELERY_BACKEND)
celery_app.conf.update(CELERY_TASK_RESULT_EXPIRES=3600)


# decorator, making 'extract' func become a task of celery.
@celery_app.task
def extract(w_id):
    """

    :param w_id:
    :return:
    """
    try:
        # 列举出所有没能成功抓取更新的情况，log里记录下。
        w = get_website(w_id)
        # log(NOTICE, "开始 #{id} {name} {site} ".format(id=w.id, name=w.company.name_cn, site=w.url))
        new_html_content = crawl(w.url)
        if not new_html_content:
            log(NOTICE, "#{id} {name} {site} 抓到更新 0 条".format(id=w.company.id, name=w.company.name_cn, site=w.url))
            return

        # if current website 'w' already have html_content. compare it with new_content and save those if diff exist.

        if w.html_content:
            old_html_content = w.html_content.content
        else:
            save_html_content(w.id, new_html_content)
            log(NOTICE, "#{id} {name} {site} 抓到更新 0 条".format(id=w.company.id, name=w.company.name_cn, site=w.url))
            return
        diff_text = diff_file(old_html_content, new_html_content)
        if not diff_text:
            log(NOTICE, "#{id} {name} {site} 抓到更新 0 条".format(id=w.company.id, name=w.company.name_cn, site=w.url))
            return

        save_html_content(w.id, new_html_content)

        # lxml是一个html解析器,与它类似的还有html5lib等。
        soup = BeautifulSoup(diff_text, 'lxml')
        items = soup.find_all('a')
        COUNT = 0
        if items:
            for a in items:
                if a.string:
                    url, text = a.get('href'), a.string
                    check_pass = check_content(url, text)
                    if check_pass:
                        url = complement_url(url, w.url)
                        if url:
                            result = save_info_feed(url, text, w.id, w.company.id)
                            if result:
                                COUNT += 1
                            # log(RECORD, "[name] [+] [{url}  {text}]".format(name=w.company.name_cn, url=url, text=text.strip()))
        if COUNT == 0:
            log(NOTICE, "#{id} {name} {site} 抓到更新 {count} 条".format(id=w.company.id, name=w.company.name_cn, site=w.url, count=COUNT))
        else:
            log(RECORD, "#{id} {name} {site} 抓到更新 {count} 条".format(id=w.company.id, name=w.company.name_cn, site=w.url, count=COUNT))

    except Exception as e:
        try:
            w = get_website(w_id)
            log(ERROR, "#{id} {name} {site} {err}".format(id=w.id, name=w.company.name_cn, site=w.url, err=str(e)))
        except Exception as e:
            log(ERROR, str(e))


def gen_info():
    """
    程序入口，
    celery介绍
    https://www.liaoxuefeng.com/article/00137760323922531a8582c08814fb09e9930cede45e3cc000

    :return:
    """

    # select all websites from Database.
    websites = get_websites()
    # websites = get_websites_desc()

    # random.shuffle(websites)
    # w : {url, company:{name_cn}, id}
    for w in websites[:]:
        if (w.url not in blacklist_site) and (w.company.name_cn not in blacklist_company):
            extract.delay(w.id)






if __name__ == '__main__':
    while True:
        gen_info()
        time.sleep(60 * CRAWL_INTERVAL)

