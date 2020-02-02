from django.shortcuts import render,redirect
from django.http import HttpResponse
from django.contrib.auth import authenticate,login,logout # 导入认证函数

from user.models import User,Address
from django.urls import reverse # 调用反向解析
from django.core.mail import send_mail  # 调用 send_mail 发送邮件
from django.views.generic import View # 调用 View 类视图
from django.conf import settings # 调用配置文件
from utils.mixin import LoginRequestMixin
from celery_tasks.tasks import send_register_active_email
# itsdangerous下的TimedJSONWebSignatureSerializer 这个模块可以设置加密以及加密的过期时间
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from itsdangerous import SignatureExpired  # 异常
from django_redis import get_redis_connection
from goods.models import GoodsSKU
from order.models import OrderGoods,OrderInfo
from django.core.paginator import Paginator
import re
# Create your views here.
# /register
#使用同一个地址进行注册和处理 ****根据请求的方式不同 get 和post 注册是get 提交是post****
# def register(request):
#     '''注册'''
#     if request.method == 'GET':
#         # 显示注册页面
#         return render(request,'register.html')
#     else:
#         # #  接收数据
#         username = request.POST.get('user_name')
#         password = request.POST.get('pwd')
#         email = request.POST.get('email')
#         allow = request.POST.get('allow')
#
#         #  进行数据校验 [all 可以循环遍历和校验数据是否完整]
#         if not all([username, password, email]):
#             # 数据不完整
#             return render(request, 'register.html', {'errmsg': '数据不完整'})
#
#         # 校验邮箱
#         if not re.match(r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
#             # 邮箱不合法
#             return render(request, 'register.html', {'errmsg': '邮箱不合法'})
#
#         if allow != 'on':
#             return render(request, 'register.html', {'errmsg': '请同意协议'})
#
#         # 检验用户是否存在
#         try:
#             user = User.objects.get(username=username)
#         except User.DoesNotExist:
#             # 说明不存在
#             user = None
#         if user:
#             # 用户名已经存在
#             return render(request, 'register.html', {'errmsg': '用户名已经存在'})
#
#         # 3 进行业务处理
#         user = User.objects.create_user(username, password, email)
#         user.is_active = 0
#         user.save()
#
#         # 4 返回应答
#         return redirect(reverse('goods:index'))

# def register_handle(request):
#     '''进行注册的处理'''
#     # return HttpResponse('OK')
#     # #  接收数据
#     username = request.POST.get('user_name')
#     password = request.POST.get('pwd')
#     email = request.POST.get('email')
#     allow = request.POST.get('allow')
#
#     #  进行数据校验 [all 可以循环遍历和校验数据是否完整]
#     if not all([username,password,email]):
#         # 数据不完整
#         return render(request,'register.html',{'errmsg':'数据不完整'})
#
#     # 校验邮箱
#     if not re.match(r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$',email):
#         # 邮箱不合法
#         return render(request,'register.html',{'errmsg':'邮箱不合法'})
#
#     if allow != 'on':
#         return render(request,'register.html',{'errmsg':'请同意协议'})
#
#     # 检验用户是否存在
#     try:
#         user = User.objects.get(username=username)
#     except User.DoesNotExist:
#         # 说明不存在
#         user = None
#     if user:
#         # 用户名已经存在
#         return render(request,'register.html',{'errmsg':'用户名已经存在'})
#
#     # 3 进行业务处理
#     user = User.objects.create_user(username,password,email)
#     user.is_active = 0
#     user.save()
#
#     # 4 返回应答
#     return redirect(reverse('goods:index'))


# 类视图 不同的请求方式对应不同的函数
# GET POST PUT DELETE OPTION

class RegisterView(View):
    '''注册'''
    def get(self,request):
        '''显示注册页面'''
        return render(request,'register.html')

    def post(self,request):
        '''进行注册的处理'''
        #  接收数据
        username = request.POST.get('user_name')
        password = request.POST.get('pwd')
        email = request.POST.get('email')
        allow = request.POST.get('allow')

        #  进行数据校验 [all 可以循环遍历和校验数据是否完整]
        if not all([username, password, email]):
            # 数据不完整
            return render(request, 'register.html', {'errmsg': '数据不完整'})

        # 校验邮箱
        if not re.match(r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            # 邮箱不合法
            return render(request, 'register.html', {'errmsg': '邮箱不合法'})

        if allow != 'on':
            return render(request, 'register.html', {'errmsg': '请同意协议'})

        # 检验用户是否存在
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            # 说明不存在
            user = None
        if user:
            # 用户名已经存在
            return render(request, 'register.html', {'errmsg': '用户名已经存在'})

        # 3 进行业务处理 创建用户
        user = User.objects.create_user(username, password, email)
        user.is_active = 0  # 0表示未激活 表示是否被激活
        user.save()

        # 发送激活邮件，包含激活链接：127.0.0.1/8000/user/active/user_id
        #激活的链接中需要包含用户的信息，并且把信息进行加密

        # 加密用户的身份信息，并且生成激活的token Serializer()参数包括 秘钥，过期时间
        serializer = Serializer(settings.SECRET_KEY,3600)
        info = {'confirm':user.id}
        token = serializer.dumps(info) # bytes数据
        token = token.decode('utf8')

        # 发邮件
        send_register_active_email.delay(email,username,token)
        # subject = '天天生鲜欢迎信息'
        # message =''
        # sender = settings.EMAIL_FROM
        # receiver = [email]
        # html_message ='<h1>%s,欢迎您注册为天天生鲜的会员</h1>请点击下面链接激活您的账户<br><a href="http://127.0.0.1:8000/user/active/%s">http://127.0.0.1:8000/user/active/%s</a>'%(username,token,token)
        # send_mail(subject,message,sender,receiver,html_message=html_message) # send_mail作用是把邮件发送到SMTP服务器

        # 4 返回应答
        return redirect(reverse('goods:index'))


class ActiveView(View):
    '''用户激活'''
    def get(self,request,token):
        '''进行用户激活'''
        # 进行解密，获取要激活的用户的信息
        serializer = Serializer(settings.SECRET_KEY,3600)
        try:
            info = serializer.loads(token)
            # 获取待激活的用户的ID
            user_id = info['confirm']
            # 根据ID获取用户信息
            user = User.objects.get(id=user_id)
            user.is_active = 1 # 1表示激活了
            user.save()
            # 跳转到登录界面
            return redirect(reverse('user:login'))
        except SignatureExpired as e:
            # 激活链接已经过期、
            return HttpResponse('激活链接已经过期')



#/user/login
class LoginView(View):
    '''登录'''
    def get(self,request):
        '''显示登录页面'''
        # 判断是否记住用户名
        if 'username' in request.COOKIES:
            username = request.COOKIES.get('username')
            checked = 'checked'
        else:
            username = ''
            checked = ''
        return render(request,'login.html',{'username':username,'checked':checked})

    def post(self,request):
        '''登录的处理'''
        #  接收数据
        username = request.POST.get('username')
        password = request.POST.get('pwd')

        # 校验数据
        if not all([username,password]):
            return render(request,'login.html',{'errmsg':'数据不完整'})

        #业务的处里：登录效验
        # authenticate验证用户名密码对不对
        user = authenticate(username=username, password=password)
        if user is not None:
            if user.is_active:
                # 用户已激活
                # 记录用户的登录状态
                login(request,user)
                # 获取登录后索要跳转的地址  默认跳转到首页
                next_url = request.GET('next',reverse('goods:index'))
                # 跳转到next_url
                response =  redirect(next_url)
                # 判断用户是否要记住用户名
                remember = request.POST.get('remember')
                if remember =='on':
                    # 记住用户名
                    response.set_cookie('username',username,max_age=7*24*3600)
                else:
                    response.delete_cookie('username')
                    # 返回应答
                return response

            else:
                # 用户未激活
                return render(request,'login.html',{'errmsg':'账户未激活'})
        else:
            # 用户名或密码错误
            return render(request,'login.html',{'errmsg':'用户名或密码错误'})


#/user/logout
class LogoutView(View):
    def get(self,request):
        '''退出登录'''
        logout(request)
        # 退出后返回主页面
        return redirect(reverse('goods:index'))


#/user
class UserInfoView(LoginRequestMixin,View):
# class UserInfoView(View):
    '''用户中心--信息页面'''
    def get(self,request):
        # page = user
        # 1 如果用户未登录 返回AnonymousUser类的一个实例
        # 2 如果用户登录了，返回User类的一个实例
        # 1和2  这两都有  # request.user.is_authenticated()方法 前者返回False 后者返回True
        # 除了给模板文件传递的模板变量之外，django框架也会把request.user也传给模板文件

        # 获取用户登录信息
        # 获取登录用户对应的User对象
        user = request.user
        address = Address.objects.get_default_address(user)  ## 模型管理器类的运用 函数的封装


        # 获取用户的历史浏览记录
        # from redis import StrictRedis
        # sr =StrictRedis(host='127.0.0.1',port=6379,db=3)
        con = get_redis_connection('default')  # 使用原生客户端 返回对象也是StricRedis查询集  连接到redis数据库的链接

        history_key = 'histort_%d' % user.id  # 根据登陆用户对应的User对象的Id 拼接出对应历史浏览记录的key值

        # 获取用户最新浏览的5个商品
        sku_id = con.lrange(history_key,0,4)

        # 根据用户最新浏览的5个商品的Id顺序 遍历从数据库中查询用户浏览的商品的具体信息
        goods_li = []
        for id in sku_id:
            goods =GoodsSKU.objects.get(id = id)
            goods_li.append(goods)

        #  组织上下文
        context = {'page':'user',
                   'address':address,
                   'goods_li':goods_li}

        return render(request,'user_center_info.html',context)


#/user/order
class UserOrderView(LoginRequestMixin,View):
# class UserOrderView(View):
    '''用户中心--订单页面'''
    def get(self,request,page):
        # page = order
        # 获取用户订单的信息
        user = request.user
        orders = OrderInfo.objects.filter(user=user).order_by('-create_time')
        # 遍历获取订单商品的信息
        for order in orders:
            # 根据order_id查询商品的信息
            order_skus = OrderGoods.objects.filter(order_id = order.order_id)

            # 遍历order_skus计算商品的小计
            for order_sku in order_skus:
                amount = order_sku.count*order_sku.price


                # 动态给order_sku添加属性amount,保存订单商品小计
                order_sku.amount = amount
            #动态给order添加属性order_skus,保存订单商品的信息
            order.order_skus = order_skus
            # 动态给order添加属性,保存订单状态标题
            order.status_name = OrderInfo.ORDER_STATUS[order.order_status]

        #对数据进行分页
        paginator = Paginator(orders, 5)  # Show 5 contacts per page
        #获取第page页的内容
        try:
            page=int(page)
        except Exception as e:
            page=1
        if page > paginator.num_pages:
            page=1
        # 获取第page页的Page的实例对象
        order_page = paginator.page(page)

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

        #组织上下文
        context = {'page':'order',
                   'order_page':order_page,
                   'pages':pages}



        return render(request,'user_center_order.html',context)


#/user/address
class AddressView(LoginRequestMixin,View):
# class AddressView(View):
    '''用户中心--地址页面'''
    def get(self,request):
        # page = address
        # 获取用户默认的收货地址

        # 获取登录用户对应的User对象
        user = request.user
        # try:
        #     address =  Address.objects.get(user=user,is_default = True)
        # except Address.DoesNotExist:
        #     # 不存在默认的地址
        #     address = None
        address = Address.objects.get_default_address(user) # # 模型管理器类的运用 函数的封装
        # 使用模板
        return render(request,'user_center_site.html',{'page':'address','address':address})


    def post(self,request):
        '''地址添加'''
        # 接收数据
        receiver = request.POST.get('receiver')
        addr = request.POST.get('addr')
        zip_code = request.POST.get('zip_code')
        phone = request.POST.get('phone')

        # 效验数据
        if not all([receiver,addr,phone]):
            return render(request,'user_center_info.html',{'errmsg':'数据不完整'})
        # 校验手机号是否规范
        if not re.match(r'^1[3|4|5|7|8][0-9]{9}$',phone):
            return render(request,'user_center_site.html',{"errmsg":'手机号格式不正确'})

        # 业务的处理：地址添加
        # 如果已经存在了默认的收货地址，添加的地址不作为默的地址，否则作为默认的地址

        # 获取登录用户对应的User对象
        user = request.user
        # try:
        #     address =  Address.objects.get(user=user,is_default = True)
        # except Address.DoesNotExist:
        #     # 不存在默认的地址
        #     address = None
        address = Address.objects.get_default_address(user)    # 模型管理器类的运用 函数的封装

        if address:
            is_default = False
        else:
            is_default = True


        # 添加地址
        Address.objects.create(user = user,
                               receiver = receiver,
                               addr = addr,
                               zip_code = zip_code,
                               phone = phone,
                               is_default = is_default)

        # 返回应答
        return redirect(reverse('user:address')) # get请求方式






