# main/tests/test_wiki_permissions.py
# Wiki writes are staff-only. Run: python manage.py test main.tests
from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings

from main.models import Slug, User

LOCMEM = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}


@override_settings(CACHES=LOCMEM, SECURE_SSL_REDIRECT=False)
class WikiTestBase(TestCase):
    def setUp(self):
        cache.clear()
        # SuperTemplateView logs every hit straight to Redis (not the cache
        # API), which a test run doesn't have.
        patcher = mock.patch('main.views.base.SuperTemplateView.log_request')
        patcher.start()
        self.addCleanup(patcher.stop)
        self.page = Slug.objects.create(name='target-page', meta_tags='', meta_description='')
        self.staff = User.objects.create_user(email='staff@example.com', password='pw', is_staff=True)
        self.resident = User.objects.create_user(email='res@example.com', password='pw')


class WikiStaffOnlyTests(WikiTestBase):
    """Wiki writes are staff-only - a signed-in non-staff account must not
    be able to mint pages/URLs (or history rows) without limit."""
    def setUp(self):
        super().setUp()
        self.wiki = Slug(name='docs', parent=self.page, meta_tags='', meta_description='', wiki_body='x')
        self.wiki.wiki_root = self.wiki
        self.wiki.save()

    def test_non_staff_cannot_create_or_edit(self):
        self.client.force_login(self.resident)
        before = Slug.objects.count()
        for url, data in [
            ('/target-page/wiki/create/', {'name': 'spam', 'wiki_body': 'x'}),
            ('/target-page/docs/create/', {'name': 'spam2', 'wiki_body': 'x'}),
            ('/target-page/docs/edit/', {'name': 'docs', 'wiki_body': 'defaced'}),
        ]:
            self.assertEqual(self.client.get(url).status_code, 403, url)
            self.assertEqual(self.client.post(url, data).status_code, 403, url)
        self.assertEqual(Slug.objects.count(), before)
        self.wiki.refresh_from_db()
        self.assertEqual(self.wiki.wiki_body, 'x')

    def test_anonymous_sent_to_login(self):
        response = self.client.post('/target-page/docs/create/', {'name': 'spam'})
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response['Location'])

    def test_staff_can_create_and_edit(self):
        self.client.force_login(self.staff)
        self.client.post('/target-page/docs/create/', {'name': 'New Page', 'wiki_body': 'hi'})
        self.assertTrue(Slug.objects.filter(name='new-page', wiki_root=self.wiki).exists())
        self.client.post('/target-page/docs/edit/', {'name': 'docs', 'wiki_body': 'edited'})
        self.wiki.refresh_from_db()
        self.assertEqual(self.wiki.wiki_body, 'edited')
