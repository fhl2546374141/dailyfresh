from django.shortcuts import render,redirect
from django.views.generic import View
from goods.models import GoodsType,IndexGoodsBanner,IndexPromotionBanner,IndexTypeGoodsBanner,GoodsSKU
from django_redis import get_redis_connection
from django.core.cache import cache
from django.urls import reverse
from order.models import OrderGoods
from django.core.paginator import Paginator


# class Test(object):
#     def __init__(self):
#         self.name ='adc'
# t = Test()
# t.age = 10
# print(t.age)
# 表示动态的添加属性


# Create your views here.
class IndexView(View):
    '''首页'''
    def get(self,request):
        '''显示首页'''
        # 尝试从缓存在获取数据
        context = cache.get('index_page_data')
        if context is None:  # 缓存没有数据
            # 都是从数据库获取信息
            # 获取商品的种类信息
            types = GoodsType.objects.all()
            # 获取首页轮播商品信息
            goods_banners = IndexGoodsBanner.objects.all().order_by('index')  # 商品的展示顺序
            # 获取首页促销活动信息
            promotion_banners = IndexPromotionBanner.objects.all().order_by('index')
            # 获取首页分类商品展示信息
            for type in types: # 遍历types 值为GoodsType
                # 获取type种类首页分类商品的图片展示信息
                image_banners = IndexTypeGoodsBanner.objects.filter(type=type,display_type=1).order_by('index')
                # 获取type种类首页分类商品的文字信息
                title_banners = IndexTypeGoodsBanner.objects.filter(type=type,display_type=0).order_by('index')

                # 动态的给type太添加属性，分别保存首页分类商品的图片展示信息和文字展示信息
                type.image_banners = image_banners
                type.title_banners = title_banners

            context= {'types':types,
                      'goods_banner':goods_banners,
                      'promotion_banners':promotion_banners,
                      }
            # 设置缓存
            # key value timeout
            cache.set('index_page_data',context,3600)  # 需要设置过期时间

        # 获取用户购物车商品的数目..d
        user = request.user
        cart_count = 0  # 未登录时 购物车商品数目默认是0
        if user.is_authenticated:
            # 用户已经登录
            conn = get_redis_connection('default') #链接redis数据库
            cart_key = 'cart_%d' % user.id
            cart_count = conn.hlen(cart_key)

        # 组织上下文
        context.update(cart_count=cart_count)

        #使用模板
        return render(request,'index.html',context)


#/goods/商品ID
class DetailView(View):
    '''详情页'''
    def get(self,request,goods_id):
        '''显示详情页'''
        try:
            sku = GoodsSKU.objects.get(id = goods_id)
        except GoodsSKU.DoesNotExist:
            # 商品不存在
            return redirect(reverse('goods:index'))
        # 获取商品的分类(种类)信息
        types = GoodsType.objects.all()

        # 获取商品的评论信息
        sku_orders = OrderGoods.objects.filter(sku=sku).exclude(comment='')  #exclude去除

        # 获取新品信息
        new_skus = GoodsType.objects.filter(type=sku.type).order_by('-create_time')[:2]

        # 获取同一SPU的其他规格的商品
        same_spu_skus = GoodsSKU.objects.filter(goods = sku.goods).exclude(id = goods_id)

        # 获取用户购物车商品的数目
        user = request.user
        cart_count = 0  # 未登录时 购物车商品数目默认是0
        if user.is_authenticated:
            # 用户已经登录
            conn = get_redis_connection('default') #链接redis数据库
            cart_key = 'cart_%d' % user.id
            cart_count = conn.hlen(cart_key)

            # 添加用户的历史记录
            conn = get_redis_connection('default') # 链接redis数据库链接
            history_key = 'history_%d' % user.id
            # 移出列表中的goods_id
            conn.lrem(history_key,0,goods_id)
            # 把goods_id插入到列表的左侧
            conn.lpush(history_key,goods_id)
            # 只保留用户最新浏览的5条记录
            conn.ltrim(history_key,0,4)

        # 组织上下文
        context = {'sku':sku,'types':types,
                  'sku_orders':sku_orders,
                  'new_skus':new_skus,
                  'cart_count':cart_count,
                   'same_spu_skus':same_spu_skus}

        # 返回模板
        return render(request,'detail.html',context)


# 种类id 页码，排序
# /list？type_id=种类id&page=页码&sort=排序
# /list/种类id/页码/排序
#/list/种类id/页码？sort=排序    url配置时，？后边的不参与匹配
class ListView(View):
    '''列表页'''
    def get(self,request,type_id,page):
        '''显示列表页'''
        # 获取种类信息
        try:
            type = GoodsType.objects.get(id = type_id)
        except GoodsType.DoesNotExist:
            # 种类不存在
            return redirect(reverse('goods:index'))

        # 获取商品的分类(种类)信息
        types = GoodsType.objects.all()
        # 获取排序的方式并且获取分类商品的信息
        # sort=default 按照默认的方式排序
        # sort=price 按照价格的来排序
        # sort=hot 按照销量来排序
        sort=request.GET.get('sort')
        if sort =='price':
            skus = GoodsSKU.objects.filter(type=type).order_by('price')
        elif sort == 'hot':
            skus = GoodsSKU.objects.filter(type=type).order_by('-sales')
        else:
            sort = 'default'
            skus = GoodsSKU.objects.filter(type=type).order_by('-id')

        #对数据进行分页
        paginator = Paginator(skus, 5)  # Show 5 contacts per page
        #获取第page页的内容
        try:
            page=int(page)
        except Exception as e:
            page=1
        if page > paginator.num_pages:
            page=1
        skus_page = paginator.page(page)

        # todo :进行页码的控制，页面上最多显示5个页码
        # 1 总页数小于5页时，页面上显示所有页码
        # 2 如果当前页是前三页，显示1-5页
        # 3 如果当前页是后三页，显示后5页的页码
        # 4 其他情况，显示当前页的前2页；当前页；当前页的后两页
        num_pages = paginator.num_pages
        if num_pages< 5 :
            pages = range(1,num_pages+1)
        elif page <=3:
            pages =range(1,6)
        elif num_pages-page <=2:
            pages = range(num_pages-4,num_pages+1)
        else:
            pages = range(page-2,page+3)
        # 获取新品信息
        new_skus = GoodsType.objects.filter(type=type).order_by('-create_time')[:2]

        # 获取用户购物车商品的数目
        user = request.user
        cart_count = 0  # 未登录时 购物车商品数目默认是0
        if user.is_authenticated:
            # 用户已经登录
            conn = get_redis_connection('default') #链接redis数据库
            cart_key = 'cart_%d' % user.id
            cart_count = conn.hlen(cart_key)

        # 组织上下文
        context={'type':type,
                 'skus_page':skus_page,
                 'types':types,
                 'new_skus':new_skus,
                 'cart_count':cart_count,
                 'sort':sort,
                 'pages':pages}
        # 返回模板
        return render(request,'list.html',context)






























