#定义索引类

from haystack import indexes
from goods.models import GoodsSKU

# 指定对于某个类的某些数据建立索引
# 类名固定格式，model类 + Index
class GoodsSKUIndex(indexes.SearchIndex, indexes.Indexable):
    # 索引字段，use_templete=True 指定根据表中的那些字段建立索引文件的说明，放到一个文件中
    text = indexes.CharField(document=True, use_template=True)
    # author = indexes.CharField(model_attr='user')
    # pub_date = indexes.DateTimeField(model_attr='pub_date')

    def get_model(self):
        # 返回模型类
        return GoodsSKU
    # 建立索引的数据
    def index_queryset(self, using=None):
        """Used when the entire index for model is updated."""
        # return self.get_model().objects.filter(pub_date__lte=datetime.datetime.now())
        return self.get_model().objects.all()
