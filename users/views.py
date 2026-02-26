from django.contrib import messages
from django.contrib.auth import authenticate, login, get_user_model
from django.http import HttpResponse
from django.shortcuts import render, redirect
from .forms import  UserForm
User = get_user_model()

# Create your views here.

def about(request):
    return render(request, 'users/about.html')

def site_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('listing')
        else:
            messages.error(request, 'Username OR password is incorrect')
    return render(request, 'users/login.html')

def user_register(request):
    if request.method == "POST":
        form = UserForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("listing")
    else:
        form = UserForm()

    return render(request, "users/register.html", {"form": form})
