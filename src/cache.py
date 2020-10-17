# 缓存
import threading, common, config
from promise import Promise
class Cache(object):
  def __init__(self, func):
    self.func = func

  def GetPromise(self, handle):
    ret = None
    # 如果是正在进行做的用户，直接返回其promise
    self.crawling_map_lock.acquire()
    if handle in self.crawling_map:
      ret = self.crawling_map.get(handle)
    self.crawling_map_lock.release()
    if ret is not None:
      return ret
    # 否则，查看是否是最近2小时内查询过
    self.data_map_lock.acquire()
    data = self.data_map.get(handle, None)
    if data is not None and data.get('crawl_time', 0) + config.GetConfig('cache', 'recrawl_time', default=common.kNsPerTwoHour) >= common.GetTime():
      ret = Promise()
      ret.result = data
    self.data_map_lock.release()
    if ret is not None:
      return ret
    # 重新进行爬取
    self.crawling_map_lock.acquire()
    # 判断是否是正在进行的作业，直接返回其promise，防止在大量查询同一个人时造成多次爬取
    if handle in self.crawling_map:
      ret = self.crawling_map.get(handle)
    else:
      ret = Promise(self.func, (handle, ), self.UpdateData, (handle, ))
      ret.start()
      self.crawling_map[handle] = ret
    self.crawling_map_lock.release()
    return ret

  def UpdateData(self, handle, data):
    # 更新数据
    self.data_map_lock.acquire()
    data['crawl_time'] = common.GetTime()
    self.data_map[handle] = data
    # 数据太多了直接清完所有缓存
    if len(self.data_map) >= config.GetConfig('cache', 'maxsize', default=10000):
      self.data_map.clear()
    self.data_map_lock.release()
    # 更新这个handle的状态为不是正在进行作业
    self.crawling_map_lock.acquire()
    self.crawling_map.pop(handle)
    self.crawling_map_lock.release()
    print(handle, data)

  # 爬虫函数
  func = None

  # 正在进行作业的用户哈希表，key为handle，value为promise
  crawling_map = dict()
  # 该集合的多线程锁
  crawling_map_lock = threading.Lock()

  # 查询结果的缓存
  data_map = dict()
  # 缓存的多线程锁
  data_map_lock = threading.Lock()