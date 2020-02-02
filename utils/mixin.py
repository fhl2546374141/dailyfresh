from django.contrib.auth.decorators import login_required
# 封装as_view的mixin
#将共同的行为运用于多个类的- -种方法是编写-一个封裴as. view() 方法的Mixin。
#例如，如果你有许多通用视图，它们应该使用Login_ required() 装饰器，你可以这样实现- - 个Mixin:
# 实现用户登录的跳转
class LoginRequestMixin(object):
    @classmethod
    def as_view(cls,**initkwargs):
        # 调用父类的as_view
        view = super(LoginRequestMixin,cls).as_view(**initkwargs)
        return login_required(view)