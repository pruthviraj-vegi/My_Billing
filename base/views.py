"""Views for authentication, home page, and error handling."""

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import TemplateView


from .forms import CustomLoginForm


class CustomLoginView(LoginView):
    """Handle user login with remember-me and safe redirect support."""

    form_class = CustomLoginForm
    template_name = "base/login.html"
    redirect_authenticated_user = True

    def get_success_url(self):
        """
        Redirect to the exact page after login.
        Priority:
        1. 'next' parameter from POST request (form submission)
        2. 'next' URL parameter from GET request
        3. 'next' stored in session (by middleware)
        4. Default to home page
        """
        redirect_url = self.request.POST.get("next") or self.request.GET.get("next")

        # If not in GET/POST, check session (stored by middleware)
        if not redirect_url:
            redirect_url = self.request.session.get("next")
            # Clean up session after retrieving
            if redirect_url:
                del self.request.session["next"]

        # Validate the redirect URL for security
        if redirect_url:
            # Check if URL is safe (same host, allowed scheme)
            if url_has_allowed_host_and_scheme(redirect_url, allowed_hosts=None):
                return redirect_url

        # Default to home page
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
    """Dashboard home page, accessible to all authenticated roles."""

    template_name = "base/home.html"
    login_url = "base:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["user"] = self.request.user
        return context


def custom_404_view(request, _exception):
    """
    Custom 404 error handler.
    Django error handlers must be function-based views that accept:
    - handler404: (request, exception)
    - handler500: (request)
    - handler403: (request, exception)
    - handler400: (request, exception)
    """
    return render(request, "404.html", status=404)


def logout_view(request):
    """Log the user out and redirect to the login page."""
    logout(request)
    return redirect("base:login")
