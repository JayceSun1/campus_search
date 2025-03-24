from django.db import models

# Create your models here.
class item(models.Model):
    title = models.CharField(max_length=255)
    url = models.CharField(max_length=255)
    content = models.TextField()
    department = models.CharField(max_length=255)