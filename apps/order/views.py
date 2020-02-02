from django.shortcuts import render,redirect
from django.views.generic import View
from utils.mixin import LoginRequestMixin
from django.urls import reverse
from goods.models import GoodsSKU
from django_redis import get_redis_connection
from user.models import Address
from django.http import JsonResponse
from order.models import OrderInfo,OrderGoods
from datetime import datetime
from django.db import transaction
from alipay import AliPay
import os


from django.conf import settings
# Create your views here.
#/order/place
class OrderPlaceView(LoginRequestMixin,View):
    '''提交订单页面显示'''
    def post(self,request):
        '''提交订单页面显示'''
        # 获取用户登录
        user=request.user

        # 获取参数sku_ids
        sku_ids = request.POST.getlist('sku_dis')

        #校验参数
        if not sku_ids:
            return redirect(reverse('cart:show'))

        conn=get_redis_connection('default')
        cart_key = 'cart_%d' % user.id

        skus=[]
        #保存商品的总件数和总价格
        total_count=0
        total_price=0
        # 遍历sku_ids获取用户要购买的商品的信息
        for sku_id in sku_ids:
            # 根据商品的ID获取商品的信息
            sku=  GoodsSKU.objects.get(id=sku_id)
            # 获取用户购买的商品的数量
            count = conn.hget(cart_key,sku_id)
            # 计算商品的小计
            amount = sku.price*int(count)
            # 动态添加属性    (count和amount)保存数量和小计显示在页面上
            sku.count = count
            sku.amount = amount
            # 追加
            skus.append(sku)
            # 累加计算商品的总件数和总价格
            total_count+=count
            total_price+=amount

        # 运费：实际开发 属于一个子系统
        transit_price = 10

        # 实付款
        total_pay = total_price+transit_price

        # 获取用户的收件地址
        addrs = Address.objects.filter(user=user)

        #组织上下文
        sku_ids = ','.join(sku_ids)  #列表转换为字符串
        context = {'skus':skus,
                   'total_count':total_count,
                   'total_price':total_price,
                   'total_pay':total_pay,
                   'addrs':addrs,
                   'transit_price':transit_price,
                   'sku_ids':sku_ids}

        # 返回模板
        return render(request,'place_order.html',context)

# 前端传过来的参数：地址id(addr_id),支付方式(pay_mothed),用户要购买的商品id的字符串(sku_ids)
# mysql事务：一组sql操作,要么都成功，要么都失败
#高并发
#支付宝支付
class OrderCommitView(View):
    '''订单创建'''
    @transaction.atomic
    def post(self,request):
        '''订单创建'''
        # 判断用户是否登录
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res':0,'errmsg':'用户未登录'})

        # 接受参数 传递的参数：addr_id,pay_mothed,sku_ids
        addr_id = request.POST.get('addr_id')
        pay_mothed = request.POST.get('pay_mothed')
        sku_ids = request.POST.get('sku_ids')

        # 校验参数
        if not all([addr_id,pay_mothed,sku_ids]):
            return JsonResponse({'res':1,'errmsg':'参数不完整'})

        # 校验地址
        try:
            addr = Address.objects.get(id=addr_id)
        except Exception as e:
            return JsonResponse({'res':2,'errmsg':'地址非法'})

        # 校验支付方式
        if pay_mothed not in OrderInfo.PAY_METHODS.keys():
            return JsonResponse({'res':3,'errmsg':'非法的支付方式'})

        # todo:创建订单核心业务处理

        # 组织参数 需要的参数：order_id , total_count , total_price , transit_price
        #订单ID:当前时间+用户ID组成
        order_id = datetime.now().strftime('%Y%m%d%H%M%S')+str(user.id)

        # 运费
        transit_price = 10

        # 总数目和总价格
        total_count=0
        total_price=0

        #设置事务保存点
        save_id = transaction.savepoint()
        try:
            #todo:向df_order_info表中添加一条条记录
            order = OrderInfo.objects.create(order_id=order_id,
                                     user=user,
                                     addr=addr,
                                     transit_price=transit_price,
                                     pay_mothed=pay_mothed,
                                     total_count=total_count,
                                     total_price=total_price)

            # todo:用户的订单有几个商品，就需要给df_order_goods表中添加几条记录
            conn = get_redis_connection('default')
            cart_key='cart_%d' % user.id
            sku_ids=sku_ids.split(',') #将字符串转换为列表
            for sku_id in sku_ids:
                # 获取商品信息
                try:
                    sku = GoodsSKU.objects.get(id=sku_id)   #普通的查询  不加锁
                    # mysql语句：select * form df_goods_sku where id=sku_id for update;  加锁
                    # sku = GoodsSKU.objects.select_for_update.get(id=sku_id)    加锁的查询
                except:
                    transaction.savepoint_rollback(save_id)
                    return JsonResponse({'res':4,'errmsg':'商品不存在'})

                # 从redis中获取用户所需要的商品的数量
                count = conn.hget(cart_key,sku_id)

                # todo:判断商品的库存
                if int(count)>sku.stock:
                    transaction.savepoint_rollback(save_id)
                    return JsonResponse({'res':6,'errmsg':'商品库存不足'})

                # todo:向df_order_goods表中添加记录
                OrderGoods.objects.create(order=order,
                                          sku=sku,
                                          count=count,
                                          price=sku.price)


                # todo:更新商品的库存和销量
                sku.stock-=int(count)
                sku.sales+=int(count)
                sku.save()

                # todo :累加计算商品的总数目和总价格
                amount = sku.price*int(count)
                total_count+=int(count)
                total_price+=amount


            #todo:更新df_order_info中商品的总数量和总价格
            order.total_count=total_count
            order.total_price=total_price
            order.save()
        except Exception as e:
            transaction.savepoint_rollback(save_id)
            return JsonResponse({'res':7,'errmsg':'下单失败'})

        #提交事务
        transaction.savepoint_commit(save_id)

        # todo:清除用户购物车中的记录
        conn.hdel(cart_key,*sku_ids)

        # 返回应答
        return JsonResponse({'res':5,"message":'创建成功'})


class OrderCommitView2(View):
    '''订单创建'''
    @transaction.atomic
    def post(self,request):
        '''订单创建'''
        # 判断用户是否登录
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res':0,'errmsg':'用户未登录'})

        # 接受参数 传递的参数：addr_id,pay_mothed,sku_ids
        addr_id = request.POST.get('addr_id')
        pay_mothed = request.POST.get('pay_mothed')
        sku_ids = request.POST.get('sku_ids')

        # 校验参数
        if not all([addr_id,pay_mothed,sku_ids]):
            return JsonResponse({'res':1,'errmsg':'参数不完整'})

        # 校验地址
        try:
            addr = Address.objects.get(id=addr_id)
        except Exception as e:
            return JsonResponse({'res':2,'errmsg':'地址非法'})

        # 校验支付方式
        if pay_mothed not in OrderInfo.PAY_METHODS.keys():
            return JsonResponse({'res':3,'errmsg':'非法的支付方式'})

        # todo:创建订单核心业务处理

        # 组织参数 需要的参数：order_id , total_count , total_price , transit_price
        #订单ID:当前时间+用户ID组成
        order_id = datetime.now().strftime('%Y%m%d%H%M%S')+str(user.id)

        # 运费
        transit_price = 10

        # 总数目和总价格
        total_count=0
        total_price=0

        #设置事务保存点
        save_id = transaction.savepoint()

        try:
            #todo:向df_order_info表中添加一条条记录
            order = OrderInfo.objects.create(order_id=order_id,
                                     user=user,
                                     addr=addr,
                                     transit_price=transit_price,
                                     pay_mothed=pay_mothed,
                                     total_count=total_count,
                                     total_price=total_price)
            # todo:用户的订单有几个商品，就需要给df_order_goods表中添加几条记录
            conn = get_redis_connection('default')
            cart_key='cart_%d' % user.id
            sku_ids=sku_ids.split(',') #将字符串转换为列表
            for sku_id in sku_ids:
                for i in range(3):
                    # 获取商品信息
                    try:
                        sku = GoodsSKU.objects.get(id=sku_id)
                    except:
                        transaction.savepoint_rollback(save_id)
                        return JsonResponse({'res':4,'errmsg':'商品不存在'})

                    # 从redis中获取用户所需要的商品的数量
                    count = conn.hget(cart_key,sku_id)

                    # todo:判断商品的库存
                    if int(count)>sku.stock:
                        transaction.savepoint_rollback(save_id)
                        return JsonResponse({'res':6,'errmsg':'商品库存不足'})

                    # todo:更新商品的库存和销量
                    orgin_stock=sku.stock
                    new_stock=orgin_stock-int(count)
                    new_sales=sku.sales+int(count)

                    # 乐观锁 在查询数据的时候不会加锁，而是在更新的时候要做判断，如果判断现在的库存量和原来的不一样，说明被改掉了
                    # 更新就会失败，但是不代表库存组 需要循环多尝试几次 一般是3次 如果失败 就说明库存不足
                    # update df_goods_sku set stock=new_stock sales=new_sales where id=sku_id and stock=orgin_stock
                    # 返回受影响的行数
                    res = GoodsSKU.objects.filter(id=sku_id,stock=orgin_stock).update(stock=new_stock,sales=new_sales)
                    if res ==0:
                        if i==2:  #尝试第三次
                            transaction.savepoint_rollback(save_id)
                            return JsonResponse({'res':7,'errmsg':'下单失败2'})
                        continue

                    # todo:向df_order_goods表中添加记录
                    OrderGoods.objects.create(order=order,
                                              sku=sku,
                                              count=count,
                                              price=sku.price)



                    # todo :累加计算商品的总数目和总价格
                    amount = sku.price*int(count)
                    total_count+=int(count)
                    total_price+=amount

                    # 跳出循环
                    break

            #todo:更新df_order_info中商品的总数量和总价格
            order.total_count=total_count
            order.total_price=total_price
            order.save()
        except Exception as e:
            transaction.savepoint_rollback(save_id)
            return JsonResponse({'res':7,'errmsg':'下单失败'})

        #提交事务
        transaction.savepoint_commit(save_id)

        # todo:清除用户购物车中的记录
        conn.hdel(cart_key,*sku_ids)

        # 返回应答
        return JsonResponse({'res':5,"message":'创建成功'})


# ajax post
# 前端传递参数:订单id(order_id)
#/order/pay
class OrderPayView(View):
    '''订单支付'''
    def post(self,request):
        '''订单支付'''
        # 用户是否登录
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res':0,'errmsg':'用户未登录'})

        # 接收参数
        order_id = request.POST.get('order_id')

        # 校验参数
        if not order_id:
            return JsonResponse({'res':1,'errmsg':'无效订单id'})

        # 是否存在该订单
        try:
            order = OrderInfo.objects.get(order_id=order_id,
                                          user=user,
                                          pay_method=3,
                                          order_status=1)
        except OrderInfo.DoesNotExist:
            # 订单不存在
            return JsonResponse({'res':2,'errmsg':'订单不存在'})

        # 业务处理:使用python sdk调用支付宝的支付接口
        # 初始化
        alipay = AliPay(
            appid="2016101600702192", #应用ID
            app_notify_url=None,  # 默认回调url
            app_private_key_path=os.path.join(settings.BASE_DIR,'apps/order/app_private_key.pem'),
            # 支付宝的公钥，验证支付宝回传消息使用，不是你自己的公钥,
            alipay_public_key_path=os.path.join(settings.BASE_DIR,'apps/order/alipay_public_key.pem'),
            sign_type="RSA2",  # RSA 或者 RSA2
            debug = True  # 默认False
        )
        # 调用支付接口
        # 电脑网站支付，需要跳转到https://openapi.alipaydev.com/gateway.do? + order_string
        total_pay = order.total_price+order.transit_price   #Decimal不能被序列化
        order_string = alipay.api_alipay_trade_page_pay(
            out_trade_no=order_id,  #订单id
            total_amount=str(total_pay), # 支付总金额
            subject='天天生鲜%s' %order_id,
            return_url=None,
            notify_url=None  # 可选, 不填则使用默认notify url
        )

        # 返回应答
        pay_url = 'https://openapi.alipaydev.com/gateway.do?' + order_string
        return JsonResponse({'res':3,'pay_url':pay_url})


# ajax post
# 前端传递参数:订单id(order_id)
#/order/check
class CheckPayView(View):
    '''查看支付订单的结果'''
    def post(self,request):
        '''查询支付结果'''
        # 用户是否登录
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res': 0, 'errmsg': '用户未登录'})

        # 接收参数
        order_id = request.POST.get('order_id')

        # 校验参数
        if not order_id:
            return JsonResponse({'res': 1, 'errmsg': '无效订单id'})
        # 是否存在该订单
        try:
            order = OrderInfo.objects.get(order_id=order_id,
                                          user=user,
                                          pay_method=3,
                                          order_status=1)
        except OrderInfo.DoesNotExist:
            # 订单不存在
            return JsonResponse({'res': 2, 'errmsg': '订单不存在'})

        # 业务处理:使用python sdk调用支付宝的支付接口
        # 初始化
        alipay = AliPay(
            appid="2016101600702192",  # 应用ID
            app_notify_url=None,  # 默认回调url
            app_private_key_path=os.path.join(settings.BASE_DIR, 'apps/order/app_private_key.pem'),
            # 支付宝的公钥，验证支付宝回传消息使用，不是你自己的公钥,
            alipay_public_key_path=os.path.join(settings.BASE_DIR, 'apps/order/alipay_public_key.pem'),
            sign_type="RSA2",  # RSA 或者 RSA2
            debug=True  # 默认False
        )
        while True:

            # 调用支付宝的交易查询接口
            response = alipay.api_alipay_trade_query(order_id)
            # response = {
            #         "trade_no": "2017032121001004070200176844", 支付宝交易号
            #         "code": "10000", 交易是否成功
            #         "invoice_amount": "20.00",
            #         "open_id": "20880072506750308812798160715407",
            #         "fund_bill_list": [
            #             {
            #                 "amount": "20.00",
            #                 "fund_channel": "ALIPAYACCOUNT"
            #             }
            #         ],
            #         "buyer_logon_id": "csq***@sandbox.com",
            #         "send_pay_date": "2017-03-21 13:29:17",
            #         "receipt_amount": "20.00",
            #         "out_trade_no": "out_trade_no15",
            #         "buyer_pay_amount": "20.00",
            #         "buyer_user_id": "2088102169481075",
            #         "msg": "Success",
            #         "point_amount": "0.00",
            #         "trade_status": "TRADE_SUCCESS", 支付的结果
            #         "total_amount": "20.00"
            #
            # }
            code = response.get('code')
            trade_status = response.get('trade_status')

            if code=='10000' and trade_status =='TRADE_SUCCESS':
                # 支付成功
                # 获取支付宝交易号
                trade_no = response.get('trade_no')
                # 更新订单状态
                order.trade_no = trade_no
                order.order_status = 4
                order.save()
                # 返回结果
                return JsonResponse({'res':3,'message':'交易成功'})

            elif code =='40004' or (code == '10000' and trade_status =='WAIT_BUYER_PAY'):
                # 等待买家付款
                # 业务处理失败，可能一会成功
                import time
                time.sleep(5)
                continue

            else:
                # 支付出错
                return JsonResponse({'res':4,'errmsg':'交易失败'})


class CommentView(View):
    '''订单评论'''
    def get(self,request,order_id):   #提供评论的页面
        '''提供评论页面'''
        user=request.user

        # 校验数据
        if not order_id:
            return redirect(reverse('user:order'))
        try:
            order = OrderInfo.objects.get(id=order_id,user=user)
        except OrderInfo.DoesNotExist:
            return redirect(reverse('user:order'))


        # 根据订单的状态获取订单订单的状态信息 动态给order添加属性
        order.status_name =OrderInfo.ORDER_STATUS(order.order_status)

        # 获取订单商品的信息
        order_skus = OrderGoods.objects.filter(order_id=order_id)

        for order_sku in order_skus:
            # 计算商品小计
            amount = order_sku.count*order_sku.prcie
            # 动态给order_sku添加属性amount,保存商品小计
            order_sku.amount = amount
        # 动态给order添加属性order_skus,保存订单商品信息
        order.order_skus=order_skus

        # 使用模板
        return render(request,'order_comment.html',{'order':order})

    def post(self,request,order_id):  # 进行评论的处理
        '''处理评论内容'''
        user=request.user

        # 校验数据
        if not order_id:
            return redirect(reverse('user:order'))
        try:
            order = OrderInfo.objects.get(id=order_id,user=user)
        except OrderInfo.DoesNotExist:
            return redirect(reverse('user:order'))

        # 获取评论数
        total_count = request.POST.get('total_count')
        total_count = int(total_count)
        # 循环获取订单中商品的评论内容
        for i in range(1,total_count+1):
            # 获取评论的商品的ID
            sku_id = request.POST.get('sku_%d' % i) # sku_1 sku_2 sku_3  名字对应的值是商品的ID 就会知道该商品对应的那个评论
            #获取评论商品的内容
            content = request.POST.get('content_%d'% i, '') #content_1 content_2 content_3

            try:
                order_goods = OrderGoods.objects.get(order=order,sku_id =sku_id)
            except OrderGoods.DoesNotExist:
                continue


            order_goods.comment=content
            order_goods.save()

        order.order_status=5 # 已完成
        order.save()

        return redirect(reverse('user:order',kwargs={'page':1}))

















