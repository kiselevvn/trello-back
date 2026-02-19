from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class Board(models.Model):
    """Модель доски (Board)"""
    title = models.CharField(max_length=255, verbose_name="Название доски")
    description = models.TextField(blank=True, null=True, verbose_name="Описание")
    owner = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='boards',
        verbose_name="Владелец"
    )
    members = models.ManyToManyField(
        User, 
        related_name='shared_boards',
        blank=True,
        verbose_name="Участники"
    )
    background_color = models.CharField(
        max_length=7, 
        default='#0079bf',
        verbose_name="Цвет фона"
    )
    is_archived = models.BooleanField(default=False, verbose_name="В архиве")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    
    class Meta:
        verbose_name = "Доска"
        verbose_name_plural = "Доски"
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title


class Column(models.Model):
    """Модель колонки (списка тем) в доске"""
    title = models.CharField(max_length=255, verbose_name="Название колонки")
    board = models.ForeignKey(
        Board, 
        on_delete=models.CASCADE, 
        related_name='columns',
        verbose_name="Доска"
    )
    position = models.PositiveIntegerField(default=0, verbose_name="Позиция")
    color = models.CharField(
        max_length=7, 
        default='#ebecf0',
        verbose_name="Цвет колонки"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    
    class Meta:
        verbose_name = "Колонка"
        verbose_name_plural = "Колонки"
        ordering = ['position']
    
    def __str__(self):
        return f"{self.title} - {self.board.title}"
    
    def save(self, *args, **kwargs):
        # Автоматическая установка позиции при создании
        if not self.pk:
            max_position = Column.objects.filter(board=self.board).aggregate(
                models.Max('position')
            )['position__max']
            self.position = (max_position or -1) + 1
        super().save(*args, **kwargs)


class Task(models.Model):
    """Модель задачи (карточки)"""
    PRIORITY_CHOICES = [
        ('low', 'Низкий'),
        ('medium', 'Средний'),
        ('high', 'Высокий'),
    ]
    
    title = models.CharField(max_length=255, verbose_name="Название задачи")
    description = models.TextField(blank=True, null=True, verbose_name="Описание")
    column = models.ForeignKey(
        Column, 
        on_delete=models.CASCADE, 
        related_name='tasks',
        verbose_name="Колонка"
    )
    assignee = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL,
        null=True, 
        blank=True,
        related_name='assigned_tasks',
        verbose_name="Исполнитель"
    )
    creator = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        related_name='created_tasks',
        verbose_name="Создатель"
    )
    due_date = models.DateTimeField(null=True, blank=True, verbose_name="Срок выполнения")
    priority = models.CharField(
        max_length=10, 
        choices=PRIORITY_CHOICES, 
        default='medium',
        verbose_name="Приоритет"
    )
    position = models.PositiveIntegerField(default=0, verbose_name="Позиция в колонке")
    is_archived = models.BooleanField(default=False, verbose_name="В архиве")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    
    class Meta:
        verbose_name = "Задача"
        verbose_name_plural = "Задачи"
        ordering = ['column', 'position']
    
    def __str__(self):
        return self.title
    
    @property
    def board(self):
        return self.column.board
    
    def save(self, *args, **kwargs):
        # Автоматическая установка позиции при создании
        if not self.pk:
            max_position = Task.objects.filter(column=self.column).aggregate(
                models.Max('position')
            )['position__max']
            self.position = (max_position or -1) + 1
        super().save(*args, **kwargs)


class Label(models.Model):
    """Модель метки для задач"""
    name = models.CharField(max_length=50, verbose_name="Название метки")
    color = models.CharField(max_length=7, default='#61bd4f', verbose_name="Цвет метки")
    board = models.ForeignKey(
        Board, 
        on_delete=models.CASCADE, 
        related_name='labels',
        verbose_name="Доска"
    )
    
    class Meta:
        verbose_name = "Метка"
        verbose_name_plural = "Метки"
        unique_together = ['board', 'name']
    
    def __str__(self):
        return f"{self.name} - {self.board.title}"


class TaskLabel(models.Model):
    """Связующая модель для связи задач и меток"""
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='task_labels')
    label = models.ForeignKey(Label, on_delete=models.CASCADE)
    
    class Meta:
        verbose_name = "Метка задачи"
        verbose_name_plural = "Метки задач"
        unique_together = ['task', 'label']


class Comment(models.Model):
    """Модель комментария к задаче"""
    task = models.ForeignKey(
        Task, 
        on_delete=models.CASCADE, 
        related_name='comments',
        verbose_name="Задача"
    )
    author = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='comments',
        verbose_name="Автор"
    )
    text = models.TextField(verbose_name="Текст комментария")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    
    class Meta:
        verbose_name = "Комментарий"
        verbose_name_plural = "Комментарии"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Комментарий от {self.author} к задаче {self.task.title}"


class Attachment(models.Model):
    """Модель вложения к задаче"""
    task = models.ForeignKey(
        Task, 
        on_delete=models.CASCADE, 
        related_name='attachments',
        verbose_name="Задача"
    )
    file = models.FileField(upload_to='attachments/%Y/%m/%d/', verbose_name="Файл")
    uploaded_by = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        verbose_name="Загрузил"
    )
    file_name = models.CharField(max_length=255, verbose_name="Имя файла")
    file_size = models.PositiveIntegerField(verbose_name="Размер файла")
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата загрузки")
    
    class Meta:
        verbose_name = "Вложение"
        verbose_name_plural = "Вложения"
    
    def __str__(self):
        return self.file_name


class ActivityLog(models.Model):
    """Модель для лога активности"""
    ACTION_CHOICES = [
        ('create_board', 'Создана доска'),
        ('update_board', 'Обновлена доска'),
        ('create_column', 'Создана колонка'),
        ('update_column', 'Обновлена колонка'),
        ('move_column', 'Перемещена колонка'),
        ('create_task', 'Создана задача'),
        ('update_task', 'Обновлена задача'),
        ('move_task', 'Перемещена задача'),
        ('add_comment', 'Добавлен комментарий'),
        ('add_member', 'Добавлен участник'),
        ('remove_member', 'Удален участник'),
    ]
    
    user = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        verbose_name="Пользователь"
    )
    board = models.ForeignKey(
        Board, 
        on_delete=models.CASCADE, 
        related_name='activities',
        verbose_name="Доска"
    )
    action = models.CharField(max_length=50, choices=ACTION_CHOICES, verbose_name="Действие")
    details = models.JSONField(default=dict, verbose_name="Детали")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата события")
    
    class Meta:
        verbose_name = "Лог активности"
        verbose_name_plural = "Логи активности"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_action_display()} - {self.board.title}"
    
# Расширенная модель пользователя (если нужно)
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    
# Напоминания для задач
class Reminder(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='reminders')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    remind_at = models.DateTimeField()
    notified = models.BooleanField(default=False)