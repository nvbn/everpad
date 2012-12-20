try:
    import local
except ImportError:
    raise ImportError('Copy dist.py to local.py')


from everpad import const


const.HOST = local.HOST
const.CONSUMER_KEY = local.CONSUMER_KEY
const.CONSUMER_SECRET = local.CONSUMER_SECRET
const.DB_PATH = local.DB_PATH
TOKEN = local.TOKEN
