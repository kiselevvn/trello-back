from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django import forms
from django.shortcuts import render, redirect
from django.urls import path
from django.contrib import messages
from django.http import HttpResponseRedirect
from .models import (
    Board, Column, Task, Label, Comment, 
    Attachment, ActivityLog, TaskLabel
)

# Inline модели для админки
class ColumnInline(admin.TabularInline):
    model = Column
    extra = 1
    ordering = ['position']

class TaskInline(admin.TabularInline):
    model = Task
    extra = 1
    fields = ['title', 'assignee', 'priority', 'position']
    ordering = ['position']

class LabelInline(admin.TabularInline):
    model = Label
    extra = 1

class CommentInline(admin.TabularInline):
    model = Comment
    extra = 0
    readonly_fields = ['created_at', 'updated_at']

class AttachmentInline(admin.TabularInline):
    model = Attachment
    extra = 0
    readonly_fields = ['uploaded_at']

@admin.register(Board)
class BoardAdmin(admin.ModelAdmin):
    list_display = ['title', 'owner', 'is_archived', 'created_at', 'member_count']
    list_filter = ['is_archived', 'created_at', 'owner']
    search_fields = ['title', 'description', 'owner__username']
    filter_horizontal = ['members']
    inlines = [ColumnInline, LabelInline]
    
    def member_count(self, obj):
        return obj.members.count()
    member_count.short_description = 'Участников'

@admin.register(Column)
class ColumnAdmin(admin.ModelAdmin):
    list_display = ['title', 'board', 'position', 'task_count', 'created_at']
    list_filter = ['board', 'created_at']
    search_fields = ['title', 'board__title']
    ordering = ['board', 'position']
    inlines = [TaskInline]
    
    def task_count(self, obj):
        return obj.tasks.count()
    task_count.short_description = 'Задач'

@admin.register(Label)
class LabelAdmin(admin.ModelAdmin):
    list_display = ['name', 'board', 'color']
    list_filter = ['board']
    search_fields = ['name', 'board__title']

@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'board', 'action', 'created_at']
    list_filter = ['action', 'created_at', 'board']
    search_fields = ['user__username', 'board__title']
    readonly_fields = ['user', 'board', 'action', 'details', 'created_at']
    date_hierarchy = 'created_at'

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ['author', 'task', 'created_at', 'truncated_text']
    list_filter = ['created_at', 'author']
    search_fields = ['text', 'author__username', 'task__title']
    readonly_fields = ['created_at', 'updated_at']
    
    def truncated_text(self, obj):
        return obj.text[:50] + '...' if len(obj.text) > 50 else obj.text
    truncated_text.short_description = 'Текст'

@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ['file_name', 'task', 'uploaded_by', 'uploaded_at', 'file_size_formatted']
    list_filter = ['uploaded_at']
    search_fields = ['file_name', 'task__title']
    readonly_fields = ['uploaded_at']
    
    def file_size_formatted(self, obj):
        if obj.file_size < 1024:
            return f"{obj.file_size} B"
        elif obj.file_size < 1024 * 1024:
            return f"{obj.file_size / 1024:.1f} KB"
        else:
            return f"{obj.file_size / (1024 * 1024):.1f} MB"
    file_size_formatted.short_description = 'Размер файла'

# Форма для массового добавления задач
class MassTaskForm(forms.Form):
    """Форма для массового добавления задач пользователям"""
    title = forms.CharField(
        label='Название задачи',
        max_length=255,
        required=True,
        widget=forms.TextInput(attrs={'class': 'vTextField', 'style': 'width: 100%;'})
    )
    description = forms.CharField(
        label='Описание',
        required=False,
        widget=forms.Textarea(attrs={'rows': 4, 'style': 'width: 100%;'})
    )
    column = forms.ModelChoiceField(
        label='Колонка',
        queryset=Column.objects.all(),
        required=True
    )
    due_date = forms.DateTimeField(
        label='Срок выполнения',
        required=False,
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'})
    )
    priority = forms.ChoiceField(
        label='Приоритет',
        choices=Task.PRIORITY_CHOICES,
        initial='medium'
    )
    users = forms.ModelMultipleChoiceField(
        label='Пользователи',
        queryset=User.objects.filter(is_active=True),
        required=True,
        widget=forms.SelectMultiple(attrs={'style': 'width: 100%; height: 200px;'})
    )
    add_labels = forms.ModelMultipleChoiceField(
        label='Метки',
        queryset=Label.objects.all(),
        required=False,
        widget=forms.SelectMultiple(attrs={'style': 'width: 100%;'})
    )

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['title', 'column', 'assignee', 'priority', 'due_date', 'is_archived', 'created_at']
    list_filter = ['priority', 'is_archived', 'created_at', 'column__board', 'column']
    search_fields = ['title', 'description', 'assignee__username', 'creator__username']
    readonly_fields = ['created_at', 'updated_at']
    filter_horizontal = []
    raw_id_fields = ['assignee', 'creator']
    date_hierarchy = 'created_at'
    
    # Добавляем кастомный action
    actions = ['mass_create_tasks_action']
    
    # Добавляем кастомную view
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('mass-create/', self.admin_site.admin_view(self.mass_create_tasks), name='mass_create_tasks'),
        ]
        return custom_urls + urls
    
    def mass_create_tasks_action(self, request, queryset):
        """Action для массового создания задач"""
        # Здесь можно реализовать логику для выбранных объектов
        # Пока просто перенаправляем на отдельную форму
        return redirect('admin:mass_create_tasks')
    mass_create_tasks_action.short_description = "Массово создать задачи для пользователей"
    
    def mass_create_tasks(self, request):
        """View для массового создания задач"""
        if request.method == 'POST':
            form = MassTaskForm(request.POST)
            if form.is_valid():
                column = form.cleaned_data['column']
                title = form.cleaned_data['title']
                description = form.cleaned_data['description']
                due_date = form.cleaned_data['due_date']
                priority = form.cleaned_data['priority']
                users = form.cleaned_data['users']
                labels = form.cleaned_data.get('add_labels', [])
                
                created_count = 0
                for user in users:
                    task = Task.objects.create(
                        title=f"{title} ({user.username})",
                        description=description,
                        column=column,
                        assignee=user,
                        creator=request.user,
                        due_date=due_date,
                        priority=priority,
                    )
                    
                    # Добавляем метки если есть
                    for label in labels:
                        TaskLabel.objects.get_or_create(task=task, label=label)
                    
                    # Логируем действие
                    ActivityLog.objects.create(
                        user=request.user,
                        board=column.board,
                        action='create_task',
                        details={
                            'task_id': task.id,
                            'task_title': task.title,
                            'assignee': user.username,
                        }
                    )
                    created_count += 1
                
                messages.success(request, f'Успешно создано {created_count} задач для {len(users)} пользователей')
                return redirect('admin:taskboard_task_changelist')
        else:
            form = MassTaskForm()
        
        context = {
            'form': form,
            'title': 'Массовое создание задач',
            'opts': self.model._meta,
            'has_view_permission': True,
            'media': self.media,
        }
        
        return render(request, 'admin/board/mass_create_tasks.html', context)

# Регистрируем TaskLabel (опционально, можно через inline)
class TaskLabelInline(admin.TabularInline):
    model = TaskLabel
    extra = 1

# Кастомная форма для отображения меток в Task
class TaskAdminForm(forms.ModelForm):
    labels = forms.ModelMultipleChoiceField(
        queryset=Label.objects.all(),
        required=False,
        widget=forms.SelectMultiple(attrs={'style': 'width: 100%;'})
    )
    
    class Meta:
        model = Task
        fields = '__all__'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['labels'].initial = self.instance.labels.all()
    
    def save(self, commit=True):
        task = super().save(commit=False)
        if commit:
            task.save()
        
        if task.pk:
            # Сохраняем метки
            labels = self.cleaned_data.get('labels', [])
            # Удаляем старые связи
            TaskLabel.objects.filter(task=task).delete()
            # Добавляем новые
            for label in labels:
                TaskLabel.objects.create(task=task, label=label)
        
        return task

# Обновляем TaskAdmin с новой формой
TaskAdmin.form = TaskAdminForm

# Шаблон для массового создания задач (создайте файл templates/admin/taskboard/mass_create_tasks.html)
"""
{% extends "admin/base_site.html" %}
{% load i18n admin_urls static admin_modify %}

{% block extrastyle %}
    {{ block.super }}
    <link rel="stylesheet" type="text/css" href="{% static "admin/css/forms.css" %}">
{% endblock %}

{% block breadcrumbs %}
<div class="breadcrumbs">
<a href="{% url 'admin:index' %}">{% trans 'Home' %}</a>
&rsaquo; <a href="{% url 'admin:app_list' app_label=opts.app_label %}">{{ opts.app_config.verbose_name }}</a>
&rsaquo; <a href="{% url opts|admin_urlname:'changelist' %}">{{ opts.verbose_name_plural|capfirst }}</a>
&rsaquo; Массовое создание задач
</div>
{% endblock %}

{% block content %}
<div id="content-main">
    <form method="post" id="mass_task_form">
        {% csrf_token %}
        
        <fieldset class="module aligned">
            {% for field in form %}
                <div class="form-row">
                    {{ field.errors }}
                    <div class="flex-container">
                        <label for="{{ field.id_for_label }}" class="required">
                            {{ field.label }}
                        </label>
                        {{ field }}
                        {% if field.help_text %}
                            <div class="help">{{ field.help_text|safe }}</div>
                        {% endif %}
                    </div>
                </div>
            {% endfor %}
        </fieldset>
        
        <div class="submit-row">
            <input type="submit" value="Создать задачи" class="default" name="_save">
            <a href="{% url opts|admin_urlname:'changelist' %}" class="closelink">Отмена</a>
        </div>
    </form>
</div>
{% endblock %}
"""

# Если используете кастомную модель UserProfile
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        # Создаем профиль если нужно
        pass

# Можно также добавить фильтры по связанным полям
class BoardOwnerFilter(admin.SimpleListFilter):
    title = 'Владелец доски'
    parameter_name = 'owner'
    
    def lookups(self, request, model_admin):
        owners = User.objects.filter(boards__isnull=False).distinct()
        return [(owner.id, owner.username) for owner in owners]
    
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(owner_id=self.value())

BoardAdmin.list_filter = [BoardOwnerFilter, 'is_archived', 'created_at']

# Улучшенный поиск для Task
class TaskColumnFilter(admin.SimpleListFilter):
    title = 'Колонка'
    parameter_name = 'column'
    
    def lookups(self, request, model_admin):
        columns = Column.objects.all()
        return [(column.id, f"{column.title} - {column.board.title}") for column in columns]
    
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(column_id=self.value())

TaskAdmin.list_filter = [TaskColumnFilter, 'priority', 'is_archived', 'created_at']