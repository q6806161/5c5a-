from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from multiprocessing import Process,Queue
from email.mime.text import MIMEText
from selenium import webdriver
import requests
from requests.exceptions import RequestException
import smtplib
import json
import time
import random
import imp
import re
import sys
import os
import winsound
imp.reload(sys)
requests.packages.urllib3.disable_warnings()

"""
本爬虫用于a，采用双进程
1个进程完成selenium视频链接抽取
2个进程利用requests完成视频下载和文件保存

数据采集和视频下载采用同步抽取同步下载，鉴于视频下载相对地址抽取慢很多
因此下载进程用多个，抽取进程用一个会是更好的选择
"""

class Site5c5a_Spider(object):
    
    def __init__(self):
        self.user_agent_list = [
        "Mozilla/5.0 (Windows NT 5.2) AppleWebKit/534.30 (KHTML, like Gecko) Chrome/12.0.742.122 Safari/534.30",
        "Mozilla/5.0 (Windows NT 6.1) AppleWebKit/535.1 (KHTML, like Gecko) Chrome/14.0.835.202 Safari/535.1",
        "Mozilla/5.0 (compatible; MSIE 9.0; Windows Phone OS 7.5; Trident/5.0; IEMobile/9.0; SAMSUNG; OMNIA7)",
        "Mozilla/5.0 (compatible; MSIE 9.0; Windows NT 6.1; Trident/5.0; XBLWP7; ZuneWP7)",
        "Mozilla/5.0 (Windows NT 5.2) AppleWebKit/534.30 (KHTML, like Gecko) Chrome/12.0.742.122 Safari/534.30",
        "Mozilla/5.0 (Windows NT 5.1; rv:5.0) Gecko/20100101 Firefox/5.0",
        "Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 5.2; Trident/4.0; .NET CLR 1.1.4322; .NET CLR 2.0.50727; .NET4.0E; .NET CLR 3.0.4506.2152; .NET CLR 3.5.30729; .NET4.0C)",
        "Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 5.2; .NET CLR 1.1.4322; .NET CLR 2.0.50727; .NET4.0E; .NET CLR 3.0.4506.2152; .NET CLR 3.5.30729; .NET4.0C)",
        "Mozilla/4.0 (compatible; MSIE 60; Windows NT 5.1; SV1; .NET CLR 2.0.50727)",
        "Mozilla/5.0 (compatible; MSIE 9.0; Windows NT 6.1; Trident/5.0; SLCC2; .NET CLR 2.0.50727; .NET CLR 3.5.30729; .NET CLR 3.0.30729; Media Center PC 6.0; .NET4.0C; .NET4.0E)",
        "Opera/9.80 (Windows NT 5.1; U; zh-cn) Presto/2.9.168 Version/11.50",
        "Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; SV1)",
        "Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 5.1; Trident/4.0; .NET CLR 2.0.50727; .NET CLR 3.0.04506.648; .NET CLR 3.5.21022; .NET4.0E; .NET CLR 3.0.4506.2152; .NET CLR 3.5.30729; .NET4.0C)",
        "Mozilla/5.0 (Windows; U; Windows NT 5.1; zh-CN) AppleWebKit/533.21.1 (KHTML, like Gecko) Version/5.0.5 Safari/533.21.1",
        "Mozilla/5.0 (Windows; U; Windows NT 5.1; ) AppleWebKit/534.12 (KHTML, like Gecko) Maxthon/3.0 Safari/534.12",
        "Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; SV1; .NET CLR 2.0.50727; TheWorld)",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.108 Safari/537.36"]
        self.headers = {'User-Agent':self.user_agent_list[random.randint(0,len(self.user_agent_list)-1)]}
        self.s = requests.Session()
        self.url_first_page = "https://www.5c5a.com/"
        self.API = ""
        
        
    def video_url_writer(self,q):
        """
        chrome设置不要在__init__进行，不然会出现权限（多进程下）不够的情况，暂时不清楚怎么回事
        para: all_flag 出现全部标签点击显示所有集数列表，如果没有的话就返回重新搜索；
        para: esplise_maxnum 视频最大集数
        """
        chrome_options = Options()
        chrome_options.add_argument("--ignore-certificate-errors") # 如果出现证书验证问题，设置忽略
        # chrome_options.add_argument("--headless")        # 无界面模式设置
        capa = DesiredCapabilities.CHROME                          # 采用等待元素出现停止加载模式
        capa["pageLoadStrategy"] = "none"     
        driver = webdriver.Chrome(desired_capabilities=capa,options=chrome_options)
        wait = WebDriverWait(driver,12)    # 显示等待，最大等待时间是8s
        driver.get(self.url_first_page)
        while True:
            try:
                wait.until(EC.element_to_be_clickable((By.ID,"ff-wd"))).send_keys("蓝猫淘气3000问幽默系列")
                time.sleep(3)
                driver.find_element_by_class_name("input-group-btn").click()
                wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR,"li>a[href = '#all']")))
                break
            except BaseException as e:
                print(e)
                driver.refresh()
        esplise_maxnum = re.sub("[\u4e00-\u9fa5]+","",
                                driver.find_element_by_css_selector("h1>small[class='badge']").text)
        esplise_num = 1
        """
        循环执行
        点击"全部" → 点击"第几集" → 等待页面加载出子frame，切换 → 加载视频下载url → 返回
        
        进程队列检查
        para: check_time 检查队列是否为空，是则放入"视频下载地址","目前集数","最大集数"
        如果出现下载进程出现问题，则循环检测20次，超过则整个程序结束
        （其中最大集数用于终止下载进程循环的）
        
        错误捕捉
        para: page_load_time 表示用于检查页面元素是否正常加载的次数
        一个捕捉用于检查返回视频集数列表页面是否成功，循环检测5次，每次间隔3秒，如果
        """
        page_load_check_time = 0
        while esplise_num <= int(esplise_maxnum):
            if page_load_check_time <=5:
                try:
                    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR,"li>a[href = '#all']"))).click()
                    time.sleep(3)
                    driver.find_element_by_css_selector(f"li[data-id ^='60554-1-{esplise_num}']").click()
                    iframe = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR,"iframe")))
                    driver.switch_to.frame(iframe)
                    video_tag = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR,"video[preload='metadata']")))
                    video_download_url = video_tag.get_attribute('src')
                    for check_time in range(20):
                        if q.empty():
                            q.put((video_download_url,esplise_num,int(esplise_maxnum)))
                            break
                        elif check_time == 20:
                            print("老哥，请检查视频下载出现啥问题了！")
                            sys.exit()
                        else:
                            time.sleep(10)
                            winsound.Beep(1000,440)
                    driver.switch_to.default_content()
                    esplise_num += 1
                    page_load_check_time = 0
                except (NoSuchElementException,TimeoutException):
                    driver.refresh()
                    time.sleep(5)
                    page_load_check_time += 1
            else:
                print(f"下载{esplise_num}出现错误，请检查网页响应情况")
                sys.exit()
    
    """
    代理抽取模块
    """
    def proxies_pick(self):
        for pick_times in range(3):
            response = requests.get(url = self.API,headers = self.headers,timeout = 5)
            json_data = json.loads(response.text)
            if isinstance(json_data["RESULT"],str):
                print(json_data["RESULT"])
                time.sleep(5)
            else:
                return json_data["RESULT"]
        while True:
            continue_or_not_flag = input("请输入'Y'or'N'确定是否以代理的模式启动下载")
            if continue_or_not_flag == "Y":
                return
            elif continue_or_not_flag =="N":
                sys.exit()
            else:
                print("大哥看提示好吗！")
                continue
    
    
    def file_download(self,esplise_num,response,temp_size,total_size):
        with open(f"E:\蓝猫淘气三千问\{esplise_num:0>3}.mp4", "ab") as f:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    temp_size += len(chunk)
                    f.write(chunk)
                    f.flush() # 不用等到缓存全满再写到文件，每次强制刷新实时更新文件
    
                    ###这是下载实现进度显示####
                    done = int(50 * temp_size / total_size)
                    sys.stdout.write("\r[%s%s] %d%%" % ('█' * done, ' ' * (50 - done), 100 * temp_size / total_size))
                    sys.stdout.flush()
        print()  # 避免上面\r 回车符
    """
        para: check_q 队列检查次数，检查4次，循环结束没有拿到内容直接退出程序并打印出"取值进程出错"
        para: not_success_download 返回没有成功下载的集数
        para: video_url 视频地址
        para: esplise_num 视频集数
        para: esplise_maxnum 视频最大集数
        """
    def video_download(self,q):
        ip_port_list = self.proxies_pick()
        not_success_download = []
        check_q = 0
        while True:
            video_download_url_esplise = q.get(True)
            if not video_download_url_esplise:
                time.sleep(5)
                check_q +=1
            elif check_q == 5:
                print("取值进程出错")
                sys.exit()
            else:
                video_url = video_download_url_esplise[0]
                esplise_num = video_download_url_esplise[1]
                esplise_maxnum = video_download_url_esplise[2]
                # 先看看本地文件已下载量
                if os.path.exists(f"E:\蓝猫淘气三千问\{esplise_num:0>3}.mp4"):
                    temp_size = os.path.getsize(f"E:\蓝猫淘气三千问\{esplise_num:0>3}.mp4")
                else:
                    temp_size = 0
                while True:
                    time_ip_pick = 0
                    ip = ip_port_list[0]
                    proxies = {
                        "http":"http://" + ip["ip"]+ ":" + ip["port"],
                        "https":"https://" + ip["ip"]+ ":" + ip["port"]}
                    try:
                        response = self.s.get(video_url, proxies = proxies, headers=self.headers, stream=True, verify=False,timeout=5)
                        total_size = int(response.headers['Content-Length'])
                        if 0<temp_size<total_size:
                            print(f"正在继续下载蓝猫淘气三千问第{esplise_num:0>3}集")
                            # 核心部分，这个是请求下载时，从本地文件已经下载过的后面下载
                            headers = {
                            'User-Agent':self.user_agent_list[random.randint(0,len(self.user_agent_list)-1)],
                            'Range': f'bytes={temp_size}-'
                            }  
                            # 重新请求网址，加入新的请求头的
                            response = requests.get(video_url, proxies = proxies, stream=True, verify=False, headers=headers,timeout=5)
                            response.raise_for_status()     # 确保程序在下载失败时停止
                            self.file_download(esplise_num,response,temp_size,total_size)
                            break
                        elif temp_size ==0:
                            print(f"正在下载第{esplise_num}集！")
                            self.file_download(esplise_num,response,temp_size,total_size)
                            break
                        else:
                            print(f"第{esplise_num}已经完成下载")
                            break
                    except TimeoutError:
                        ip_port_list = self.proxies_pick()
                        
                # if retry_time == 4:
                    # print(f"第{esplise_num:0>3}集没有成功下载")
                    # not_success_download.append(esplise_num)
            if esplise_num == esplise_maxnum:
                break
    
    """
    邮件发送模块
    """
    def email_send(self):
        msg = MIMEText('蓝猫淘气三千问全部下载完成', 'plain', 'utf-8')
        # 输入Email地址和口令:
        from_addr = "976006273@qq.com"
        password = "hiwdlcxegwmebfic"
        # 输入SMTP服务器地址:
        smtp_server = "smtp.qq.com"
        # 输入收件人地址:
        to_addr = "976006273@qq.com"
        server = smtplib.SMTP(smtp_server, 25) # SMTP协议默认端口是25
        server.login(from_addr, password)
        server.sendmail(from_addr, [to_addr], msg.as_string())
        server.quit()



if __name__ == "__main__":
    q = Queue()
    Site5c5a_downloader = Site5c5a_Spider()
    # Site5c5a_downloader.video_url_writer()
    video_url_get = Process(target=Site5c5a_downloader.video_url_writer,args=(q,))
    video_downloader_0 = Process(target=Site5c5a_downloader.video_download,args=(q,))
    video_downloader_1 = Process(target=Site5c5a_downloader.video_download,args=(q,))
    
    video_url_get.start()
    video_downloader_0.start()
    video_downloader_1.start()
    # #等待proc_write1结束
    
    video_url_get.join()
    video_downloader_0.join()
    video_downloader_1.join()
    # #proc_raader进程是死循环，强制结束
    video_downloader_0.terminate()
    video_downloader_1.terminate()
    os.system("E:\KuGou\1.mp3")
    
