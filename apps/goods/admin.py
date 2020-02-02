from django.contrib import admin
from goods.models import GoodsType,IndexPromotionBanner,IndexTypeGoodsBanner,IndexGoodsBanner
from django.core.cache import cache

# Register your models here.
class BaseAdimn(admin.ModelAdmin):     #父类
    def save_model(self, request, obj, form, change):
        '''新增或者更新表中的数据时调用'''
        super().save_model(request, obj, form, change)

        # 发出任务，让celery worker重新生成首页静态页面
        from celery_tasks.tasks import generate_static_index_html
        generate_static_index_html.delay()

        #清除缓存
        cache.delete('index_page_data')



    def delete_model(self, request, obj):
        '''删除数据表中的数据时调用'''
        super().delete_model(request,obj)

        # 发出任务，让celery worker重新生成首页静态页面
        from celery_tasks.tasks import generate_static_index_html
        generate_static_index_html.delay()

        #清除缓存
        cache.delete('index_page_data')





class IndexPromotionBannerAdmin(BaseAdimn):
    pass

class GoodsTypeAdmin(BaseAdimn):
    pass

class IndexTypeGoodsBannerAdmin(BaseAdimn):
    pass

class IndexGoodsBannerAdmin(BaseAdimn):
    pass


admin.site.register(GoodsType,GoodsTypeAdmin)
admin.site.register(IndexPromotionBanner,IndexPromotionBannerAdmin)
admin.site.register(IndexTypeGoodsBanner,IndexTypeGoodsBannerAdmin)
admin.site.register(IndexGoodsBanner,IndexGoodsBannerAdmin)






