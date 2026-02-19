from rest_framework import permissions


class IsBoardOwnerOrMember(permissions.BasePermission):
    """
    Разрешение для владельца доски или участника.
    """
    def has_object_permission(self, request, view, obj):
        # Чтение разрешено всем участникам
        if request.method in permissions.SAFE_METHODS:
            return obj.owner == request.user or request.user in obj.members.all()
        
        # Запись разрешена только владельцу
        return obj.owner == request.user


class IsBoardMember(permissions.BasePermission):
    """
    Разрешение для участников доски.
    """
    def has_object_permission(self, request, view, obj):
        # Проверяем, является ли пользователь участником доски
        if hasattr(obj, 'board'):
            board = obj.board
        elif hasattr(obj, 'column'):
            board = obj.column.board
        else:
            board = obj
        
        return board.owner == request.user or request.user in board.members.all()


class IsTaskAssigneeOrCreator(permissions.BasePermission):
    """
    Разрешение для исполнителя задачи или создателя.
    """
    def has_object_permission(self, request, view, obj):
        # Владелец доски может все
        if obj.column.board.owner == request.user:
            return True
        
        # Чтение разрешено всем участникам доски
        if request.method in permissions.SAFE_METHODS:
            board = obj.column.board
            return request.user in board.members.all()
        
        # Редактирование разрешено создателю или исполнителю
        return obj.creator == request.user or obj.assignee == request.user


class IsCommentAuthor(permissions.BasePermission):
    """
    Разрешение для автора комментария.
    """
    def has_object_permission(self, request, view, obj):
        # Чтение разрешено всем участникам доски
        if request.method in permissions.SAFE_METHODS:
            board = obj.task.column.board
            return board.owner == request.user or request.user in board.members.all()
        
        # Редактирование/удаление только автору
        return obj.author == request.user