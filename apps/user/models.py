from django.db import models
from django.contrib.auth.models import AbstractUser
from db.base_model import BaseModel

# Create your models here.
class User(AbstractUser,BaseModel):
    '''用户模型类'''
    class Meta:
        db_table = 'df_user'
        verbose_name = '用户'
        verbose_name_plural = verbose_name

#  定义地址模型管理器类 管理器的作用：1 改变查询的结果集  2 封装函数：操作模型类对应的数据表(增删改查)
class AddressManager(models.Manager):
    '''地址模型管理器类'''
    def get_default_address(self,user):
        # 获取用户默认的收货地址
        #self.model  model的作用：获取模型类的对象的类名  self指的是object
        try:
            address = self.objects.get(user=user, is_default=True)
        except self.model.DoesNotExist:
            # 不存在默认的地址
            address = None
        return address




class Address(BaseModel):
    '''地址表模型类'''
    user = models.ForeignKey('User',on_delete=models.CASCADE,verbose_name='所属账户')
    receiver = models.CharField(max_length=20,verbose_name='收件人')
    addr = models.CharField(max_length=200,verbose_name='收件地址')
    zip_code = models.CharField(max_length=6,verbose_name='邮政编码')
    phone = models.CharField(max_length=11,verbose_name='联系方式')
    is_default = models.BooleanField(default=False,verbose_name='是否默认')
    # 自定义一个模型管理器对象
    object = AddressManager()

    class Meta:
        db_table = 'df_address'  # 指定表名
        verbose_name = '地址'
        verbose_name_plural = verbose_name
