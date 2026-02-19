from rest_framework import viewsets, generics, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Count, Case, Prefetch, When, IntegerField, F
from django.db import transaction
from django.utils import timezone
from django.contrib.auth.models import User
from ..models import (
    Board, Column, Task, Label, Comment, 
    Attachment, ActivityLog
)
from .serializers import (
    BoardSerializer, ColumnSerializer, TaskSerializer,
    LabelSerializer, CommentSerializer, AttachmentSerializer,
    ActivityLogSerializer, TaskMoveSerializer, ColumnMoveSerializer,
    BoardStatisticsSerializer, UserSimpleSerializer, UserTasksStatisticsSerializer
)
from .permissions import (
    IsBoardOwnerOrMember, IsBoardMember, 
    IsTaskAssigneeOrCreator, IsCommentAuthor
)


# === ViewSets для основных моделей ===
class BoardViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления досками.
    
    - Список: GET /api/boards/
    - Создание: POST /api/boards/
    - Детали: GET /api/boards/{id}/
    - Обновление: PUT /api/boards/{id}/
    - Частичное обновление: PATCH /api/boards/{id}/
    - Удаление: DELETE /api/boards/{id}/
    """
    serializer_class = BoardSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """
        Возвращает доски, где пользователь является владельцем или участником.
        """
        board_id = self.kwargs.get('board_id', None)
        tasks = Prefetch('tasks', queryset=Task.objects.filter(column__board_id=board_id))
        columns = Prefetch('columns', queryset=Column.objects.prefetch_related(tasks).filter(board_id=board_id))
        return Board.objects.filter(
            Q(owner=self.request.user) | Q(members=self.request.user)
        ).distinct().prefetch_related('members', 'labels', columns).order_by('-created_at')
    
    def get_permissions(self):
        """
        Разные разрешения для разных действий.
        """
        if self.action in ['update', 'partial_update', 'destroy']:
            permission_classes = [IsAuthenticated, IsBoardOwnerOrMember]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    def perform_create(self, serializer):
        """Создание доски с текущим пользователем в качестве владельца."""
        serializer.save(owner=self.request.user)
        
        # Логируем создание
        ActivityLog.objects.create(
            user=self.request.user,
            board=serializer.instance,
            action='create_board',
            details={'board_title': serializer.instance.title}
        )
    
    def perform_update(self, serializer):
        """Обновление доски с логированием."""
        old_title = self.get_object().title
        serializer.save()
        
        # Логируем обновление
        if old_title != serializer.instance.title:
            ActivityLog.objects.create(
                user=self.request.user,
                board=serializer.instance,
                action='update_board',
                details={
                    'old_title': old_title,
                    'new_title': serializer.instance.title
                }
            )
    
    def perform_destroy(self, instance):
        """Удаление доски с логированием."""
        ActivityLog.objects.create(
            user=self.request.user,
            board=instance,
            action='delete_board',
            details={'board_title': instance.title}
        )
        instance.delete()
    
    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        """Получение статистики по доске."""
        board = self.get_object()
        
        # Подсчет задач
        total_tasks = Task.objects.filter(column__board=board).count()
        completed_tasks = Task.objects.filter(
            column__board=board,
            is_archived=True
        ).count()
        overdue_tasks = Task.objects.filter(
            column__board=board,
            due_date__lt=timezone.now(),
            is_archived=False
        ).count()
        
        # Статистика по колонкам
        columns_statistics = {}
        for column in board.columns.all():
            columns_statistics[column.title] = {
                'total': column.tasks.count(),
                'completed': column.tasks.filter(is_archived=True).count(),
                'overdue': column.tasks.filter(
                    due_date__lt=timezone.now(),
                    is_archived=False
                ).count()
            }
        
        data = {
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
            'overdue_tasks': overdue_tasks,
            'total_members': board.members.count() + 1,  # +1 для владельца
            'columns_statistics': columns_statistics
        }
        
        serializer = BoardStatisticsSerializer(data)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def activities(self, request, pk=None):
        """Получение лога активности доски."""
        board = self.get_object()
        activities = ActivityLog.objects.filter(board=board).order_by('-created_at')[:50]
        serializer = ActivityLogSerializer(activities, many=True)
        return Response(serializer.data)


class ColumnViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления колонками.
    """
    serializer_class = ColumnSerializer
    # permission_classes = [IsAuthenticated, IsBoardMember]
    
    def get_queryset(self):
        board_id = self.kwargs.get("board_id", None)
        tasks = Prefetch("tasks", queryset=Task.objects.filter(column__board_id=board_id))
        queryset = Column.objects.prefetch_related(tasks)
        
        queryset = queryset.filter(board_id=board_id)
        
        return queryset.select_related('board').order_by('position')
    
    def perform_create(self, serializer):
        """Создание колонки с логированием."""
        column = serializer.save()
        
        ActivityLog.objects.create(
            user=self.request.user,
            board=column.board,
            action='create_column',
            details={
                'column_title': column.title,
                'position': column.position
            }
        )
    
    def perform_update(self, serializer):
        """Обновление колонки с логированием."""
        old_title = self.get_object().title
        column = serializer.save()
        
        if old_title != column.title:
            ActivityLog.objects.create(
                user=self.request.user,
                board=column.board,
                action='update_column',
                details={
                    'old_title': old_title,
                    'new_title': column.title
                }
            )
    
    def perform_destroy(self, instance):
        """Удаление колонки с логированием."""
        ActivityLog.objects.create(
            user=self.request.user,
            board=instance.board,
            action='delete_column',
            details={'column_title': instance.title}
        )
        instance.delete()
    
    @action(detail=True, methods=['patch'])
    def move(self, request, pk=None):
        """Перемещение колонки."""
        column = self.get_object()
        serializer = ColumnMoveSerializer(data=request.data)
        
        if serializer.is_valid():
            new_position = serializer.validated_data['position']
            
            # Обновляем позиции других колонок
            with transaction.atomic():
                if new_position < column.position:
                    # Перемещаем вверх
                    Column.objects.filter(
                        board=column.board,
                        position__gte=new_position,
                        position__lt=column.position
                    ).update(position=F('position') + 1)
                else:
                    # Перемещаем вниз
                    Column.objects.filter(
                        board=column.board,
                        position__gt=column.position,
                        position__lte=new_position
                    ).update(position=F('position') - 1)
                
                column.position = new_position
                column.save()
            
            ActivityLog.objects.create(
                user=self.request.user,
                board=column.board,
                action='move_column',
                details={
                    'column_title': column.title,
                    'from_position': column.position,
                    'to_position': new_position
                }
            )
            
            return Response({'status': 'column moved'})
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TaskViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления задачами.
    """
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated, IsBoardMember]
    
    def get_queryset(self):
        queryset = Task.objects.all()
        
        # Фильтрация по колонке
        column_id = self.request.query_params.get('column')
        if column_id:
            queryset = queryset.filter(column_id=column_id)
        
        # Фильтрация по доске
        board_id = self.request.query_params.get('board')
        if board_id:
            queryset = queryset.filter(column__board_id=board_id)
        
        # Фильтрация по исполнителю
        assignee_id = self.request.query_params.get('assignee')
        if assignee_id:
            queryset = queryset.filter(assignee_id=assignee_id)
        
        # Фильтрация по меткам
        label_id = self.request.query_params.get('label')
        if label_id:
            queryset = queryset.filter(task_labels__label_id=label_id)
        
        # Фильтрация по статусу
        is_archived = self.request.query_params.get('is_archived')
        if is_archived is not None:
            queryset = queryset.filter(is_archived=is_archived.lower() == 'true')
        
        # Поиск
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | 
                Q(description__icontains=search)
            )
        
        return queryset.select_related(
            'column', 'column__board', 'assignee', 'creator'
        ).prefetch_related(
            'task_labels', 'task_labels__label'
        ).order_by('column__position', 'position')
    
    def get_permissions(self):
        """
        Разные разрешения для разных действий.
        """
        if self.action in ['update', 'partial_update', 'destroy']:
            permission_classes = [IsAuthenticated, IsTaskAssigneeOrCreator]
        else:
            permission_classes = [IsAuthenticated, IsBoardMember]
        return [permission() for permission in permission_classes]
    
    def perform_create(self, serializer):
        """Создание задачи с логированием."""
        task = serializer.save(creator=self.request.user)
        
        ActivityLog.objects.create(
            user=self.request.user,
            board=task.column.board,
            action='create_task',
            details={
                'task_id': task.id,
                'task_title': task.title,
                'column': task.column.title
            }
        )
    
    def perform_update(self, serializer):
        """Обновление задачи с логированием."""
        old_data = self.get_object()
        task = serializer.save()
        
        # Логируем изменения
        changes = {}
        if old_data.title != task.title:
            changes['title'] = {'old': old_data.title, 'new': task.title}
        if old_data.column != task.column:
            changes['column'] = {
                'old': old_data.column.title,
                'new': task.column.title
            }
        if old_data.assignee != task.assignee:
            changes['assignee'] = {
                'old': old_data.assignee.username if old_data.assignee else None,
                'new': task.assignee.username if task.assignee else None
            }
        
        if changes:
            ActivityLog.objects.create(
                user=self.request.user,
                board=task.column.board,
                action='update_task',
                details={
                    'task_id': task.id,
                    'task_title': task.title,
                    'changes': changes
                }
            )
    
    def perform_destroy(self, instance):
        """Удаление задачи с логированием."""
        ActivityLog.objects.create(
            user=self.request.user,
            board=instance.column.board,
            action='delete_task',
            details={
                'task_id': instance.id,
                'task_title': instance.title
            }
        )
        instance.delete()
    
    @action(detail=True, methods=['patch'])
    def move(self, request, pk=None):
        """Перемещение задачи между колонками или внутри колонки."""
        task = self.get_object()
        print(task.pk, task)
        serializer = TaskMoveSerializer(data=request.data)
        
        if serializer.is_valid():
            column_id = serializer.validated_data['column_id']
            new_position = serializer.validated_data['position'] + 1
            print(serializer.validated_data)
            print("column_id: ", column_id, "new_position: ",  new_position)
            
            try:
                new_column = Column.objects.get(id=column_id)
                # new
            except Column.DoesNotExist:
                return Response(
                    {'error': 'Column not found'}, 
                    status=status.HTTP_404_NOT_FOUND
                )
             
            print("new_column", new_column, new_column.tasks.all())
            
            
            with transaction.atomic():
                old_column = task.column
                old_position = task.position
                print("old_column: ", old_column, old_position, "new_column: ", new_column, new_position)
                
                # Если перемещаем в другую колонку
                if old_column != new_column:
                    # Обновляем позиции в старой колонке
                    r1 = Task.objects.filter(
                        column=old_column,
                        position__gt=old_position
                    ).update(position=F('position') - 1)
                    
                    # Обновляем позиции в новой колонке
                    r2 = Task.objects.filter(
                        column=new_column,
                        position__gte=new_position
                    ).update(position=F('position') + 1)
                    print("update psnts", r1, r2)
                    task.column = new_column
                    task.position = new_position
                    task.save()
                    
                    ActivityLog.objects.create(
                        user=self.request.user,
                        board=task.column.board,
                        action='move_task',
                        details={
                            'task_id': task.id,
                            'task_title': task.title,
                            'from_column': old_column.title,
                            'to_column': new_column.title,
                            'from_position': old_position,
                            'to_position': new_position
                        }
                    )
                else:
                    # Перемещение внутри одной колонки
                    if new_position < old_position:
                        Task.objects.filter(
                            column=old_column,
                            position__gte=new_position,
                            position__lt=old_position
                        ).update(position=F('position') + 1)
                    else:
                        Task.objects.filter(
                            column=old_column,
                            position__gt=old_position,
                            position__lte=new_position
                        ).update(position=F('position') - 1)
                    
                    task.position = new_position
                    task.save()
                
                return Response({'status': 'task moved'})
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        """Архивирование задачи."""
        task = self.get_object()
        task.is_archived = True
        task.save()
        
        ActivityLog.objects.create(
            user=self.request.user,
            board=task.column.board,
            action='archive_task',
            details={
                'task_id': task.id,
                'task_title': task.title
            }
        )
        
        return Response({'status': 'task archived'})
    
    @action(detail=True, methods=['post'])
    def restore(self, request, pk=None):
        """Восстановление задачи из архива."""
        task = self.get_object()
        task.is_archived = False
        task.save()
        
        return Response({'status': 'task restored'})


class LabelViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления метками.
    """
    serializer_class = LabelSerializer
    permission_classes = [IsAuthenticated, IsBoardMember]
    
    def get_queryset(self):
        board_id = self.request.query_params.get('board')
        queryset = Label.objects.all()
        
        if board_id:
            queryset = queryset.filter(board_id=board_id)
        
        return queryset.select_related('board')
    
    def perform_create(self, serializer):
        """Создание метки."""
        serializer.save()


class CommentViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления комментариями.
    """
    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        task_id = self.request.query_params.get('task')
        queryset = Comment.objects.all()
        
        if task_id:
            queryset = queryset.filter(task_id=task_id)
        
        return queryset.select_related('author', 'task').order_by('-created_at')
    
    def get_permissions(self):
        """
        Разные разрешения для разных действий.
        """
        if self.action in ['update', 'partial_update', 'destroy']:
            permission_classes = [IsAuthenticated, IsCommentAuthor]
        else:
            permission_classes = [IsAuthenticated, IsBoardMember]
        return [permission() for permission in permission_classes]
    
    def perform_create(self, serializer):
        """Создание комментария с логированием."""
        comment = serializer.save(author=self.request.user)
        
        ActivityLog.objects.create(
            user=self.request.user,
            board=comment.task.column.board,
            action='add_comment',
            details={
                'task_id': comment.task.id,
                'task_title': comment.task.title,
                'comment_id': comment.id
            }
        )


class AttachmentViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления вложениями.
    """
    serializer_class = AttachmentSerializer
    permission_classes = [IsAuthenticated, IsBoardMember]
    
    def get_queryset(self):
        task_id = self.request.query_params.get('task')
        queryset = Attachment.objects.all()
        
        if task_id:
            queryset = queryset.filter(task_id=task_id)
        
        return queryset.select_related('uploaded_by', 'task')
    
    def perform_create(self, serializer):
        """Создание вложения."""
        serializer.save(uploaded_by=self.request.user)


# === Дополнительные ViewSets ===
class UserViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet для получения списка пользователей.
    """
    queryset = User.objects.filter(is_active=True)
    serializer_class = UserSimpleSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['username', 'email', 'first_name', 'last_name']
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Получение информации о текущем пользователе."""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def tasks_statistics(self, request):
        """Получение статистики по задачам пользователя."""
        user = request.user
        
        # Задачи, где пользователь исполнитель
        assigned_tasks = Task.objects.filter(assignee=user)
        total_assigned = assigned_tasks.count()
        completed_assigned = assigned_tasks.filter(is_archived=True).count()
        overdue_assigned = assigned_tasks.filter(
            due_date__lt=timezone.now(),
            is_archived=False
        ).count()
        
        # Задачи, созданные пользователем
        created_tasks = Task.objects.filter(creator=user)
        total_created = created_tasks.count()
        
        data = {
            'assigned': {
                'total': total_assigned,
                'completed': completed_assigned,
                'overdue': overdue_assigned
            },
            'created': {
                'total': total_created
            }
        }
        
        return Response(data)


class ActivityLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet для просмотра логов активности.
    """
    serializer_class = ActivityLogSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        
        # Показываем логи только для досок, к которым пользователь имеет доступ
        user_boards = Board.objects.filter(
            Q(owner=user) | Q(members=user)
        ).values_list('id', flat=True)
        
        return ActivityLog.objects.filter(
            board_id__in=user_boards
        ).select_related('user', 'board').order_by('-created_at')


# === Generic Views для особых случаев ===
class BoardMembersAPIView(generics.GenericAPIView):
    """
    API для управления участниками доски.
    """
    permission_classes = [IsAuthenticated, IsBoardOwnerOrMember]
    
    def get_serializer_class(self):
        return UserSimpleSerializer
    
    def get_queryset(self):
        board_id = self.kwargs.get('board_id')
        try:
            board = Board.objects.get(id=board_id)
        except Board.DoesNotExist:
            return User.objects.none()
        
        # Возвращаем всех участников доски (включая владельца)
        return User.objects.filter(
            Q(id=board.owner_id) | Q(id__in=board.members.all())
        ).distinct()
    
    def get(self, request, board_id):
        """Получение списка участников доски."""
        try:
            board = Board.objects.get(id=board_id)
        except Board.DoesNotExist:
            return Response(
                {'error': 'Board not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Проверяем права доступа
        if not (board.owner == request.user or request.user in board.members.all()):
            return Response(
                {'error': 'Permission denied'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        users = self.get_queryset()
        serializer = self.get_serializer(users, many=True)
        return Response(serializer.data)
    
    def post(self, request, board_id):
        """Добавление участника в доску."""
        try:
            board = Board.objects.get(id=board_id)
        except Board.DoesNotExist:
            return Response(
                {'error': 'Board not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Только владелец может добавлять участников
        if board.owner != request.user:
            return Response(
                {'error': 'Only board owner can add members'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        user_id = request.data.get('user_id')
        if not user_id:
            return Response(
                {'error': 'user_id is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Не добавляем владельца
        if user == board.owner:
            return Response(
                {'error': 'User is board owner'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Добавляем пользователя
        board.members.add(user)
        
        ActivityLog.objects.create(
            user=request.user,
            board=board,
            action='add_member',
            details={
                'member_id': user.id,
                'member_username': user.username
            }
        )
        
        return Response({'status': 'member added'}, status=status.HTTP_201_CREATED)
    
    def delete(self, request, board_id):
        """Удаление участника из доски."""
        try:
            board = Board.objects.get(id=board_id)
        except Board.DoesNotExist:
            return Response(
                {'error': 'Board not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Только владелец может удалять участников
        if board.owner != request.user:
            return Response(
                {'error': 'Only board owner can remove members'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        user_id = request.data.get('user_id')
       