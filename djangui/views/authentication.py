from django.views.generic import CreateView
from django.http import JsonResponse
from django.core.urlresolvers import reverse
from django.contrib.auth import login, authenticate, get_user_model
from django.forms import modelform_factory
from django.utils.translation import gettext_lazy as _
from django.utils.encoding import force_unicode

class DjanguiRegister(CreateView):
    template_name = 'registration/register.html'
    model = get_user_model()
    fields = ('username', 'email', 'password')

    def post(self, request, *args, **kwargs):
        self.object = None
        form = self.get_form_class()
        post = request.POST.copy()
        post['username'] = post['username'].lower()
        form = form(post)
        if request.POST['password'] != request.POST['password2']:
            form.add_error('password', 'Passwords do not match.')
        if request.POST['username'].lower() == 'admin':
            form.add_error('username', 'Reserved username.')
        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def get_success_url(self):
        next_url = self.request.POST.get('next')
        # for some bizarre reason the password isn't setting by the modelform
        self.object.set_password(self.request.POST['password'])
        self.object.save()
        auser = authenticate(username=self.object.username, password=self.request.POST['password'])
        login(self.request, auser)
        return reverse(next_url) if next_url else reverse('djangui_home')

def djangui_login(request):
    User = get_user_model()
    form = modelform_factory(User, fields=('username', 'password'))
    user = User.objects.filter(username=request.POST.get('username'))
    if user:
        user = user[0]
    else:
        user = None
    form = form(request.POST, instance=user)
    if form.is_valid():
        data = form.cleaned_data
        user = authenticate(username=data['username'], password=data['password'])
        if user is None:
            return JsonResponse({'valid': False, 'errors': {'__all__': [force_unicode(_('You have entered an invalid username or password.'))]}})
        login(request, user)
        return JsonResponse({'valid': True, 'redirect': request.POST['next']})
    else:
        return JsonResponse({'valid': False, 'errors': form.errors})