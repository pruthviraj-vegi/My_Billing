from django.urls import reverse_lazy
from django.contrib.auth.views import LoginView
from django.contrib import messages
from django.views.generic import TemplateView
from django.shortcuts import redirect
from .forms import CustomLoginForm
from django.contrib.auth import logout


class CustomLoginView(LoginView):
    form_class = CustomLoginForm
    template_name = "base/login.html"
    redirect_authenticated_user = True

    def get_success_url(self):
        # Redirect to admin panel or dashboard
        return reverse_lazy("base:home")

    def form_valid(self, form):
        remember = form.cleaned_data.get("remember")
        if not remember:
            # Set session to expire when browser closes
            self.request.session.set_expiry(0)

        # Call parent form_valid to handle login
        response = super().form_valid(form)

        # Add success message
        messages.success(self.request, f"Welcome back, {self.request.user.full_name}!")

        return response

    def form_invalid(self, form):
        # Add error message for invalid login
        messages.error(
            self.request, "Invalid phone number or password. Please try again."
        )
        return super().form_invalid(form)


class HomeView(TemplateView):
    template_name = "base/home.html"
    login_url = "base:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["user"] = self.request.user
        return context


def logout_view(request):
    logout(request)
    return redirect("base:login")
