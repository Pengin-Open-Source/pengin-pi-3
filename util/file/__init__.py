import os
from pathlib import Path
from uuid import uuid4 as id
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from util.s3 import File as S3File
from util.defaults import default


class LocalFile:
    """
    A class to handle file operations for local storage, mimicking the S3File interface.
    """
    def __init__(self):
        self.storage = FileSystemStorage(location=settings.MEDIA_ROOT, base_url=settings.MEDIA_URL)

    def create(self, file):
        """
        Saves a file to the local filesystem.
        :param file: Uploaded file object from Django request.
        :return: The name of the saved file.
        """
        try:
            # Sanitize filename and ensure uniqueness
            ext = Path(file.name).suffix
            filename = f"{id()}{ext}"
            
            # The FileSystemStorage.save method handles filename conflicts
            saved_filename = self.storage.save(filename, file)
            return saved_filename
        except Exception as e:
            print(f"LocalFile create Exception: {e}")
            return default.image

    def read(self, file_name):
        """
        Reads a file from local storage.
        Note: This is more for symmetry with S3. Direct file access is usually better.
        :param file_name: The name of the file to read.
        :return: File object or raises an exception.
        """
        try:
            return self.storage.open(file_name, 'rb')
        except Exception as e:
            print(f"LocalFile read Exception: {e}")
            return e

    def get_URL(self, file_name, exp=None):
        """
        Gets the public URL for a file.
        :param file_name: The name of the file.
        :param exp: Expiration, not used for local storage but kept for interface compatibility.
        :return: The URL to access the file.
        """
        if not file_name:
            return default.image
        try:
            return self.storage.url(file_name)
        except Exception as e:
            print(f"LocalFile get_URL Exception: {e}")
            return default.image


def get_file_handler():
    """
    Factory function to get the configured file handler.
    """
    backend = getattr(settings, 'FILE_STORAGE_BACKEND', 'local')
    if backend == 's3':
        return S3File()
    elif backend == 'local':
        return LocalFile()
    else:
        raise ValueError(f"Invalid FILE_STORAGE_BACKEND: {backend}")