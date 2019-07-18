# -*-coding:utf-8-*-
import time
from werkzeug.routing import BaseConverter
from apps.app import mdbs, cache
from apps.utils.format.time_format import time_to_utcdate

__author__ = "Allen Woo"


class RegexConverter(BaseConverter):
    """
    让路由支持正则
    """

    def __init__(self, url_map, *items):
        super(RegexConverter, self).__init__(url_map)
        self.regex = items[0]


def push_url_to_db(app):
    """
    同步url到数据库
    :param app:
    :return:
    """
    # back up
    ut = time_to_utcdate(time.time(), "%Y%m%d%H")
    if not mdbs["sys"].dbs["sys_urls_back"].find_one({"backup_time": ut}):
        sys_urls = list(mdbs["site"].dbs["sys_urls"].find({}, {"_id": 0}))
        for sys_url in sys_urls:
            sys_url["backup_time"] = ut
        mdbs["sys"].dbs["sys_urls_back"].insert(sys_urls)
        mdbs["sys"].dbs["sys_urls_back"].delete_many({"backup_time": {"$lt": ut}})

    for rule in app.url_map.iter_rules():
        if rule.endpoint.startswith("api.") or rule.endpoint.startswith("open_api."):
            type = "api"
        else:
            continue
        now_time = time.time()
        r = mdbs["sys"].dbs["sys_urls"].find_one({"url": rule.rule.rstrip("/")})
        if not r:
            # 不存在
            mdbs["sys"].dbs["sys_urls"].insert_one({"url": rule.rule.rstrip("/"),
                                                "methods": list(rule.methods),
                                                "endpoint": rule.endpoint,
                                                "custom_permission": {},
                                                "type": type,
                                                "create": "auto",
                                                "update_time": now_time})

        elif r:
            new_methods = list(rule.methods)
            if r["methods"]:
                new_methods.extend(r["methods"])
            new_methods = list(set(new_methods))
            mdbs["sys"].dbs["sys_urls"].update_one({"_id": r["_id"]},
                                               {"$set": {"methods": new_methods,
                                                         "endpoint": rule.endpoint,
                                                         "type": type,
                                                         "create": "auto",
                                                         "update_time": now_time}})

    urls = mdbs["sys"].dbs["sys_urls"].find({})
    for url in urls:
        if "url" in url:
            cache.delete(key="get_sys_url_url_{}".format(url['url']), db_type="redis")

    """
    # 清理已不存在的api
    # 时间7天是为了防止多台服务器同时启动时造成误删
    """
    ut = time.time() - 86400*7
    mdbs["sys"].dbs["sys_urls"].delete_many(
        {"type": {"$ne": "page"}, "update_time": {"$lt": ut}})
