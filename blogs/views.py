# blogs/views.py
# Reading is public (no login required); creating/editing/deleting is
# gated to staff via main.auth.is_admin_required/is_admin_provider - same
# convention as about/home/products/jobs. tobuwebprod gated this to a
# "Marketing department" (teams.permissions.can_manage_blog), but that
# department-specific RBAC concept was deliberately left out of
# main.auth during the earlier auth-consolidation phase (no such app/
# concept exists in this generic starter), so plain staff gating is used
# here instead - a real department-scoped gate can be layered on top of
# main.auth's TeamRole framework later if a specific deployment wants one.
import json
from datetime import datetime
from django.apps import apps
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.db.models import Q
from werkzeug.utils import secure_filename

from main.auth import is_admin_required
from main.models import Event
from util.paginate import paginate
from util.file import get_file_handler
from .models import BlogPost
from .forms import BlogForm

conn = get_file_handler()


def handle_blog_event_sync(blog_post, form, user):
    """Creates, updates, or deletes an associated Event based on the
    is_event toggle state. A blog-linked event defaults to public
    visibility, since attaching one to a post is meant to promote it
    (workshop, announcement, job fair) on the public calendar."""
    is_event = form.cleaned_data.get('is_event')

    if is_event:
        location = form.cleaned_data.get('event_location', '')
        start_dt = form.cleaned_data.get('event_start_datetime')
        end_dt = form.cleaned_data.get('event_end_datetime')

        if blog_post.event:
            event = blog_post.event
            event.title = blog_post.title
            event.description = blog_post.content
            event.location = location
            event.start_datetime = start_dt
            event.end_datetime = end_dt
            event.save()
        else:
            event = Event.objects.create(
                title=blog_post.title,
                description=blog_post.content,
                location=location,
                start_datetime=start_dt,
                end_datetime=end_dt,
                author=user,
                organizer=user,
                visibility=Event.VISIBILITY_PUBLIC,
            )
            blog_post.event = event
            blog_post.is_event = True
    else:
        blog_post.is_event = False
        if blog_post.event:
            old_event = blog_post.event
            blog_post.event = None
            old_event.delete()


def handle_blog_file_upload(blog_post, request):
    """Saves file attachment via FileIO/S3 handler if uploaded."""
    uploaded_file = request.FILES.get('attachment')
    if uploaded_file:
        uploaded_file.filename = secure_filename(uploaded_file.name)
        saved_key = conn.create(uploaded_file)
        blog_post.file = saved_key
        if not blog_post.file_name:
            blog_post.file_name = uploaded_file.name


class BlogsListView(ListView):
    """The public blog feed - no login required to read."""
    model = BlogPost
    template_name = 'blogs.html'
    context_object_name = 'posts'

    def get_filtered_queryset(self):
        qs = BlogPost.objects.select_related('author', 'event')

        # 1. Search Query Filter
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(title__icontains=q) |
                Q(content__icontains=q) |
                Q(tags__icontains=q)
            ).distinct()

        # 2. Selected Tags Filter
        selected_tags = [t for t in self.request.GET.getlist('tag') if t.strip()]
        if selected_tags:
            tag_query = Q()
            for tag in selected_tags:
                tag_query |= Q(tags__icontains=tag)
            qs = qs.filter(tag_query)

        # 3. Date Range Filter
        start_date_str = self.request.GET.get('start_date', '').strip()
        end_date_str = self.request.GET.get('end_date', '').strip()

        if start_date_str:
            try:
                start_dt = datetime.strptime(start_date_str, '%Y-%m-%d')
                qs = qs.filter(date__gte=start_dt)
            except ValueError:
                pass

        if end_date_str:
            try:
                end_dt = datetime.strptime(end_date_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
                qs = qs.filter(date__lte=end_dt)
            except ValueError:
                pass

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = self.get_filtered_queryset()
        page_number = self.request.GET.get('page', 1)

        context['posts'] = paginate(
            queryset=lambda: queryset,
            page=int(page_number),
            per_page=6,
            key='date'
        )

        # Extract available tags and published dates scoped to the visible queryset
        all_tags_raw = queryset.values_list('tags', flat=True)
        distinct_tags = set()
        for tag_str in all_tags_raw:
            if tag_str:
                for t in tag_str.split(','):
                    cleaned = t.strip()
                    if cleaned:
                        distinct_tags.add(cleaned)

        context['available_tags'] = sorted(list(distinct_tags))
        context['selected_tags'] = self.request.GET.getlist('tag')

        # Standardized search-state variables so templates don't need to
        # reach into request.GET directly (dotted lookups can't be passed
        # as macro args, and this keeps the "clear filters" logic in one place).
        context['query'] = self.request.GET.get('q', '').strip()
        clear_params = self.request.GET.copy()
        clear_params.pop('q', None)
        clear_params.pop('page', None)
        context['clear_search_url'] = '?' + clear_params.urlencode()
        context['clear_all_filters_url'] = self.request.path

        post_dates = list(queryset.values_list('date', flat=True))
        context['published_dates_json'] = json.dumps(
            [d.strftime('%Y-%m-%d') for d in post_dates if d]
        )

        context['is_admin'] = self.request.user.is_authenticated and self.request.user.is_staff
        context['primary_title'] = 'Blog'
        return context


class BlogPostDetailView(DetailView):
    """A single post - no login required to read."""
    model = BlogPost
    template_name = 'blogpost.html'
    context_object_name = 'post'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        post = self.object
        user = self.request.user

        file_url = None
        if post.file:
            try:
                file_url = conn.get_URL(post.file)
            except Exception:
                file_url = None

        is_admin = user.is_authenticated and user.is_staff
        context['file_url'] = file_url
        context['can_edit'] = is_admin
        context['is_admin'] = is_admin
        context['primary_title'] = post.title
        # events isn't a dependency of this branch (only main.Event is) - the
        # "Add to Calendar" ICS link only makes sense if the calendar app
        # providing events:event_ics is actually installed.
        context['events_enabled'] = apps.is_installed('events')
        return context


@method_decorator(is_admin_required, name='dispatch')
class BlogPostCreateView(CreateView):
    model = BlogPost
    form_class = BlogForm
    template_name = 'blogs_create.html'

    def form_valid(self, form):
        blog_post = form.save(commit=False)
        blog_post.author = self.request.user
        blog_post.date = timezone.now()

        handle_blog_file_upload(blog_post, self.request)
        handle_blog_event_sync(blog_post, form, self.request.user)
        blog_post.save()

        blog_post.save_history(user=self.request.user)
        return redirect('blogs:blog_post', pk=blog_post.pk)


@method_decorator(is_admin_required, name='dispatch')
class BlogPostEditView(UpdateView):
    model = BlogPost
    form_class = BlogForm
    template_name = 'edit_blog_post.html'

    def form_valid(self, form):
        blog_post = form.save(commit=False)
        handle_blog_file_upload(blog_post, self.request)
        handle_blog_event_sync(blog_post, form, self.request.user)
        blog_post.save()

        blog_post.save_history(user=self.request.user)
        return redirect('blogs:blog_post', pk=blog_post.pk)


@method_decorator(is_admin_required, name='dispatch')
class BlogPostDeleteView(DeleteView):
    model = BlogPost
    success_url = reverse_lazy('blogs:blogs')

    def post(self, request, *args, **kwargs):
        blog_post = get_object_or_404(BlogPost, pk=self.kwargs.get('pk'))

        if blog_post.event:
            blog_post.event.delete()

        blog_post.save_history(user=request.user)
        blog_post.delete()
        return redirect(self.success_url)
