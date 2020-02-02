# 自定义一个从存储类
#如果你需要提供自定义文件储存功能——一个普通的例子是，把文件储存在远程系统中——自定义一个存储类可以完成这一任务来完成。
# 通过FastDFS 和nginx进行配置
from django.conf import settings
from django.core.files.storage import Storage
from fdfs_client.client import Fdfs_client
class FDFSStorage(Storage):
    '''fast dfs文件存储类'''

    def __init__(self,client_conf,base_url):
        if client_conf is None:
            client_conf=settings.FAST_CLIENT_CONF   # 通过settings配置文件来优化代码 进行动态的添加
        self.client_conf = client_conf
        if base_url is None:
            base_url = settings.FDFS_URL
        self.base_url = base_url

    def _open(self,name, mode='rb'):
        '''打开文件时使用'''
        pass

    def _save(self,name, content):
        '''保存文件时使用'''
        # neme:选择的上传文件的名字
        # content:包含上传文件内容的File对象  File是个类

        # 创建一个Fdfs_client的对象  Python与FastDFS的交互
        client = Fdfs_client('self.client_conf')

        # 上传文件到fast dfs 系统中
        res = client.upload_by_buffer(content.read())  # 上传的是文件的内容到fast dfs系统中
        # res 返回的这个是个字典 是这个dict
        # dict
        # {
        #     'Group name': group_name,
        #     'Remote file_id': remote_file_id,
        #     'Status': 'Upload successed.',
        #     'Local file name': '',
        #     'Uploaded size': upload_size,
        #     'Storage IP': storage_ip
        # }
        if res.get('Status') != 'Upload successed':
            raise Exception('上传文件到fast fds系统失败')
        #获取返回的文件的ID
        filename = res.get('Remote file_id')

        return filename


    def exists(self, name):
        '''django判断文件名是否可用'''
        # 返回True表示文件名不可用
        # 返回False 表示文件名可用
        return False


    def url(self, name):
        '''返回访问文件的url路径'''
        # ngnix服务器的IP地址和文件的获取到文件的ID。 当admin上传照片时 上传到FastDFS  当浏览器获取到FastDFS返回的
        # http: // 172.16.179.131: 8888 / '+name时，直接请求 nginx服务器 ngnix从FastDFS中拿到图片 返回给浏览器
        return 'self.base_url'+name


