from django.shortcuts import render
from django.views.generic import View
from django.http import JsonResponse
from goods.models import GoodsSKU
from django_redis import get_redis_connection
from utils.mixin import LoginRequestMixin
# Create your views here.
# 添加商品到购物车
# 1 请求方式：采用ajax post
#  三种传参方式：get传参，post传参，(url传参:url配置时，捕获参数)
# 涉及到数据的修改(增删改)：采用post
# 传递参数：采用get
# 2 传递参数：商品ID 商品数量
# ajax 发起的请求在后台，浏览器看不到效果
class CartAddView(View):
    '''购物车记录添加'''
    def post(self,request):
        '''购物车记录添加'''

        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res':0,'errmsg':'请登录'})

        # 接收数据
        sku_id = request.POST.get('sku_id')
        count = request.POST.get('count')
        # 数据的校验
        if not all([sku_id,count]):
            return JsonResponse({'res':1,'errmsg':'数据不完整'})

        # 校验添加的商品数量
        try:
            count = int(count)
        except Exception as e:
            #数目出错
            return JsonResponse({'res':2,'errmsg':'数目出错'})

        # 校验商品是否存在
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except Exception as e:
            # 商品不存在
            return JsonResponse({'res':3,'errmsg':'商品不存在'})

        # 业务处理：添加购物车记录
        conn = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id
        # 先尝试获取sku_id的值--> hget(cart_key,sku_id)
        # 如果sku_id 在hget 中不存在 返回None
        cart_count = conn.hget(cart_key,sku_id)
        if cart_count:
            # 累加购物车中的商品数目
            count += int(cart_count)

        # 校验商品的库存
        if count>sku.stock:
            return JsonResponse({'res':4,'errmsg':'库存不足'})

        # 设置hash中sku_id对应的值
        conn.hset(cart_key,sku_id,count)

        # 统计所有商品的件数
        total_count = conn.hlen(cart_key)

   # 返回应答
        return JsonResponse({'res':5,'message':'添加成功','total_count':total_count})



class CartInfoView(LoginRequestMixin,View):
    '''购物车'''
    def get(self,request):
        '''显示商品信息'''
        # 获取登录用户信息
        user = request.user
        #获取用户购物车中商品的信息
        conn = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id
        # hgetall返回的是一个字典
        cart_dict = conn.hgetall(cart_key)


        # 保存用户购物车中商品的总数目和总价格
        total_count=0
        total_price=0
        #  从商品的ID获取商品的所有信息
        # 因此，遍历cart_dict获取商品的ID和count 并且放到skus列表中
        skus =[]
        for sku_id,count in cart_dict.items():
            #根据商品的ID获取商品的所有信息
            sku = GoodsSKU.objects.get(id=sku_id)
            # 计算小计
            amount = sku.price*int(count)
            # 动态给sku对象添加属性amount，保存商品的小计
            sku.amount=amount
            # 动态给sku对象添加属性count,保存商品的数量
            sku.count=count

            skus.append(sku)

            # 累加计算商品的总数目和总价格
            total_count+=int(count)
            total_price+=amount

        # 组织上下文
        context={'total_count':total_count,
                 'total_price':total_price,
                 'skus':skus}
        return render(request,'cart.html',context)


# 更新购物车记录
# ajax post 请求
# 传递的参数：商品(商品_id),更新商品的数量：count
#/cart/update
class CartUpdateView(View):
    '''更新购物车记录'''
    def post(self,request):
        '''更新购物车记录'''

        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res':0,'errmsg':'请登录'})

        # 接收数据
        sku_id = request.POST.get('sku_id')
        count = request.POST.get('count')
        # 数据的校验
        if not all([sku_id,count]):
            return JsonResponse({'res':1,'errmsg':'数据不完整'})

        # 校验添加的商品数量
        try:
            count = int(count)
        except Exception as e:
            #数目出错
            return JsonResponse({'res':2,'errmsg':'数目出错'})

        # 校验商品是否存在
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except Exception as e:
            # 商品不存在
            return JsonResponse({'res':3,'errmsg':'商品不存在'})

        # 业务处理：添加购物车记录
        conn = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id

        # 校验商品的库存
        if count>sku.stock:
            return JsonResponse({'res':4,'errmsg':'库存不足'})

        # 设置hash中sku_id对应的值 （更新）
        conn.hset(cart_key,sku_id,count)

        # 统计所有商品的总件数
        total_count=0
        vals = conn.hvals(cart_key)
        for val in vals:
            total_count +=int(val)


        # 返回应答
        return JsonResponse({'res':5,'message':'更新成功','total_count':total_count})


# 删除购物车记录
# ajax post 请求
# 传递的参数：商品(商品_id)
# /cart/delete
class CartDeleteView(View):
    '''购物车记录删除'''
    def post(self,request):
        '''购物车记录删除'''
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res':0,'errmsg':'请登录'})

        # 接收数据
        sku_id = request.POST.get('sku_id')

        # 数据的校验
        if not sku_id:
            return JsonResponse({'res':1,'errmsg':'无效的商品id'})

        # 检验商品是否存在
        try:
            sku =GoodsSKU.objects.get(id=sku_id)
        except Exception as e:
            return JsonResponse({'res':2,'errmsg':'商品不存在'})

        # 业务处理：删除购物车记录
        conn = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id

        # 删除
        conn.hdel(cart_key,sku_id)

        # 统计所有商品的总件数
        total_count=0
        vals = conn.hvals(cart_key)
        for val in vals:
            total_count +=int(val)

        # 返回应答
        return JsonResponse({'res':3,'total_count':total_count,'message':'删除成功'})
        




