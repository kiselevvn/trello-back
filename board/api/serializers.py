from rest_framework import serializers
from django.contrib.auth.models import User
from ..models import (
    Board, Column, Task, Label, Comment, 
    Attachment, ActivityLog, TaskLabel
)


# === Вспомогательные сериализаторы ===
class UserSimpleSerializer(serializers.ModelSerializer):
    """Упрощенный сериализатор пользователя"""
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']


class BoardSimpleSerializer(serializers.ModelSerializer):
    """Упрощенный сериализатор доски"""
    owner = UserSimpleSerializer(read_only=True)
    
    class Meta:
        model = Board
        fields = ['id', 'title', 'owner', 'background_color']


class LabelSerializer(serializers.ModelSerializer):
    """Сериализатор меток"""
    class Meta:
        model = Label
        fields = ['id', 'name', 'color', 'board']
        read_only_fields = ['id']



class TaskLabelSerializer(serializers.ModelSerializer):
    """Сериализатор связи задачи с меткой"""
    label = LabelSerializer(read_only=True)
    label_id = serializers.PrimaryKeyRelatedField(
        queryset=Label.objects.all(),
        write_only=True,
        source='label'
    )
    
    class Meta:
        model = TaskLabel
        fields = ['id', 'label', 'label_id']


class TaskSerializer(serializers.ModelSerializer):
    """Сериализатор задачи"""
    assignee = UserSimpleSerializer(read_only=True)
    assignee_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        write_only=True,
        source='assignee',
        required=False,
        allow_null=True
    )
    creator = UserSimpleSerializer(read_only=True)
    labels = TaskLabelSerializer(many=True, read_only=True, source='task_labels')
    label_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False
    )
    column_title = serializers.CharField(source='column.title', read_only=True)
    board_id = serializers.IntegerField(source='column.board.id', read_only=True)
    is_overdue = serializers.SerializerMethodField()
    
    class Meta:
        model = Task
        fields = [
            'id', 'title', 'description', 'column', 'assignee', 'assignee_id',
            'creator', 'due_date', 'priority', 'position', 'is_archived',
            'created_at', 'updated_at', 'labels', 'label_ids',
            'column_title', 'board_id', 'is_overdue'
        ]
        read_only_fields = ['id', 'creator', 'created_at', 'updated_at']
    
    def get_is_overdue(self, obj):
        from django.utils import timezone
        if obj.due_date:
            return obj.due_date < timezone.now()
        return False
    
    def create(self, validated_data):
        # Извлекаем данные о метках
        label_ids = validated_data.pop('label_ids', [])
        
        # Устанавливаем создателя
        validated_data['creator'] = self.context['request'].user
        
        # Создаем задачу
        task = super().create(validated_data)
        
        # Добавляем метки
        for label_id in label_ids:
            try:
                label = Label.objects.get(id=label_id)
                TaskLabel.objects.create(task=task, label=label)
            except Label.DoesNotExist:
                continue
        
        return task
    
    def update(self, instance, validated_data):
        # Обновляем метки если они есть
        label_ids = validated_data.pop('label_ids', None)
        
        task = super().update(instance, validated_data)
        
        if label_ids is not None:
            # Удаляем старые связи
            TaskLabel.objects.filter(task=task).delete()
            # Добавляем новые метки
            for label_id in label_ids:
                try:
                    label = Label.objects.get(id=label_id)
                    TaskLabel.objects.create(task=task, label=label)
                except Label.DoesNotExist:
                    continue
        
        return task
    
    def validate(self, data):
        # Проверяем, что пользователь имеет доступ к колонке
        request = self.context.get('request')
        column = data.get('column')
        
        if column and request:
            user = request.user
            board = column.board
            if not (board.owner == user or user in board.members.all()):
                raise serializers.ValidationError("У вас нет прав на редактирование этой доски")
        
        return data



class ColumnSimpleSerializer(serializers.ModelSerializer):
    
    tasks = TaskSerializer(many=True, required=False)
    
    """Упрощенный сериализатор колонки"""
    class Meta:
        model = Column
        fields = ['id', 'title', 'position', 'color', 'tasks']
        read_only_fields = ['id']


# === Основные сериализаторы ===
class BoardSerializer(serializers.ModelSerializer):
    """Полный сериализатор доски"""
    owner = UserSimpleSerializer(read_only=True)
    members = UserSimpleSerializer(many=True, read_only=True)
    member_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=User.objects.all(),
        write_only=True,
        source='members',
        required=False
    )
    columns = ColumnSimpleSerializer(many=True, read_only=True)
    labels = LabelSerializer(many=True, read_only=True)
    is_owner = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    
    class Meta:
        model = Board
        fields = [
            'id', 'title', 'description', 'owner', 'members', 'member_ids',
            'background_color', 'is_archived', 'created_at', 'updated_at',
            'columns', 'labels', 'is_owner', 'can_edit'
        ]
        read_only_fields = ['id', 'owner', 'created_at', 'updated_at', 'columns', 'labels']
    
    def get_is_owner(self, obj):
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            return obj.owner == request.user
        return False
    
    def get_can_edit(self, obj):
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            return obj.owner == request.user or request.user in obj.members.all()
        return False
    
    def create(self, validated_data):
        # Устанавливаем текущего пользователя как владельца
        validated_data['owner'] = self.context['request'].user
        return super().create(validated_data)


class ColumnSerializer(serializers.ModelSerializer):
    """Сериализатор колонки с задачами"""
    
    tasks = TaskSerializer(many=True, required=False)
    tasks_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Column
        fields = ['id', 'title', 'board', 'position', 'color', 'created_at', 'updated_at', 'tasks_count', 'tasks']
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_tasks_count(self, obj):
        return obj.tasks.count()
    
    def validate(self, data):
        # Проверяем, что пользователь имеет доступ к доске
        request = self.context.get('request')
        board = data.get('board')
        
        if board and request:
            user = request.user
            if not (board.owner == user or user in board.members.all()):
                raise serializers.ValidationError("У вас нет прав на редактирование этой доски")
        
        return data



class TaskMoveSerializer(serializers.Serializer):
    """Сериализатор для перемещения задач"""
    column_id = serializers.IntegerField()
    position = serializers.IntegerField(min_value=0)
    
    def validate_column_id(self, value):
        try:
            Column.objects.get(id=value)
        except Column.DoesNotExist:
            raise serializers.ValidationError("Колонка не найдена")
        return value


class ColumnMoveSerializer(serializers.Serializer):
    """Сериализатор для перемещения колонок"""
    position = serializers.IntegerField(min_value=0)


class CommentSerializer(serializers.ModelSerializer):
    """Сериализатор комментариев"""
    author = UserSimpleSerializer(read_only=True)
    
    class Meta:
        model = Comment
        fields = ['id', 'task', 'author', 'text', 'created_at', 'updated_at']
        read_only_fields = ['id', 'author', 'created_at', 'updated_at']
    
    def create(self, validated_data):
        validated_data['author'] = self.context['request'].user
        return super().create(validated_data)


class AttachmentSerializer(serializers.ModelSerializer):
    """Сериализатор вложений"""
    uploaded_by = UserSimpleSerializer(read_only=True)
    file_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Attachment
        fields = [
            'id', 'task', 'file', 'file_name', 'file_size',
            'uploaded_by', 'uploaded_at', 'file_url'
        ]
        read_only_fields = ['id', 'uploaded_by', 'uploaded_at', 'file_name', 'file_size']
    
    def get_file_url(self, obj):
        request = self.context.get('request')
        if request and obj.file:
            return request.build_absolute_uri(obj.file.url)
        return None
    
    def create(self, validated_data):
        validated_data['uploaded_by'] = self.context['request'].user
        validated_data['file_name'] = validated_data['file'].name
        validated_data['file_size'] = validated_data['file'].size
        return super().create(validated_data)


class ActivityLogSerializer(serializers.ModelSerializer):
    """Сериализатор лога активности"""
    user = UserSimpleSerializer(read_only=True)
    board = BoardSimpleSerializer(read_only=True)
    
    class Meta:
        model = ActivityLog
        fields = ['id', 'user', 'board', 'action', 'details', 'created_at']
        read_only_fields = fields


# === Сериализаторы для статистики ===
class BoardStatisticsSerializer(serializers.Serializer):
    """Сериализатор статистики доски"""
    total_tasks = serializers.IntegerField()
    completed_tasks = serializers.IntegerField()
    overdue_tasks = serializers.IntegerField()
    total_members = serializers.IntegerField()
    columns_statistics = serializers.DictField()


class UserTasksStatisticsSerializer(serializers.Serializer):
    """Сериализатор статистики задач пользователя"""
    user = UserSimpleSerializer()
    total_tasks = serializers.IntegerField()
    completed_tasks = serializers.IntegerField()
    overdue_tasks = serializers.IntegerField()