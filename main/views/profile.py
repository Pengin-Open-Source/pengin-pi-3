from django.shortcuts import render, redirect
from django.views import View
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from main.forms.profile import ProfileForm
from werkzeug.utils import secure_filename
from util.security.ratelimit import RateLimitedPostMixin

try:
    from util.file import get_file_handler
    file_handler = get_file_handler()
except Exception:
    file_handler = None


class ProfileView(LoginRequiredMixin, RateLimitedPostMixin, View):
    def get(self, request):
        form = ProfileForm(instance=request.user)
        
        image_url = None
        if request.user.image:
            if file_handler and hasattr(file_handler, 'get_URL'):
                try:
                    image_url = file_handler.get_URL(request.user.image)
                except Exception:
                    image_url = request.user.image
            else:
                image_url = request.user.image

        context = {
            'form': form,
            'image_url': image_url,
            'primary_title': 'Your Profile',
        }
        return render(request, 'components/profile.html', context)

    def post(self, request):
        form = ProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            user = form.save(commit=False)
            uploaded_image = request.FILES.get('profile_image')
            
            if uploaded_image:
                uploaded_image.filename = secure_filename(uploaded_image.name)
                if file_handler and hasattr(file_handler, 'create'):
                    user.image = file_handler.create(uploaded_image)
                else:
                    # Default media fallback
                    from django.core.files.storage import default_storage
                    filename = default_storage.save(f"profiles/{uploaded_image.name}", uploaded_image)
                    user.image = default_storage.url(filename)

            user.save_history(user=request.user)
            user.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('profile')

        image_url = request.user.image
        if image_url and file_handler and hasattr(file_handler, 'get_URL'):
            try:
                image_url = file_handler.get_URL(request.user.image)
            except Exception:
                pass

        context = {
            'form': form,
            'image_url': image_url,
            'primary_title': 'Your Profile',
        }
        return render(request, 'components/profile.html', context)