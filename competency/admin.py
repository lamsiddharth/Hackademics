from django.contrib import admin
from .models import *
# Register your models here.

admin.site.register(CompetencyTest)
admin.site.register(TestResult)

admin.site.register(Question)

admin.site.register(CompetencyTestSession)
admin.site.register(Answer)


